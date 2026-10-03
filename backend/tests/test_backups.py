from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.api.routes.backups import backup_service
from app.core.config import Settings
from app.core.errors import AppError
from app.main import app
from app.services.backup_service import BackupService, SCHEMA


@pytest.fixture
def backups(database_engine: Engine, tmp_path: Path) -> BackupService:
    return BackupService(Path(database_engine.url.database), tmp_path / "backups", "0.6.0")


@pytest.fixture
def backup_client(client: TestClient, backups: BackupService):
    # Backup does not use db_session: explicitly isolate its own source dependency.
    app.dependency_overrides[backup_service] = lambda: backups
    yield client


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(service: BackupService, metadata):
    database = service.root / metadata.filename
    return database, database.with_name(database.name + ".json")


def test_create_metadata_and_read_only_verify(backups: BackupService):
    baseline = sha(backups.source)
    item = backups.create()
    db, manifest = files(backups, item)
    before = {path: (sha(path), path.stat().st_mtime_ns) for path in (db, manifest)}
    assert item.backup_version == 1
    assert item.database_sha256 == sha(db)
    assert item.file_size == db.stat().st_size
    assert item.app_version == "0.6.0"
    assert item.source_database == backups.source.name
    assert item.alembic_version == SCHEMA
    assert item.integrity_check == "ok" and item.foreign_key_errors == 0
    assert item.created_at_utc.endswith("Z") and item.verified_at_utc.endswith("Z")
    assert not json.loads(manifest.read_text()).get("source_path")
    result = backups.verify(item.backup_id)
    assert result.status == "valid" and result.compatible_for_restore
    assert result.structure_valid
    assert result.verified_at_utc >= item.verified_at_utc
    assert before == {path: (sha(path), path.stat().st_mtime_ns) for path in (db, manifest)}
    assert sha(backups.source) == baseline
    assert [entry.backup_id for entry in backups.list()] == [item.backup_id]


def test_wal_committed_and_uncommitted_data(backups: BackupService):
    with closing(sqlite3.connect(backups.source)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO categories(id,name) VALUES('committed','committed')")
        writer.commit()
        assert Path(str(backups.source) + "-wal").stat().st_size > 0
        writer.execute("INSERT INTO categories(id,name) VALUES('uncommitted','uncommitted')")
        item = backups.create()
        with closing(sqlite3.connect(f"file:{backups.root / item.filename}?mode=ro", uri=True)) as snapshot:
            assert snapshot.execute("SELECT id FROM categories").fetchall() == [("committed",)]
        writer.rollback()


def test_concurrent_create_no_overwrite(backups: BackupService):
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(lambda _: backups.create(), range(3)))
    assert len({entry.filename for entry in results}) == 3
    assert len({entry.backup_id for entry in results}) == 3
    for entry in results:
        assert backups.verify(entry.backup_id).status == "valid"
    assert len(backups.list()) == 3


def test_list_ignores_incomplete_unknown_invalid_orphans(backups: BackupService, monkeypatch):
    item = backups.create()
    db, manifest = files(backups, item)
    (backups.root / "unknown.sqlite3").write_bytes(b"unknown")
    (backups.root / (item.filename + ".partial")).write_bytes(b"partial")
    (backups.root / (item.filename.replace("dayflow", "other") + ".json")).write_text(manifest.read_text())
    orphan = backups.create()
    files(backups, orphan)[1].unlink()
    broken = backups.create()
    files(backups, broken)[1].write_text("not json")
    monkeypatch.setattr(backups, "_inspect", lambda *args: pytest.fail("List must not Verify"))
    assert [entry.backup_id for entry in backups.list()] == [item.backup_id]
    assert db.exists()


def test_newest_first_and_stable_tie(backups: BackupService):
    a, b = backups.create(), backups.create()
    assert [entry.backup_id for entry in backups.list()] == [b.backup_id, a.backup_id]
    for item in (a, b):
        _, manifest = files(backups, item)
        data = json.loads(manifest.read_text())
        data["created_at_utc"] = "2026-01-01T00:00:00Z"
        manifest.write_text(json.dumps(data))
    assert [entry.backup_id for entry in backups.list()] == sorted([a.backup_id, b.backup_id], reverse=True)


