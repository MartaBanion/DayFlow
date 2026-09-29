from __future__ import annotations

from datetime import date, datetime, time as time_type, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.reminder import ReminderStatus


class ReminderStatusValue(StrEnum):
    PENDING = ReminderStatus.PENDING.value
    ACKNOWLEDGED = ReminderStatus.ACKNOWLEDGED.value
    DISMISSED = ReminderStatus.DISMISSED.value


class ReminderCreate(BaseModel):
    date: date
    time: time_type
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("time")
    @classmethod
    def time_is_local(cls, value: time_type) -> time_type:
        if value.tzinfo is not None and value.utcoffset() is not None:
            raise ValueError("Reminder time must not include a UTC offset")
        return value

    @field_validator("timezone")
    @classmethod
    def timezone_is_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("timezone must not be blank")
        return value


class ReminderUpdate(ReminderCreate):
    pass


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    trigger_at_utc: datetime
    reminder_timezone: str
    status: ReminderStatusValue
    acknowledged_at_utc: datetime | None
    dismissed_at_utc: datetime | None
    created_at_utc: datetime
    updated_at_utc: datetime
    version: int

    @field_serializer(
        "trigger_at_utc",
        "acknowledged_at_utc",
        "dismissed_at_utc",
        "created_at_utc",
        "updated_at_utc",
    )
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )


class ReminderVersionRequest(BaseModel):
    version: int = Field(ge=1)
