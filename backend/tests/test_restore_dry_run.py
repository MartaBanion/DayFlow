"""Restore dry-run tests; all databases and Backup files are isolated."""

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy.engine import Engine

from app.services.backup_service import BackupService

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def backups(database_engine: Engine, tmp_path: Path) -> BackupService:
    return BackupService(Path(database_engine.url.database), tmp_path / "backups", "0.9.0")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def backup_snapshot(root: Path) -> dict[str, str]:
    return {
        path.name: digest(path)
        for path in sorted(root.iterdir())
        if path.is_file() and not path.is_symlink()
    }


def backup_files(service: BackupService, backup_id: str, filename: str) -> tuple[Path, Path]:
    database = service.root / filename
    return database, database.with_name(database.name + ".json")


def run_cli(source: Path, backup_id: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "DAYFLOW_DATABASE_PATH": str(source)}
    return subprocess.run(
        [sys.executable, "-m", "app.maintenance_cli", "restore", "--dry-run", backup_id, "--json"],
        cwd=BACKEND,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )


def assert_no_safety_state(source: Path) -> None:
    maintenance = source.parent / "maintenance"
    assert not maintenance.exists()


def test_valid_backup_generates_read_only_restore_plan(backups: BackupService):
    before = digest(backups.source)
    item = backups.create()
    target, manifest = backup_files(backups, item.backup_id, item.filename)
    artifacts_before = backup_snapshot(backups.root)
    result = run_cli(backups.source, item.backup_id)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["status"] == "ready"
    assert plan["dry_run"] is True
    assert plan["schema_compatible"] is True
    assert plan["current_database"]["alembic_version"] == "0005_add_deadlines_recurrence_reminders"
    assert plan["target_backup"]["backup_id"] == item.backup_id
    assert plan["target_verification"]["status"] == "valid"
    assert plan["changes_performed"] is False
    assert plan["lock_created"] is False
    assert plan["database_write_performed"] is False
    assert digest(backups.source) == before
    assert backup_snapshot(backups.root) == artifacts_before
    assert digest(target) == item.database_sha256
    assert json.loads(manifest.read_text())["database_sha256"] == item.database_sha256
    assert_no_safety_state(backups.source)
    assert "No changes performed" not in result.stdout  # JSON is the machine-readable mode.


def test_human_output_names_current_target_schema_steps_and_no_changes(backups: BackupService):
    item = backups.create()
    artifacts_before = backup_snapshot(backups.root)
    environment = {**os.environ, "DAYFLOW_DATABASE_PATH": str(backups.source)}
    result = subprocess.run(
        [sys.executable, "-m", "app.maintenance_cli", "restore", "--dry-run", item.backup_id],
        cwd=BACKEND,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0
    assert "当前数据库" in result.stdout
    assert item.filename in result.stdout
    assert "0005_add_deadlines_recurrence_reminders" in result.stdout
    assert "Maintenance lock" in result.stdout
    assert "未知使用者" in result.stdout
    assert "No changes performed." in result.stdout
    assert backup_snapshot(backups.root) == artifacts_before
    assert_no_safety_state(backups.source)


def test_corrupted_backup_is_rejected_without_state_or_database_change(backups: BackupService):
    item = backups.create()
    database, _ = backup_files(backups, item.backup_id, item.filename)
    database.write_bytes(b"not a SQLite database")
    before = digest(backups.source)
    artifacts_before = backup_snapshot(backups.root)
    result = run_cli(backups.source, item.backup_id)
    plan = json.loads(result.stdout)
    assert result.returncode != 0
    assert plan["status"] == "rejected"
    assert plan["target_verification"]["status"] == "corrupted"
    assert plan["schema_compatible"] is False
    assert digest(backups.source) == before
    assert backup_snapshot(backups.root) == artifacts_before
    assert_no_safety_state(backups.source)


def test_incompatible_schema_is_rejected_without_migration(backups: BackupService):
    item = backups.create()
    database, manifest = backup_files(backups, item.backup_id, item.filename)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE alembic_version SET version_num=?", ("0004_add_projects",))
        connection.commit()
    data = json.loads(manifest.read_text())
    data.update(alembic_version="0004_add_projects", database_sha256=digest(database), file_size=database.stat().st_size)
    manifest.write_text(json.dumps(data))
    before = digest(backups.source)
    artifacts_before = backup_snapshot(backups.root)
    result = run_cli(backups.source, item.backup_id)
    plan = json.loads(result.stdout)
    assert result.returncode != 0
    assert plan["target_verification"]["status"] == "incompatible"
    assert plan["schema_compatible"] is False
    assert digest(backups.source) == before
    assert backup_snapshot(backups.root) == artifacts_before
    assert_no_safety_state(backups.source)


def test_manifest_mismatch_is_rejected_without_repair(backups: BackupService):
    item = backups.create()
    _, manifest = backup_files(backups, item.backup_id, item.filename)
    data = json.loads(manifest.read_text())
    data["database_sha256"] = "0" * 64
    manifest.write_text(json.dumps(data))
    manifest_before = digest(manifest)
    before = digest(backups.source)
    artifacts_before = backup_snapshot(backups.root)
    result = run_cli(backups.source, item.backup_id)
    plan = json.loads(result.stdout)
    assert result.returncode != 0
    assert plan["target_verification"]["status"] == "manifest_mismatch"
    assert plan["schema_compatible"] is False
    assert digest(manifest) == manifest_before
    assert digest(backups.source) == before
    assert backup_snapshot(backups.root) == artifacts_before
    assert_no_safety_state(backups.source)


def test_missing_backup_is_rejected_without_registration(backups: BackupService):
    item = backups.create()
    database, manifest = backup_files(backups, item.backup_id, item.filename)
    database.unlink()
    manifest_before = digest(manifest)
    before = digest(backups.source)
    artifacts_before = backup_snapshot(backups.root)
    result = run_cli(backups.source, item.backup_id)
    plan = json.loads(result.stdout)
    assert result.returncode != 0
    assert plan["status"] == "rejected"
    assert plan["schema_compatible"] is False
    assert plan["refusal_reasons"]
    assert digest(manifest) == manifest_before
    assert digest(backups.source) == before
    assert backup_snapshot(backups.root) == artifacts_before
    assert_no_safety_state(backups.source)