@pytest.mark.parametrize("field,value", [
    ("database_sha256", "0" * 64), ("file_size", 1), ("alembic_version", "unknown")
])
def test_manifest_mismatch(backups: BackupService, field, value):
    item = backups.create()
    db, manifest = files(backups, item)
    data = json.loads(manifest.read_text())
    data[field] = value
    manifest.write_text(json.dumps(data))
    before = sha(manifest), sha(db)
    result = backups.verify(item.backup_id)
    assert result.status == "manifest_mismatch" and not result.compatible_for_restore
    assert before == (sha(manifest), sha(db))


@pytest.mark.parametrize("version", ["0004_add_projects", "unknown", "0006_future"])
def test_incompatible_versions(backups: BackupService, version):
    item = backups.create()
    db, manifest = files(backups, item)
    with closing(sqlite3.connect(db)) as connection:
        connection.execute("UPDATE alembic_version SET version_num=?", (version,))
        connection.commit()
    data = json.loads(manifest.read_text())
    data.update(alembic_version=version, database_sha256=sha(db), file_size=db.stat().st_size)
    manifest.write_text(json.dumps(data))
    result = backups.verify(item.backup_id)
    assert result.status == "incompatible" and not result.compatible_for_restore


@pytest.mark.parametrize("mutation", ["corrupt", "missing", "unreadable", "directory", "symlink", "hardlink", "wal", "structure", "fk", "index"])
def test_invalid_files(backups: BackupService, tmp_path, mutation):
    item = backups.create()
    db, _ = files(backups, item)
    if mutation == "corrupt":
        db.write_bytes(b"not sqlite")
    elif mutation == "missing":
        db.unlink()
    elif mutation == "unreadable":
        db.chmod(0)
    elif mutation == "directory":
        db.unlink()
        db.mkdir()
    elif mutation in ("symlink", "hardlink"):
        outside = tmp_path / "outside.sqlite3"
        db.rename(outside)
        if mutation == "symlink":
            db.symlink_to(outside)
        else:
            os.link(outside, db)
    elif mutation == "wal":
        Path(str(db) + "-wal").write_bytes(b"unsafe")
    else:
        with closing(sqlite3.connect(db)) as connection:
            if mutation == "structure":
                connection.execute("DROP TABLE reminders")
            elif mutation == "index":
                connection.execute("DROP INDEX uq_tasks_recurrence_occurrence")
            else:
                connection.execute("INSERT INTO task_tags VALUES('missing-task','missing-tag')")
            connection.commit()
    result = backups.verify(item.backup_id)
    assert not result.compatible_for_restore
    assert result.status in ("corrupted", "unreadable")


@pytest.mark.parametrize("value", ["../x", "/tmp/x", "%2e%2e", "x\\y", "", str(uuid4()).upper(), "not-a-uuid"])
def test_invalid_identifier(backups: BackupService, value):
    with pytest.raises(AppError) as error:
        backups.verify(value)
    assert error.value.code == "backup_id_invalid"


