from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deadline import deadline_status_at
from app.core.errors import ReviewConfigurationError
from app.core.time import ensure_utc, utc_now
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus
from app.schemas.review import (
    ReviewProject,
    ReviewRead,
    ReviewScope,
    ReviewTaskSection,
)
from app.schemas.task import TaskRead

UTC = timezone.utc


@dataclass(frozen=True)
class ReviewWindow:
    generated_at_utc: datetime
    local_timezone: str
    local_date: date
    range_start_utc: datetime
    range_end_utc: datetime


@dataclass(frozen=True)
class ProjectCounts:
    task_count: int
    completed_task_count: int
    pending_task_count: int
    latest_completed_at_utc: datetime | None


class ReviewService:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock

    def get(
        self,
        session: Session,
        scope: ReviewScope,
        timezone_name: str,
    ) -> ReviewRead:
        generated_at_utc = ensure_utc((self._clock or utc_now)())
        window = self._review_window(scope, timezone_name, generated_at_utc)

        completed_tasks = self._completed_tasks(session, window)
        pending_candidates = self._pending_attention_candidates(
            session, window.local_date
        )
        overdue_tasks = [
            task
            for task in pending_candidates
            if self._deadline_status(task, generated_at_utc) == "overdue"
        ]
        overdue_tasks.sort(key=self._overdue_sort_key)
        carryover_tasks = sorted(
            (
                task
                for task in pending_candidates
                if task.planned_date is not None
                and task.planned_date < window.local_date
            ),
            key=lambda task: (task.planned_date, task.created_at_utc, task.id),
        )

        projects = self._projects(session)
        project_counts = self._project_counts(
            session, [project.id for project in projects]
        )
        project_overdue = Counter(
            task.project_id for task in overdue_tasks if task.project_id is not None
        )

        return ReviewRead(
            scope=scope,
            local_timezone=window.local_timezone,
            local_date=window.local_date,
            range_start_utc=window.range_start_utc,
            range_end_utc=window.range_end_utc,
            generated_at_utc=generated_at_utc,
            completed=self._task_section(completed_tasks, generated_at_utc),
            overdue=self._task_section(overdue_tasks, generated_at_utc),
            carryover=self._task_section(carryover_tasks, generated_at_utc),
            projects=[
                self._project_read(
                    project,
                    project_counts.get(project.id, ProjectCounts(0, 0, 0, None)),
                    project_overdue[project.id],
                )
                for project in projects
            ],
        )

    @staticmethod
    def _review_window(
        scope: ReviewScope,
        timezone_name: str,
        generated_at_utc: datetime,
    ) -> ReviewWindow:
        normalized_timezone = timezone_name.strip()
        if not normalized_timezone:
            raise ReviewConfigurationError()
        try:
            zone = ZoneInfo(normalized_timezone)
        except ZoneInfoNotFoundError as error:
            raise ReviewConfigurationError() from error

        local_date = generated_at_utc.astimezone(zone).date()
        if scope == ReviewScope.TODAY:
            range_start_date = local_date
            range_end_date = local_date + timedelta(days=1)
        else:
            range_start_date = local_date - timedelta(days=local_date.weekday())
            range_end_date = range_start_date + timedelta(days=7)

        range_start_utc = datetime.combine(
            range_start_date, time.min, tzinfo=zone
        ).astimezone(UTC)
        range_end_utc = datetime.combine(
            range_end_date, time.min, tzinfo=zone
        ).astimezone(UTC)
        return ReviewWindow(
            generated_at_utc=generated_at_utc,
            local_timezone=normalized_timezone,
            local_date=local_date,
            range_start_utc=range_start_utc,
            range_end_utc=range_end_utc,
        )

    @staticmethod
    def _task_options():
        return (
            selectinload(Task.category),
            selectinload(Task.project),
            selectinload(Task.tags),
        )

    def _completed_tasks(
        self, session: Session, window: ReviewWindow
    ) -> list[Task]:
        statement = (
            select(Task)
            .options(*self._task_options())
            .where(
                Task.deleted_at_utc.is_(None),
                Task.status == TaskStatus.COMPLETED.value,
                Task.completed_at_utc.is_not(None),
                Task.completed_at_utc >= window.range_start_utc,
                Task.completed_at_utc < window.range_end_utc,
            )
            .order_by(Task.completed_at_utc.desc(), Task.id)
        )
        return list(session.scalars(statement).unique().all())

    def _pending_attention_candidates(
        self, session: Session, current_local_date: date
    ) -> list[Task]:
        statement = (
            select(Task)
            .options(*self._task_options())
            .where(
                Task.deleted_at_utc.is_(None),
                Task.status == TaskStatus.PENDING.value,
                or_(
                    Task.deadline_date.is_not(None),
                    Task.planned_date < current_local_date,
                ),
            )
        )
        return list(session.scalars(statement).unique().all())

    @staticmethod
    def _projects(session: Session) -> list[Project]:
        statement = (
            select(Project)
            .where(Project.deleted_at_utc.is_(None))
            .order_by(
                case((Project.status == ProjectStatus.ACTIVE.value, 0), else_=1),
                func.lower(Project.name),
                Project.id,
            )
        )
        return list(session.scalars(statement).all())

    @staticmethod
    def _project_counts(
        session: Session, project_ids: list[str]
    ) -> dict[str, ProjectCounts]:
        if not project_ids:
            return {}
        rows = session.execute(
            select(
                Task.project_id,
                func.count(Task.id).label("task_count"),
                func.sum(
                    case(
                        (Task.status == TaskStatus.COMPLETED.value, 1),
                        else_=0,
                    )
                ).label("completed_task_count"),
                func.sum(
                    case(
                        (Task.status == TaskStatus.PENDING.value, 1),
                        else_=0,
                    )
                ).label("pending_task_count"),
                func.max(
                    case(
                        (
                            Task.status == TaskStatus.COMPLETED.value,
                            Task.completed_at_utc,
                        ),
                        else_=None,
                    )
                ).label("latest_completed_at_utc"),
            )
            .where(
                Task.project_id.in_(project_ids),
                Task.deleted_at_utc.is_(None),
            )
            .group_by(Task.project_id)
        ).all()
        return {
            row.project_id: ProjectCounts(
                task_count=int(row.task_count),
                completed_task_count=int(row.completed_task_count or 0),
                pending_task_count=int(row.pending_task_count or 0),
                latest_completed_at_utc=row.latest_completed_at_utc,
            )
            for row in rows
        }

    @classmethod
    def _task_section(
        cls, tasks: list[Task], generated_at_utc: datetime
    ) -> ReviewTaskSection:
        task_reads = [cls._task_read(task, generated_at_utc) for task in tasks]
        return ReviewTaskSection(count=len(task_reads), tasks=task_reads)

    @classmethod
    def _task_read(cls, task: Task, generated_at_utc: datetime) -> TaskRead:
        values = {
            field_name: (
                cls._deadline_status(task, generated_at_utc)
                if field_name == "deadline_status"
                else getattr(task, field_name)
            )
            for field_name in TaskRead.model_fields
        }
        return TaskRead.model_validate(values)

    @staticmethod
    def _deadline_status(task: Task, generated_at_utc: datetime) -> str:
        return deadline_status_at(
            status=task.status,
            deleted_at_utc=task.deleted_at_utc,
            deadline_date=task.deadline_date,
            deadline_at_utc=task.deadline_at_utc,
            deadline_timezone=task.deadline_timezone,
            generated_at_utc=generated_at_utc,
        )

    @staticmethod
    def _overdue_sort_key(task: Task):
        return (
            task.deadline_date,
            0 if task.deadline_at_utc is not None else 1,
            task.deadline_at_utc or datetime.max.replace(tzinfo=UTC),
            task.created_at_utc,
            task.id,
        )

    @staticmethod
    def _project_read(
        project: Project,
        counts: ProjectCounts,
        overdue_task_count: int,
    ) -> ReviewProject:
        progress_percent = (
            0
            if counts.task_count == 0
            else int(counts.completed_task_count * 100 / counts.task_count)
        )
        return ReviewProject(
            id=project.id,
            name=project.name,
            status=project.status,
            task_count=counts.task_count,
            completed_task_count=counts.completed_task_count,
            pending_task_count=counts.pending_task_count,
            overdue_task_count=overdue_task_count,
            progress_percent=progress_percent,
            latest_completed_at_utc=counts.latest_completed_at_utc,
        )
