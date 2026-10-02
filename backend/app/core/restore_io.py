"""Linux-only descriptor operations for isolated Restore; no unsafe fallback."""
from contextlib import contextmanager
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import stat
import time
from uuid import uuid4


class RestoreRefused(RuntimeError):
    """Safe operator-facing reason, never raw OS/SQLite exception text."""


@contextmanager
def directory(path: Path):
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        if path != path.resolve() or not path.is_absolute():
            raise RestoreRefused("目录路径不安全。")
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise RestoreRefused("目录所有权或权限不安全。")
        yield fd
    finally:
        os.close(fd)


def regular(parent: int, name: str) -> int:
    if Path(name).name != name:
        raise RestoreRefused("文件标识不安全。")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o022:
        os.close(fd)
        raise RestoreRefused("文件类型、链接或权限不安全。")
    return fd


def identity(parent: int, name: str):
    fd = regular(parent, name)
    try:
        before = os.fstat(fd)
        with os.fdopen(os.dup(fd), "rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if key(before) != key(after):
            raise RestoreRefused("文件在检查期间发生变化。")
        return (*key(before), digest)
    finally:
        os.close(fd)


def copy_file(src: int, name: str, dst: int, output: str):
    before = identity(src, name)
    fd = regular(src, name)
    target = None
    try:
        if (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != before[:2]:
            raise RestoreRefused("复制源已替换。")
        target = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dst)
        deadline = time.monotonic() + 30
        with os.fdopen(os.dup(fd), "rb") as reader, os.fdopen(os.dup(target), "wb") as writer:
            while block := reader.read(1024 * 1024):
                if time.monotonic() > deadline:
                    raise RestoreRefused("文件复制超时。")
                writer.write(block)
            writer.flush()
            os.fsync(writer.fileno())
        os.fsync(dst)
        if identity(src, name) != before or identity(dst, output)[-1] != before[-1]:
            raise RestoreRefused("复制内容验证失败。")
        return before
    finally:
        os.close(fd)
        if target is not None:
            os.close(target)


def mkdir(parent: int, name: str):
    os.mkdir(name, 0o700, dir_fd=parent)
    os.fsync(parent)


def rename_noreplace(src: int, name: str, dst: int, output: str):
    if not same_mount(src, dst):
        raise RestoreRefused("恢复切换禁止跨文件系统。")
    libc = ctypes.CDLL(None, use_errno=True)
    fn = getattr(libc, "renameat2", None)
    if fn is None:
        raise RestoreRefused("系统不支持安全无覆盖切换。")
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(src, os.fsencode(name), dst, os.fsencode(output), 1):
        raise OSError(ctypes.get_errno(), "no-replace rename refused")
    os.fsync(src)
    os.fsync(dst)


def mount_id(fd: int) -> str:
    fields = dict(line.split(":", 1) for line in Path(f"/proc/self/fdinfo/{fd}").read_text().splitlines() if ":" in line)
    if "mnt_id" not in fields:
        raise RestoreRefused("无法确认文件系统挂载身份。")
    return fields["mnt_id"].strip()


def same_mount(src: int, dst: int) -> bool:
    return os.fstat(src).st_dev == os.fstat(dst).st_dev and mount_id(src) == mount_id(dst)


def platform_check(parent: int):
    # Use the opened descriptor's mount ID, not a longest-path heuristic:
    # stacked/bind mounts can have identical pathnames but different semantics.
    actual_mount = mount_id(parent)
    matches = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        if left.split()[0] == actual_mount:
            matches.append(right.split()[0])
    if matches != ["ext4"] or not hasattr(ctypes.CDLL(None), "renameat2"):
        raise RestoreRefused("恢复原型仅支持已验证的 Linux/WSL ext4。")
    # Missing source checks flag support without modifying a directory entry.
    missing = f".dayflow-capability-{uuid4().hex}"
    try:
        rename_noreplace(parent, missing, parent, missing + "-target")
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise RestoreRefused("安全切换能力检查失败。") from exc
    else:
        raise RestoreRefused("能力检查遇到非预期文件。")


def external_users(identities: set[tuple[int, int]], proc: Path = Path("/proc")):
    """Best effort detection, refusing incomplete visibility; never kills processes."""
    if proc != Path("/proc") and not proc.is_dir():
        raise RestoreRefused("无法检查外部数据库使用者。")
    deadline = time.monotonic() + 10
    try:
        processes = {p for p in proc.iterdir() if p.name.isdigit()}
        for process in processes:
            if time.monotonic() > deadline:
                raise RestoreRefused("进程使用状态检查超时。")
            try:
                for descriptor in (process / "fd").iterdir():
                    try:
                        info = descriptor.stat()
                    except FileNotFoundError:
                        continue
                    if (info.st_dev, info.st_ino) in identities:
                        raise RestoreRefused("检测到外部数据库使用者；请先关闭相关工具。")
                for line in (process / "maps").read_text().splitlines():
                    fields = line.split(None, 5)
                    major, minor = (int(x, 16) for x in fields[3].split(":"))
                    if (os.makedev(major, minor), int(fields[4])) in identities:
                        raise RestoreRefused("检测到外部数据库文件映射。")
            except FileNotFoundError:
                if process.exists():
                    raise RestoreRefused("进程检查不完整。")
                continue
        # New processes may not have been inspected. Do not assume a moving
        # enumeration is a complete view or retry indefinitely.
        if {p for p in proc.iterdir() if p.name.isdigit()} - processes:
            raise RestoreRefused("进程枚举发生变化；使用状态无法完整确认。")
    except (OSError, ValueError, IndexError) as exc:
        raise RestoreRefused("无法完整检查外部使用者；恢复已拒绝。") from exc
