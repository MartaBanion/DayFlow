"""Recovery coordination exclusively on migrated disposable databases."""
import json
import os
from pathlib import Path
import stat
import subprocess
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.test_restore_execution import setup_restore, execute, blocked
from app import maintenance_cli
from app.core.config import Settings
from app.core.maintenance import MaintenanceBlocked, MaintenanceSafety, fcntl
from app.core.restore_io import RestoreRefused
from app.services.recovery_service import RecoveryService
from app.services.storage_service import qualify_storage
from app.db import session as sessions
from app.main import app


@pytest.fixture
def completed(setup_restore):
    service, item = setup_restore
    result = execute(service, item)
    return RecoveryService(service), result.operation_id


def acknowledge(recovery, selected):
    return recovery.acknowledge(selected, f"ACKNOWLEDGE {selected}")


def evidence(recovery):
    return {str(path.relative_to(recovery.restore.backup.root)): path.read_bytes()
            for path in recovery.restore.backup.root.rglob("*") if path.is_file()}


def workspace(recovery, selected):
    return recovery.restore.backup.root / "restore-operations" / selected


def assert_startup_blocked(recovery):
    with pytest.raises(MaintenanceBlocked):
        recovery.check_startup()
    with pytest.raises(MaintenanceBlocked):
        with recovery.backend_usage():
            pytest.fail("Backend must remain blocked")


def assert_precommit_failure(recovery, selected):
    assert (recovery.maintenance.root / recovery.maintenance.LOCK).is_file()
    assert (recovery.maintenance.root / recovery.maintenance.STATE).is_file()
    assert not (recovery.maintenance.root / recovery.maintenance.CLEARANCE).exists()
    assert_startup_blocked(recovery)


def test_f12_acknowledge_preserves_evidence_and_unblocks(completed):
    recovery, selected = completed
    before = evidence(recovery)
    gate = recovery.maintenance.root / recovery.maintenance.GATE
    inode = gate.stat().st_ino
    blocked(recovery.restore)
    result = acknowledge(recovery, selected)
    assert result["acknowledge_committed"] is True
    assert result["cleanup_complete"] is True
    assert result["startup_allowed"] is True
    assert result["evidence_deleted"] is False and result["services_started"] is False
    after = evidence(recovery)
    for name, contents in before.items():
        if name.endswith("events.jsonl"):
            assert after[name].startswith(contents)
        else:
            assert after[name] == contents
    assert gate.stat().st_ino == inode
    assert set(p.name for p in recovery.maintenance.root.iterdir()) == {
        recovery.maintenance.GATE, recovery.maintenance.CLEARANCE,
    }
    assert (workspace(recovery, selected) / "startup-clearance.json").read_bytes() == (
        recovery.maintenance.root / recovery.maintenance.CLEARANCE
    ).read_bytes()
    assert recovery.check_startup() is True
    with recovery.backend_usage():
        with pytest.raises(MaintenanceBlocked):
            with recovery.maintenance.execution_lease():
                pytest.fail("exclusive lock cannot overlap Backend")
    status = recovery.status()
    assert status == {
        "startup_blocked": False,
        "startup_allowed": True,
        "stage": "acknowledged",
        "operation_id": selected,
        "acknowledge_committed": True,
        "cleanup_complete": True,
        "acknowledgement_candidate": False,
        "blocking_reason": None,
    }


@pytest.mark.parametrize("suffix", [" ", " extra", "\n", "\t"])
def test_exact_confirmation(completed, suffix):
    recovery, selected = completed
    before = evidence(recovery)
    with pytest.raises(RestoreRefused):
        recovery.acknowledge(selected, f"ACKNOWLEDGE {selected}{suffix}")
    assert evidence(recovery) == before
    blocked(recovery.restore)


