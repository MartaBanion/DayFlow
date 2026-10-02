"""Linux/WSL state-only safety prototype. No SQLite or Restore operations.

The durable marker survives process death; flock only serializes cooperating
processes. The coordination inode is never removed or replaced by this module.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import stat
import sys
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, UUID4, field_validator

try:
    import fcntl
except ImportError:  # No unsafe fallback on unsupported platforms.
    fcntl = None


class MaintenanceBlocked(RuntimeError):
    """Safe startup/operator error, without internal paths or record contents."""


Stage = Literal["idle", "prepare", "verified", "switching", "verifying", "completed", "failed", "blocked"]
NEXT: dict[str, set[str]] = {
    "prepare": {"verified", "failed", "blocked"},
    "verified": {"switching", "failed", "blocked"},
    "switching": {"verifying", "failed", "blocked"},
    "verifying": {"completed", "failed", "blocked"},
}
MESSAGE = "DayFlow 无法启动：维护或恢复流程未完成，或安全状态无法验证。请先人工检查；不会自动清理或恢复。"


class MaintenanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    format_version: Literal[1] = 1
    lock_id: UUID4
    created_at_utc: str
    operation: Literal["restore-safety-prototype"] = "restore-safety-prototype"
    stage: Stage
    app_version: str = Field(min_length=1, max_length=64)

    @field_validator("created_at_utc")
    @classmethod
    def utc_timestamp(cls, value: str) -> str:
        if not value.endswith("Z") or datetime.fromisoformat(value).utcoffset().total_seconds() != 0:
            raise ValueError("Expected UTC timestamp")
        return value


class MaintenanceSafety:
    LOCK = "maintenance.lock"
    STATE = "restore-state.json"
    GATE = "coordination.lock"

    def __init__(self, root: Path, app_version: str):
        self.root = root.absolute()
        self.app_version = app_version

    @contextmanager
    def _directory(self, *, create: bool) -> Iterator[int | None]:
        if fcntl is None or not hasattr(os, "O_NOFOLLOW"):
            raise MaintenanceBlocked("维护安全检查需要 Linux / WSL 文件锁能力。")
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            parts = self.root.parts[1:]
            for i, part in enumerate(parts):
                if part in {".", ".."}:
                    raise MaintenanceBlocked(MESSAGE)
                last = i == len(parts) - 1
                if last and create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                        os.fsync(fd)
                    except FileExistsError:
                        pass
                try:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                except FileNotFoundError:
                    if last and not create:
                        yield None
                        return
                    raise
                os.close(fd)
                fd = child
            info = os.fstat(fd)
            if info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise MaintenanceBlocked(MESSAGE)
            yield fd
        except OSError as exc:
            raise MaintenanceBlocked(MESSAGE) from exc
        finally:
            os.close(fd)

    @staticmethod
    def _regular(fd: int) -> None:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise MaintenanceBlocked(MESSAGE)

    @contextmanager
    def _gate(self, directory: int, *, exclusive: bool, create: bool) -> Iterator[None]:
        flags = os.O_RDWR if create else os.O_RDONLY
        if create:
            flags |= os.O_CREAT
        fd = os.open(self.GATE, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
        try:
            self._regular(fd)
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            named = os.stat(self.GATE, dir_fd=directory, follow_symlinks=False)
            held = os.fstat(fd)
            if (named.st_dev, named.st_ino) != (held.st_dev, held.st_ino):
                raise MaintenanceBlocked(MESSAGE)
            if create:
                os.fsync(fd)
                os.fsync(directory)
            yield
        finally:
            os.close(fd)

    def _read(self, directory: int, name: str) -> MaintenanceRecord | None:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            return None
        try:
            self._regular(fd)
            if os.fstat(fd).st_size > 4096:
                raise MaintenanceBlocked(MESSAGE)
            raw = os.read(fd, 4097)
            return MaintenanceRecord.model_validate_json(raw)
        except ValueError as exc:
            raise MaintenanceBlocked(MESSAGE) from exc
        finally:
            os.close(fd)

    def _publish(self, directory: int, name: str, record: MaintenanceRecord, *, replace: bool) -> None:
        # Only controlled state files, never a database or a Backup. A leftover
        # partial is intentionally retained and blocks startup after IO failure.
        temporary = f"state-{uuid4().hex}.partial"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(record.model_dump_json() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        else:
            os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            os.unlink(temporary, dir_fd=directory)
        os.fsync(directory)

    def _check(self, directory: int) -> None:
        entries = set(os.listdir(directory))
        if entries - {self.GATE, self.STATE}:
            # Includes maintenance.lock, partials, and unexpected files.
            raise MaintenanceBlocked(MESSAGE)
        record = self._read(directory, self.STATE)
        if record is not None and record.stage != "completed":
            raise MaintenanceBlocked(MESSAGE)

    def check_startup(self) -> None:
        """Read-only preflight; no directory, file or database is created."""
        with self._directory(create=False) as directory:
            if directory is None:
                return  # Missing state is idle.
            if not os.listdir(directory):
                return
            with self._gate(directory, exclusive=False, create=False):
                self._check(directory)

    @contextmanager
    def backend_usage(self) -> Iterator[None]:
        """Hold shared usage lease throughout ASGI lifespan, before DB access."""
        with self._directory(create=True) as directory:
            with self._gate(directory, exclusive=False, create=True):
                self._check(directory)
                yield

    def begin(self) -> MaintenanceRecord:
        with self._directory(create=True) as directory:
            with self._gate(directory, exclusive=True, create=True):
                self._check(directory)
                record = MaintenanceRecord(
                    lock_id=uuid4(), created_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    app_version=self.app_version, stage="prepare",
                )
                self._publish(directory, self.LOCK, record, replace=False)
                self._publish(directory, self.STATE, record, replace=True)
                return record

    def _owned(self, directory: int, lock_id: str) -> MaintenanceRecord:
        if set(os.listdir(directory)) != {self.GATE, self.LOCK, self.STATE}:
            raise MaintenanceBlocked(MESSAGE)
        lock = self._read(directory, self.LOCK)
        state = self._read(directory, self.STATE)
        if lock is None or state is None or str(lock.lock_id) != lock_id or lock.stage != "prepare":
            raise MaintenanceBlocked(MESSAGE)
        if lock.model_dump(exclude={"stage"}) != state.model_dump(exclude={"stage"}):
            raise MaintenanceBlocked(MESSAGE)
        return state

    def inspect(self) -> MaintenanceRecord | None:
        """Read current record; absence means idle, malformed records raise."""
        with self._directory(create=False) as directory:
            if directory is None:
                return None
            if not os.listdir(directory):
                return None
            with self._gate(directory, exclusive=False, create=False):
                state = self._read(directory, self.STATE)
                lock = self._read(directory, self.LOCK)
                if lock is not None:
                    return self._owned(directory, str(lock.lock_id))
                self._check(directory)
                return state

    def advance(self, lock_id: str, expected: Stage, target: Stage, *, confirmed: bool = False) -> MaintenanceRecord:
        with self._directory(create=False) as directory:
            if directory is None:
                raise MaintenanceBlocked(MESSAGE)
            with self._gate(directory, exclusive=True, create=False):
                state = self._owned(directory, lock_id)
                if state.stage != expected or target not in NEXT.get(expected, set()):
                    raise MaintenanceBlocked("维护状态转换无效或记录已改变。")
                if target == "completed" and not confirmed:
                    raise MaintenanceBlocked("完成原型流程需要明确人工确认；不代表真实恢复已验证。")
                updated = state.model_copy(update={"stage": target})
                self._publish(directory, self.STATE, updated, replace=True)
                return updated

    def cleanup(self, lock_id: str, *, confirmed: bool = False) -> None:
        """Explicit completed-prototype cleanup only. Never erase failure evidence."""
        if not confirmed:
            raise MaintenanceBlocked("清理维护锁需要明确人工确认。")
        with self._directory(create=False) as directory:
            if directory is None:
                raise MaintenanceBlocked(MESSAGE)
            with self._gate(directory, exclusive=True, create=False):
                state = self._owned(directory, lock_id)
                if state.stage != "completed":
                    raise MaintenanceBlocked(MESSAGE)
                os.unlink(self.LOCK, dir_fd=directory)
                os.fsync(directory)
                # Keep completed state and coordination inode for inspection.


def main() -> int:
    """Launcher-only read check, deliberately no mutation/Restore commands."""
    from app.core.config import get_settings

    if sys.argv[1:] != ["--check"]:
        print("用法：python -m app.core.maintenance --check", file=sys.stderr)
        return 2
    settings = get_settings()
    try:
        MaintenanceSafety(settings.maintenance_root, settings.app_version).check_startup()
    except MaintenanceBlocked as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Maintenance startup check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
