from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID
from datetime import datetime


class BackupManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    backup_version: Literal[1] = 1
    backup_id: str
    filename: str
    created_at_utc: str
    app_version: str = Field(min_length=1, max_length=32)
    alembic_version: str = Field(min_length=1, max_length=128)
    database_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_size: int = Field(gt=0)
    integrity_check: Literal["ok"]
    foreign_key_errors: Literal[0]
    verified_at_utc: str
    source_database: str = Field(pattern=r"^[A-Za-z0-9_.-]+$", max_length=255)

    @field_validator("backup_id")
    @classmethod
    def canonical_id(cls, value: str) -> str:
        if str(UUID(value)) != value or UUID(value).version != 4:
            raise ValueError("Expected canonical UUID4")
        return value

    @field_validator("created_at_utc", "verified_at_utc")
    @classmethod
    def utc_timestamp(cls, value: str) -> str:
        import re
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value):
            raise ValueError("Expected UTC RFC3339 timestamp")
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value


class BackupRead(BackupManifest):
    # List compatibility reflects recorded metadata, not a fresh integrity scan.
    compatible_for_restore: bool


class BackupVerification(BaseModel):
    backup_id: str
    verified_at_utc: str
    status: Literal["valid", "incompatible", "corrupted", "unreadable", "manifest_mismatch"]
    compatible_for_restore: bool = False
    database_sha256: str | None = None
    file_size: int | None = None
    alembic_version: str | None = None
    integrity_check: str | None = None
    foreign_key_errors: int | None = None
    structure_valid: bool = False
    issues: list[str] = Field(default_factory=list)