@pytest.mark.parametrize("mutation", ["sha", "fingerprint", "log", "receipt", "operation", "candidate"])
def test_f1_reverification_rejects_inconsistent_evidence(completed, mutation, monkeypatch):
    recovery, selected = completed
    work = recovery.restore.backup.root / "restore-operations" / selected
    if mutation == "sha":
        with recovery.restore.source.open("ab") as stream:
            stream.write(b"changed")
    elif mutation == "fingerprint":
        monkeypatch.setattr("app.services.recovery_service.logical_status", lambda *a, **kw: {})
    elif mutation == "log":
        (work / "events.jsonl").unlink()
    elif mutation == "candidate":
        (work / "candidate.sqlite3").write_bytes(b"changed")
    elif mutation == "operation":
        path = work / "operation.json"
        data = json.loads(path.read_text()); data["operation_id"] = str(uuid4())
        path.write_text(json.dumps(data))
    else:
        path = work / "events.jsonl"
        path.write_text("\n".join(line for line in path.read_text().splitlines()
                                  if json.loads(line)["event"] != "final_verified") + "\n")
    with pytest.raises((RestoreRefused, FileNotFoundError, MaintenanceBlocked)):
        acknowledge(recovery, selected)
    assert_precommit_failure(recovery, selected)


@pytest.mark.parametrize("stage", ["prepare", "verified", "switching", "verifying", "failed", "blocked", "unknown", "corrupt", "v1"])
def test_acknowledge_rejects_wrong_state(completed, stage):
    recovery, selected = completed
    path = recovery.maintenance.root / recovery.maintenance.STATE
    data = json.loads(path.read_text())
    if stage == "v1":
        data.update(format_version=1, operation="restore-safety-prototype")
    else:
        data["stage"] = stage
    path.write_text("{" if stage == "corrupt" else json.dumps(data))
    with pytest.raises((RestoreRefused, MaintenanceBlocked)):
        acknowledge(recovery, selected)
    assert_startup_blocked(recovery)


def test_acknowledge_lock_contention_and_lifetime(completed, monkeypatch):
    recovery, selected = completed
    gate = recovery.maintenance.root / recovery.maintenance.GATE
    with gate.open("rb") as stream:
        fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
        with pytest.raises(MaintenanceBlocked):
            acknowledge(recovery, selected)
    original = recovery.restore.record
    def record(*args, **kwargs):
        with gate.open("rb") as stream:
            with pytest.raises(BlockingIOError):
                fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return original(*args, **kwargs)
    monkeypatch.setattr(recovery.restore, "record", record)
    acknowledge(recovery, selected)


@pytest.mark.parametrize("event", ["acknowledge_verified", "acknowledge_decision_prepared"])
def test_f2_acknowledge_log_failure_keeps_active_blockers(completed, event, monkeypatch):
    recovery, selected = completed
    original = recovery.restore.record

    def record(workspace, name, **fields):
        if name == event:
            raise OSError("injected acknowledge log failure")
        return original(workspace, name, **fields)

    monkeypatch.setattr(recovery.restore, "record", record)
    with pytest.raises((OSError, MaintenanceBlocked)):
        acknowledge(recovery, selected)
    assert_precommit_failure(recovery, selected)


def test_f3_clearance_receipt_create_failure_keeps_active_blockers(completed, monkeypatch):
    recovery, selected = completed

    def fail(*_args, **_kwargs):
        raise PermissionError("injected clearance creation failure")

    monkeypatch.setattr(recovery.maintenance, "publish_clearance", fail)
    with pytest.raises((PermissionError, MaintenanceBlocked)):
        acknowledge(recovery, selected)
    assert_precommit_failure(recovery, selected)


def test_f4_clearance_receipt_file_fsync_failure_keeps_active_blockers(completed, monkeypatch):
    recovery, selected = completed
    maintenance_inode = recovery.maintenance.root.stat().st_ino
    original_open, original_fsync = os.open, os.fsync
    receipt_fds = set()

    def open_file(path, flags, *args, dir_fd=None, **kwargs):
        fd = original_open(path, flags, *args, dir_fd=dir_fd, **kwargs)
        if (isinstance(path, str) and path.startswith("clearance-")
                and dir_fd is not None and os.fstat(dir_fd).st_ino == maintenance_inode):
            receipt_fds.add(fd)
        return fd

    def sync(fd):
        if fd in receipt_fds:
            raise OSError("injected clearance file fsync failure")
        return original_fsync(fd)

    monkeypatch.setattr(os, "open", open_file)
    monkeypatch.setattr(os, "fsync", sync)
    with pytest.raises((OSError, MaintenanceBlocked)):
        acknowledge(recovery, selected)
    assert_precommit_failure(recovery, selected)


