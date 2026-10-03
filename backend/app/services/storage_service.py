"""Restore storage mechanisms, probed only in disposable system-temp files."""
import os
from pathlib import Path
import tempfile

from app.core.maintenance import fcntl
from app.core.restore_io import (
    RestoreRefused, directory, identity, mount_id, platform_check,
    regular, rename_noreplace, same_mount,
)


def qualify_storage(live: Path, backup: Path | None = None, workspace: Path | None = None) -> dict:
    """Inspect requested directories; never create artifacts inside them.

    Temp probe must share the actual mounted filesystem. This qualifies syscall
    behavior, not power-loss durability or permission to restore personal data.
    """
    try:
        with directory(live) as live_fd:
            platform_check(live_fd)
            os.fsync(live_fd)
            for path in (backup, workspace):
                if path is not None:
                    with directory(path) as other:
                        if not same_mount(live_fd, other):
                            raise RestoreRefused("恢复目录必须位于同一挂载文件系统。")
                        platform_check(other)
                        os.fsync(other)
            if fcntl is None:
                raise RestoreRefused("系统缺少 flock 支持。")
            with tempfile.TemporaryDirectory(prefix="dayflow-storage-probe-") as temporary:
                with directory(Path(temporary)) as probe:
                    if not same_mount(live_fd, probe):
                        raise RestoreRefused("无法在同一挂载的隔离临时目录验证存储能力。")
                    for name in ("source", "occupied", "lease"):
                        fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=probe)
                        try:
                            os.write(fd, name.encode())
                            os.fsync(fd)
                        finally:
                            os.close(fd)
                    before = identity(probe, "occupied")
                    try:
                        rename_noreplace(probe, "source", probe, "occupied")
                    except FileExistsError:
                        pass
                    else:
                        raise RestoreRefused("文件系统未遵守无覆盖 rename 语义。")
                    if identity(probe, "occupied") != before:
                        raise RestoreRefused("无覆盖检查改变了目标文件。")
                    rename_noreplace(probe, "source", probe, "installed")
                    fd = regular(probe, "installed")
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    first, second = regular(probe, "lease"), regular(probe, "lease")
                    try:
                        fcntl.flock(first, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        try:
                            fcntl.flock(second, fcntl.LOCK_SH | fcntl.LOCK_NB)
                        except BlockingIOError:
                            pass
                        else:
                            raise RestoreRefused("flock 未提供预期的互斥语义。")
                    finally:
                        os.close(second)
                        os.close(first)
                    os.fsync(probe)
            return {"status": "qualified", "filesystem": "ext4", "mount_id": mount_id(live_fd),
                    "same_mount": True, "rename_noreplace": True, "file_fsync": True,
                    "directory_fsync": True, "flock": True, "real_restore_approved": False}
    except OSError as exc:
        raise RestoreRefused("存储能力检查失败；恢复必须拒绝，不会降级切换。") from exc
