"""State-only safety tests: no Restore, Backup, or real database access."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.core.maintenance import MaintenanceBlocked, MaintenanceSafety
from app.main import app

BACKEND = Path(__file__).resolve().parents[1]
PROJECT = BACKEND.parent


@pytest.fixture
def safety(tmp_path):
    return MaintenanceSafety(tmp_path / "maintenance", "0.8.0")


def contents(root):
    return {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}


def complete(safety, lock_id):
    for old, new in [("prepare", "verified"), ("verified", "switching"), ("switching", "verifying"), ("verifying", "completed")]:
        safety.advance(lock_id, old, new, confirmed=True)


def test_idle_check_is_read_only_and_settings_are_database_adjacent(safety, tmp_path):
    assert Settings(database_path=tmp_path / "test.sqlite3", _env_file=None).maintenance_root == safety.root
    safety.check_startup()
    assert safety.inspect() is None
    assert not safety.root.exists()


def test_create_duplicate_and_valid_transitions(safety):
    record = safety.begin()
    assert record.stage == "prepare"
    assert record.created_at_utc.endswith("Z")
    assert record.operation == "restore-safety-prototype"
    assert record.app_version == "0.8.0"
    assert record.lock_id.version == 4
    original = contents(safety.root)
    with pytest.raises(MaintenanceBlocked):
        safety.begin()
    assert contents(safety.root) == original
    assert safety.inspect() == record
    complete(safety, str(record.lock_id))
    assert safety.inspect().stage == "completed"
    with pytest.raises(MaintenanceBlocked):
        safety.check_startup()  # Even completed still needs explicit lock cleanup.


def test_cleanup_requires_identity_completion_confirmation_and_preserves_record(safety):
    lock_id = str(safety.begin().lock_id)
    with pytest.raises(MaintenanceBlocked):
        safety.cleanup(lock_id, confirmed=True)
    complete(safety, lock_id)
    original = contents(safety.root)
    for wrong_id, confirmed in [(lock_id, False), (str(uuid4()), True)]:
        with pytest.raises(MaintenanceBlocked):
            safety.cleanup(wrong_id, confirmed=confirmed)
        assert contents(safety.root) == original
    safety.cleanup(lock_id, confirmed=True)
    safety.check_startup()
    assert safety.inspect().stage == "completed"
    assert (safety.root / safety.STATE).read_bytes() == original[safety.STATE]
    assert (safety.root / safety.GATE).exists()


@pytest.mark.parametrize("expected,target", [("prepare", "switching"), ("verified", "switching"), ("prepare", "unknown"), ("prepare", "idle")])
def test_invalid_or_stale_transition_preserves_state(safety, expected, target):
    lock_id = str(safety.begin().lock_id)
    original = contents(safety.root)
    with pytest.raises(MaintenanceBlocked):
        safety.advance(lock_id, expected, target)
    assert contents(safety.root) == original


@pytest.mark.parametrize("stage", ["failed", "blocked"])
def test_exception_states_are_terminal_and_cannot_be_cleaned(safety, stage):
    lock_id = str(safety.begin().lock_id)
    safety.advance(lock_id, "prepare", stage)
    for action in [safety.check_startup, lambda: safety.advance(lock_id, stage, "completed", confirmed=True), lambda: safety.cleanup(lock_id, confirmed=True)]:
        with pytest.raises(MaintenanceBlocked):
            action()


def test_completion_needs_explicit_confirmation(safety):
    lock_id = str(safety.begin().lock_id)
    safety.advance(lock_id, "prepare", "verified")
    safety.advance(lock_id, "verified", "switching")
    safety.advance(lock_id, "switching", "verifying")
    with pytest.raises(MaintenanceBlocked):
        safety.advance(lock_id, "verifying", "completed")
    assert safety.inspect().stage == "verifying"


@pytest.mark.parametrize("damage", ["json", "unknown_stage", "wrong_id", "unknown_operation", "missing_state", "oversized", "partial"])
def test_corrupt_state_fails_closed_without_cleanup(safety, damage):
    record = safety.begin()
    state = safety.root / safety.STATE
    if damage == "json":
        state.write_text("{broken")
    elif damage == "missing_state":
        state.unlink()
    elif damage == "oversized":
        state.write_text("x" * 5000)
    elif damage == "partial":
        (safety.root / "state-aborted.partial").write_text("incomplete")
    else:
        data = json.loads(state.read_text())
        key, value = {"unknown_stage": ("stage", "unknown"), "wrong_id": ("lock_id", str(uuid4())), "unknown_operation": ("operation", "restore")}[damage]
        data[key] = value
        state.write_text(json.dumps(data))
    original = contents(safety.root)
    for action in [safety.inspect, safety.check_startup, lambda: safety.cleanup(str(record.lock_id), confirmed=True)]:
        with pytest.raises(MaintenanceBlocked):
            action()
    assert contents(safety.root) == original


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory", "fifo"])
@pytest.mark.parametrize("name", [MaintenanceSafety.GATE, MaintenanceSafety.LOCK, MaintenanceSafety.STATE])
def test_unsafe_file_types_rejected(safety, tmp_path, kind, name):
    safety.begin()
    path = safety.root / name
    path.unlink()
    outside = tmp_path / "outside"
    outside.write_text("untouched")
    if kind == "symlink":
        path.symlink_to(outside)
    elif kind == "hardlink":
        os.link(outside, path)
    elif kind == "directory":
        path.mkdir()
    else:
        os.mkfifo(path)
    with pytest.raises(MaintenanceBlocked):
        safety.check_startup()
    with pytest.raises(MaintenanceBlocked):
        safety.inspect()
    assert outside.read_text() == "untouched"


def test_symlink_root_rejected(safety, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    safety.root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(MaintenanceBlocked):
        safety.begin()
    with pytest.raises(MaintenanceBlocked):
        safety.check_startup()
    assert not list(outside.iterdir())


def test_usage_lease_blocks_maintenance_and_active_marker_blocks_backend(safety):
    with safety.backend_usage():
        safety.check_startup()
        with pytest.raises(MaintenanceBlocked):
            safety.begin()
    safety.begin()
    with pytest.raises(MaintenanceBlocked), safety.backend_usage():
        pytest.fail("Backend cannot start")


def test_concurrent_begin_has_only_one_owner(safety):
    def attempt(_):
        try:
            return safety.begin()
        except MaintenanceBlocked:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(4)))
    assert sum(record is not None for record in results) == 1
    assert safety.inspect().stage == "prepare"


def test_failed_publication_keeps_blocking_evidence(safety, monkeypatch):
    original = safety._publish
    def fail_state(directory, name, record, *, replace):
        if name == safety.STATE:
            raise OSError("simulated disk failure")
        original(directory, name, record, replace=replace)
    monkeypatch.setattr(safety, "_publish", fail_state)
    with pytest.raises(MaintenanceBlocked):
        safety.begin()
    assert (safety.root / safety.LOCK).exists()
    with pytest.raises(MaintenanceBlocked):
        safety.check_startup()


def test_fsync_failure_retains_partial_and_blocks_startup(safety, monkeypatch):
    with safety.backend_usage():
        pass
    fsync = os.fsync
    calls = 0
    def fail(fd):
        nonlocal calls
        calls += 1
        if calls == 3:  # First state file flush, after coordination file/directory.
            raise OSError("simulated flush failure")
        fsync(fd)
    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(MaintenanceBlocked):
        safety.begin()
    assert list(safety.root.glob("*.partial"))
    with pytest.raises(MaintenanceBlocked):
        safety.check_startup()


@pytest.mark.parametrize("stage", ["prepare", "verified", "switching", "verifying", "failed", "blocked", "idle", "unknown"])
def test_state_alone_blocks_startup_even_when_lock_is_lost(safety, stage):
    safety.begin()
    (safety.root / safety.LOCK).unlink()
    state_path = safety.root / safety.STATE
    state = json.loads(state_path.read_text())
    state["stage"] = stage
    state_path.write_text(json.dumps(state))
    before = contents(safety.root)
    with pytest.raises(MaintenanceBlocked):
        safety.check_startup()
    assert contents(safety.root) == before


def test_platform_missing_fails_closed(safety, monkeypatch):
    monkeypatch.setattr("app.core.maintenance.fcntl", None)
    with pytest.raises(MaintenanceBlocked, match="Linux"):
        safety.check_startup()
    assert not safety.root.exists()


def test_cross_process_usage_lock_releases_on_exit_not_by_pid_guessing(safety):
    code = '''
import os, sys
from pathlib import Path
from app.core.maintenance import MaintenanceSafety
with MaintenanceSafety(Path(sys.argv[1]), "0.8.0").backend_usage():
    print("ready", flush=True)
    sys.stdin.readline()
    os._exit(27)
'''
    child = subprocess.Popen([sys.executable, "-c", code, str(safety.root)], cwd=BACKEND, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # Bounded readiness, never an unbounded read on a failed child.
        import select
        assert select.select([child.stdout], [], [], 10)[0]
        assert child.stdout.readline().strip() == "ready"
        with pytest.raises(MaintenanceBlocked):
            safety.begin()
        child.communicate("exit\n", timeout=10)
        assert child.returncode == 27
        assert safety.begin().stage == "prepare"
    finally:
        if child.poll() is None:
            child.terminate()  # Only this isolated subprocess owned by the test.
            child.communicate(timeout=10)


@pytest.mark.parametrize("stage", ["prepare", "switching", "verifying"])
def test_process_crash_retains_state_and_blocks_next_start(safety, stage):
    code = '''
import os, sys
from pathlib import Path
from app.core.maintenance import MaintenanceSafety
s = MaintenanceSafety(Path(sys.argv[1]), "0.8.0")
r = s.begin()
for old, new in [("prepare", "verified"), ("verified", "switching"), ("switching", "verifying")]:
    if s.inspect().stage == sys.argv[2]: break
    s.advance(str(r.lock_id), old, new)
os._exit(27)
'''
    child = subprocess.run([sys.executable, "-c", code, str(safety.root), stage], cwd=BACKEND, timeout=10)
    assert child.returncode == 27
    assert safety.inspect().stage == stage
    original = contents(safety.root)
    with pytest.raises(MaintenanceBlocked):
        safety.check_startup()
    with pytest.raises(MaintenanceBlocked), safety.backend_usage():
        pytest.fail("Crash must block subsequent startup")
    assert contents(safety.root) == original


def test_backend_lifespan_checks_state_and_holds_lease(safety, tmp_path, monkeypatch):
    settings = Settings(database_path=tmp_path / "never-open.sqlite3", _env_file=None)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    with TestClient(app) as client:
        assert client.get('/healthz').status_code == 200
        with pytest.raises(MaintenanceBlocked):
            safety.begin()
    safety.begin()
    with pytest.raises(MaintenanceBlocked), TestClient(app):
        pytest.fail("Blocked lifespan cannot serve")
    assert not settings.database_path.exists()


@pytest.mark.parametrize("state", ["normal", "maintenance", "pending_without_lock"])
def test_launcher_preflight_allow_and_reject(database_engine, tmp_path, state):
    database = Path(database_engine.url.database)
    safety = MaintenanceSafety(database.parent / "maintenance", "0.8.0")
    if state != "normal":
        safety.begin()
        if state == "pending_without_lock":
            (safety.root / safety.LOCK).unlink()  # Simulate lost marker; state still blocks.
    before = database.read_bytes()
    records = contents(safety.root) if safety.root.exists() else None
    env = {**os.environ, "DAYFLOW_DATABASE_PATH": str(database), "DAYFLOW_ALLOW_NONREAL_DATABASE": "1", "DAYFLOW_STATE_DIR": str(tmp_path / "launcher")}
    result = subprocess.run(["bash", str(PROJECT / "scripts/dayflow-start.sh"), "--check"], env=env, capture_output=True, text=True, timeout=30)
    if state == "normal":
        assert result.returncode == 0, result.stderr
        assert "Maintenance startup check: PASS" in result.stdout
    else:
        assert result.returncode != 0
        assert "维护" in result.stderr
        assert "Database Alembic" not in result.stdout
        assert contents(safety.root) == records
    assert database.read_bytes() == before
    assert not (tmp_path / "launcher/backend.meta").exists()