def test_f5_clearance_receipt_directory_fsync_failure_keeps_active_blockers(completed, monkeypatch):
    recovery, selected = completed
    maintenance_inode = recovery.maintenance.root.stat().st_ino
    original_link, original_fsync = os.link, os.fsync
    receipt_linked = False

    def link(src, dst, *args, src_dir_fd=None, dst_dir_fd=None, **kwargs):
        nonlocal receipt_linked
        result = original_link(src, dst, *args, src_dir_fd=src_dir_fd,
                               dst_dir_fd=dst_dir_fd, **kwargs)
        if (dst == recovery.maintenance.CLEARANCE and dst_dir_fd is not None
                and os.fstat(dst_dir_fd).st_ino == maintenance_inode):
            receipt_linked = True
        return result

    def sync(fd):
        if (receipt_linked and stat.S_ISDIR(os.fstat(fd).st_mode)
                and os.fstat(fd).st_ino == maintenance_inode):
            raise OSError("injected clearance directory fsync failure")
        return original_fsync(fd)

    monkeypatch.setattr(os, "link", link)
    monkeypatch.setattr(os, "fsync", sync)
    with pytest.raises((OSError, MaintenanceBlocked)):
        acknowledge(recovery, selected)
    assert (recovery.maintenance.root / recovery.maintenance.CLEARANCE).exists()
    assert (recovery.maintenance.root / recovery.maintenance.LOCK).exists()
    assert (recovery.maintenance.root / recovery.maintenance.STATE).exists()
    assert_startup_blocked(recovery)


def test_f6_active_state_archive_failure_keeps_active_blockers(completed, monkeypatch):
    recovery, selected = completed

    def fail(*_args, **_kwargs):
        raise OSError("injected active state archive failure")

    monkeypatch.setattr(recovery, "_write_once", fail)
    with pytest.raises((OSError, MaintenanceBlocked)):
        acknowledge(recovery, selected)
    assert_precommit_failure(recovery, selected)


@pytest.mark.parametrize(
    "name,remaining",
    [
        ("maintenance.lock", {"maintenance.lock", "restore-state.json"}),
        ("restore-state.json", {"restore-state.json"}),
    ],
)
def test_f7_f8_blocker_removal_failure_remains_blocked(completed, name, remaining, monkeypatch):
    recovery, selected = completed
    original = os.unlink

    def unlink(path, *args, **kwargs):
        if path == name:
            raise PermissionError("injected blocker removal failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink)
    result = acknowledge(recovery, selected)
    assert result["acknowledge_committed"] is True
    assert result["cleanup_complete"] is False
    assert result["startup_allowed"] is False
    assert {item for item in remaining if (recovery.maintenance.root / item).exists()} == remaining
    assert (recovery.maintenance.root / recovery.maintenance.CLEARANCE).is_file()
    assert_startup_blocked(recovery)
    assert (workspace(recovery, selected) / "original").exists()


def test_final_sync_and_blocker_recreation_failure_uses_durable_clearance(completed, monkeypatch):
    """Regression: F9 is committed before cleanup; no compensation is required."""
    recovery, selected = completed
    original_unlink, original_sync, original_open = os.unlink, os.fsync, os.open
    state_removed = False
    recreation_attempted = False

    def unlink(path, *args, **kwargs):
        nonlocal state_removed
        result = original_unlink(path, *args, **kwargs)
        if path == recovery.maintenance.STATE:
            state_removed = True
        return result

    def sync(fd):
        if (state_removed and stat.S_ISDIR(os.fstat(fd).st_mode)
                and os.fstat(fd).st_ino == recovery.maintenance.root.stat().st_ino):
            raise OSError("injected final directory sync failure")
        return original_sync(fd)

    def open_file(path, flags, *args, **kwargs):
        nonlocal recreation_attempted
        if state_removed and flags & os.O_CREAT and path != recovery.maintenance.GATE:
            recreation_attempted = True
            raise PermissionError("injected blocker recreation failure")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink)
    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "open", open_file)
    result = acknowledge(recovery, selected)
    assert state_removed and not recreation_attempted
    assert result["acknowledge_committed"] is True
    assert result["cleanup_complete"] is False
    assert result["startup_allowed"] is True
    assert (workspace(recovery, selected) / "original" / recovery.restore.source.name).is_file()
    assert (workspace(recovery, selected) / "candidate.sqlite3").is_file()
    assert (recovery.maintenance.root / recovery.maintenance.CLEARANCE).is_file()
    # Once the transient IO injection is gone, both admission paths must reach
    # the same deterministic answer from the durable, fully reverified receipt.
    monkeypatch.setattr(os, "unlink", original_unlink)
    monkeypatch.setattr(os, "fsync", original_sync)
    monkeypatch.setattr(os, "open", original_open)
    assert recovery.check_startup() is True
    with recovery.backend_usage():
        pass


