from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base
from app.db.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.task import Task


class ReminderStatus(StrEnum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'acknowledged', 'dismissed')",
            name="ck_reminders_status",
        ),
        CheckConstraint(
            "(status = 'pending' AND acknowledged_at_utc IS NULL AND dismissed_at_utc IS NULL) "
            "OR (status = 'acknowledged' AND acknowledged_at_utc IS NOT NULL AND dismissed_at_utc IS NULL) "
            "OR (status = 'dismissed' AND acknowledged_at_utc IS NULL AND dismissed_at_utc IS NOT NULL)",
            name="ck_reminders_state_timestamps",
        ),
        CheckConstraint("version >= 1", name="ck_reminders_version_positive"),
        Index("ix_reminders_status_trigger", "status", "trigger_at_utc"),
        Index("ix_reminders_task_status", "task_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    reminder_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ReminderStatus.PENDING.value,
        server_default=ReminderStatus.PENDING.value,
    )
    acknowledged_at_utc: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    dismissed_at_utc: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    task: Mapped["Task"] = relationship("Task", back_populates="reminders")
    __mapper_args__ = {"version_id_col": version}
