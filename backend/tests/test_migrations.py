from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_clean_database_can_upgrade_and_downgrade(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert "tasks" in inspect(engine).get_table_names()
    engine.dispose()

    command.downgrade(config, "base")
    engine = create_engine(database_url)
    assert "tasks" not in inspect(engine).get_table_names()
    engine.dispose()


def test_sqlite_foreign_keys_are_enabled(database_engine) -> None:
    with database_engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_v01_data_is_preserved_by_v02_upgrade(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'v01-copy.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "0001_create_tasks")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tasks "
                "(id, title, description, status, planned_date, created_at_utc, "
                "updated_at_utc, completed_at_utc, deleted_at_utc, version) "
                "VALUES (:id, :title, :description, :status, :planned_date, "
                ":created_at, :updated_at, :completed_at, :deleted_at, :version)"
            ),
            [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "title": "Existing active task",
                    "description": None,
                    "status": "pending",
                    "planned_date": "2026-09-26",
                    "created_at": "2026-09-26T00:00:00.000000Z",
                    "updated_at": "2026-09-26T00:00:00.000000Z",
                    "completed_at": None,
                    "deleted_at": None,
                    "version": 4,
                },
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "title": "Existing deleted task",
                    "description": "Keep this row",
                    "status": "completed",
                    "planned_date": None,
                    "created_at": "2026-09-26T00:00:00.000000Z",
                    "updated_at": "2026-09-26T00:00:00.000000Z",
                    "completed_at": "2026-09-26T01:00:00.000000Z",
                    "deleted_at": "2026-09-26T02:00:00.000000Z",
                    "version": 2,
                },
            ],
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0002_add_priority_categories_tags"
        )
        rows = connection.execute(
            text(
                "SELECT id, status, planned_date, completed_at_utc, deleted_at_utc, "
                "version, priority, category_id "
                "FROM tasks ORDER BY id"
            )
        ).all()
        assert len(rows) == 2
        assert [row[0] for row in rows] == [
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        ]
        assert [row[1] for row in rows] == ["pending", "completed"]
        assert rows[0][2] == "2026-09-26"
        assert rows[1][2] is None
        assert rows[0][3] is None
        assert rows[1][3] == "2026-09-26T01:00:00.000000Z"
        assert rows[0][4] is None
        assert rows[1][4] == "2026-09-26T02:00:00.000000Z"
        assert [row[5] for row in rows] == [4, 2]
        assert [row[6] for row in rows] == ["normal", "normal"]
        assert [row[7] for row in rows] == [None, None]
        assert connection.execute(text("SELECT COUNT(*) FROM tasks WHERE deleted_at_utc IS NULL")).scalar() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM tasks WHERE deleted_at_utc IS NOT NULL")).scalar() == 1
    engine.dispose()
