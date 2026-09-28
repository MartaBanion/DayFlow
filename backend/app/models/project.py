from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import CheckConstraint, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base
from app.db.types import UTCDateTime


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed')",
            name="ck_projects_status",
        ),
        CheckConstraint("version >= 1", name="ck_projects_version_positive"),
        Index(
            "uq_projects_active_name",
            "name",
            unique=True,
            sqlite_where=text("deleted_at_utc IS NULL"),
        ),
        Index("ix_projects_deleted_status", "deleted_at_utc", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(
        String(200, collation="NOCASE"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ProjectStatus.ACTIVE.value,
        server_default=ProjectStatus.ACTIVE.value,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )
    completed_at_utc: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    deleted_at_utc: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    version: Mapped[int] = mapped_column(
        # Project mutations explicitly advance this value once per operation.
        # SQLAlchemy still checks the old value in the UPDATE predicate.
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="project"
    )

    __mapper_args__ = {"version_id_col": version}