def test_root_symlink_and_canonical_boundary(backups: BackupService, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    backups.root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(AppError, match="Unsafe Backup root"):
        backups.create()
    assert not list(outside.iterdir())
    with pytest.raises(AppError):
        BackupService(backups.source, tmp_path / "outside" / ".." / "escape", "0.6.0").create()


def test_manifest_publication_failure_preserves_orphan(backups: BackupService, monkeypatch):
    publish = backups._publish
    def fail(root_fd, temporary, final, **kwargs):
        if final.endswith(".json"):
            raise OSError("simulated manifest publication failure")
        publish(root_fd, temporary, final, **kwargs)
    monkeypatch.setattr(backups, "_publish", fail)
    with pytest.raises(AppError) as error:
        backups.create()
    assert error.value.code == "backup_registration_failed"
    assert "may exist" in error.value.message
    assert len(list(backups.root.glob("*.sqlite3"))) == 1
    assert backups.list() == []


def test_publish_never_overwrites(backups: BackupService):
    with backups._root(create=True) as root_fd:
        (backups.root / "source.partial").write_bytes(b"new")
        (backups.root / "existing.sqlite3").write_bytes(b"old")
        with pytest.raises(FileExistsError):
            backups._publish(root_fd, "source.partial", "existing.sqlite3")
    assert (backups.root / "existing.sqlite3").read_bytes() == b"old"


def test_timeout_does_not_register(backups: BackupService):
    backups.timeout = 0
    with pytest.raises(AppError) as error:
        backups.create()
    assert error.value.code == "backup_timeout"
    assert backups.list() == []


def test_source_missing_is_not_created(backups: BackupService):
    backups.source = backups.source.with_name("missing.sqlite3")
    with pytest.raises(AppError):
        backups.create()
    assert not backups.source.exists() and backups.list() == []


def test_list_missing_root_is_pure_read(backups: BackupService):
    assert backups.list() == []
    assert not backups.root.exists()


@pytest.mark.parametrize("origin,expected", [
    (None, 201), ("http://localhost:5173", 201), ("http://127.0.0.1:5173", 201),
    ("https://evil.example", 403), ("null", 403), ("http://localhost:9999", 403),
    ("http://localhost:5173.evil.example", 403),
])
def test_api_origin(backup_client, backups, origin, expected):
    headers = {"Origin": origin} if origin is not None else {}
    response = backup_client.post("/api/v1/backups", headers=headers)
    assert response.status_code == expected
    if expected == 403:
        assert response.json()["error"]["code"] == "backup_origin_rejected"
        assert not backups.root.exists()
    else:
        backup_id = response.json()["backup_id"]
        assert backup_client.get("/api/v1/backups").json()[0]["backup_id"] == backup_id
        assert backup_client.post(f"/api/v1/backups/{backup_id}/verify").json()["status"] == "valid"
        assert backup_client.post(f"/api/v1/backups/{backup_id}/verify", headers={"Origin": "null"}).status_code == 403


def test_api_rejects_paths_and_body(backup_client, backups):
    assert backup_client.post("/api/v1/backups", json={"source": "/tmp/anything"}).status_code == 422
    assert backup_client.post("/api/v1/backups?filename=x").status_code == 422
    assert backup_client.post("/api/v1/backups/invalid/verify").status_code == 422
    assert backup_client.post(f"/api/v1/backups/{uuid4()}/verify").status_code == 404
    assert not backups.root.exists()


def test_settings_derive_isolated_backup_root(tmp_path):
    settings = Settings(database_path=tmp_path / "database.sqlite3", _env_file=None)
    assert settings.backup_root == tmp_path / "backups"


@pytest.mark.parametrize("failure", [PermissionError(13, "denied"), OSError(28, "disk full")])
def test_creation_io_failure_no_registration(backups, monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(backups, "_publish", fail)
    with pytest.raises(AppError) as error:
        backups.create()
    assert error.value.code in ("backup_permission_denied", "backup_io_failed")
    assert backups.list() == []


def test_source_connection_is_read_only(backups, monkeypatch):
    connect = sqlite3.connect
    observed = []
    def probe(database, *args, **kwargs):
        connection = connect(database, *args, **kwargs)
        if str(backups.source) in str(database):
            observed.append(database)
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                connection.execute("INSERT INTO categories VALUES('forbidden','forbidden')")
        return connection
    monkeypatch.setattr(sqlite3, "connect", probe)
    backups.create()
    assert observed and all("mode=ro" in str(uri) for uri in observed)


def test_committed_concurrent_writes_are_consistent(backups):
    with closing(sqlite3.connect(backups.source)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    def write():
        with closing(sqlite3.connect(backups.source)) as connection:
            for i in range(20):
                connection.execute("INSERT INTO categories VALUES(?,?)", (str(i), str(i)))
                connection.execute("INSERT INTO tags VALUES(?,?)", (str(i), str(i)))
                connection.commit()
    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(write)
        item = backups.create()
        writer.result()
    with closing(sqlite3.connect(backups.root / item.filename)) as snapshot:
        assert snapshot.execute("SELECT COUNT(*) FROM categories").fetchone() == snapshot.execute("SELECT COUNT(*) FROM tags").fetchone()
    assert backups.verify(item.backup_id).status == "valid"


def test_exclusive_lock_times_out(backups):
    backups.timeout = 0.05
    with closing(sqlite3.connect(backups.source)) as writer:
        writer.execute("BEGIN EXCLUSIVE")
        with pytest.raises(AppError) as error:
            backups.create()
        assert error.value.code == "backup_timeout"
        writer.rollback()
    assert backups.list() == []


@pytest.mark.parametrize("field,value", [("filename", "../../escape.sqlite3"), ("created_at_utc", "invalid"), ("secret", "must-not-be-accepted")])
def test_bad_manifest_is_skipped(backups, field, value):
    item = backups.create()
    _, manifest = files(backups, item)
    data = json.loads(manifest.read_text())
    data[field] = value
    manifest.write_text(json.dumps(data))
    assert backups.list() == []
    with pytest.raises(AppError) as error:
        backups.verify(item.backup_id)
    assert error.value.code == "backup_not_found"


def test_missing_required_table_and_sidecars_never_modified(backups):
    item = backups.create()
    db, _ = files(backups, item)
    wal = Path(str(db) + "-wal")
    wal.write_bytes(b"diagnostic material")
    before = sha(db), sha(wal)
    assert backups.verify(item.backup_id).status == "unreadable"
    assert before == (sha(db), sha(wal))


def test_verify_many_readers(backups):
    item = backups.create()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: backups.verify(item.backup_id), range(8)))
    assert all(result.status == "valid" for result in results)


def test_manifest_fsync_failure_does_not_register(backups, monkeypatch):
    fsync = os.fsync
    calls = 0
    def fail(fd):
        nonlocal calls
        calls += 1
        if calls == 4:  # DB file, DB directory, Manifest file, Manifest directory.
            raise OSError(28, "simulated directory fsync failure")
        fsync(fd)
    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(AppError) as error:
        backups.create()
    assert error.value.code == "backup_registration_failed"
    assert len(list(backups.root.glob("*.sqlite3"))) == 1
    assert backups.list() == []


def test_actual_old_schema_is_incompatible(backups, tmp_path):
    from alembic import command
    from alembic.config import Config
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    old = tmp_path / "old.sqlite3"
    config.attributes["database_url"] = "sqlite:///" + str(old)
    command.upgrade(config, "0004_add_projects")
    item = backups.create()
    db, manifest = files(backups, item)
    db.write_bytes(old.read_bytes())  # Offline isolated fixture, never Backup algorithm.
    data = json.loads(manifest.read_text())
    data.update(database_sha256=sha(db), file_size=db.stat().st_size, alembic_version="0004_add_projects")
    manifest.write_text(json.dumps(data))
    result = backups.verify(item.backup_id)
    assert result.status == "incompatible" and not result.compatible_for_restore


def test_create_incompatible_source_rejected(backups):
    with closing(sqlite3.connect(backups.source)) as source:
        source.execute("UPDATE alembic_version SET version_num='unknown'")
        source.commit()
    with pytest.raises(AppError) as error:
        backups.create()
    assert error.value.code == "backup_schema_incompatible"
    assert backups.list() == []


def test_verify_sqlite_uses_the_hashed_inode(backup_client, backups, monkeypatch):
    item = backups.create()
    db, _ = files(backups, item)
    connect = sqlite3.connect
    saved = backups.root / "original.saved"
    def swap(database, *args, **kwargs):
        if "immutable=1" not in str(database):
            return connect(database, *args, **kwargs)
        db.rename(saved)
        with closing(connect(db)) as replacement:
            replacement.execute("CREATE TABLE replacement_only(x)")
        connection = connect(database, *args, **kwargs)
        # A fresh name-based open would inspect the replacement table instead.
        assert connection.execute("SELECT COUNT(*) FROM tasks").fetchone() == (0,)
        db.unlink()
        saved.rename(db)
        return connection
    monkeypatch.setattr(sqlite3, "connect", swap)
    response = backup_client.post(f"/api/v1/backups/{item.backup_id}/verify")
    assert response.status_code == 200
    assert not response.json()["compatible_for_restore"]  # Rename changed ctime.


def test_create_target_substitution_cannot_write_outside(backup_client, backups, tmp_path, monkeypatch):
    outside = tmp_path / "outside.sqlite3"
    outside.write_bytes(b"outside sentinel")
    connect = sqlite3.connect
    def swap(database, *args, **kwargs):
        if str(database).startswith("file:/proc/self/fd/") and "mode=rw" in str(database):
            temporary = next(backups.root.glob("*.sqlite3.partial"))
            temporary.rename(backups.root / "target.saved")
            temporary.symlink_to(outside)
        return connect(database, *args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", swap)
    response = backup_client.post("/api/v1/backups")
    assert response.status_code != 201
    assert outside.read_bytes() == b"outside sentinel"
    assert backups.list() == []


def test_publish_substitution_fails_without_external_inode(backup_client, backups, tmp_path, monkeypatch):
    outside = tmp_path / "outside.sqlite3"
    outside.write_bytes(b"outside sentinel")
    link = os.link
    def swap(source, destination, **kwargs):
        if str(destination).endswith(".sqlite3"):
            temporary = next(backups.root.glob("*.sqlite3.partial"))
            temporary.rename(backups.root / "verified.saved")
            temporary.symlink_to(outside)
        return link(source, destination, **kwargs)
    monkeypatch.setattr(os, "link", swap)
    response = backup_client.post("/api/v1/backups")
    assert response.status_code != 201
    assert backups.list() == []
    assert outside.read_bytes() == b"outside sentinel"
    final = next(backups.root.glob("*.sqlite3"))
    assert not final.is_symlink()
    with closing(sqlite3.connect(final)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tasks").fetchone() == (0,)


def test_fifo_is_unreadable_without_blocking(backup_client, backups):
    item = backups.create()
    db, _ = files(backups, item)
    db.unlink()
    os.mkfifo(db)
    response = backup_client.post(f"/api/v1/backups/{item.backup_id}/verify")
    assert response.status_code == 200 and response.json()["status"] == "unreadable"
    assert backup_client.get("/api/v1/backups").json() == []


def test_platform_unavailable_fails_closed(backup_client, backups, monkeypatch):
    is_dir = Path.is_dir
    monkeypatch.setattr(Path, "is_dir", lambda path: False if str(path) == "/proc/self/fd" else is_dir(path))
    response = backup_client.post("/api/v1/backups")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "backup_platform_unsupported"
    assert not backups.root.exists()


def test_alembic_table_without_pk_is_not_compatible(backup_client, backups):
    item = backups.create()
    db, _ = files(backups, item)
    with closing(sqlite3.connect(db)) as connection:
        connection.execute("DROP TABLE alembic_version")
        connection.execute("CREATE TABLE alembic_version(version_num VARCHAR(128) NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES(?)", (SCHEMA,))
        connection.commit()
    response = backup_client.post(f"/api/v1/backups/{item.backup_id}/verify")
    assert response.status_code == 200 and response.json()["status"] == "corrupted"
    assert not response.json()["structure_valid"]


def test_list_orders_fractional_timestamps_by_instant(backups):
    earlier, later = backups.create(), backups.create()
    for item, date in ((earlier, "2026-01-01T00:00:00Z"), (later, "2026-01-01T00:00:00.500000Z")):
        _, manifest = files(backups, item)
        data = json.loads(manifest.read_text())
        data["created_at_utc"] = date
        manifest.write_text(json.dumps(data))
    assert [item.backup_id for item in backups.list()] == [later.backup_id, earlier.backup_id]
