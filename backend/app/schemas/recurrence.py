from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.models.recurrence import RecurrenceFrequency


class RecurrenceFrequencyValue(StrEnum):
    DAILY = RecurrenceFrequency.DAILY.value
    WEEKLY = RecurrenceFrequency.WEEKLY.value
    MONTHLY = RecurrenceFrequency.MONTHLY.value


def _validate_weekdays(value: list[int] | None) -> list[int] | None:
    if value is None:
        return None
    if len(value) != len(set(value)) or any(day < 0 or day > 6 for day in value):
        raise ValueError("weekdays must contain unique values from 0 through 6")
    return sorted(value)


class RecurrenceCreate(BaseModel):
    version: int = Field(ge=1)
    frequency: RecurrenceFrequencyValue
    starts_on: date
    timezone: str | None = Field(default=None, max_length=64)
    weekdays: list[int] | None = None
    month_day: int | None = Field(default=None, ge=1, le=28)

    @field_validator("weekdays")
    @classmethod
    def weekdays_are_valid(cls, value: list[int] | None) -> list[int] | None:
        return _validate_weekdays(value)

    @field_validator("timezone")
    @classmethod
    def timezone_is_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("timezone must not be blank")
        return value


class RecurrenceUpdate(BaseModel):
    frequency: RecurrenceFrequencyValue | None = None
    starts_on: date | None = None
    timezone: str | None = Field(default=None, max_length=64)
    weekdays: list[int] | None = None
    month_day: int | None = Field(default=None, ge=1, le=28)

    @field_validator("weekdays")
    @classmethod
    def weekdays_are_valid(cls, value: list[int] | None) -> list[int] | None:
        return _validate_weekdays(value)

    @field_validator("timezone")
    @classmethod
    def timezone_is_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("timezone must not be blank")
        return value


class RecurrenceRead(BaseModel):
    id: str
    frequency: RecurrenceFrequencyValue
    weekdays: list[int] | None
    month_day: int | None
    starts_on: date
    timezone: str
    stopped_at_utc: datetime | None
    created_at_utc: datetime
    updated_at_utc: datetime
    version: int

    @field_serializer(
        "stopped_at_utc",
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


class RecurrenceVersionRequest(BaseModel):
    version: int = Field(ge=1)