def _complete_after_final_cleanup_sync_failure(recovery, selected, monkeypatch):
    original_unlink, original_sync = os.unlink, os.fsync
    state_removed = False

    def unlink(path, *args, **kwargs):
        nonlocal state_removed
        result = original_unlink(path, *args, **kwargs)
        if path == recovery.maintenance.STATE:
            state_removed = True
        return result

    def sync(fd):
        if (state_removed and stat.S_ISDIR(os.fstat(fd).st_mode)
                and os.fstat(fd).st_ino == recovery.maintenance.root.stat().st_ino):
            raise OSError("injected final directory sync failure")
        return original_sync(fd)

    monkeypatch.setattr(os, "unlink", unlink)
    monkeypatch.setattr(os, "fsync", sync)
    result = acknowledge(recovery, selected)
    monkeypatch.setattr(os, "unlink", original_unlink)
    monkeypatch.setattr(os, "fsync", original_sync)
    assert result["acknowledge_committed"] and result["startup_allowed"]


@pytest.mark.parametrize("location", ["maintenance", "workspace"])
def test_f10_corrupt_receipt_after_f9_blocks_startup(completed, monkeypatch, location):
    recovery, selected = completed
    _complete_after_final_cleanup_sync_failure(recovery, selected, monkeypatch)
    receipt = (recovery.maintenance.root / recovery.maintenance.CLEARANCE
               if location == "maintenance"
               else workspace(recovery, selected) / "startup-clearance.json")
    receipt.write_bytes(b"{corrupt")
    assert_startup_blocked(recovery)
    assert recovery.status()["startup_allowed"] is False


def test_completed_workspace_without_clearance_blocks_startup(completed):
    recovery, selected = completed
    for name in (recovery.maintenance.LOCK, recovery.maintenance.STATE):
        (recovery.maintenance.root / name).unlink()
    assert (workspace(recovery, selected) / "operation.json").is_file()
    assert_startup_blocked(recovery)
    assert recovery.status()["startup_allowed"] is False


def test_f11_live_database_change_after_f9_blocks_startup(completed, monkeypatch):
    recovery, selected = completed
    _complete_after_final_cleanup_sync_failure(recovery, selected, monkeypatch)
    with recovery.restore.source.open("ab") as stream:
        stream.write(b"changed")
    assert_startup_blocked(recovery)


def test_f13_reappearing_old_blocker_after_cleanup_blocks_startup(completed):
    recovery, selected = completed
    state = (recovery.maintenance.root / recovery.maintenance.STATE).read_bytes()
    acknowledge(recovery, selected)
    (recovery.maintenance.root / recovery.maintenance.STATE).write_bytes(state)
    assert_startup_blocked(recovery)


