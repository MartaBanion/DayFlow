from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.task import Task, TaskPriority, TaskStatus


class TaskStatusValue(StrEnum):
    PENDING = TaskStatus.PENDING.value
    COMPLETED = TaskStatus.COMPLETED.value


class PriorityValue(StrEnum):
    LOW = TaskPriority.LOW.value
    NORMAL = TaskPriority.NORMAL.value
    HIGH = TaskPriority.HIGH.value


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
    tag_ids: list[UUID] = Field(default_factory=list)

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
    priority: PriorityValue | None = None
    category_id: UUID | None = None
    tag_ids: list[UUID] | None = None

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
    category: CategoryRead | None
    tags: list[TagRead] = Field(default_factory=list)
    created_at_utc: datetime
    updated_at_utc: datetime
    completed_at_utc: datetime | None
    deleted_at_utc: datetime | None
    version: int

    @field_serializer("created_at_utc", "updated_at_utc", "completed_at_utc", "deleted_at_utc")
    def serialize_timestamps(self, value: datetime | None) -> str | None:
        return _serialize_utc(value)
