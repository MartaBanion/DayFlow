from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base
from app.db.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.project import Project
    from app.models.recurrence import RecurrenceRule
    from app.models.reminder import Reminder
    from app.models.tag import Tag


class TaskStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class TaskPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class DeadlineStatus(StrEnum):
    NONE = "none"
    UPCOMING = "upcoming"
    DUE_TODAY = "due_today"
    OVERDUE = "overdue"
    COMPLETED = "completed"


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed')",
            name="ck_tasks_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high')",
            name="ck_tasks_priority",
        ),
        CheckConstraint(
            "(start_at_utc IS NULL AND end_at_utc IS NULL AND schedule_timezone IS NULL) "
            "OR (start_at_utc IS NOT NULL AND end_at_utc IS NOT NULL AND schedule_timezone IS NOT NULL)",
            name="ck_tasks_schedule_complete",
        ),
        CheckConstraint(
            "start_at_utc IS NULL OR planned_date IS NOT NULL",
            name="ck_tasks_schedule_requires_date",
        ),
        CheckConstraint(
            "(deadline_date IS NULL AND deadline_at_utc IS NULL AND deadline_timezone IS NULL) "
            "OR (deadline_date IS NOT NULL AND deadline_at_utc IS NULL AND deadline_timezone IS NOT NULL) "
            "OR (deadline_date IS NOT NULL AND deadline_at_utc IS NOT NULL AND deadline_timezone IS NOT NULL)",
            name="ck_tasks_deadline_state",
        ),
        CheckConstraint(
            "(recurrence_rule_id IS NULL AND recurrence_occurrence_date IS NULL) "
            "OR (recurrence_rule_id IS NOT NULL AND recurrence_occurrence_date IS NOT NULL)",
            name="ck_tasks_recurrence_pair",
        ),
        CheckConstraint("version >= 1", name="ck_tasks_version_positive"),
        Index("ix_tasks_planned_date_deleted", "planned_date", "deleted_at_utc"),
        Index("ix_tasks_category_deleted", "category_id", "deleted_at_utc"),
        Index("ix_tasks_project_deleted", "project_id", "deleted_at_utc"),
        Index("ix_tasks_deadline_date_active", "deadline_date", "deleted_at_utc", "status"),
        Index("uq_tasks_recurrence_occurrence", "recurrence_rule_id", "recurrence_occurrence_date", unique=True),
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
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskPriority.NORMAL.value,
        server_default=TaskPriority.NORMAL.value,
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_at_utc: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    end_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    schedule_timezone: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    deadline_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline_at_utc: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    deadline_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recurrence_rule_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("recurrence_rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
    recurrence_occurrence_date: Mapped[date | None] = mapped_column(Date, nullable=True)
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
    category: Mapped["Category | None"] = relationship(
        "Category", back_populates="tasks", lazy="selectin"
    )
    project: Mapped["Project | None"] = relationship(
        "Project", back_populates="tasks", lazy="selectin"
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary="task_tags", back_populates="tasks", lazy="selectin"
    )
    recurrence_rule: Mapped["RecurrenceRule | None"] = relationship(
        "RecurrenceRule", back_populates="tasks", lazy="selectin"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder", back_populates="task", cascade="all, delete-orphan"
    )

    @property
    def deadline_status(self) -> str:
        if self.deadline_date is None or self.deleted_at_utc is not None:
            return DeadlineStatus.NONE.value
        if self.status == TaskStatus.COMPLETED.value:
            return DeadlineStatus.COMPLETED.value
        zone = ZoneInfo(self.deadline_timezone)
        now_local = datetime.now(zone)
        if self.deadline_at_utc is not None:
            deadline_at = self.deadline_at_utc
            if deadline_at.tzinfo is None or deadline_at.utcoffset() is None:
                deadline_at = deadline_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= deadline_at.astimezone(timezone.utc):
                return DeadlineStatus.OVERDUE.value
        elif now_local.date() > self.deadline_date:
            return DeadlineStatus.OVERDUE.value
        if now_local.date() == self.deadline_date:
            return DeadlineStatus.DUE_TODAY.value
        return DeadlineStatus.UPCOMING.value

    __mapper_args__ = {"version_id_col": version}
