"""Execution/abort tests use migrated disposable databases only."""
import errno
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from app.core.maintenance import MaintenanceBlocked, MaintenanceSafety
from app.core.restore_io import RestoreRefused, external_users, directory, rename_noreplace
from app.services.backup_service import BackupService
from app.services.restore_service import RestoreService, RestoreFailed, logical_status
from app import maintenance_cli
from app.core.errors import AppError


@pytest.fixture
def setup_restore(database_engine, tmp_path, monkeypatch):
    source = Path(database_engine.url.database)
    database_engine.dispose()
    backup = BackupService(source, tmp_path / "backups", "0.8.0")
    item = backup.create()
    # Distinguish live from target without introducing task/API fixture dependencies.
    with sqlite3.connect(source) as c:
        c.execute("INSERT INTO categories (id,name) VALUES ('current-only','current')")
    c.close()
    # Model the test operation's explicitly isolated, fully visible process set.
    # Production continues scanning /proc and refusing inaccessible host processes.
    proc_view = tmp_path / "proc-view"
    proc_view.mkdir()
    (proc_view / str(os.getpid())).symlink_to(Path("/proc") / str(os.getpid()))
    monkeypatch.setattr("app.services.restore_service.external_users", lambda identities: external_users(identities, proc_view))
    return RestoreService(backup), item


def execute(service, item):
    return service.execute(item.backup_id, f"RESTORE {item.backup_id}")


def blocked(service):
    with pytest.raises(MaintenanceBlocked):
        service.maintenance.check_startup()
    with pytest.raises(MaintenanceBlocked):
        with service.maintenance.backend_usage():
            pytest.fail("Backend must not start")


