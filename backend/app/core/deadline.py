from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from app.core.errors import DeadlineValidationError, ScheduleValidationError
from app.core.schedule import _local_to_utc, resolve_timezone
from app.core.time import ensure_utc


@dataclass(frozen=True)
class DeadlineInstants:
    deadline_date: date
    deadline_at_utc: datetime | None
    timezone_name: str


def deadline_status_at(
    *,
    status: str,
    deleted_at_utc: datetime | None,
    deadline_date: date | None,
    deadline_at_utc: datetime | None,
    deadline_timezone: str | None,
    generated_at_utc: datetime,
) -> str:
    """Evaluate the released Deadline status at one explicit UTC instant."""

    if deadline_date is None or deleted_at_utc is not None:
        return "none"
    if status == "completed":
        return "completed"
    if deadline_timezone is None:
        raise DeadlineValidationError(
            "a Deadline requires deadline_date and deadline_timezone"
        )

    try:
        zone = resolve_timezone(deadline_timezone)
        current_utc = ensure_utc(generated_at_utc)
    except (ScheduleValidationError, ValueError) as error:
        message = (
            error.message
            if isinstance(error, ScheduleValidationError)
            else str(error)
        )
        raise DeadlineValidationError(message) from error

    current_local_date = current_utc.astimezone(zone).date()
    if deadline_at_utc is not None:
        try:
            deadline_utc = ensure_utc(deadline_at_utc)
        except ValueError as error:
            raise DeadlineValidationError(str(error)) from error
        if current_utc >= deadline_utc:
            return "overdue"
    elif current_local_date > deadline_date:
        return "overdue"

    if current_local_date == deadline_date:
        return "due_today"
    return "upcoming"


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
