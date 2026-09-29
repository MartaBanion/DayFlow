from __future__ import annotations

from datetime import date, datetime, time
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import get_settings
from app.core.errors import (
    ReminderNotFoundError,
    ReminderStateError,
    ReminderValidationError,
    ReminderVersionConflictError,
    TaskNotFoundError,
)
from app.core.schedule import _local_to_utc, resolve_timezone
from app.core.time import utc_now
from app.models.reminder import Reminder, ReminderStatus
from app.models.task import Task, TaskStatus
from app.schemas.reminder import ReminderCreate, ReminderUpdate

logger = logging.getLogger("dayflow.reminder")


class ReminderService:
    def list_for_task(self, session: Session, task_id: str) -> list[Reminder]:
        self._get_task(session, task_id)
        return list(
            session.scalars(
                select(Reminder)
                .where(Reminder.task_id == task_id)
                .order_by(Reminder.trigger_at_utc, Reminder.created_at_utc)
            ).all()
        )

    def create(
        self,
        session: Session,
        task_id: str,
        payload: ReminderCreate,
    ) -> Reminder:
        try:
            self._get_task(session, task_id)
            trigger_at_utc, timezone_name = self._trigger_from_value(
                payload.date, payload.time, payload.timezone
            )
            reminder = Reminder(
                task_id=task_id,
                trigger_at_utc=trigger_at_utc,
                reminder_timezone=timezone_name,
            )
            session.add(reminder)
            session.commit()
            session.refresh(reminder)
            return reminder
        except Exception:
            session.rollback()
            raise

    def update(
        self,
        session: Session,
        reminder_id: str,
        expected_version: int,
        payload: ReminderUpdate,
    ) -> Reminder:
        try:
            reminder = self.get(session, reminder_id)
            self._check_version(reminder, expected_version)
            trigger_at_utc, timezone_name = self._trigger_from_value(
                payload.date, payload.time, payload.timezone
            )
            if (
                reminder.trigger_at_utc == trigger_at_utc
                and reminder.reminder_timezone == timezone_name
                and reminder.status == ReminderStatus.PENDING.value
            ):
                return reminder
            reminder.trigger_at_utc = trigger_at_utc
            reminder.reminder_timezone = timezone_name
            reminder.status = ReminderStatus.PENDING.value
            reminder.acknowledged_at_utc = None
            reminder.dismissed_at_utc = None
            self._touch(reminder)
            self._commit(session, reminder, expected_version)
            session.refresh(reminder)
            return reminder
        except Exception:
            session.rollback()
            raise

    def get(self, session: Session, reminder_id: str) -> Reminder:
        reminder = session.get(Reminder, reminder_id)
        if reminder is None:
            raise ReminderNotFoundError(reminder_id)
        return reminder

    def due(self, session: Session) -> list[Reminder]:
        # This query deliberately has no flush, update, or commit side effect.
        return list(
            session.scalars(
                select(Reminder)
                .join(Task, Task.id == Reminder.task_id)
                .where(
                    Reminder.status == ReminderStatus.PENDING.value,
                    Reminder.trigger_at_utc <= utc_now(),
                    Task.status == TaskStatus.PENDING.value,
                    Task.deleted_at_utc.is_(None),
                )
                .options(selectinload(Reminder.task))
                .order_by(Reminder.trigger_at_utc, Reminder.created_at_utc)
            ).all()
        )

    def acknowledge(
        self,
        session: Session,
        reminder_id: str,
        expected_version: int,
    ) -> Reminder:
        return self._transition(
            session,
            reminder_id,
            expected_version,
            ReminderStatus.ACKNOWLEDGED.value,
        )

    def dismiss(
        self,
        session: Session,
        reminder_id: str,
        expected_version: int,
    ) -> Reminder:
        return self._transition(
            session,
            reminder_id,
            expected_version,
            ReminderStatus.DISMISSED.value,
        )

    def delete(self, session: Session, reminder_id: str, expected_version: int) -> None:
        try:
            reminder = self.get(session, reminder_id)
            self._check_version(reminder, expected_version)
            session.delete(reminder)
            self._commit(session, reminder, expected_version)
        except Exception:
            session.rollback()
            raise

    def _transition(
        self,
        session: Session,
        reminder_id: str,
        expected_version: int,
        status: str,
    ) -> Reminder:
        try:
            reminder = self.get(session, reminder_id)
            self._check_version(reminder, expected_version)
            if reminder.status != ReminderStatus.PENDING.value:
                raise ReminderStateError("only pending reminders can be acknowledged or dismissed")
            now = utc_now()
            reminder.status = status
            reminder.acknowledged_at_utc = now if status == ReminderStatus.ACKNOWLEDGED.value else None
            reminder.dismissed_at_utc = now if status == ReminderStatus.DISMISSED.value else None
            self._touch(reminder)
            self._commit(session, reminder, expected_version)
            session.refresh(reminder)
            return reminder
        except Exception:
            session.rollback()
            raise

    @staticmethod
    def _get_task(session: Session, task_id: str) -> Task:
        task = session.scalar(select(Task).where(Task.id == task_id, Task.deleted_at_utc.is_(None)))
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    @staticmethod
    def _trigger_from_value(
        trigger_date: date,
        trigger_time: time,
        timezone_name: str | None,
    ) -> tuple[datetime, str]:
        if trigger_time.tzinfo is not None and trigger_time.utcoffset() is not None:
            raise ReminderValidationError("Reminder time must not include a UTC offset")
        resolved_name = (timezone_name or get_settings().timezone).strip()
        try:
            zone = resolve_timezone(resolved_name)
            trigger_at_utc = _local_to_utc(
                datetime.combine(trigger_date, trigger_time), zone, "Reminder time"
            )
        except Exception as error:
            if isinstance(error, ReminderValidationError):
                raise
            raise ReminderValidationError(str(error)) from error
        return trigger_at_utc, resolved_name

    @staticmethod
    def _check_version(reminder: Reminder, expected_version: int) -> None:
        if reminder.version != expected_version:
            raise ReminderVersionConflictError(
                reminder.id, expected_version, reminder.version
            )

    @staticmethod
    def _touch(reminder: Reminder) -> None:
        reminder.version += 1
        reminder.updated_at_utc = utc_now()

    @staticmethod
    def _commit(session: Session, reminder: Reminder, expected_version: int) -> None:
        try:
            session.commit()
        except StaleDataError:
            session.rollback()
            actual = session.scalar(select(Reminder.version).where(Reminder.id == reminder.id))
            raise ReminderVersionConflictError(
                reminder.id, expected_version, actual or -1
            )
        except SQLAlchemyError:
            session.rollback()
            logger.exception("Database transaction rolled back during Reminder mutation")
            raise
