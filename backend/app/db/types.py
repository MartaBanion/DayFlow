from datetime import datetime

from sqlalchemy import String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from app.core.time import ensure_utc


class UTCDateTime(TypeDecorator[datetime]):
    """Persist timezone-aware UTC datetimes without SQLite timezone loss."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> str | None:
        if value is None:
            return None
        return ensure_utc(value).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )

    def process_result_value(
        self, value: str | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
