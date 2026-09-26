from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


UTC = timezone.utc


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""

    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC and reject ambiguous naive values."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("UTC datetimes must include timezone information")
    return value.astimezone(UTC)


def today_in_timezone(timezone_name: str) -> date:
    return datetime.now(ZoneInfo(timezone_name)).date()
