from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


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

    command.upgrade(config, "0002_add_priority_categories_tags")
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


def test_v02_data_is_preserved_by_schedule_upgrade(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'v02-copy.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "0002_add_priority_categories_tags")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tasks "
                "(id, title, description, status, planned_date, priority, category_id, "
                "created_at_utc, updated_at_utc, completed_at_utc, deleted_at_utc, version) "
                "VALUES (:id, :title, :description, :status, :planned_date, :priority, "
                ":category_id, :created_at, :updated_at, :completed_at, :deleted_at, :version)"
            ),
            {
                "id": "00000000-0000-0000-0000-000000000003",
                "title": "Existing V0.2 task",
                "description": "Keep all V0.2 fields",
                "status": "pending",
                "planned_date": "2026-09-26",
                "priority": "high",
                "category_id": None,
                "created_at": "2026-09-26T00:00:00.000000Z",
                "updated_at": "2026-09-26T00:00:00.000000Z",
                "completed_at": None,
                "deleted_at": None,
                "version": 7,
            },
        )
    engine.dispose()

    command.upgrade(config, "0003_add_task_schedule")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0003_add_task_schedule"
        )
        columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
        assert {"start_at_utc", "end_at_utc", "schedule_timezone"} <= columns
        row = connection.execute(
            text(
                "SELECT id, title, description, status, planned_date, priority, "
                "category_id, completed_at_utc, deleted_at_utc, version, "
                "start_at_utc, end_at_utc, schedule_timezone "
                "FROM tasks"
            )
        ).one()
        assert row[:10] == (
            "00000000-0000-0000-0000-000000000003",
            "Existing V0.2 task",
            "Keep all V0.2 fields",
            "pending",
            "2026-09-26",
            "high",
            None,
            None,
            None,
            7,
        )
        assert row[10:] == (None, None, None)
    engine.dispose()


def test_schedule_downgrade_fails_closed_when_data_exists(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'scheduled-downgrade.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tasks "
                "(id, title, description, status, planned_date, priority, category_id, "
                "start_at_utc, end_at_utc, schedule_timezone, created_at_utc, "
                "updated_at_utc, completed_at_utc, deleted_at_utc, version) "
                "VALUES (:id, :title, :description, :status, :planned_date, :priority, "
                ":category_id, :start_at, :end_at, :timezone, :created_at, :updated_at, "
                ":completed_at, :deleted_at, :version)"
            ),
            {
                "id": "00000000-0000-0000-0000-000000000004",
                "title": "Scheduled task",
                "description": None,
                "status": "pending",
                "planned_date": "2026-09-26",
                "priority": "normal",
                "category_id": None,
                "start_at": "2026-09-26T06:00:00.000000Z",
                "end_at": "2026-09-26T07:00:00.000000Z",
                "timezone": "Asia/Shanghai",
                "created_at": "2026-09-26T00:00:00.000000Z",
                "updated_at": "2026-09-26T00:00:00.000000Z",
                "completed_at": None,
                "deleted_at": None,
                "version": 1,
            },
        )
    engine.dispose()

    with pytest.raises(RuntimeError, match="scheduled tasks exist"):
        command.downgrade(config, "0002_add_priority_categories_tags")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0003_add_task_schedule"
        )
        assert "start_at_utc" in {column["name"] for column in inspect(engine).get_columns("tasks")}
    engine.dispose()


def test_schedule_empty_downgrade_and_upgrade_round_trip(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'schedule-round-trip.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "0003_add_task_schedule")

    command.downgrade(config, "0002_add_priority_categories_tags")
    command.upgrade(config, "0003_add_task_schedule")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0003_add_task_schedule"
        )
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()


