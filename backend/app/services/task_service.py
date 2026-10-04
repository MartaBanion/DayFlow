from __future__ import annotations

from datetime import date, datetime
import logging

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import (
    CategoryNameConflictError,
    CategoryNotFoundError,
    DeadlineValidationError,
    ProjectNotFoundError,
    ScheduleConflictError,
    ScheduleValidationError,
    TagNameConflictError,
    TagNotFoundError,
    TaskQueryConfigurationError,
    TaskNotFoundError,
    TaskVersionConflictError,
)
from app.core.config import get_settings
from app.core.time import ensure_utc, utc_now
from app.core.schedule import (
    local_schedule_to_utc,
    move_schedule_to_date,
    resolve_timezone,
    validate_persisted_schedule,
)
from app.core.deadline import (
    deadline_status_at,
    local_deadline_to_utc,
    validate_persisted_deadline,
)
from app.models.category import Category
from app.models.project import Project
from app.models.tag import Tag, task_tags
from app.models.task import Task, TaskPriority, TaskStatus
from app.schemas.task import (
    CategoryCreate,
    CategoryUpdate,
    TagCreate,
    TagUpdate,
    TaskCreate,
    TaskSortValue,
    TaskStatusFilterValue,
    TaskUpdate,
    PlannedBucketValue,
)

logger = logging.getLogger("dayflow.task")


