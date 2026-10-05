from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "DayFlow Personal"
    app_version: str = "0.8.0"
    environment: str = Field(default="development", alias="DAYFLOW_ENV")
    database_path: Path = Field(
        default=PROJECT_ROOT / "data" / "dayflow.sqlite3",
        alias="DAYFLOW_DATABASE_PATH",
    )
    timezone: str = Field(default="Asia/Shanghai", alias="DAYFLOW_TIMEZONE")
    frontend_origin: str = Field(
        default="http://localhost:5173", alias="DAYFLOW_FRONTEND_ORIGIN"
    )
    log_level: str = Field(default="INFO", alias="DAYFLOW_LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    @property
    def resolved_database_path(self) -> Path:
        path = self.database_path
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def backup_root(self) -> Path:
        return self.resolved_database_path.parent / "backups"

    @property
    def maintenance_root(self) -> Path:
        return self.resolved_database_path.parent / "maintenance"

    @property
    def database_url(self) -> str:
        database_path = self.database_path
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path
        return f"sqlite:///{database_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
