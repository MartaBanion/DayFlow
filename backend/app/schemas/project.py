from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.project import ProjectStatus


class ProjectStatusValue(StrEnum):
    ACTIVE = ProjectStatus.ACTIVE.value
    COMPLETED = ProjectStatus.COMPLETED.value


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class ProjectUpdate(BaseModel):
    # A non-optional default preserves partial-update semantics while explicit
    # JSON null is rejected as invalid input for the required name field.
    name: str = Field(default="", max_length=200)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: ProjectStatusValue


class ProjectRead(BaseModel):
    id: str
    name: str
    description: str | None
    status: ProjectStatusValue
    created_at_utc: datetime
    updated_at_utc: datetime
    completed_at_utc: datetime | None
    deleted_at_utc: datetime | None
    version: int
    task_count: int = Field(ge=0)
    completed_task_count: int = Field(ge=0)
    progress_percent: int = Field(ge=0, le=100)

    @field_validator(
        "created_at_utc",
        "updated_at_utc",
        "completed_at_utc",
        "deleted_at_utc",
        mode="before",
    )
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_serializer(
        "created_at_utc",
        "updated_at_utc",
        "completed_at_utc",
        "deleted_at_utc",
    )
    def serialize_timestamps(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )


class ProjectVersionRequest(BaseModel):
    version: int = Field(ge=1)
