"""Filesystem Backup operations only. No Restore or business database mutation."""
from __future__ import annotations

from contextlib import contextmanager, closing
from datetime import datetime, timezone
import errno
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from typing import Iterator
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint

import app.models  # Register the current schema for read-only structural checks.
from app.core.errors import AppError
from app.db.base import Base
from app.schemas.backup import BackupManifest, BackupRead, BackupVerification

SCHEMA = "0005_add_deadlines_recurrence_reminders"
NAME = re.compile(r"^dayflow-backup-\d{8}T\d{12}Z-[0-9a-f]{32}\.sqlite3$")
logger = logging.getLogger("dayflow.backup")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def io_error(exc: OSError) -> AppError:
    if exc.errno in (errno.ENOSYS, errno.ENOTSUP, errno.EXDEV):
        return AppError("backup_platform_unsupported", "Backup requires Linux/WSL descriptor and hard-link support", 503)
    if exc.errno in (errno.EACCES, errno.EPERM):
        return AppError("backup_permission_denied", "Backup file permission denied", 403)
    if exc.errno == errno.ENOENT:
        return AppError("backup_not_found", "Backup file was not found", 404)
    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
        return AppError("backup_path_unsafe", "Unsafe Backup path", 422)
    if exc.errno == errno.EEXIST:
        return AppError("backup_file_conflict", "Backup publication would overwrite a file", 409)
    return AppError("backup_io_failed", "Backup filesystem operation failed", 500)


