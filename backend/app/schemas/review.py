from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field, field_serializer

from app.schemas.project import ProjectStatusValue
from app.schemas.task import TaskRead


class ReviewScope(StrEnum):
    TODAY = "today"
    WEEK = "week"


def _serialize_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


class ReviewTaskSection(BaseModel):
    count: int = Field(ge=0)
    tasks: list[TaskRead] = Field(default_factory=list)


class ReviewProject(BaseModel):
    id: str
    name: str
    status: ProjectStatusValue
    task_count: int = Field(ge=0)
    completed_task_count: int = Field(ge=0)
    pending_task_count: int = Field(ge=0)
    overdue_task_count: int = Field(ge=0)
    progress_percent: int = Field(ge=0, le=100)
    latest_completed_at_utc: datetime | None

    @field_serializer("latest_completed_at_utc")
    def serialize_latest_completion(self, value: datetime | None) -> str | None:
        return _serialize_utc(value)


class ReviewRead(BaseModel):
    scope: ReviewScope
    local_timezone: str
    local_date: date
    range_start_utc: datetime
    range_end_utc: datetime
    generated_at_utc: datetime
    completed: ReviewTaskSection
    overdue: ReviewTaskSection
    carryover: ReviewTaskSection
    projects: list[ReviewProject] = Field(default_factory=list)

    @field_serializer("range_start_utc", "range_end_utc", "generated_at_utc")
    def serialize_timestamps(self, value: datetime) -> str:
        serialized = _serialize_utc(value)
        assert serialized is not None
        return serialized