def launcher_blocked(service):
    records = {path.name: path.read_bytes() for path in service.maintenance.root.iterdir()}
    env = {**os.environ, "DAYFLOW_DATABASE_PATH": str(service.source),
           "DAYFLOW_ALLOW_NONREAL_DATABASE": "1",
           "DAYFLOW_STATE_DIR": str(service.source.parent / "launcher-review")}
    script = Path(__file__).resolve().parents[2] / "scripts" / "dayflow-start.sh"
    result = subprocess.run(["bash", str(script), "--check"], env=env, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert records == {path.name: path.read_bytes() for path in service.maintenance.root.iterdir()}
    assert not (service.source.parent / "launcher-review" / "backend.meta").exists()


def test_success_preserves_all_and_completed_blocks(setup_restore):
    service, item = setup_restore
    old = service.source.read_bytes()
    target = service.backup.root / item.filename
    manifest = target.with_name(target.name + ".json")
    manifest_before = manifest.read_bytes()
    result = execute(service, item)
    workspace = service.backup.root / "restore-operations" / result.operation_id
    assert service.source.read_bytes() == target.read_bytes()
    assert (workspace / "original" / service.source.name).read_bytes() == old
    assert (workspace / "candidate.sqlite3").read_bytes() == target.read_bytes()
    assert not (workspace / "install.sqlite3.partial").exists()
    safety_service = BackupService(service.source, workspace / "pre-restore-safety", "0.8.0")
    assert safety_service.verify(result.safety_backup_id).status == "valid"
    assert logical_status(safety_service.root / safety_service.list()[0].filename, standalone=True)["categories"]["count"] == 1
    assert logical_status(service.source, standalone=True)["categories"]["count"] == 0
    assert manifest.read_bytes() == manifest_before
    record = service.maintenance.inspect()
    assert record.stage == "completed" and record.format_version == 2 and record.operation == "restore"
    blocked(service)
    with pytest.raises(MaintenanceBlocked):
        service.maintenance.cleanup(str(record.lock_id), confirmed=True)
    assert "current-only" not in (workspace / "events.jsonl").read_text()


@pytest.mark.parametrize("point", ["C0", "C1", "C2", "C3", "C4", "C5a", "C5b", "C5c", "C6", "C7", "C8", "C9"])
def test_process_abort_each_crash_point(setup_restore, point):
    service, item = setup_restore
    before = service.source.read_bytes()
    target = (service.backup.root / item.filename).read_bytes()
    manifest_path = service.backup.root / (item.filename + ".json")
    manifest_bytes = manifest_path.read_bytes()
    script = """
import os,sys
from pathlib import Path
from app.services.backup_service import BackupService
from app.services.restore_service import RestoreService
import app.services.restore_service as execution
from app.core.restore_io import external_users
execution.external_users=lambda ids: external_users(ids,Path(sys.argv[1]).parent/'proc-view')
s=RestoreService(BackupService(Path(sys.argv[1]),Path(sys.argv[2]),'0.8.0'),fault=lambda point: os._exit(73) if point==sys.argv[4] else None)
s.execute(sys.argv[3],'RESTORE '+sys.argv[3])
"""
    result = subprocess.run([sys.executable, "-c", script, str(service.source), str(service.backup.root), item.backup_id, point], capture_output=True, timeout=30)
    assert result.returncode == 73, result.stderr.decode()
    blocked(service)
    launcher_blocked(service)
    workspaces = list((service.backup.root / "restore-operations").iterdir())
    assert len(workspaces) == 1
    work = workspaces[0]
    assert (service.backup.root / item.filename).read_bytes() == target
    assert manifest_path.read_bytes() == manifest_bytes
    if point not in {"C0"}:
        manifests = list((work / "pre-restore-safety").glob("*.sqlite3.json"))
        assert len(manifests) == 1
        safety_metadata = json.loads(manifests[0].read_text())
        safety_path = work / "pre-restore-safety" / safety_metadata["filename"]
        assert hashlib.sha256(safety_path.read_bytes()).hexdigest() == safety_metadata["database_sha256"]
        assert logical_status(safety_path, standalone=True)["categories"]["count"] == 1
    if point in {"C3", "C4", "C5a", "C5b", "C5c", "C6", "C7", "C8", "C9"}:
        assert (work / "candidate.sqlite3").read_bytes() == target
        assert (work / "install.sqlite3.partial").exists() == (point not in {"C6", "C7", "C8", "C9"})
    state = service.maintenance.inspect()
    expected_stage = ("completed" if point == "C9" else "verifying" if point in {"C7", "C8"}
                      else "switching" if point in {"C4", "C5a", "C5b", "C5c", "C6"} else "prepare")
    assert state.stage == expected_stage
    assert state.format_version == 2
    events = [json.loads(line)["event"] for line in (work / "events.jsonl").read_text().splitlines()]
    assert ("result" in events) == (point == "C9")
    assert ("switch_intent" in events) == (point in {"C4", "C5a", "C5b", "C5c", "C6", "C7", "C8", "C9"})
    assert (service.maintenance.root / "maintenance.lock").exists()
    assert not Path(str(service.source) + "-wal").exists()
    assert not Path(str(service.source) + "-shm").exists()
    assert target == (service.backup.root / item.filename).read_bytes()
    if point in {"C5c", "C6", "C7", "C8", "C9"}:
        assert (work / "original" / service.source.name).read_bytes() == before
    if point == "C5c":
        assert not service.source.exists()
    elif point in {"C6", "C7", "C8", "C9"}:
        assert service.source.read_bytes() == target
    else:
        assert service.source.read_bytes() == before


def test_live_wal_shm_preserved_with_committed_snapshot(setup_restore):
    service, item = setup_restore
    script = """
import sqlite3,os,sys
c=sqlite3.connect(sys.argv[1]);c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA wal_autocheckpoint=0')
c.execute("INSERT INTO tags(id,name) VALUES ('wal-row','committed')");c.commit()
c.execute("INSERT INTO tags(id,name) VALUES ('uncommitted','excluded')");os._exit(0)
"""
    subprocess.run([sys.executable, "-c", script, str(service.source)], check=True)
    wal = Path(str(service.source) + "-wal")
    shm = Path(str(service.source) + "-shm")
    initial = {p.name: p.read_bytes() for p in (service.source, wal, shm)}
    result = execute(service, item)
    workspace = service.backup.root / "restore-operations" / result.operation_id
    for name, value in initial.items():
        assert (workspace / "original" / name).read_bytes() == value
        assert (workspace / "current-evidence" / name).read_bytes() == value
    assert not wal.exists() and not shm.exists()
    safety = BackupService(service.source, workspace / "pre-restore-safety", "0.8.0")
    assert logical_status(safety.root / safety.list()[0].filename, standalone=True)["tags"]["count"] == 1


@pytest.mark.parametrize("stage", ["prepare", "verified", "switching", "verifying", "completed"])
def test_state_publication_failure_stops_progress(setup_restore, monkeypatch, stage):
    service, item = setup_restore
    old = service.source.read_bytes()
    original = MaintenanceSafety._publish
    def fail(self, fd, name, record, *, replace):
        if name == self.STATE and record.stage == stage:
            raise OSError(errno.ENOSPC, "simulated")
        return original(self, fd, name, record, replace=replace)
    monkeypatch.setattr(MaintenanceSafety, "_publish", fail)
    with pytest.raises((RestoreFailed, OSError)):
        execute(service, item)
    blocked(service)
    if stage in {"prepare", "verified", "switching"}:
        assert service.source.read_bytes() == old


@pytest.mark.parametrize("case", ["corrupt", "manifest", "missing", "incompatible", "invalid_id"])
def test_admission_target_failure_no_restore_state(setup_restore, case):
    service, item = setup_restore
    target = service.backup.root / item.filename
    if case == "corrupt":
        target.write_bytes(b"broken")
    elif case == "manifest":
        path = target.with_name(target.name + ".json")
        data = json.loads(path.read_text()); data["database_sha256"] = "0" * 64; path.write_text(json.dumps(data))
    elif case == "missing":
        target.unlink()
    elif case == "incompatible":
        with sqlite3.connect(target) as c:
            c.execute("UPDATE alembic_version SET version_num='0004_add_projects'")
    backup_id = "../invalid" if case == "invalid_id" else item.backup_id
    before = service.source.read_bytes()
    with pytest.raises((RestoreRefused, AppError)):
        service.execute(backup_id, f"RESTORE {backup_id}")
    assert service.source.read_bytes() == before
    assert not (service.maintenance.root / "maintenance.lock").exists()
    assert not (service.backup.root / "restore-operations").exists()


def test_backend_shared_lease_refuses_admission(setup_restore):
    service, item = setup_restore
    with service.maintenance.backend_usage():
        with pytest.raises((MaintenanceBlocked, BlockingIOError)):
            execute(service, item)
    assert not (service.maintenance.root / "maintenance.lock").exists()


def test_external_descriptor_detected(setup_restore):
    service, item = setup_restore
    script = "import sys;f=open(sys.argv[1],'rb');print('ready',flush=True);sys.stdin.read()"
    child = subprocess.Popen([sys.executable, "-c", script, str(service.source)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        (service.source.parent / "proc-view" / str(child.pid)).symlink_to(Path("/proc") / str(child.pid))
        with pytest.raises(RestoreRefused):
            execute(service, item)
        assert child.poll() is None
        assert not (service.maintenance.root / "maintenance.lock").exists()
    finally:
        child.communicate(timeout=5)


def test_proc_unavailable_refuses(tmp_path):
    with pytest.raises(RestoreRefused):
        external_users(set(), tmp_path / "missing")


def test_no_replace_collision_keeps_both(tmp_path):
    (tmp_path / "source").write_bytes(b"s")
    (tmp_path / "target").write_bytes(b"t")
    with directory(tmp_path) as fd:
        with pytest.raises(FileExistsError):
            rename_noreplace(fd, "source", fd, "target")
    assert (tmp_path / "source").read_bytes() == b"s"
    assert (tmp_path / "target").read_bytes() == b"t"


@pytest.mark.parametrize("point", ["C1", "C2", "C3", "C4", "C5c", "C6", "C7", "C8"])
def test_injected_exception_retains_blocking(setup_restore, point):
    service, item = setup_restore
    def fail(name):
        if name == point:
            raise OSError(errno.ENOSPC, "simulated disk failure")
    service.fault = fail
    with pytest.raises(RestoreFailed):
        execute(service, item)
    blocked(service)


@pytest.mark.parametrize("confirmation", ["", "RESTORE wrong"])
def test_wrong_confirmation_no_state(setup_restore, confirmation):
    service, item = setup_restore
    with pytest.raises(RestoreRefused):
        service.execute(item.backup_id, confirmation)
    assert not service.maintenance.root.exists()


def test_cli_non_tty_rejected_without_service(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(maintenance_cli, "get_settings", lambda: pytest.fail("Must refuse before configuration"))
    assert maintenance_cli.main(["restore", "bad-id"]) == 2


def test_real_location_rejected_without_opening(monkeypatch):
    from app.core.config import PROJECT_ROOT
    # Guard is checked lexically before file access; no real DB is opened.
    source = PROJECT_ROOT / "data" / "dayflow.sqlite3"
    service = RestoreService(BackupService(source, source.parent / "backups", "0.8.0"))
    monkeypatch.setattr(Path, "resolve", lambda self: self)
    with pytest.raises(RestoreRefused):
        service.isolation()


@pytest.mark.parametrize("failure", ["safety", "target", "candidate", "candidate_verify", "install", "final_verify"])
def test_phase_failure_retains_artifacts(setup_restore, monkeypatch, failure):
    import app.services.restore_service as module
    service, item = setup_restore
    before = service.source.read_bytes()
    if failure == "safety":
        monkeypatch.setattr(BackupService, "create", lambda self: (_ for _ in ()).throw(OSError(errno.EACCES, "test")))
    elif failure == "target":
        original = service.verify_target
        def target(backup_id, expected=None):
            if expected is not None:
                raise RestoreRefused("changed")
            return original(backup_id)
        monkeypatch.setattr(service, "verify_target", target)
    elif failure == "candidate":
        original = module.copy_file
        def copy(src, name, dst, output):
            if output == "candidate.sqlite3":
                raise OSError(errno.ENOSPC, "test")
            return original(src, name, dst, output)
        monkeypatch.setattr(module, "copy_file", copy)
    elif failure in {"candidate_verify", "final_verify"}:
        original = BackupService._inspect
        def inspect(self, root, name, backup_id, expected_fd=None):
            result = original(self, root, name, backup_id, expected_fd)
            if name == ("candidate.sqlite3" if failure == "candidate_verify" else service.source.name):
                result.status = "corrupted"
            return result
        monkeypatch.setattr(BackupService, "_inspect", inspect)
    elif failure == "install":
        original = module.rename_noreplace
        def rename(src, name, dst, output):
            if name == "install.sqlite3.partial":
                raise FileExistsError(errno.EEXIST, "test")
            return original(src, name, dst, output)
        monkeypatch.setattr(module, "rename_noreplace", rename)
    with pytest.raises(RestoreFailed):
        execute(service, item)
    blocked(service)
    if failure not in {"install", "final_verify"}:
        assert service.source.read_bytes() == before
    if failure == "install":
        assert not service.source.exists()
    assert (service.backup.root / item.filename).exists()


def test_reappearing_wal_prevents_install(setup_restore):
    service, item = setup_restore
    def inject(point):
        if point == "C5c":
            Path(str(service.source) + "-wal").write_bytes(b"unexpected")
    service.fault = inject
    with pytest.raises(RestoreFailed):
        execute(service, item)
    assert not service.source.exists()
    blocked(service)


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_fsync_failure_blocks_after_admission(setup_restore, monkeypatch, kind):
    import stat
    service, item = setup_restore
    real_sync = os.fsync
    armed = False
    def arm(point):
        nonlocal armed
        if point == "C0":
            armed = True
    service.fault = arm
    def sync(fd):
        matches = stat.S_ISDIR(os.fstat(fd).st_mode) == (kind == "directory")
        if armed and matches:
            raise OSError(errno.EIO, "test")
        return real_sync(fd)
    monkeypatch.setattr(os, "fsync", sync)
    before = service.source.read_bytes()
    with pytest.raises(RestoreFailed) as error:
        execute(service, item)
    assert not error.value.failure_recorded
    assert service.source.read_bytes() == before
    blocked(service)


@pytest.mark.parametrize("error", [errno.EXDEV, errno.ENOSYS, errno.EACCES])
def test_capability_failure_no_admission(setup_restore, monkeypatch, error):
    import app.core.restore_io as module
    service, item = setup_restore
    monkeypatch.setattr(module, "rename_noreplace", lambda *args: (_ for _ in ()).throw(OSError(error, "test")))
    with pytest.raises(RestoreRefused):
        execute(service, item)
    assert not service.maintenance.root.exists()


def test_proc_permission_failure_refuses(tmp_path, monkeypatch):
    import app.core.restore_io as module
    original = Path.iterdir
    def deny(path):
        if path == Path("/proc"):
            raise PermissionError("test")
        return original(path)
    monkeypatch.setattr(Path, "iterdir", deny)
    with pytest.raises(RestoreRefused):
        module.external_users(set())


def test_external_sqlite_connection_refuses(setup_restore):
    service, item = setup_restore
    child = subprocess.Popen([sys.executable, "-c", "import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);c.execute('SELECT * FROM tasks');print('ready',flush=True);sys.stdin.read()", str(service.source)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        (service.source.parent / "proc-view" / str(child.pid)).symlink_to(Path("/proc") / str(child.pid))
        with pytest.raises(RestoreRefused):
            execute(service, item)
    finally:
        child.communicate(timeout=5)


@pytest.mark.parametrize("answer", ["wrong", "", None])
def test_cli_tty_confirmation_refusal(setup_restore, monkeypatch, answer):
    service, item = setup_restore
    from app.core.config import Settings
    monkeypatch.setattr(maintenance_cli, "get_settings", lambda: Settings(database_path=service.source))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    def respond(prompt):
        if answer is None:
            raise EOFError
        return answer
    monkeypatch.setattr("builtins.input", respond)
    assert maintenance_cli.main(["restore", item.backup_id]) == 2
    assert not (service.maintenance.root / "maintenance.lock").exists()


def test_cli_json_execution_refused(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert maintenance_cli.main(["restore", "id", "--json"]) == 2


@pytest.mark.parametrize("point,archived", [("C5a", ["-wal"]), ("C5b", ["-wal", "-shm"]), ("C5c", ["-wal", "-shm", ""])])
def test_actual_sidecar_move_abort(setup_restore, point, archived):
    service, item = setup_restore
    writer = "import sqlite3,os,sys;c=sqlite3.connect(sys.argv[1]);c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA wal_autocheckpoint=0');c.execute(\"INSERT INTO tags(id,name) VALUES ('wal','wal')\");c.commit();os._exit(0)"
    subprocess.run([sys.executable, "-c", writer, str(service.source)], check=True)
    initial = {suffix: Path(str(service.source) + suffix).read_bytes() for suffix in ("", "-wal", "-shm")}
    runner = "from pathlib import Path;import os,sys;from app.services.backup_service import BackupService;from app.services.restore_service import RestoreService;import app.services.restore_service as execution;from app.core.restore_io import external_users;execution.external_users=lambda ids:external_users(ids,Path(sys.argv[1]).parent/'proc-view');s=RestoreService(BackupService(Path(sys.argv[1]),Path(sys.argv[2]),'0.8.0'),fault=lambda p:os._exit(73) if p==sys.argv[4] else None);s.execute(sys.argv[3],'RESTORE '+sys.argv[3])"
    result = subprocess.run([sys.executable, "-c", runner, str(service.source), str(service.backup.root), item.backup_id, point], capture_output=True, timeout=30)
    assert result.returncode == 73, result.stderr.decode()
    workspace = next((service.backup.root / "restore-operations").iterdir())
    for suffix, data in initial.items():
        location = workspace / "original" / (service.source.name + suffix) if suffix in archived else Path(str(service.source) + suffix)
        assert location.read_bytes() == data
    blocked(service)
    launcher_blocked(service)


def test_archive_collision_cannot_overwrite(setup_restore):
    service, item = setup_restore
    before = service.source.read_bytes()
    def conflict(point):
        if point == "C4":
            workspace = next((service.backup.root / "restore-operations").iterdir())
            (workspace / "original" / service.source.name).write_bytes(b"already exists")
    service.fault = conflict
    with pytest.raises(RestoreFailed):
        execute(service, item)
    assert service.source.read_bytes() == before
    blocked(service)


def test_target_changed_after_safety_refuses(setup_restore):
    service, item = setup_restore
    before = service.source.read_bytes()
    def corrupt(point):
        if point == "C1":
            (service.backup.root / item.filename).write_bytes(b"replaced")
    service.fault = corrupt
    with pytest.raises(RestoreFailed):
        execute(service, item)
    assert service.source.read_bytes() == before
    assert not list((service.backup.root / "restore-operations").glob("*/candidate.sqlite3"))
    blocked(service)


def test_current_corrupt_fails_before_state(setup_restore):
    service, item = setup_restore
    service.source.write_bytes(b"broken current")
    with pytest.raises(sqlite3.DatabaseError):
        execute(service, item)
    assert not (service.maintenance.root / "maintenance.lock").exists()
    assert not (service.backup.root / "restore-operations").exists()


def test_unknown_state_refuses(setup_restore):
    service, item = setup_restore
    record = service.maintenance.begin()
    path = service.maintenance.root / "restore-state.json"
    value = json.loads(path.read_text()); value["stage"] = "unknown"; path.write_text(json.dumps(value))
    with pytest.raises(MaintenanceBlocked):
        execute(service, item)
    assert (service.maintenance.root / "maintenance.lock").exists()


def test_summary_target_hash_mismatch_refuses(setup_restore):
    service, item = setup_restore
    with pytest.raises(RestoreRefused):
        service.execute(item.backup_id, f"RESTORE {item.backup_id}", expected_target_sha="0" * 64)
    assert not service.maintenance.root.exists()


def test_cross_mount_detected_before_admission(setup_restore, monkeypatch):
    service, item = setup_restore
    monkeypatch.setattr("app.services.restore_service.same_mount", lambda *args: False)
    with pytest.raises(RestoreRefused):
        execute(service, item)
    assert not (service.maintenance.root / "maintenance.lock").exists()


def test_symlink_root_refuses(setup_restore):
    service, item = setup_restore
    renamed = service.backup.root.with_name("old-backups")
    service.backup.root.rename(renamed)
    service.backup.root.symlink_to(renamed)
    with pytest.raises((AppError, RestoreRefused)):
        execute(service, item)
    assert not service.maintenance.root.exists()


def test_hardlinked_source_refuses(setup_restore):
    service, item = setup_restore
    os.link(service.source, service.source.with_name("another-link"))
    with pytest.raises(RestoreRefused):
        execute(service, item)
    assert not service.maintenance.root.exists()


def test_tty_cli_success(setup_restore, monkeypatch, capsys):
    service, item = setup_restore
    from app.core.config import Settings
    monkeypatch.setattr(maintenance_cli, "get_settings", lambda: Settings(database_path=service.source))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: f"RESTORE {item.backup_id}")
    assert maintenance_cli.main(["restore", item.backup_id]) == 0
    output = capsys.readouterr().out
    assert "DayFlow remains stopped." in output
    assert "Maintenance confirmation is still required" in output
    blocked(service)


def test_prototype_transition_cannot_complete_execution(setup_restore):
    service, item = setup_restore
    def stop(point):
        if point == "C0":
            raise SystemExit(73)
    service.fault = stop
    with pytest.raises(SystemExit):
        execute(service, item)
    state = service.maintenance.inspect()
    with pytest.raises(MaintenanceBlocked):
        service.maintenance.advance(str(state.lock_id), "prepare", "verified", confirmed=True)
    assert service.maintenance.inspect().stage == "prepare"


@pytest.mark.parametrize("alias", ["symlink", "hardlink", "normalized"])
def test_protected_database_alias_refuses_without_sqlite(setup_restore, tmp_path, monkeypatch, alias):
    import app.services.restore_service as module
    service, item = setup_restore
    project = tmp_path / "protected-project"
    data = project / "data"
    data.mkdir(parents=True)
    protected = data / "dayflow.sqlite3"
    protected.write_bytes(b"protected fixture, not a real database")
    monkeypatch.setattr(module, "PROJECT_ROOT", project)
    path = tmp_path / "alias.sqlite3"
    if alias == "symlink":
        path.symlink_to(protected)
    elif alias == "hardlink":
        os.link(protected, path)
    else:
        path = data / ".." / "data" / "dayflow.sqlite3"
    probe = RestoreService(BackupService(path, path.parent / "backups", "0.8.0"))
    monkeypatch.setattr(module.sqlite3, "connect", lambda *a, **kw: pytest.fail("Must reject before SQLite access"))
    with pytest.raises(RestoreRefused):
        probe.isolation()
    assert protected.read_bytes() == b"protected fixture, not a real database"
    assert not (data / "maintenance").exists()


def test_bind_like_inode_alias_refused(setup_restore, tmp_path, monkeypatch):
    import app.services.restore_service as module
    service, item = setup_restore
    project = tmp_path / "project"
    (project / "data").mkdir(parents=True)
    protected = project / "data" / "dayflow.sqlite3"
    protected.write_bytes(b"fixture")
    monkeypatch.setattr(module, "PROJECT_ROOT", project)
    original = Path.stat
    def stat(path, *args, **kwargs):
        # Model the same inode visible through a different mount path, without
        # privileged mounts or opening any real database.
        return original(protected, *args, **kwargs) if path == service.source else original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", stat)
    with pytest.raises(RestoreRefused):
        execute(service, item)
    assert not service.maintenance.root.exists()


def test_environment_temp_root_cannot_expand_boundary(setup_restore, monkeypatch):
    service, item = setup_restore
    monkeypatch.setattr("app.services.restore_service.tempfile.gettempdir", lambda: "/home")
    with pytest.raises(RestoreRefused):
        execute(service, item)
    assert not service.maintenance.root.exists()


@pytest.mark.parametrize("artifact", ["database", "manifest"])
def test_identical_bytes_replacement_after_confirmation_refused(setup_restore, artifact):
    service, item = setup_restore
    summary = service.preview(item.backup_id)
    target = service.backup.root / item.filename
    if artifact == "manifest":
        target = target.with_name(target.name + ".json")
    replacement = target.with_name("replacement")
    replacement.write_bytes(target.read_bytes())
    replacement.replace(target)
    with pytest.raises(RestoreRefused):
        service.execute(item.backup_id, f"RESTORE {item.backup_id}",
                        expected_target_snapshot=summary["_target_snapshot"])
    assert not service.maintenance.root.exists()


@pytest.mark.parametrize("variation", ["lower", "leading", "trailing", "extra", "newline"])
def test_confirmation_is_exact(setup_restore, variation):
    service, item = setup_restore
    text = f"RESTORE {item.backup_id}"
    text = {"lower": text.lower(), "leading": " " + text, "trailing": text + " ",
            "extra": text + " extra", "newline": text + "\n"}[variation]
    with pytest.raises(RestoreRefused):
        service.execute(item.backup_id, text)
    assert not service.maintenance.root.exists()


def test_exclusive_gate_held_for_entire_execution(setup_restore):
    import fcntl
    service, item = setup_restore
    observed = []
    gate_identity = None
    def check(point):
        nonlocal gate_identity
        path = service.maintenance.root / "coordination.lock"
        with path.open("rb") as fd:
            inode = (os.fstat(fd.fileno()).st_dev, os.fstat(fd.fileno()).st_ino)
            gate_identity = gate_identity or inode
            assert inode == gate_identity
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        observed.append(point)
    service.fault = check
    execute(service, item)
    assert observed == ["C0", "C1", "C2", "C3", "C4", "C5a", "C5b", "C5c", "C6", "C7", "C8", "C9"]


def test_external_usage_rechecked_before_switching(setup_restore, monkeypatch):
    service, item = setup_restore
    calls = 0
    before = service.source.read_bytes()
    def inspect(identities):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RestoreRefused("external user appeared")
    monkeypatch.setattr("app.services.restore_service.external_users", inspect)
    with pytest.raises(RestoreFailed):
        execute(service, item)
    assert calls == 2
    assert service.source.read_bytes() == before
    work = next((service.backup.root / "restore-operations").iterdir())
    assert not list((work / "original").iterdir())
    blocked(service)


def test_completed_v2_state_blocks_even_without_marker(setup_restore):
    service, item = setup_restore
    execute(service, item)
    (service.maintenance.root / "maintenance.lock").unlink()  # isolated tampering fixture
    blocked(service)


@pytest.mark.parametrize("event", ["switch_intent", "move_intent", "result"])
def test_log_persistence_barriers(setup_restore, monkeypatch, event):
    service, item = setup_restore
    before = service.source.read_bytes()
    original = service.record
    def record(workspace, name, **fields):
        if name == event:
            raise OSError(errno.EIO, "simulated log flush failure")
        return original(workspace, name, **fields)
    monkeypatch.setattr(service, "record", record)
    with pytest.raises(RestoreFailed):
        execute(service, item)
    blocked(service)
    assert service.maintenance.inspect().stage != "completed"
    if event != "result":
        assert service.source.read_bytes() == before
        work = next((service.backup.root / "restore-operations").iterdir())
        assert not list((work / "original").iterdir())
    else:
        assert service.source.read_bytes() == (service.backup.root / item.filename).read_bytes()


def test_switching_state_failure_preserves_wal_shm_db(setup_restore, monkeypatch):
    service, item = setup_restore
    writer = "import sqlite3,os,sys;c=sqlite3.connect(sys.argv[1]);c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA wal_autocheckpoint=0');c.execute(\"INSERT INTO tags(id,name) VALUES ('wal','wal')\");c.commit();os._exit(0)"
    subprocess.run([sys.executable, "-c", writer, str(service.source)], check=True)
    initial = {Path(str(service.source) + suffix): Path(str(service.source) + suffix).read_bytes()
               for suffix in ("", "-wal", "-shm")}
    original = MaintenanceSafety._publish
    def publish(self, fd, name, record, *, replace):
        if record.stage == "switching":
            raise OSError(errno.EIO, "simulated state flush failure")
        return original(self, fd, name, record, replace=replace)
    monkeypatch.setattr(MaintenanceSafety, "_publish", publish)
    with pytest.raises(RestoreFailed):
        execute(service, item)
    assert all(path.read_bytes() == data for path, data in initial.items())
    blocked(service)


def test_target_candidate_install_independent_inodes(setup_restore):
    service, item = setup_restore
    def inspect(point):
        if point == "C3":
            work = next((service.backup.root / "restore-operations").iterdir())
            paths = [service.backup.root / item.filename, work / "candidate.sqlite3", work / "install.sqlite3.partial"]
            assert len({(p.stat().st_dev, p.stat().st_ino) for p in paths}) == 3
            assert len({hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}) == 1
    service.fault = inspect
    execute(service, item)


def test_new_process_visibility_gap_rejected(tmp_path, monkeypatch):
    original = Path.iterdir
    view = tmp_path / "proc-empty"
    view.mkdir()
    calls = 0
    def listing(path):
        nonlocal calls
        if path == view:
            calls += 1
            return iter([] if calls == 1 else [view / "123"])
        return original(path)
    monkeypatch.setattr(Path, "iterdir", listing)
    with pytest.raises(RestoreRefused):
        external_users(set(), view)


def test_stdout_non_tty_rejected(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(maintenance_cli, "get_settings", lambda: pytest.fail("Must refuse before settings"))
    assert maintenance_cli.main(["restore", "bad-id"]) == 2


def test_archive_name_replacement_detected_before_install(setup_restore, monkeypatch):
    import app.services.restore_service as module
    service, item = setup_restore
    old = service.source.read_bytes()
    original = module.rename_noreplace
    def race(src, name, dst, output):
        if name == service.source.name:
            # Same-byte replacement between source checking and rename must
            # not be accepted merely because SHA matches.
            replacement = service.source.with_name("racing-replacement")
            replacement.write_bytes(old)
            service.source.rename(service.source.with_name("racing-original"))
            replacement.rename(service.source)
        return original(src, name, dst, output)
    monkeypatch.setattr(module, "rename_noreplace", race)
    with pytest.raises(RestoreFailed):
        execute(service, item)
    blocked(service)
    assert not service.source.exists()
    work = next((service.backup.root / "restore-operations").iterdir())
    assert (work / "original" / service.source.name).read_bytes() == old
    assert (work / "candidate.sqlite3").exists()
    assert (work / "install.sqlite3.partial").exists()


def test_filesystem_detection_uses_descriptor_mount_not_path(setup_restore, monkeypatch):
    import app.core.restore_io as module
    service, item = setup_restore
    original = Path.read_text
    def mountinfo(path, *args, **kwargs):
        if path == Path("/proc/self/mountinfo"):
            return "11 1 0:1 / / rw - ext4 disk rw\n12 1 0:2 / / rw - 9p disk rw\n"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", mountinfo)
    monkeypatch.setattr(module, "mount_id", lambda fd: "12")
    with pytest.raises(RestoreRefused):
        execute(service, item)
    assert not service.maintenance.root.exists()
