from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.errors import ScheduleValidationError
from app.core.time import ensure_utc

UTC = timezone.utc


@dataclass(frozen=True)
class ScheduleInstants:
    start_at_utc: datetime
    end_at_utc: datetime
    timezone_name: str


def resolve_timezone(timezone_name: str) -> ZoneInfo:
    normalized = timezone_name.strip()
    if not normalized:
        raise ScheduleValidationError("timezone must not be blank")
    try:
        return ZoneInfo(normalized)
    except ZoneInfoNotFoundError as error:
        raise ScheduleValidationError(
            f"timezone must be a valid IANA timezone: {normalized}"
        ) from error


def _local_to_utc(local_value: datetime, zone: ZoneInfo, label: str) -> datetime:
    candidates: list[tuple[datetime, datetime]] = []
    for fold in (0, 1):
        aware = local_value.replace(tzinfo=zone, fold=fold)
        utc_value = aware.astimezone(UTC)
        round_trip = utc_value.astimezone(zone)
        if round_trip.replace(tzinfo=None) == local_value:
            candidates.append((aware, utc_value))

    if not candidates:
        raise ScheduleValidationError(
            f"{label} is a nonexistent local time in {zone.key}"
        )

    offsets = {candidate[0].utcoffset() for candidate in candidates}
    if len(offsets) > 1:
        raise ScheduleValidationError(
            f"{label} is an ambiguous local time in {zone.key}"
        )

    return candidates[0][1]


def local_schedule_to_utc(
    planned_date: date,
    start_time: time,
    end_time: time,
    timezone_name: str,
) -> ScheduleInstants:
    if start_time.tzinfo is not None or end_time.tzinfo is not None:
        raise ScheduleValidationError("schedule times must not include a UTC offset")
    if start_time >= end_time:
        raise ScheduleValidationError("schedule start_time must be before end_time")

    zone = resolve_timezone(timezone_name)
    start_local = datetime.combine(planned_date, start_time)
    end_local = datetime.combine(planned_date, end_time)
    start_at_utc = _local_to_utc(start_local, zone, "start_time")
    end_at_utc = _local_to_utc(end_local, zone, "end_time")

    if end_at_utc <= start_at_utc:
        raise ScheduleValidationError("schedule end_time must be after start_time")
    if start_at_utc.astimezone(zone).date() != planned_date:
        raise ScheduleValidationError("schedule start date does not match planned_date")
    if end_at_utc.astimezone(zone).date() != planned_date:
        raise ScheduleValidationError("cross-day schedules are not supported in V0.3")

    return ScheduleInstants(start_at_utc, end_at_utc, timezone_name.strip())


def validate_persisted_schedule(
    planned_date: date | None,
    start_at_utc: datetime | None,
    end_at_utc: datetime | None,
    timezone_name: str | None,
) -> None:
    values = (start_at_utc, end_at_utc, timezone_name)
    if all(value is None for value in values):
        return
    if any(value is None for value in values) or planned_date is None:
        raise ScheduleValidationError("a Time Block requires planned_date and all schedule fields")

    zone = resolve_timezone(timezone_name)
    try:
        normalized_start = ensure_utc(start_at_utc)
        normalized_end = ensure_utc(end_at_utc)
    except ValueError as error:
        raise ScheduleValidationError(str(error)) from error

    if normalized_end <= normalized_start:
        raise ScheduleValidationError("schedule end_at_utc must be after start_at_utc")
    if normalized_start.astimezone(zone).date() != planned_date:
        raise ScheduleValidationError("planned_date does not match the scheduled start date")
    if normalized_end.astimezone(zone).date() != planned_date:
        raise ScheduleValidationError("cross-day schedules are not supported in V0.3")


def move_schedule_to_date(
    planned_date: date,
    start_at_utc: datetime,
    end_at_utc: datetime,
    timezone_name: str,
) -> ScheduleInstants:
    zone = resolve_timezone(timezone_name)
    try:
        start_local = ensure_utc(start_at_utc).astimezone(zone)
        end_local = ensure_utc(end_at_utc).astimezone(zone)
    except ValueError as error:
        raise ScheduleValidationError(str(error)) from error

    if start_local.date() != end_local.date():
        raise ScheduleValidationError("cross-day schedules are not supported in V0.3")
    return local_schedule_to_utc(
        planned_date,
        start_local.timetz().replace(tzinfo=None),
        end_local.timetz().replace(tzinfo=None),
        timezone_name,
    )
