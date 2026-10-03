"""Isolated-only offline Restore execution. Real database execution is forbidden."""
from contextlib import closing, ExitStack
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Callable
from uuid import uuid4

from app.core.config import PROJECT_ROOT
from app.core.maintenance import MaintenanceSafety, MaintenanceBlocked
from app.core.restore_io import (
    RestoreRefused, copy_file, directory, external_users, identity, mkdir,
    platform_check, regular, rename_noreplace, same_mount,
)
from app.db.base import Base
from app.services.backup_service import BackupService, SCHEMA, timestamp
from app.services.storage_service import qualify_storage


class RestoreFailed(RestoreRefused):
    def __init__(self, operation_id: str, stage: str, recorded: bool):
        self.operation_id, self.stage, self.failure_recorded = operation_id, stage, recorded
        super().__init__("恢复失败；现场已保留，启动仍被阻断。" if recorded else
                         "恢复失败且错误记录未能持久化；保留已有标记，必须人工检查。")


@dataclass(frozen=True)
class RestoreResult:
    operation_id: str
    backup_id: str
    safety_backup_id: str
    status: str = "completed"


def logical_status(path: Path, *, standalone: bool = False):
    """Typed deterministic hashes, no row values are returned or logged."""
    deadline = time.monotonic() + 10
    with ExitStack() as stack:
        uri = path.as_uri() + "?mode=ro"
        if standalone:
            parent = stack.enter_context(directory(path.parent))
            fd = regular(parent, path.name)
            stack.callback(os.close, fd)
            uri = BackupService._fd_uri(fd, readonly=True, immutable=True)
        c = stack.enter_context(closing(sqlite3.connect(uri, uri=True)))
        c.execute("PRAGMA query_only=ON")
        c.execute("PRAGMA trusted_schema=OFF")
        c.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        if c.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or c.execute("PRAGMA foreign_key_check").fetchall():
            raise RestoreRefused("数据库完整性或外键验证失败。")
        if c.execute("SELECT version_num FROM alembic_version").fetchall() != [(SCHEMA,)] or not BackupService._structure(c):
            raise RestoreRefused("数据库版本或结构不兼容。")
        result = {}
        for table in Base.metadata.sorted_tables:
            columns = [row[1] for row in c.execute(f'PRAGMA table_info("{table.name}")')]
            order = ",".join(f'"{col.name}"' for col in table.primary_key.columns)
            digest = hashlib.sha256()
            count = 0
            for row in c.execute(f'SELECT * FROM "{table.name}" ORDER BY {order}'):
                if time.monotonic() >= deadline:
                    raise RestoreRefused("逻辑验证超时。")
                typed = [(type(value).__name__, value.hex() if isinstance(value, (bytes, float)) else value) for value in row]
                digest.update(json.dumps(typed, ensure_ascii=False, separators=(",", ":")).encode())
                digest.update(b"\n")
                count += 1
            result[table.name] = {"columns": columns, "count": count, "sha256": digest.hexdigest()}
        return result


