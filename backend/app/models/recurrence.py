from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, Date, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base
from app.db.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.task import Task


class RecurrenceFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class RecurrenceRule(Base):
    __tablename__ = "recurrence_rules"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('daily', 'weekly', 'monthly')",
            name="ck_recurrence_rules_frequency",
        ),
        CheckConstraint(
            "(frequency = 'daily' AND weekdays_mask IS NULL AND month_day IS NULL) "
            "OR (frequency = 'weekly' AND weekdays_mask IS NOT NULL AND weekdays_mask BETWEEN 1 AND 127 AND month_day IS NULL) "
            "OR (frequency = 'monthly' AND weekdays_mask IS NULL AND month_day IS NOT NULL AND month_day BETWEEN 1 AND 28)",
            name="ck_recurrence_rules_selector",
        ),
        CheckConstraint("version >= 1", name="ck_recurrence_rules_version_positive"),
        Index("ix_recurrence_rules_stopped", "stopped_at_utc"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    weekdays_mask: Mapped[int | None] = mapped_column(Integer, nullable=True)
    month_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    stopped_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="recurrence_rule"
    )
    __mapper_args__ = {"version_id_col": version}