def test_schedule_constraints_exist_and_reject_partial_rows(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'schedule-constraints.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "0003_add_task_schedule")
    engine = create_engine(database_url)

    constraint_names = {
        constraint["name"]
        for constraint in inspect(engine).get_check_constraints("tasks")
    }
    assert {
        "ck_tasks_schedule_complete",
        "ck_tasks_schedule_requires_date",
    } <= constraint_names

    values = {
        "id": "00000000-0000-0000-0000-000000000005",
        "title": "Invalid partial schedule",
        "status": "pending",
        "planned_date": "2026-09-26",
        "priority": "normal",
        "created_at": "2026-09-26T00:00:00.000000Z",
        "updated_at": "2026-09-26T00:00:00.000000Z",
        "version": 1,
        "start_at": "2026-09-26T06:00:00.000000Z",
    }
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tasks "
                    "(id, title, status, planned_date, priority, created_at_utc, "
                    "updated_at_utc, version, start_at_utc) VALUES (:id, :title, :status, "
                    ":planned_date, :priority, :created_at, :updated_at, :version, :start_at)"
                ),
                values,
            )

    values["id"] = "00000000-0000-0000-0000-000000000006"
    values["planned_date"] = None
    values["end_at"] = "2026-09-26T07:00:00.000000Z"
    values["timezone"] = "Asia/Shanghai"
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tasks "
                    "(id, title, status, planned_date, priority, created_at_utc, "
                    "updated_at_utc, version, start_at_utc, end_at_utc, schedule_timezone) "
                    "VALUES (:id, :title, :status, :planned_date, :priority, :created_at, "
                    ":updated_at, :version, :start_at, :end_at, :timezone)"
                ),
                values,
            )

    engine.dispose()


def test_v03_data_is_preserved_by_project_upgrade(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'v03-project-copy.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "0003_add_task_schedule")

    task_id = "00000000-0000-0000-0000-000000000101"
    category_id = "00000000-0000-0000-0000-000000000102"
    tag_id = "00000000-0000-0000-0000-000000000103"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text("INSERT INTO categories (id, name) VALUES (:id, :name)"),
            {"id": category_id, "name": "Existing category"},
        )
        connection.execute(
            text("INSERT INTO tags (id, name) VALUES (:id, :name)"),
            {"id": tag_id, "name": "existing-tag"},
        )
        connection.execute(
            text(
                "INSERT INTO tasks ("
                "id, title, description, status, planned_date, priority, category_id, "
                "start_at_utc, end_at_utc, schedule_timezone, created_at_utc, "
                "updated_at_utc, completed_at_utc, deleted_at_utc, version"
                ") VALUES ("
                ":id, :title, :description, :status, :planned_date, :priority, :category_id, "
                ":start_at, :end_at, :timezone, :created_at, :updated_at, :completed_at, "
                ":deleted_at, :version"
                ")"
            ),
            {
                "id": task_id,
                "title": "Existing scheduled task",
                "description": "Keep every V0.3 field",
                "status": "completed",
                "planned_date": "2026-09-26",
                "priority": "high",
                "category_id": category_id,
                "start_at": "2026-09-26T06:00:00.000000Z",
                "end_at": "2026-09-26T07:30:00.000000Z",
                "timezone": "Asia/Shanghai",
                "created_at": "2026-09-26T00:00:00.000000Z",
                "updated_at": "2026-09-26T01:00:00.000000Z",
                "completed_at": "2026-09-26T02:00:00.000000Z",
                "deleted_at": None,
                "version": 9,
            },
        )
        connection.execute(
            text("INSERT INTO task_tags (task_id, tag_id) VALUES (:task_id, :tag_id)"),
            {"task_id": task_id, "tag_id": tag_id},
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0004_add_projects"
        )
        row = connection.execute(
            text(
                "SELECT id, title, description, status, planned_date, priority, category_id, "
                "start_at_utc, end_at_utc, schedule_timezone, created_at_utc, updated_at_utc, "
                "completed_at_utc, deleted_at_utc, version, project_id "
                "FROM tasks"
            )
        ).one()
        assert row == (
            task_id,
            "Existing scheduled task",
            "Keep every V0.3 field",
            "completed",
            "2026-09-26",
            "high",
            category_id,
            "2026-09-26T06:00:00.000000Z",
            "2026-09-26T07:30:00.000000Z",
            "Asia/Shanghai",
            "2026-09-26T00:00:00.000000Z",
            "2026-09-26T01:00:00.000000Z",
            "2026-09-26T02:00:00.000000Z",
            None,
            9,
            None,
        )
        assert connection.execute(text("SELECT COUNT(*) FROM categories")).scalar() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM tags")).scalar() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM task_tags")).scalar() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM projects")).scalar() == 0

        foreign_keys = inspect(engine).get_foreign_keys("tasks")
        project_foreign_key = next(
            foreign_key
            for foreign_key in foreign_keys
            if foreign_key["referred_table"] == "projects"
        )
        assert project_foreign_key["options"]["ondelete"] == "SET NULL"
        index_names = {index["name"] for index in inspect(engine).get_indexes("projects")}
        assert {"uq_projects_active_name", "ix_projects_deleted_status"} <= index_names
    engine.dispose()