class RestoreService:
    def __init__(self, backup: BackupService, *, fault: Callable[[str], None] | None = None):
        self.backup = backup
        self.source = backup.source
        self.maintenance = MaintenanceSafety(self.source.parent / "maintenance", backup.app_version)
        self.fault = fault  # Internal isolated-test hook only; never API/env-controlled.

    def hit(self, name: str):
        if self.fault is not None:
            self.fault(name)

    def isolation(self):
        root = PROJECT_ROOT / "data"
        temporary = Path(tempfile.gettempdir()).resolve()
        if (not self.source.is_absolute() or self.source != self.source.resolve()
                or self.source.is_relative_to(root.resolve())
                or temporary not in {Path("/tmp"), Path("/var/tmp")}
                or not self.source.is_relative_to(temporary)
                or self.backup.root != self.source.parent / "backups"):
            raise RestoreRefused("执行原型只允许系统临时目录中的独立数据库；真实数据目录禁止恢复。")
        # Canonical names alone cannot identify bind aliases. Compare inode
        # identities as well; never open the protected database through SQLite.
        protected = set()
        for path in (root, root / "backups", root / "maintenance", root / "dayflow.sqlite3",
                     root / "dayflow.sqlite3-wal", root / "dayflow.sqlite3-shm"):
            try:
                info = path.stat()
            except FileNotFoundError:
                continue
            protected.add((info.st_dev, info.st_ino))
        for path in (self.source, self.backup.root, self.maintenance.root, *self.source.parents):
            try:
                info = path.stat()
            except FileNotFoundError:
                continue
            if (info.st_dev, info.st_ino) in protected:
                raise RestoreRefused("检测到受保护数据的文件或目录别名；恢复已拒绝。")
        with directory(self.source.parent) as parent:
            regular_fd = regular(parent, self.source.name)
            try:
                info = os.fstat(regular_fd)
                if (info.st_dev, info.st_ino) in protected:
                    raise RestoreRefused("打开的数据库属于受保护数据别名。")
            finally:
                os.close(regular_fd)
            platform_check(parent)
            # In particular, a maintenance-root bind mount must be refused
            # before opening/creating its coordination inode.
            for path in (self.backup.root, self.maintenance.root):
                if path.exists() or path.is_symlink():
                    with directory(path) as other:
                        if not same_mount(parent, other):
                            raise RestoreRefused("受控根目录不在同一挂载文件系统。")
        operations = self.backup.root / "restore-operations"
        qualify_storage(self.source.parent, self.backup.root if self.backup.root.exists() else None,
                        operations if operations.exists() else None)

    def inventory(self, parent: int):
        data = {}
        for suffix in ("", "-wal", "-shm"):
            name = self.source.name + suffix
            try:
                data[name] = identity(parent, name)
            except FileNotFoundError:
                if not suffix:
                    raise RestoreRefused("当前数据库不存在。")
        try:
            os.stat(self.source.name + "-journal", dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return data
        raise RestoreRefused("发现未确认的 SQLite journal。")

    def verify_target(self, backup_id: str, expected=None):
        result = self.backup.verify(backup_id)
        if result.status != "valid" or not result.compatible_for_restore or result.alembic_version != SCHEMA:
            raise RestoreRefused("目标备份未通过完整兼容验证。")
        with self.backup._root() as root:
            manifest = self.backup._find(root, backup_id)
            measured = identity(root, manifest.filename)
            if measured[-1] != result.database_sha256 or measured[2] != result.file_size:
                raise RestoreRefused("目标备份发生变化。")
            manifest_identity = identity(root, manifest.filename + ".json")
        selected = (manifest.model_dump(), measured, manifest_identity)
        if expected is not None and selected != expected:
            raise RestoreRefused("目标备份或登记信息已替换。")
        return selected

    def preview(self, backup_id: str):
        self.isolation()
        target = self.verify_target(backup_id)
        target_logic = logical_status(self.backup.root / target[0]["filename"], standalone=True)
        with directory(self.source.parent) as live:
            current = self.inventory(live)
            external_users({item[:2] for item in current.values()})
            with tempfile.TemporaryDirectory(prefix="dayflow-preview-") as temporary:
                with directory(Path(temporary)) as stage:
                    for name in current:
                        copy_file(live, name, stage, name)
                logical = logical_status(Path(temporary) / self.source.name)
            if self.inventory(live) != current:
                raise RestoreRefused("当前数据库发生变化。")
        return {"current_database": self.source.name, "current_sha256": current[self.source.name][-1],
                "current_counts": {key: value["count"] for key, value in logical.items()},
                "target_backup_id": backup_id, "target_filename": target[0]["filename"],
                "target_counts": {key: value["count"] for key, value in target_logic.items()},
                "target_sha256": target[1][-1], "schema": SCHEMA, "changes_performed": False,
                "_target_snapshot": target}

    @staticmethod
    def record(workspace: Path, event: str, **fields):
        with directory(workspace) as fd:
            out = os.open("events.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            try:
                MaintenanceSafety._regular(out)
                with os.fdopen(os.dup(out), "w") as stream:
                    stream.write(json.dumps({"at_utc": timestamp(), "event": event, **fields}, ensure_ascii=False) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.fsync(fd)
            finally:
                os.close(out)

    @staticmethod
    def metadata(workspace: Path, payload):
        with directory(workspace) as fd:
            out = os.open("operation.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(out, "w") as stream:
                json.dump(payload, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(fd)

    def execute(self, backup_id: str, confirmation: str, *, expected_target_sha: str | None = None,
                expected_target_snapshot=None):
        self.isolation()  # Before opening target, creating a gate, or inspecting SQLite.
        if confirmation != f"RESTORE {backup_id}":
            raise RestoreRefused("确认文本不匹配。")
        initial_target = self.verify_target(backup_id, expected_target_snapshot)
        if expected_target_sha is not None and initial_target[1][-1] != expected_target_sha:
            raise RestoreRefused("目标备份与确认摘要不一致。")
        with directory(self.source.parent) as live:
            with self.maintenance.execution_lease() as gate:
                current = self.inventory(live)
                external_users({item[:2] for item in current.values()})
                # Admission staging is not a Restore workspace or Backup/Candidate.
                # SQLite never opens original live names, preserving SHM evidence.
                with tempfile.TemporaryDirectory(prefix="dayflow-admission-") as temporary:
                    stage_path = Path(temporary)
                    with directory(stage_path) as stage:
                        for name in current:
                            copy_file(live, name, stage, name)
                    current_logic = logical_status(stage_path / self.source.name)
                if self.inventory(live) != current:
                    raise RestoreRefused("当前数据库在准入检查期间改变。")
                with self.backup._root() as root:
                    if root is None or not same_mount(root, live):
                        raise RestoreRefused("Backup Root 必须位于同一文件系统。")
                    # Validate private workspace root before persistent admission.
                    operations = self.backup.root / "restore-operations"
                    if operations.exists() or operations.is_symlink():
                        with directory(operations) as operation_root:
                            if not same_mount(operation_root, live):
                                raise RestoreRefused("工作目录不在同一挂载文件系统。")
                operation_id = str(uuid4())
                try:
                    self.maintenance.admit_execution(gate, operation_id)
                except (OSError, MaintenanceBlocked) as exc:
                    raise RestoreFailed(operation_id, "prepare", False) from exc
                workspace = operations / operation_id
                state = "prepare"
                workspace_created = False
                try:
                    with directory(self.backup.root) as root:
                        try:
                            mkdir(root, "restore-operations")
                        except FileExistsError:
                            pass
                    with directory(operations) as root:
                        mkdir(root, operation_id)
                    workspace_created = True
                    self.metadata(workspace, {"operation_id": operation_id, "backup_id": backup_id, "current": current, "target": initial_target[0]})
                    self.record(workspace, "prepare", operation_id=operation_id)
                    self.hit("C0")
                    with directory(workspace) as work:
                        for name in ("current-evidence", "current-working", "pre-restore-safety", "original"):
                            mkdir(work, name)
                    with directory(workspace / "current-evidence") as evidence, directory(workspace / "current-working") as working:
                        for name in current:
                            copy_file(live, name, evidence, name)
                            copy_file(evidence, name, working, name)
                    working_db = workspace / "current-working" / self.source.name
                    if logical_status(working_db) != current_logic:
                        raise RestoreRefused("当前数据库逻辑内容发生变化。")
                    safety_service = BackupService(working_db, workspace / "pre-restore-safety", self.backup.app_version)
                    safety = safety_service.create()
                    if safety_service.verify(safety.backup_id).status != "valid" or logical_status(safety_service.root / safety.filename, standalone=True) != current_logic:
                        raise RestoreRefused("Safety Backup 验证失败。")
                    self.record(workspace, "safety", safety_backup_id=safety.backup_id, sha256=safety.database_sha256)
                    self.hit("C1")
                    target = self.verify_target(backup_id, initial_target)
                    self.record(workspace, "target_verified", sha256=target[1][-1])
                    self.hit("C2")
                    with self.backup._root() as root, directory(workspace) as work:
                        copied = copy_file(root, target[0]["filename"], work, "candidate.sqlite3")
                        if copied != target[1]:
                            raise RestoreRefused("目标备份已替换。")
                        inspection = self.backup._inspect(work, "candidate.sqlite3", backup_id)
                        if inspection.status != "valid" or inspection.database_sha256 != target[1][-1]:
                            raise RestoreRefused("Candidate 验证失败。")
                        target_logic = logical_status(workspace / "candidate.sqlite3", standalone=True)
                        if identity(work, "candidate.sqlite3")[-1] != target[1][-1]:
                            raise RestoreRefused("Candidate 在逻辑验证期间改变。")
                        copy_file(work, "candidate.sqlite3", work, "install.sqlite3.partial")
                        if self.backup._inspect(work, "install.sqlite3.partial", backup_id).status != "valid":
                            raise RestoreRefused("Install Copy 验证失败。")
                    self.record(workspace, "candidates_verified", fingerprint=target_logic, sha256=target[1][-1])
                    self.hit("C3")
                    self.maintenance.execution_stage(gate, operation_id, state, "verified")
                    state = "verified"
                    external_users({item[:2] for item in current.values()})
                    if self.inventory(live) != current:
                        raise RestoreRefused("归档前 live 文件发生变化。")
                    self.record(workspace, "switch_intent", inventory=current)
                    self.maintenance.execution_stage(gate, operation_id, state, "switching")
                    state = "switching"
                    self.hit("C4")
                    with directory(workspace / "original") as archive:
                        for suffix, crash in (("-wal", "C5a"), ("-shm", "C5b"), ("", "C5c")):
                            name = self.source.name + suffix
                            if name in current:
                                if identity(live, name) != current[name]:
                                    raise RestoreRefused("归档源已改变。")
                                self.record(workspace, "move_intent", artifact=name)
                                fd = regular(live, name)
                                try:
                                    os.fsync(fd)
                                finally:
                                    os.close(fd)
                                rename_noreplace(live, name, archive, name)
                                # Rename changes ctime, but inode/bytes must still
                                # match the previously verified source receipt.
                                archived = identity(archive, name)
                                if archived[:4] != current[name][:4] or archived[-1] != current[name][-1]:
                                    raise RestoreRefused("归档对象与已验证源不一致。")
                                self.record(workspace, "move_done", artifact=name)
                            self.hit(crash)
                    for suffix in ("", "-wal", "-shm", "-journal"):
                        try:
                            os.stat(self.source.name + suffix, dir_fd=live, follow_symlinks=False)
                        except FileNotFoundError:
                            continue
                        raise RestoreRefused("live 位置出现非预期文件，禁止安装。")
                    with directory(workspace) as work:
                        if identity(work, "install.sqlite3.partial")[-1] != target[1][-1]:
                            raise RestoreRefused("Install Copy 已改变。")
                        self.record(workspace, "install_intent")
                        rename_noreplace(work, "install.sqlite3.partial", live, self.source.name)
                    fd = regular(live, self.source.name)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    os.fsync(live)
                    self.record(workspace, "install_done")
                    self.hit("C6")
                    self.maintenance.execution_stage(gate, operation_id, state, "verifying")
                    state = "verifying"
                    self.hit("C7")
                    measured = self.backup._inspect(live, self.source.name, backup_id)
                    if measured.status != "valid" or measured.database_sha256 != target[1][-1] or measured.file_size != target[1][2]:
                        raise RestoreRefused("最终数据库物理验证失败。")
                    if logical_status(self.source, standalone=True) != target_logic:
                        raise RestoreRefused("最终数据库逻辑验证失败。")
                    if identity(live, self.source.name)[-1] != target[1][-1]:
                        raise RestoreRefused("最终数据库在逻辑验证期间改变。")
                    if set(self.inventory(live)) != {self.source.name}:
                        raise RestoreRefused("最终验证期间出现 SQLite sidecar。")
                    self.record(workspace, "final_verified", sha256=measured.database_sha256, fingerprint=target_logic)
                    self.hit("C8")
                    self.record(workspace, "result", status="completed", safety_backup_id=safety.backup_id)
                    self.maintenance.execution_stage(gate, operation_id, state, "completed")
                    state = "completed"
                    self.hit("C9")
                    return RestoreResult(operation_id, backup_id, safety.backup_id)
                except Exception as exc:
                    # Stop, retain all materials. Failure-record IO itself cannot
                    # clear the existing marker or permit the next stage.
                    recorded = False
                    try:
                        if workspace_created:
                            self.record(workspace, "failure", stage=state, reason=type(exc).__name__,
                                        errno=getattr(exc, "errno", None))
                        if state != "completed":
                            self.maintenance.execution_stage(gate, operation_id, state, "blocked" if state in {"switching", "verifying"} else "failed")
                        recorded = True
                    except Exception as persistence_error:
                        raise RestoreFailed(operation_id, state, False) from persistence_error
                    raise RestoreFailed(operation_id, state, recorded) from exc
