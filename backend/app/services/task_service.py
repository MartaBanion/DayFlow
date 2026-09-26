from __future__ import annotations

from datetime import date
import logging

from sqlalchemy import case, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import TaskNotFoundError, TaskVersionConflictError
from app.core.time import utc_now
from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate

logger = logging.getLogger("dayflow.task")


class TaskService:
    def create(self, session: Session, payload: TaskCreate) -> Task:
        task = Task(
            title=payload.title,
            description=payload.description,
            planned_date=payload.planned_date,
        )
        session.add(task)
        self._commit(session, "create task")
        session.refresh(task)
        return task

    def list(self, session: Session, planned_date: date | None = None) -> list[Task]:
        statement = select(Task).where(Task.deleted_at_utc.is_(None))
        if planned_date is not None:
            statement = statement.where(Task.planned_date == planned_date)
        statement = statement.order_by(
            case((Task.status == TaskStatus.PENDING.value, 0), else_=1),
            Task.planned_date.is_(None),
            Task.created_at_utc,
        )
        return list(session.scalars(statement).all())

    def today(self, session: Session, target_date: date) -> list[Task]:
        return self.list(session, target_date)

    def get(self, session: Session, task_id: str) -> Task:
        task = session.scalar(
            select(Task).where(Task.id == task_id, Task.deleted_at_utc.is_(None))
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
        task = self.get(session, task_id)
        self._check_version(task, expected_version)
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            return task
        for field, value in changes.items():
            setattr(task, field, value)
        self._touch(task)
        self._commit(session, "update task")
        session.refresh(task)
        return task

    def complete(self, session: Session, task_id: str, expected_version: int) -> Task:
        task = self.get(session, task_id)
        self._check_version(task, expected_version)
        if task.status == TaskStatus.COMPLETED.value:
            return task
        task.status = TaskStatus.COMPLETED.value
        task.completed_at_utc = utc_now()
        self._touch(task)
        self._commit(session, "complete task")
        session.refresh(task)
        return task

    def restore(self, session: Session, task_id: str, expected_version: int) -> Task:
        task = session.scalar(select(Task).where(Task.id == task_id))
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
        self._commit(session, "restore task")
        session.refresh(task)
        return task

    def soft_delete(self, session: Session, task_id: str, expected_version: int) -> None:
        task = self.get(session, task_id)
        self._check_version(task, expected_version)
        task.deleted_at_utc = utc_now()
        self._touch(task)
        self._commit(session, "soft delete task")

    @staticmethod
    def _check_version(task: Task, expected_version: int) -> None:
        if task.version != expected_version:
            raise TaskVersionConflictError(task.id, expected_version, task.version)

    @staticmethod
    def _touch(task: Task) -> None:
        task.version += 1
        task.updated_at_utc = utc_now()

    @staticmethod
    def _commit(session: Session, operation: str) -> None:
        try:
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception("Database transaction rolled back during %s", operation)
            raise
