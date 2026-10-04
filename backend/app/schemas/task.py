from __future__ import annotations

from datetime import date, datetime, time as time_type, timezone
from enum import StrEnum
from uuid import UUID

from app.core.deadline import deadline_status_at
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.task import DeadlineStatus, Task, TaskPriority, TaskStatus
from app.schemas.project import ProjectSummary


class TaskStatusValue(StrEnum):
    PENDING = TaskStatus.PENDING.value
    COMPLETED = TaskStatus.COMPLETED.value


class TaskStatusFilterValue(StrEnum):
    PENDING = TaskStatus.PENDING.value
    COMPLETED = TaskStatus.COMPLETED.value
    ALL = "all"


class PlannedBucketValue(StrEnum):
    UNSCHEDULED = "unscheduled"
    TODAY = "today"
    PAST = "past"
    FUTURE = "future"


class TaskSortValue(StrEnum):
    DEFAULT = "default"
    PLANNED = "planned"
    DEADLINE = "deadline"
    COMPLETED = "completed"


class PriorityValue(StrEnum):
    LOW = TaskPriority.LOW.value
    NORMAL = TaskPriority.NORMAL.value
    HIGH = TaskPriority.HIGH.value


class DeadlineStatusValue(StrEnum):
    NONE = DeadlineStatus.NONE.value
    UPCOMING = DeadlineStatus.UPCOMING.value
    DUE_TODAY = DeadlineStatus.DUE_TODAY.value
    OVERDUE = DeadlineStatus.OVERDUE.value
    COMPLETED = DeadlineStatus.COMPLETED.value


class ScheduleInput(BaseModel):
    start_time: time_type
    end_time: time_type
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("start_time", "end_time")
    @classmethod
    def schedule_time_must_be_local(cls, value: time_type) -> time_type:
        if value.tzinfo is not None and value.utcoffset() is not None:
            raise ValueError("schedule times must not include a UTC offset")
        return value

    @field_validator("timezone")
    @classmethod
    def timezone_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("timezone must not be blank")
        return value


class DeadlineInput(BaseModel):
    date: date
    time: time_type | None = None
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("time")
    @classmethod
    def deadline_time_must_be_local(cls, value: time_type | None) -> time_type | None:
        if value is not None and value.tzinfo is not None and value.utcoffset() is not None:
            raise ValueError("deadline time must not include a UTC offset")
        return value

    @field_validator("timezone")
    @classmethod
    def deadline_timezone_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("timezone must not be blank")
        return value

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
    priority: PriorityValue = PriorityValue.NORMAL
    category_id: UUID | None = None
    project_id: UUID | None = None
    tag_ids: list[UUID] = Field(default_factory=list)
    schedule: ScheduleInput | None = None
    deadline: DeadlineInput | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("tag_ids")
    @classmethod
    def tag_ids_must_be_unique(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("tag_ids must not contain duplicates")
        return value


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    planned_date: date | None = None
    # A non-optional field with a default still remains absent from
    # ``exclude_unset`` when the client omits it, while explicit JSON null is
    # rejected during request validation.
    priority: PriorityValue = PriorityValue.NORMAL
    category_id: UUID | None = None
    project_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    # ``exclude_unset`` distinguishes omitted schedule from explicit null,
    # which is required to preserve versus clear a time block.
    schedule: ScheduleInput | None = None
    # ``exclude_unset`` distinguishes an omitted Deadline from ``deadline: null``.
    deadline: DeadlineInput | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("tag_ids")
    @classmethod
    def tag_ids_must_be_unique(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("tag_ids must not contain duplicates")
        return value


class TaskVersionRequest(BaseModel):
    version: int = Field(ge=1)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class CategoryUpdate(CategoryCreate):
    pass


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class TagUpdate(TagCreate):
    pass


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    status: TaskStatusValue
    planned_date: date | None
    priority: PriorityValue
    deadline_date: date | None
    deadline_at_utc: datetime | None
    deadline_timezone: str | None
    deadline_status: DeadlineStatusValue
    category: CategoryRead | None
    project_id: str | None = None
    project: ProjectSummary | None = None
    tags: list[TagRead] = Field(default_factory=list)
    start_at_utc: datetime | None
    end_at_utc: datetime | None
    schedule_timezone: str | None
    recurrence_rule_id: str | None
    recurrence_occurrence_date: date | None
    created_at_utc: datetime
    updated_at_utc: datetime
    completed_at_utc: datetime | None
    deleted_at_utc: datetime | None
    version: int

    @classmethod
    def from_task_at(cls, task: Task, generated_at_utc: datetime) -> "TaskRead":
        values = {
            field_name: (
                deadline_status_at(
                    status=task.status,
                    deleted_at_utc=task.deleted_at_utc,
                    deadline_date=task.deadline_date,
                    deadline_at_utc=task.deadline_at_utc,
                    deadline_timezone=task.deadline_timezone,
                    generated_at_utc=generated_at_utc,
                )
                if field_name == "deadline_status"
                else getattr(task, field_name)
            )
            for field_name in cls.model_fields
        }
        return cls.model_validate(values)

    @field_serializer(
        "created_at_utc",
        "updated_at_utc",
        "completed_at_utc",
        "deleted_at_utc",
        "start_at_utc",
        "end_at_utc",
        "deadline_at_utc",
    )
    def serialize_timestamps(self, value: datetime | None) -> str | None:
        return _serialize_utc(value)