class BackupService:
    def __init__(self, source: Path, root: Path, app_version: str, timeout: float = 10.0):
        self.source = source.absolute()
        self.root = root.absolute()
        self.app_version = app_version
        self.timeout = timeout

    @staticmethod
    def _fd_uri(fd: int, *, readonly: bool, immutable: bool = False) -> str:
        if not Path(f"/proc/self/fd/{fd}").exists():
            raise AppError("backup_platform_unsupported", "Backup requires Linux/WSL file descriptors", 503)
        return f"file:/proc/self/fd/{fd}?mode={'ro' if readonly else 'rw'}" + ("&immutable=1" if immutable else "")

    @staticmethod
    def _same_file(root_fd: int, name: str, fd: int) -> bool:
        actual = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        expected = os.fstat(fd)
        return stat.S_ISREG(actual.st_mode) and (actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino)

    @contextmanager
    def _root(self, create: bool = False) -> Iterator[int | None]:
        if os.name != "posix" or not Path("/proc/self/fd").is_dir() or not hasattr(os, "O_NOFOLLOW"):
            raise AppError("backup_platform_unsupported", "Backup requires Linux/WSL descriptor support", 503)
        # Reject symlinks in every existing component, including the root itself.
        for component in [*reversed(self.root.parents), self.root]:
            if component.is_symlink():
                raise AppError("backup_path_unsafe", "Unsafe Backup root", 422)
        if self.root.resolve() != self.root:
            raise AppError("backup_path_unsafe", "Unsafe Backup root", 422)
        try:
            # Walk by descriptor: a parent symlink swap cannot redirect mkdir/open.
            fd = os.open(self.root.anchor, os.O_RDONLY | os.O_DIRECTORY)
            try:
                for component in self.root.parts[1:]:
                    try:
                        next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    except FileNotFoundError:
                        if not create:
                            yield None
                            return
                        try:
                            os.mkdir(component, mode=0o700, dir_fd=fd)
                        except FileExistsError:
                            pass  # Concurrent creator made the same directory.
                        next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    os.close(fd)
                    fd = next_fd
                yield fd
            finally:
                os.close(fd)
        except OSError as exc:
            logger.warning("Backup filesystem failure: errno=%s", exc.errno)
            raise io_error(exc) from exc

    def _file(self, root_fd: int, name: str) -> int:
        if Path(name).name != name or name in (".", ".."):
            raise AppError("backup_path_unsafe", "Unsafe Backup filename", 422)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(fd)
            raise AppError("backup_path_unsafe", "Backup must be an independent regular file", 422)
        if not info.st_mode & 0o444:
            os.close(fd)
            raise PermissionError(errno.EACCES, "Unreadable Backup")
        return fd

    def _manifest(self, root_fd: int, name: str) -> BackupManifest:
        with os.fdopen(self._file(root_fd, name), "rb") as stream:
            raw = stream.read(16_385)
        if len(raw) > 16_384:
            raise AppError("backup_manifest_invalid", "Invalid Backup manifest", 422)
        try:
            manifest = BackupManifest.model_validate(json.loads(raw))
        except (ValidationError, ValueError, UnicodeError) as exc:
            raise AppError("backup_manifest_invalid", "Invalid Backup manifest", 422) from exc
        if not NAME.fullmatch(manifest.filename) or name != manifest.filename + ".json":
            raise AppError("backup_manifest_invalid", "Manifest filename does not match registration", 422)
        return manifest

    def _find(self, root_fd: int, backup_id: str) -> BackupManifest:
        matches = []
        for name in os.listdir(root_fd):
            if not name.endswith(".sqlite3.json") or not NAME.fullmatch(name[:-5]):
                continue
            try:
                manifest = self._manifest(root_fd, name)
            except (AppError, OSError):
                logger.warning("Skipped invalid Backup registration")
                continue
            if manifest.backup_id == backup_id:
                matches.append(manifest)
        if len(matches) > 1:
            raise AppError("backup_manifest_invalid", "Duplicate Backup registration", 422)
        if not matches:
            raise AppError("backup_not_found", "Registered Backup was not found", 404)
        return matches[0]

    def list(self) -> list[BackupRead]:
        entries: list[BackupRead] = []
        with self._root() as root_fd:
            if root_fd is None:
                return []
            ids: set[str] = set()
            duplicates: set[str] = set()
            for name in os.listdir(root_fd):
                if not name.endswith(".sqlite3.json") or not NAME.fullmatch(name[:-5]):
                    continue
                try:
                    manifest = self._manifest(root_fd, name)
                    fd = self._file(root_fd, manifest.filename)
                    os.close(fd)
                except (AppError, OSError):
                    logger.warning("Skipped invalid or unavailable Backup registration")
                    continue
                if manifest.backup_id in ids:
                    duplicates.add(manifest.backup_id)
                ids.add(manifest.backup_id)
                entries.append(BackupRead(**manifest.model_dump(), compatible_for_restore=manifest.alembic_version == SCHEMA))
            entries = [entry for entry in entries if entry.backup_id not in duplicates]
        return sorted(entries, key=lambda entry: (datetime.fromisoformat(entry.created_at_utc.replace("Z", "+00:00")), entry.backup_id), reverse=True)

    @staticmethod
    def _structure(connection: sqlite3.Connection) -> bool:
        # Compare columns, PKs, FKs, CHECK expressions and indexes to current models.
        version_columns = connection.execute('PRAGMA table_info("alembic_version")').fetchall()
        if len(version_columns) != 1 or version_columns[0][1] != "version_num" or not version_columns[0][3] or version_columns[0][5] != 1:
            return False
        for table in Base.metadata.sorted_tables:
            row = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table.name,)).fetchone()
            if row is None:
                return False
            sql = re.sub(r'[\s"`\[\]]', '', row[0]).lower()
            columns = {row[1]: row for row in connection.execute(f'PRAGMA table_info("{table.name}")')}
            actual_pk = [row[1] for row in sorted(columns.values(), key=lambda row: row[5]) if row[5]]
            if actual_pk != [column.name for column in table.primary_key.columns]:
                return False
            for column in table.columns:
                if column.name not in columns:
                    return False
                actual = columns[column.name]
                if bool(actual[5]) != column.primary_key or (not column.nullable and not actual[3]):
                    return False
            foreign_keys = {(row[3], row[2], row[4], row[6]) for row in connection.execute(f'PRAGMA foreign_key_list("{table.name}")')}
            for fk in table.foreign_keys:
                if (fk.parent.name, fk.column.table.name, fk.column.name, fk.ondelete or "NO ACTION") not in foreign_keys:
                    return False
            indexes = list(connection.execute(f'PRAGMA index_list("{table.name}")'))
            index_columns = {row[1]: [item[2] for item in connection.execute(f'PRAGMA index_info("{row[1]}")')] for row in indexes}
            for constraint in table.constraints:
                if isinstance(constraint, CheckConstraint):
                    expression = re.sub(r'[\s"`\[\]]', '', str(constraint.sqltext)).lower()
                    if f"check({expression})" not in sql:
                        return False
                if isinstance(constraint, UniqueConstraint):
                    if not any(row[2] and not row[4] and index_columns[row[1]] == [col.name for col in constraint.columns] for row in indexes):
                        return False
            for index in table.indexes:
                actual = next((row for row in indexes if row[1] == index.name), None)
                if actual is None or bool(actual[2]) != index.unique or index_columns[index.name] != [col.name for col in index.columns]:
                    return False
                where = index.dialect_options["sqlite"].get("where")
                if bool(actual[4]) != (where is not None):
                    return False
                if where is not None:
                    index_sql = connection.execute("SELECT sql FROM sqlite_master WHERE name=?", (index.name,)).fetchone()[0]
                    if re.sub(r'\s', '', str(where)).lower() not in re.sub(r'\s', '', index_sql).lower():
                        return False
        return True

    def _inspect(self, root_fd: int, name: str, backup_id: str, expected_fd: int | None = None) -> BackupVerification:
        result = BackupVerification(backup_id=backup_id, verified_at_utc=timestamp(), status="unreadable")
        try:
            fd = self._file(root_fd, name)
        except (OSError, AppError):
            result.issues = ["Backup file is missing, unreadable, or unsafe"]
            return result
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if expected_fd is not None and (before.st_dev, before.st_ino) != (os.fstat(expected_fd).st_dev, os.fstat(expected_fd).st_ino):
                result.issues = ["Backup file was replaced before verification"]
                return result
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            result.database_sha256 = digest
            result.file_size = before.st_size
            # Published backups are standalone. Never ignore a live WAL silently.
            for suffix in ("-wal", "-shm", "-journal"):
                try:
                    os.stat(name + suffix, dir_fd=root_fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                result.issues = ["Backup has SQLite sidecar files"]
                return result
            deadline = time.monotonic() + self.timeout
            try:
                # SQLite must inspect the same opened inode that was hashed, not
                # reopen a replaceable directory entry after the first hash.
                uri = self._fd_uri(stream.fileno(), readonly=True, immutable=True)
                with closing(sqlite3.connect(uri, uri=True, timeout=min(self.timeout, 1.0))) as connection:
                    connection.execute("PRAGMA query_only=ON")
                    connection.execute("PRAGMA trusted_schema=OFF")
                    connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
                    result.integrity_check = "ok" if connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)] else "failed"
                    result.foreign_key_errors = len(connection.execute("PRAGMA foreign_key_check").fetchall())
                    rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
                    if len(rows) != 1 or not isinstance(rows[0][0], str):
                        raise sqlite3.DatabaseError("Invalid Alembic version")
                    result.alembic_version = rows[0][0]
                    result.structure_valid = self._structure(connection)
            except sqlite3.Error as exc:
                if time.monotonic() >= deadline:
                    raise AppError("backup_timeout", "Backup verification exceeded its time limit", 503) from exc
                result.status = "corrupted"
                result.issues = ["SQLite validation failed or timed out"]
                return result
            stream.seek(0)
            after_digest = hashlib.file_digest(stream, "sha256").hexdigest()
            current = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1 or (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_ctime_ns) != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) or after_digest != digest:
                result.status = "corrupted"
                result.issues = ["Backup changed during verification"]
            elif result.integrity_check != "ok" or result.foreign_key_errors:
                result.status = "corrupted"
                result.issues = ["Backup integrity or foreign key check failed"]
            elif result.alembic_version != SCHEMA:
                result.status = "incompatible"
                result.issues = ["Backup schema is not supported for Restore"]
            elif not result.structure_valid:
                result.status = "corrupted"
                result.issues = ["Required DayFlow structure is missing or altered"]
            else:
                result.status = "valid"
                result.compatible_for_restore = True
        return result

    def verify(self, backup_id: str) -> BackupVerification:
        try:
            if str(UUID(backup_id)) != backup_id or UUID(backup_id).version != 4:
                raise ValueError
        except ValueError as exc:
            raise AppError("backup_id_invalid", "Invalid Backup identifier", 422) from exc
        with self._root() as root_fd:
            if root_fd is None:
                raise AppError("backup_not_found", "Registered Backup was not found", 404)
            manifest = self._find(root_fd, backup_id)
            result = self._inspect(root_fd, manifest.filename, backup_id)
            if result.status in ("valid", "incompatible") and any((
                result.database_sha256 != manifest.database_sha256,
                result.file_size != manifest.file_size,
                result.alembic_version != manifest.alembic_version,
            )):
                result.status = "manifest_mismatch"
                result.compatible_for_restore = False
                result.issues = ["Backup file does not match its Manifest"]
            return result

    def _publish(self, root_fd: int, temporary: str, final: str, expected_fd: int | None = None) -> None:
        # Same-filesystem hard link is atomic and NOREPLACE; os.replace can overwrite.
        with os.fdopen(self._file(root_fd, temporary), "rb") as stream:
            fd = stream.fileno()
            if expected_fd is not None and ((os.fstat(fd).st_dev, os.fstat(fd).st_ino) != (os.fstat(expected_fd).st_dev, os.fstat(expected_fd).st_ino) or not self._same_file(root_fd, temporary, expected_fd)):
                raise AppError("backup_path_unsafe", "Backup file changed before publication", 422)
            os.link(f"/proc/self/fd/{fd}", final, dst_dir_fd=root_fd, follow_symlinks=True)
            if not self._same_file(root_fd, temporary, fd) or not self._same_file(root_fd, final, fd):
                raise AppError("backup_path_unsafe", "Backup file changed during publication", 422)
        try:
            os.unlink(temporary, dir_fd=root_fd)
            os.fsync(root_fd)
        except OSError:
            if final.endswith(".json"):
                # A failed Manifest durability step cannot leave a valid registration.
                # Retain diagnostic bytes under a partial name instead of deleting DB.
                try:
                    os.link(final, temporary, src_dir_fd=root_fd, dst_dir_fd=root_fd, follow_symlinks=False)
                except FileExistsError:
                    pass
                os.unlink(final, dir_fd=root_fd)
            raise

    def create(self) -> BackupRead:
        registered = False
        published = False
        backup_id = str(uuid4())
        filename = f"dayflow-backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex}.sqlite3"
        temporary = filename + ".partial"
        manifest_temp = filename + ".json.partial"
        created_at = timestamp()
        with self._root(create=True) as root_fd:
            assert root_fd is not None
            target_fd: int | None = None
            manifest_fd: int | None = None
            try:
                target_fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=root_fd)
                # Source is configured server-side, never supplied by an API caller.
                if any(path.is_symlink() for path in (self.source, *self.source.parents)) or not self.source.is_file():
                    raise AppError("backup_path_unsafe", "Invalid source database", 422)
                deadline = time.monotonic() + self.timeout
                def progress(_status: int, _remaining: int, _total: int) -> None:
                    if time.monotonic() >= deadline:
                        raise AppError("backup_timeout", "Backup exceeded its time limit", 503)
                with closing(sqlite3.connect(self.source.as_uri() + "?mode=ro", uri=True, timeout=min(self.timeout, 1.0))) as source:
                    with closing(sqlite3.connect(self._fd_uri(target_fd, readonly=False), uri=True, timeout=min(self.timeout, 1.0))) as target:
                        source.backup(target, pages=128, progress=progress, sleep=0.01)
                verified = self._inspect(root_fd, temporary, backup_id, expected_fd=target_fd)
                if verified.status == "incompatible":
                    raise AppError("backup_schema_incompatible", "Source schema is not supported for Backup creation", 422)
                if verified.status != "valid":
                    raise AppError("backup_creation_failed", "Backup snapshot failed validation", 500)
                manifest = BackupManifest(
                    backup_id=backup_id, filename=filename, created_at_utc=created_at,
                    app_version=self.app_version, alembic_version=verified.alembic_version,
                    database_sha256=verified.database_sha256, file_size=verified.file_size,
                    integrity_check="ok", foreign_key_errors=0,
                    verified_at_utc=verified.verified_at_utc, source_database=self.source.name,
                )
                fd = self._file(root_fd, temporary)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                self._publish(root_fd, temporary, filename, expected_fd=target_fd)
                published = True
                manifest_fd = os.open(manifest_temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=root_fd)
                with os.fdopen(manifest_fd, "w", encoding="utf-8", closefd=False) as stream:
                    json.dump(manifest.model_dump(), stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._publish(root_fd, manifest_temp, filename + ".json", expected_fd=manifest_fd)
                registered = True
                return BackupRead(**manifest.model_dump(), compatible_for_restore=True)
            except OSError as exc:
                logger.warning("Backup creation failed: errno=%s", exc.errno)
                if published and not registered:
                    raise AppError("backup_registration_failed", "Backup data file may exist but registration failed", 500) from exc
                raise io_error(exc) from exc
            except sqlite3.Error as exc:
                logger.warning("SQLite Backup creation failed: %s", type(exc).__name__)
                if getattr(exc, "sqlite_errorcode", None) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                    raise AppError("backup_timeout", "Source database is busy; retry later", 503) from exc
                raise AppError("backup_creation_failed", "SQLite Backup creation failed", 500) from exc
            finally:
                if target_fd is not None:
                    os.close(target_fd)
                if manifest_fd is not None:
                    os.close(manifest_fd)
