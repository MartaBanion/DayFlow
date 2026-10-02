from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.backup import BackupRead, BackupVerification


class CurrentDatabaseStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logical_name: str
    app_version: str
    file_size: int = Field(ge=0)
    database_sha256: str
    alembic_version: str | None
    integrity_check: str | None
    foreign_key_errors: int | None
    structure_valid: bool
    readable: bool
    wal_present: bool
    shm_present: bool


class RestorePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_version: Literal[1] = 1
    command: Literal["restore --dry-run"] = "restore --dry-run"
    dry_run: Literal[True] = True
    status: Literal["ready", "rejected"]
    current_database: CurrentDatabaseStatus
    target_backup: BackupRead | None
    target_verification: BackupVerification | None
    schema_compatible: bool
    steps: list[str]
    refusal_reasons: list[str] = Field(default_factory=list)
    changes_performed: Literal[False] = False
    lock_created: Literal[False] = False
    database_write_performed: Literal[False] = False
