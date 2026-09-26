from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.task import Task, TaskStatus


class TaskStatusValue(StrEnum):
    PENDING = TaskStatus.PENDING.value
    COMPLETED = TaskStatus.COMPLETED.value


def _serialize_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    planned_date: date | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    planned_date: date | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class TaskVersionRequest(BaseModel):
    version: int = Field(ge=1)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    status: TaskStatusValue
    planned_date: date | None
    created_at_utc: datetime
    updated_at_utc: datetime
    completed_at_utc: datetime | None
    deleted_at_utc: datetime | None
    version: int

    @field_serializer("created_at_utc", "updated_at_utc", "completed_at_utc", "deleted_at_utc")
    def serialize_timestamps(self, value: datetime | None) -> str | None:
        return _serialize_utc(value)