@pytest.mark.parametrize("field,value", [("alembic_version", "unknown"), ("integrity_check", "corrupt"), ("foreign_key_errors", 1), ("compatible_for_restore", False)])
def test_acknowledge_full_verification_failure(completed, monkeypatch, field, value):
    recovery, selected = completed
    inspect = recovery.restore.backup._inspect
    def changed(*args, **kwargs):
        measured = inspect(*args, **kwargs)
        # Actual inspection folds these checks into the valid/compatible status.
        return measured.model_copy(update={field: value, "status": "corrupted", "compatible_for_restore": False})
    monkeypatch.setattr(recovery.restore.backup, "_inspect", changed)
    with pytest.raises(RestoreRefused):
        acknowledge(recovery, selected)
    blocked(recovery.restore)


def test_cli_acknowledge_success(completed, monkeypatch):
    recovery, selected = completed
    monkeypatch.setattr(maintenance_cli, "get_settings", lambda: Settings(database_path=recovery.restore.source, _env_file=None))
    monkeypatch.setattr(maintenance_cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(maintenance_cli.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a: f"ACKNOWLEDGE {selected}")
    assert maintenance_cli.main(["acknowledge", selected]) == 0
    assert recovery.check_startup() is True


def test_backend_shutdown_error_preserves_blocker(database_engine, monkeypatch):
    settings = Settings(database_path=Path(database_engine.url.database), _env_file=None)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    engine = sessions.get_engine(settings.database_url)
    def dispose(*args, **kwargs):
        raise OSError("injected dispose failure")
    monkeypatch.setattr(engine, "dispose", dispose)
    with pytest.raises((OSError, MaintenanceBlocked)):
        with TestClient(app):
            pass
    safety = MaintenanceSafety(settings.maintenance_root, settings.app_version)
    with pytest.raises(MaintenanceBlocked):
        safety.check_startup()


@pytest.mark.parametrize("stdin,stdout,answer", [(False, True, ""), (True, False, ""), (True, True, "wrong"), (True, True, None)])
def test_cli_refuses_without_exact_tty_confirmation(completed, monkeypatch, stdin, stdout, answer):
    recovery, selected = completed
    settings = Settings(database_path=recovery.restore.source, _env_file=None)
    monkeypatch.setattr(maintenance_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(maintenance_cli.sys.stdin, "isatty", lambda: stdin)
    monkeypatch.setattr(maintenance_cli.sys.stdout, "isatty", lambda: stdout)
    def response(*args):
        if answer is None:
            raise EOFError
        return answer
    monkeypatch.setattr("builtins.input", response)
    assert maintenance_cli.main(["acknowledge", selected]) == 2
    blocked(recovery.restore)


def test_status_read_only(completed):
    recovery, selected = completed
    before = evidence(recovery)
    state = recovery.status()
    assert state["startup_blocked"] and state["operation_id"] == selected
    assert state["acknowledgement_candidate"]
    assert evidence(recovery) == before


def test_storage_probe_leaves_requested_directory_unchanged(tmp_path):
    before = list(tmp_path.iterdir())
    result = qualify_storage(tmp_path)
    assert result["status"] == "qualified" and not result["real_restore_approved"]
    assert list(tmp_path.iterdir()) == before


@pytest.mark.parametrize("capability", ["mount", "platform", "rename", "file-sync", "dir-sync", "flock"])
def test_storage_missing_capability_fails_closed(tmp_path, monkeypatch, capability):
    import app.services.storage_service as storage
    def fail(*args, **kwargs):
        raise OSError("unsupported")
    if capability == "mount":
        monkeypatch.setattr(storage, "same_mount", lambda *args: False)
    elif capability == "platform":
        monkeypatch.setattr(storage, "platform_check", fail)
    elif capability == "rename":
        monkeypatch.setattr(storage, "rename_noreplace", fail)
    elif capability == "flock":
        monkeypatch.setattr(storage, "fcntl", None)
    else:
        original = os.fsync
        def sync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode) == (capability == "dir-sync"):
                fail()
            return original(fd)
        monkeypatch.setattr(os, "fsync", sync)
    with pytest.raises(RestoreRefused):
        qualify_storage(tmp_path)


def test_backend_database_lifetime_disposes_before_unlock(database_engine, tmp_path, monkeypatch):
    source = Path(database_engine.url.database)
    settings = Settings(database_path=source, _env_file=None)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    engine = sessions.get_engine(settings.database_url)
    original = engine.dispose
    events = []
    def dispose(*args, **kwargs):
        assert not sessions._runtime_sessions
        with (settings.maintenance_root / "coordination.lock").open("rb") as stream:
            with pytest.raises(BlockingIOError):
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        events.append("dispose")
        return original(*args, **kwargs)
    monkeypatch.setattr(engine, "dispose", dispose)
    with TestClient(app):
        dependency = sessions.get_db()
        session = next(dependency)
        session.execute(text("SELECT 1"))
        assert engine.pool.checkedout() == 1
        with pytest.raises(MaintenanceBlocked):
            with MaintenanceSafety(settings.maintenance_root, settings.app_version).execution_lease():
                pytest.fail("Backend active")
    assert events == ["dispose"] and sessions._runtime_engine is None
    with (settings.maintenance_root / "coordination.lock").open("rb") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    dependency.close()


def test_backend_start_race_refuses_before_database_initialization(tmp_path, monkeypatch):
    settings = Settings(database_path=tmp_path / "never-open.sqlite3", _env_file=None)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    safety = MaintenanceSafety(settings.maintenance_root, settings.app_version)
    safety.check_startup()  # Launcher preflight succeeded earlier.
    with safety.execution_lease():
        with pytest.raises(MaintenanceBlocked):
            with TestClient(app):
                pytest.fail("startup under exclusive Restore")
    assert not settings.resolved_database_path.exists()


def test_backend_rechecks_state_after_shared_acquisition(tmp_path, monkeypatch):
    safety = MaintenanceSafety(tmp_path / "maintenance", "0.6.0")
    original = safety._check
    checks = 0
    def check(fd, *args, **kwargs):
        nonlocal checks
        checks += 1
        if checks == 1:
            original(fd, *args, **kwargs)
            # Another operation completed its admission after the first check.
            (safety.root / "maintenance.lock").write_text("intervening operation")
        else:
            original(fd, *args, **kwargs)
    monkeypatch.setattr(safety, "_check", check)
    with pytest.raises(MaintenanceBlocked):
        with safety.backend_usage():
            pytest.fail("post-lock check must reject changed state")
    assert checks == 2


@pytest.mark.parametrize("filesystem", ["9p", "drvfs", "unknown", "xfs", "nfs"])
def test_storage_actual_mount_type_is_authoritative(tmp_path, monkeypatch, filesystem):
    import app.core.restore_io as io
    original = Path.read_text
    def read(path, *args, **kwargs):
        if path == Path("/proc/self/mountinfo"):
            return f"12 1 0:2 / / rw - {filesystem} disk rw\n"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(io, "mount_id", lambda fd: "12")
    with pytest.raises(RestoreRefused):
        qualify_storage(tmp_path)


@pytest.mark.parametrize("acknowledged", [False, True])
def test_launcher_check_completed_then_acknowledged(completed, acknowledged):
    recovery, selected = completed
    if acknowledged:
        acknowledge(recovery, selected)
    script = Path(__file__).resolve().parents[2] / "scripts" / "dayflow-start.sh"
    env = {**os.environ, "DAYFLOW_DATABASE_PATH": str(recovery.restore.source),
           "DAYFLOW_ALLOW_NONREAL_DATABASE": "1", "DAYFLOW_STATE_DIR": str(recovery.restore.source.parent / "launcher")}
    result = subprocess.run(["bash", str(script), "--check"], env=env, capture_output=True, timeout=30)
    assert (result.returncode == 0) == acknowledged, result.stderr.decode()
