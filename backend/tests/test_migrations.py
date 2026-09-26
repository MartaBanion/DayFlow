from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


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