class TaskService:
    def create(
        self,
        session: Session,
        payload: TaskCreate,
        *,
        allow_schedule_conflict: bool = False,
    ) -> Task:
        try:
            category = self._resolve_category(session, payload.category_id)
            project = self._resolve_project(session, payload.project_id)
            tags = self._resolve_tags(session, payload.tag_ids)
            start_at_utc, end_at_utc, schedule_timezone = self._schedule_for_create(
                payload
            )
            deadline_date, deadline_at_utc, deadline_timezone = self._deadline_for_create(
                payload
            )
            self._ensure_no_schedule_conflict(
                session,
                start_at_utc,
                end_at_utc,
                allow_schedule_conflict=allow_schedule_conflict,
            )
            task = Task(
                title=payload.title,
                description=payload.description,
                planned_date=payload.planned_date,
                priority=payload.priority.value,
                category=category,
                project=project,
                tags=tags,
                start_at_utc=start_at_utc,
                end_at_utc=end_at_utc,
                schedule_timezone=schedule_timezone,
                deadline_date=deadline_date,
                deadline_at_utc=deadline_at_utc,
                deadline_timezone=deadline_timezone,
            )
            session.add(task)
            self._commit(session, "create task")
            session.refresh(task)
            return task
        except Exception:
            session.rollback()
            raise

    def list(
        self,
        session: Session,
        planned_date: date | None = None,
        *,
        inbox: bool = False,
        query: str | None = None,
        priority: str | None = None,
        category_id: str | None = None,
        project_id: str | None = None,
        tag_id: str | None = None,
        status: str | None = None,
        overdue: bool = False,
        planned_bucket: str | None = None,
        sort: str = TaskSortValue.DEFAULT.value,
        generated_at_utc: datetime | None = None,
    ) -> list[Task]:
        request_clock = ensure_utc(generated_at_utc or utc_now())
        statement = (
            select(Task)
            .options(
                selectinload(Task.category),
                selectinload(Task.project),
                selectinload(Task.tags),
            )
            .where(Task.deleted_at_utc.is_(None))
        )
        if planned_date is not None:
            statement = statement.where(Task.planned_date == planned_date)
        if inbox:
            statement = statement.where(
                Task.planned_date.is_(None),
                Task.status == TaskStatus.PENDING.value,
            )
        if status is not None and status != TaskStatusFilterValue.ALL.value:
            statement = statement.where(Task.status == status)
        if planned_bucket is not None:
            planned_date_filter = self._planned_bucket_filter(
                planned_bucket, request_clock
            )
            statement = statement.where(planned_date_filter)
        if overdue:
            statement = statement.where(
                Task.status == TaskStatus.PENDING.value,
                Task.deadline_date.is_not(None),
            )
        if query:
            pattern = self._like_pattern(query)
            statement = statement.where(
                or_(
                    Task.title.ilike(pattern, escape="\\"),
                    Task.description.ilike(pattern, escape="\\"),
                )
            )
        if priority is not None:
            statement = statement.where(Task.priority == priority)
        if category_id is not None:
            statement = statement.where(Task.category_id == category_id)
        if project_id is not None:
            statement = statement.where(Task.project_id == project_id)
        if tag_id is not None:
            statement = statement.join(
                task_tags, task_tags.c.task_id == Task.id
            ).where(task_tags.c.tag_id == tag_id)

        statement = statement.order_by(*self._task_order(sort))
        tasks = list(session.scalars(statement).unique().all())
        if overdue:
            tasks = [
                task
                for task in tasks
                if self._deadline_status(task, request_clock) == "overdue"
            ]
        return tasks

    @staticmethod
    def _planned_bucket_filter(planned_bucket: str, generated_at_utc: datetime):
        try:
            zone = resolve_timezone(get_settings().timezone)
        except ScheduleValidationError as error:
            raise TaskQueryConfigurationError() from error
        current_local_date = generated_at_utc.astimezone(zone).date()
        if planned_bucket == PlannedBucketValue.UNSCHEDULED.value:
            return Task.planned_date.is_(None)
        if planned_bucket == PlannedBucketValue.TODAY.value:
            return Task.planned_date == current_local_date
        if planned_bucket == PlannedBucketValue.PAST.value:
            return Task.planned_date < current_local_date
        return Task.planned_date > current_local_date

    @staticmethod
    def _task_order(sort: str):
        pending_first = case(
            (Task.status == TaskStatus.PENDING.value, 0), else_=1
        )
        if sort == TaskSortValue.PLANNED.value:
            return (
                case((Task.planned_date.is_(None), 1), else_=0),
                Task.planned_date,
                Task.created_at_utc,
                Task.id,
            )
        if sort == TaskSortValue.DEADLINE.value:
            return (
                case((Task.deadline_date.is_(None), 1), else_=0),
                Task.deadline_date,
                case((Task.deadline_at_utc.is_(None), 1), else_=0),
                Task.deadline_at_utc,
                Task.created_at_utc,
                Task.id,
            )
        if sort == TaskSortValue.COMPLETED.value:
            return (
                case((Task.completed_at_utc.is_(None), 1), else_=0),
                Task.completed_at_utc.desc(),
                Task.created_at_utc,
                Task.id,
            )
        return (
            pending_first,
            Task.planned_date.is_(None),
            Task.created_at_utc,
            Task.id,
        )

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

    def today(self, session: Session, target_date: date) -> list[Task]:
        return self.list(session, target_date)

    def calendar(self, session: Session, start_date: date, end_date: date) -> list[Task]:
        statement = (
            select(Task)
            .options(
                selectinload(Task.category),
                selectinload(Task.project),
                selectinload(Task.tags),
            )
            .where(
                Task.deleted_at_utc.is_(None),
                Task.planned_date >= start_date,
                Task.planned_date <= end_date,
            )
            .order_by(
                Task.planned_date,
                Task.start_at_utc.is_(None),
                Task.start_at_utc,
                case((Task.status == TaskStatus.PENDING.value, 0), else_=1),
                Task.created_at_utc,
            )
        )
        return list(session.scalars(statement).unique().all())

    def get(self, session: Session, task_id: str) -> Task:
        task = session.scalar(
            select(Task)
            .options(
                selectinload(Task.category),
                selectinload(Task.project),
                selectinload(Task.tags),
            )
            .where(Task.id == task_id, Task.deleted_at_utc.is_(None))
        )
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def update(
        self,
        session: Session,
        task_id: str,
        expected_version: int,
        payload: TaskUpdate,
        *,
        allow_schedule_conflict: bool = False,
    ) -> Task:
        try:
            task = self.get(session, task_id)
            self._check_version(task, expected_version)
            changes = payload.model_dump(exclude_unset=True)
            if not changes:
                return task

            category_requested = "category_id" in changes
            project_requested = "project_id" in changes
            tag_ids_requested = "tag_ids" in changes
            category = (
                self._resolve_category(session, changes["category_id"])
                if category_requested
                else None
            )
            project = (
                self._resolve_project(session, changes["project_id"])
                if project_requested
                else None
            )
            tags = (
                self._resolve_tags(session, changes["tag_ids"] or [])
                if tag_ids_requested
                else None
            )

            planned_date = changes.get("planned_date", task.planned_date)
            start_at_utc, end_at_utc, schedule_timezone = self._schedule_for_update(
                task, changes, planned_date
            )
            deadline_date, deadline_at_utc, deadline_timezone = self._deadline_for_update(
                task, changes
            )

            changed = False
            for field in ("title", "description", "planned_date", "priority"):
                if field not in changes:
                    continue
                value = changes[field]
                if isinstance(value, TaskPriority):
                    value = value.value
                if getattr(task, field) != value:
                    changed = True

            if category_requested:
                category_id = category.id if category is not None else None
                if task.category_id != category_id:
                    changed = True

            if project_requested:
                project_id = project.id if project is not None else None
                if task.project_id != project_id:
                    changed = True

            if tag_ids_requested:
                requested_tag_ids = {tag.id for tag in tags or []}
                current_tag_ids = {tag.id for tag in task.tags}
                if requested_tag_ids != current_tag_ids:
                    changed = True

            if (
                task.start_at_utc != start_at_utc
                or task.end_at_utc != end_at_utc
                or task.schedule_timezone != schedule_timezone
            ):
                changed = True

            if (
                task.deadline_date != deadline_date
                or task.deadline_at_utc != deadline_at_utc
                or task.deadline_timezone != deadline_timezone
            ):
                changed = True

            if not changed:
                return task

            if task.status == TaskStatus.PENDING.value:
                self._ensure_no_schedule_conflict(
                    session,
                    start_at_utc,
                    end_at_utc,
                    exclude_task_id=task.id,
                    allow_schedule_conflict=allow_schedule_conflict,
                )

            for field in ("title", "description", "planned_date", "priority"):
                if field not in changes:
                    continue
                value = changes[field]
                if isinstance(value, TaskPriority):
                    value = value.value
                setattr(task, field, value)

            if category_requested:
                task.category = category

            if project_requested:
                task.project = project

            if tag_ids_requested:
                task.tags = tags or []

            task.start_at_utc = start_at_utc
            task.end_at_utc = end_at_utc
            task.schedule_timezone = schedule_timezone
            task.deadline_date = deadline_date
            task.deadline_at_utc = deadline_at_utc
            task.deadline_timezone = deadline_timezone
            self._touch(task)
            self._commit(session, "update task", (task.id, expected_version))
            session.refresh(task)
            return task
        except Exception:
            session.rollback()
            raise

    def complete(self, session: Session, task_id: str, expected_version: int) -> Task:
        task = self.get(session, task_id)
        if task.recurrence_rule_id is not None:
            from app.services.recurrence_service import RecurrenceService

            return RecurrenceService().complete_occurrence(
                session, task_id, expected_version
            )
        self._check_version(task, expected_version)
        if task.status == TaskStatus.COMPLETED.value:
            return task
        task.status = TaskStatus.COMPLETED.value
        task.completed_at_utc = utc_now()
        self._touch(task)
        self._commit(session, "complete task", (task.id, expected_version))
        session.refresh(task)
        return task

    def restore(self, session: Session, task_id: str, expected_version: int) -> Task:
        task = session.scalar(
            select(Task)
            .options(
                selectinload(Task.category),
                selectinload(Task.project),
                selectinload(Task.tags),
            )
            .where(Task.id == task_id)
        )
        if task is None:
            raise TaskNotFoundError(task_id)
        self._check_version(task, expected_version)
        changed = task.deleted_at_utc is not None or task.status == TaskStatus.COMPLETED.value
        if not changed:
            return task
        task.deleted_at_utc = None
        task.status = TaskStatus.PENDING.value
        task.completed_at_utc = None
        self._touch(task)
        self._commit(session, "restore task", (task.id, expected_version))
        session.refresh(task)
        return task

    def soft_delete(self, session: Session, task_id: str, expected_version: int) -> None:
        task = self.get(session, task_id)
        self._check_version(task, expected_version)
        task.deleted_at_utc = utc_now()
        self._touch(task)
        self._commit(session, "soft delete task", (task.id, expected_version))

    def list_categories(self, session: Session) -> list[Category]:
        statement = select(Category).order_by(func.lower(Category.name), Category.name)
        return list(session.scalars(statement).all())

    def create_category(self, session: Session, payload: CategoryCreate) -> Category:
        name = payload.name.strip()
        try:
            self._ensure_category_name_available(session, name)
            category = Category(name=name)
            session.add(category)
            self._commit(session, "create category")
            session.refresh(category)
            return category
        except IntegrityError:
            session.rollback()
            raise CategoryNameConflictError(name)

    def update_category(
        self, session: Session, category_id: str, payload: CategoryUpdate
    ) -> Category:
        category = session.get(Category, category_id)
        if category is None:
            raise CategoryNotFoundError(category_id)
        name = payload.name.strip()
        if category.name == name:
            return category
        try:
            self._ensure_category_name_available(session, name, excluding=category_id)
            category.name = name
            self._commit(session, "update category")
            session.refresh(category)
            return category
        except IntegrityError:
            session.rollback()
            raise CategoryNameConflictError(name)

    def delete_category(self, session: Session, category_id: str) -> None:
        category = session.get(Category, category_id)
        if category is None:
            raise CategoryNotFoundError(category_id)
        tasks = list(session.scalars(select(Task).where(Task.category_id == category_id)).all())
        for task in tasks:
            task.category = None
            self._touch(task)
        session.delete(category)
        self._commit(session, "delete category")

    def list_tags(self, session: Session) -> list[Tag]:
        statement = select(Tag).order_by(func.lower(Tag.name), Tag.name)
        return list(session.scalars(statement).all())

    def create_tag(self, session: Session, payload: TagCreate) -> Tag:
        name = payload.name.strip()
        try:
            self._ensure_tag_name_available(session, name)
            tag = Tag(name=name)
            session.add(tag)
            self._commit(session, "create tag")
            session.refresh(tag)
            return tag
        except IntegrityError:
            session.rollback()
            raise TagNameConflictError(name)

    def update_tag(self, session: Session, tag_id: str, payload: TagUpdate) -> Tag:
        tag = session.get(Tag, tag_id)
        if tag is None:
            raise TagNotFoundError(tag_id)
        name = payload.name.strip()
        if tag.name == name:
            return tag
        try:
            self._ensure_tag_name_available(session, name, excluding=tag_id)
            tag.name = name
            self._commit(session, "update tag")
            session.refresh(tag)
            return tag
        except IntegrityError:
            session.rollback()
            raise TagNameConflictError(name)

    def delete_tag(self, session: Session, tag_id: str) -> None:
        tag = session.get(Tag, tag_id)
        if tag is None:
            raise TagNotFoundError(tag_id)
        tasks = list(
            session.scalars(
                select(Task)
                .join(task_tags, task_tags.c.task_id == Task.id)
                .where(task_tags.c.tag_id == tag_id)
            ).unique().all()
        )
        for task in tasks:
            task.tags = [task_tag for task_tag in task.tags if task_tag.id != tag_id]
            self._touch(task)
        session.delete(tag)
        self._commit(session, "delete tag")

    @staticmethod
    def _schedule_for_create(payload: TaskCreate) -> tuple[datetime | None, datetime | None, str | None]:
        if payload.schedule is None:
            return None, None, None
        if payload.planned_date is None:
            raise ScheduleValidationError("a schedule requires planned_date")

        timezone_name = payload.schedule.timezone or get_settings().timezone
        instants = local_schedule_to_utc(
            payload.planned_date,
            payload.schedule.start_time,
            payload.schedule.end_time,
            timezone_name,
        )
        validate_persisted_schedule(
            payload.planned_date,
            instants.start_at_utc,
            instants.end_at_utc,
            instants.timezone_name,
        )
        return instants.start_at_utc, instants.end_at_utc, instants.timezone_name

    @staticmethod
    def _deadline_for_create(
        payload: TaskCreate,
    ) -> tuple[date | None, datetime | None, str | None]:
        if payload.deadline is None:
            return None, None, None
        return TaskService._deadline_from_value(payload.deadline.model_dump())

    @staticmethod
    def _deadline_for_update(
        task: Task,
        changes: dict[str, object],
    ) -> tuple[date | None, datetime | None, str | None]:
        if "deadline" not in changes:
            return task.deadline_date, task.deadline_at_utc, task.deadline_timezone
        requested_deadline = changes["deadline"]
        if requested_deadline is None:
            return None, None, None
        return TaskService._deadline_from_value(requested_deadline)

    @staticmethod
    def _deadline_from_value(
        value: object,
    ) -> tuple[date, datetime | None, str]:
        if not isinstance(value, dict):
            raise DeadlineValidationError("invalid Deadline value")
        deadline_date = value.get("date")
        deadline_time = value.get("time")
        timezone_name = value.get("timezone") or get_settings().timezone
        if not isinstance(deadline_date, date):
            raise DeadlineValidationError("deadline date must be a valid date")
        if not isinstance(timezone_name, str):
            raise DeadlineValidationError("deadline timezone must be a valid IANA timezone")
        if deadline_time is None:
            # Resolve here as well as at conversion time so date-only Deadlines
            # cannot persist an invalid IANA timezone.
            from app.core.schedule import resolve_timezone

            try:
                resolve_timezone(timezone_name)
            except Exception as error:
                if isinstance(error, DeadlineValidationError):
                    raise
                raise DeadlineValidationError(str(error)) from error
            return deadline_date, None, timezone_name.strip()
        if not hasattr(deadline_time, "tzinfo"):
            raise DeadlineValidationError("deadline time must be a valid local time")
        try:
            instants = local_deadline_to_utc(deadline_date, deadline_time, timezone_name)
        except Exception as error:
            if isinstance(error, DeadlineValidationError):
                raise
            raise DeadlineValidationError(str(error)) from error
        validate_persisted_deadline(
            instants.deadline_date,
            instants.deadline_at_utc,
            instants.timezone_name,
        )
        return (
            instants.deadline_date,
            instants.deadline_at_utc,
            instants.timezone_name,
        )

    @staticmethod
    def _schedule_for_update(
        task: Task,
        changes: dict[str, object],
        planned_date: date | None,
    ) -> tuple[datetime | None, datetime | None, str | None]:
        schedule_requested = "schedule" in changes
        if schedule_requested:
            requested_schedule = changes["schedule"]
            if requested_schedule is None:
                result = (None, None, None)
            else:
                if planned_date is None:
                    raise ScheduleValidationError("a schedule requires planned_date")
                timezone_name = requested_schedule.get("timezone") or get_settings().timezone  # type: ignore[union-attr]
                instants = local_schedule_to_utc(
                    planned_date,
                    requested_schedule["start_time"],  # type: ignore[index]
                    requested_schedule["end_time"],  # type: ignore[index]
                    timezone_name,
                )
                result = (
                    instants.start_at_utc,
                    instants.end_at_utc,
                    instants.timezone_name,
                )
        elif "planned_date" in changes and task.start_at_utc is not None:
            if planned_date is None:
                raise ScheduleValidationError(
                    "clear schedule before clearing planned_date"
                )
            instants = move_schedule_to_date(
                planned_date,
                task.start_at_utc,
                task.end_at_utc,
                task.schedule_timezone,
            )
            result = (
                instants.start_at_utc,
                instants.end_at_utc,
                instants.timezone_name,
            )
        else:
            result = (
                task.start_at_utc,
                task.end_at_utc,
                task.schedule_timezone,
            )

        validate_persisted_schedule(planned_date, *result)
        return result

    @staticmethod
    def _ensure_no_schedule_conflict(
        session: Session,
        start_at_utc: datetime | None,
        end_at_utc: datetime | None,
        *,
        exclude_task_id: str | None = None,
        allow_schedule_conflict: bool = False,
    ) -> None:
        if start_at_utc is None or end_at_utc is None:
            return

        statement = select(Task.id).where(
            Task.status == TaskStatus.PENDING.value,
            Task.deleted_at_utc.is_(None),
            Task.start_at_utc.is_not(None),
            Task.end_at_utc.is_not(None),
            Task.start_at_utc < end_at_utc,
            Task.end_at_utc > start_at_utc,
        )
        if exclude_task_id is not None:
            statement = statement.where(Task.id != exclude_task_id)

        conflicting_ids = [str(task_id) for task_id in session.scalars(statement).all()]
        if conflicting_ids and not allow_schedule_conflict:
            raise ScheduleConflictError(conflicting_ids)

    @staticmethod
    def _resolve_category(session: Session, category_id) -> Category | None:
        if category_id is None:
            return None
        resolved_id = str(category_id)
        category = session.get(Category, resolved_id)
        if category is None:
            raise CategoryNotFoundError(resolved_id)
        return category

    @staticmethod
    def _resolve_project(session: Session, project_id) -> Project | None:
        if project_id is None:
            return None
        resolved_id = str(project_id)
        project = session.scalar(
            select(Project).where(
                Project.id == resolved_id,
                Project.deleted_at_utc.is_(None),
            )
        )
        if project is None:
            raise ProjectNotFoundError(resolved_id)
        return project

    @staticmethod
    def _resolve_tags(session: Session, tag_ids) -> list[Tag]:
        resolved_ids = [str(tag_id) for tag_id in tag_ids]
        if not resolved_ids:
            return []
        found = list(session.scalars(select(Tag).where(Tag.id.in_(resolved_ids))).all())
        found_by_id = {tag.id: tag for tag in found}
        for tag_id in resolved_ids:
            if tag_id not in found_by_id:
                raise TagNotFoundError(tag_id)
        return [found_by_id[tag_id] for tag_id in resolved_ids]

    @staticmethod
    def _ensure_category_name_available(
        session: Session, name: str, excluding: str | None = None
    ) -> None:
        statement = select(Category).where(func.lower(Category.name) == name.lower())
        if excluding is not None:
            statement = statement.where(Category.id != excluding)
        if session.scalar(statement) is not None:
            raise CategoryNameConflictError(name)

    @staticmethod
    def _ensure_tag_name_available(
        session: Session, name: str, excluding: str | None = None
    ) -> None:
        statement = select(Tag).where(func.lower(Tag.name) == name.lower())
        if excluding is not None:
            statement = statement.where(Tag.id != excluding)
        if session.scalar(statement) is not None:
            raise TagNameConflictError(name)

    @staticmethod
    def _like_pattern(value: str) -> str:
        escaped = (
            value.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        return f"%{escaped}%"

    @staticmethod
    def _check_version(task: Task, expected_version: int) -> None:
        if task.version != expected_version:
            raise TaskVersionConflictError(task.id, expected_version, task.version)

    @staticmethod
    def _touch(task: Task) -> None:
        task.version += 1
        task.updated_at_utc = utc_now()

    @staticmethod
    def _commit(
        session: Session,
        operation: str,
        conflict: tuple[str, int] | None = None,
    ) -> None:
        try:
            session.commit()
        except StaleDataError:
            session.rollback()
            if conflict is not None:
                task_id, expected_version = conflict
                actual_version = session.scalar(
                    select(Task.version).where(Task.id == task_id)
                )
                raise TaskVersionConflictError(
                    task_id,
                    expected_version,
                    actual_version if actual_version is not None else -1,
                )
            logger.exception("Database transaction rolled back during %s", operation)
            raise
        except SQLAlchemyError:
            session.rollback()
            logger.exception("Database transaction rolled back during %s", operation)
            raise
