from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import CheckConstraint, Date, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base
from app.db.types import UTCDateTime


class TaskStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed')",
            name="ck_tasks_status",
        ),
        CheckConstraint("version >= 1", name="ck_tasks_version_positive"),
        Index("ix_tasks_planned_date_deleted", "planned_date", "deleted_at_utc"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskStatus.PENDING.value,
        server_default=TaskStatus.PENDING.value,
    )
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )
    completed_at_utc: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    deleted_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
