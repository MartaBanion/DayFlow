from __future__ import annotations

from datetime import date
import logging

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import (
    CategoryNameConflictError,
    CategoryNotFoundError,
    TagNameConflictError,
    TagNotFoundError,
    TaskNotFoundError,
    TaskVersionConflictError,
)
from app.core.time import utc_now
from app.models.category import Category
from app.models.tag import Tag, task_tags
from app.models.task import Task, TaskPriority, TaskStatus
from app.schemas.task import (
    CategoryCreate,
    CategoryUpdate,
    TagCreate,
    TagUpdate,
    TaskCreate,
    TaskUpdate,
)

logger = logging.getLogger("dayflow.task")


class TaskService:
    def create(self, session: Session, payload: TaskCreate) -> Task:
        try:
            category = self._resolve_category(session, payload.category_id)
            tags = self._resolve_tags(session, payload.tag_ids)
            task = Task(
                title=payload.title,
                description=payload.description,
                planned_date=payload.planned_date,
                priority=payload.priority.value,
                category=category,
                tags=tags,
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
        tag_id: str | None = None,
    ) -> list[Task]:
        statement = (
            select(Task)
            .options(selectinload(Task.category), selectinload(Task.tags))
            .where(Task.deleted_at_utc.is_(None))
        )
        if planned_date is not None:
            statement = statement.where(Task.planned_date == planned_date)
        if inbox:
            statement = statement.where(
                Task.planned_date.is_(None),
                Task.status == TaskStatus.PENDING.value,
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
        if tag_id is not None:
            statement = statement.join(
                task_tags, task_tags.c.task_id == Task.id
            ).where(task_tags.c.tag_id == tag_id)

        statement = statement.order_by(
            case((Task.status == TaskStatus.PENDING.value, 0), else_=1),
            Task.planned_date.is_(None),
            Task.created_at_utc,
        )
        return list(session.scalars(statement).unique().all())

    def today(self, session: Session, target_date: date) -> list[Task]:
        return self.list(session, target_date)

    def get(self, session: Session, task_id: str) -> Task:
        task = session.scalar(
            select(Task)
            .options(selectinload(Task.category), selectinload(Task.tags))
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
    ) -> Task:
        try:
            task = self.get(session, task_id)
            self._check_version(task, expected_version)
            changes = payload.model_dump(exclude_unset=True)
            if not changes:
                return task

            category_requested = "category_id" in changes
            tag_ids_requested = "tag_ids" in changes
            category = (
                self._resolve_category(session, changes["category_id"])
                if category_requested
                else None
            )
            tags = (
                self._resolve_tags(session, changes["tag_ids"] or [])
                if tag_ids_requested
                else None
            )

            changed = False
            for field in ("title", "description", "planned_date", "priority"):
                if field not in changes:
                    continue
                value = changes[field]
                if isinstance(value, TaskPriority):
                    value = value.value
                if getattr(task, field) != value:
                    setattr(task, field, value)
                    changed = True

            if category_requested:
                category_id = category.id if category is not None else None
                if task.category_id != category_id:
                    task.category = category
                    changed = True

            if tag_ids_requested:
                requested_tag_ids = {tag.id for tag in tags or []}
                current_tag_ids = {tag.id for tag in task.tags}
                if requested_tag_ids != current_tag_ids:
                    task.tags = tags or []
                    changed = True

            if not changed:
                return task
            self._touch(task)
            self._commit(session, "update task", (task.id, expected_version))
            session.refresh(task)
            return task
        except Exception:
            session.rollback()
            raise

    def complete(self, session: Session, task_id: str, expected_version: int) -> Task:
        task = self.get(session, task_id)
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
            .options(selectinload(Task.category), selectinload(Task.tags))
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
    def _resolve_category(session: Session, category_id) -> Category | None:
        if category_id is None:
            return None
        resolved_id = str(category_id)
        category = session.get(Category, resolved_id)
        if category is None:
            raise CategoryNotFoundError(resolved_id)
        return category

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