def test_project_downgrade_fails_closed_when_project_data_exists(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'project-downgrade.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO projects (id, name, created_at_utc, updated_at_utc, version) "
                "VALUES (:id, :name, :created_at, :updated_at, 1)"
            ),
            {
                "id": "00000000-0000-0000-0000-000000000201",
                "name": "A project",
                "created_at": "2026-09-26T00:00:00.000000Z",
                "updated_at": "2026-09-26T00:00:00.000000Z",
            },
        )
    engine.dispose()

    with pytest.raises(RuntimeError, match="project data or relationships exist"):
        command.downgrade(config, "0003_add_task_schedule")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0004_add_projects"
        )
        assert "project_id" in {column["name"] for column in inspect(engine).get_columns("tasks")}
        assert connection.execute(text("SELECT COUNT(*) FROM projects")).scalar() == 1
    engine.dispose()


def test_project_empty_downgrade_and_upgrade_round_trip(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'project-round-trip.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")

    command.downgrade(config, "0003_add_task_schedule")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert "projects" not in inspect(engine).get_table_names()
        assert "project_id" not in {column["name"] for column in inspect(engine).get_columns("tasks")}
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0004_add_projects"
        )
    engine.dispose()


def test_project_downgrade_preserves_existing_task_tags(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'project-tag-round-trip.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")

    task_id = "00000000-0000-0000-0000-000000000401"
    tag_id = "00000000-0000-0000-0000-000000000402"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text("INSERT INTO tags (id, name) VALUES (:id, :name)"),
            {"id": tag_id, "name": "keep-on-downgrade"},
        )
        connection.execute(
            text(
                "INSERT INTO tasks (id, title, status, planned_date, priority, "
                "created_at_utc, updated_at_utc, version) VALUES (:id, :title, "
                ":status, :planned_date, :priority, :created_at, :updated_at, :version)"
            ),
            {
                "id": task_id,
                "title": "Task with tag",
                "status": "pending",
                "planned_date": None,
                "priority": "normal",
                "created_at": "2026-09-26T00:00:00.000000Z",
                "updated_at": "2026-09-26T00:00:00.000000Z",
                "version": 1,
            },
        )
        connection.execute(
            text("INSERT INTO task_tags (task_id, tag_id) VALUES (:task_id, :tag_id)"),
            {"task_id": task_id, "tag_id": tag_id},
        )
    engine.dispose()

    command.downgrade(config, "0003_add_task_schedule")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM task_tags")).scalar() == 1
        assert connection.execute(
            text("SELECT task_id, tag_id FROM task_tags")
        ).one() == (task_id, tag_id)
    engine.dispose()


def test_project_constraints_reject_invalid_rows(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'project-constraints.sqlite3'}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    engine = create_engine(database_url)

    constraint_names = {
        constraint["name"]
        for constraint in inspect(engine).get_check_constraints("projects")
    }
    assert {"ck_projects_status", "ck_projects_version_positive"} <= constraint_names

    base_values = {
        "id": "00000000-0000-0000-0000-000000000301",
        "name": "Invalid project",
        "created_at": "2026-09-26T00:00:00.000000Z",
        "updated_at": "2026-09-26T00:00:00.000000Z",
    }
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO projects (id, name, status, created_at_utc, updated_at_utc, version) "
                    "VALUES (:id, :name, 'paused', :created_at, :updated_at, 1)"
                ),
                base_values,
            )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO projects (id, name, status, created_at_utc, updated_at_utc, version) "
                    "VALUES (:id, :name, 'active', :created_at, :updated_at, 0)"
                ),
                {**base_values, "id": "00000000-0000-0000-0000-000000000302"},
            )
    engine.dispose()
