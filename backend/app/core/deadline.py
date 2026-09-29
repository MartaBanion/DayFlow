from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from app.core.errors import DeadlineValidationError, ScheduleValidationError
from app.core.schedule import _local_to_utc, resolve_timezone


@dataclass(frozen=True)
class DeadlineInstants:
    deadline_date: date
    deadline_at_utc: datetime | None
    timezone_name: str


def local_deadline_to_utc(
    deadline_date: date,
    deadline_time: time,
    timezone_name: str,
) -> DeadlineInstants:
    if deadline_time.tzinfo is not None and deadline_time.utcoffset() is not None:
        raise DeadlineValidationError("deadline time must not include a UTC offset")
    normalized_timezone = timezone_name.strip()
    try:
        zone = resolve_timezone(normalized_timezone)
    except ScheduleValidationError as error:
        raise DeadlineValidationError(error.message) from error
    local_value = datetime.combine(deadline_date, deadline_time)
    try:
        utc_value = _local_to_utc(local_value, zone, "deadline time")
    except ScheduleValidationError as error:
        raise DeadlineValidationError(error.message) from error
    return DeadlineInstants(deadline_date, utc_value, normalized_timezone)


def validate_persisted_deadline(
    deadline_date: date | None,
    deadline_at_utc: datetime | None,
    timezone_name: str | None,
) -> None:
    values = (deadline_date, deadline_at_utc, timezone_name)
    if all(value is None for value in values):
        return
    if deadline_date is None or timezone_name is None:
        raise DeadlineValidationError(
            "a Deadline requires deadline_date and deadline_timezone"
        )
    try:
        zone = resolve_timezone(timezone_name)
    except ScheduleValidationError as error:
        raise DeadlineValidationError(error.message) from error
    if deadline_at_utc is None:
        return
    if deadline_at_utc.tzinfo is None or deadline_at_utc.utcoffset() is None:
        raise DeadlineValidationError("deadline_at_utc must include a UTC offset")
    if deadline_at_utc.astimezone(zone).date() != deadline_date:
        raise DeadlineValidationError(
            "deadline_date does not match the Deadline local date"
        )
