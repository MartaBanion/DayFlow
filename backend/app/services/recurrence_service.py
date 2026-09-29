from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import get_settings
from app.core.errors import (
    RecurrenceRuleConflictError,
    RecurrenceRuleNotFoundError,
    RecurrenceValidationError,
    RecurrenceVersionConflictError,
    TaskNotFoundError,
    TaskVersionConflictError,
)
from app.core.schedule import resolve_timezone
from app.core.time import today_in_timezone, utc_now
from app.models.recurrence import RecurrenceFrequency, RecurrenceRule
from app.models.task import Task, TaskStatus
from app.schemas.recurrence import (
    RecurrenceCreate,
    RecurrenceFrequencyValue,
    RecurrenceUpdate,
)

logger = logging.getLogger("dayflow.recurrence")


class RecurrenceService:
    def create(
        self,
        session: Session,
        task_id: str,
        payload: RecurrenceCreate,
    ) -> RecurrenceRule:
        try:
            task = self._get_task(session, task_id, include_deleted=False)
            self._check_task_version(task, payload.version)
            if task.planned_date is None:
                raise RecurrenceValidationError("a recurring Task requires planned_date")
            if task.start_at_utc is not None:
                raise RecurrenceValidationError(
                    "repeating Time Blocks are not supported"
                )
            if task.status != TaskStatus.PENDING.value:
                raise RecurrenceValidationError(
                    "a recurrence rule can only be attached to a pending Task"
                )
            if task.recurrence_rule_id is not None:
                raise RecurrenceRuleConflictError("the Task already has a recurrence rule")

            frequency, weekdays_mask, month_day, starts_on, timezone_name = (
                self._normalize_values(payload)
            )
            if starts_on > task.planned_date:
                raise RecurrenceValidationError(
                    "starts_on cannot be later than the Task planned_date"
                )
            rule = RecurrenceRule(
                frequency=frequency,
                weekdays_mask=weekdays_mask,
                month_day=month_day,
                starts_on=starts_on,
                timezone=timezone_name,
            )
            session.add(rule)
            session.flush()
            task.recurrence_rule_id = rule.id
            task.recurrence_occurrence_date = task.planned_date
            self._touch_task(task)
            session.commit()
            session.refresh(rule)
            return rule
        except StaleDataError as error:
            session.rollback()
            actual = session.scalar(select(Task.version).where(Task.id == task_id))
            raise TaskVersionConflictError(task_id, payload.version, actual or -1) from error
        except Exception:
            session.rollback()
            raise

    def get(self, session: Session, rule_id: str) -> RecurrenceRule:
        rule = session.get(RecurrenceRule, rule_id)
        if rule is None:
            raise RecurrenceRuleNotFoundError(rule_id)
        return rule

    def update(
        self,
        session: Session,
        rule_id: str,
        expected_version: int,
        payload: RecurrenceUpdate,
    ) -> RecurrenceRule:
        try:
            rule = self.get(session, rule_id)
            self._check_rule_version(rule, expected_version)
            if rule.stopped_at_utc is not None:
                raise RecurrenceRuleConflictError("a stopped recurrence rule cannot be edited")

            changes = payload.model_dump(exclude_unset=True)
            if not changes:
                return rule
            values = {
                "frequency": rule.frequency,
                "weekdays": self._decode_weekdays(rule.weekdays_mask),
                "month_day": rule.month_day,
                "starts_on": rule.starts_on,
                "timezone": rule.timezone,
            }
            values.update(changes)
            frequency, weekdays_mask, month_day, starts_on, timezone_name = (
                self._normalize_values_dict(values)
            )
            rule.frequency = frequency
            rule.weekdays_mask = weekdays_mask
            rule.month_day = month_day
            rule.starts_on = starts_on
            rule.timezone = timezone_name
            self._touch_rule(rule)
            self._commit_rule(session, rule, expected_version)
            session.refresh(rule)
            return rule
        except Exception:
            session.rollback()
            raise

    def stop(
        self,
        session: Session,
        rule_id: str,
        expected_version: int,
    ) -> RecurrenceRule:
        try:
            rule = self.get(session, rule_id)
            self._check_rule_version(rule, expected_version)
            if rule.stopped_at_utc is None:
                rule.stopped_at_utc = utc_now()
                self._touch_rule(rule)
                self._commit_rule(session, rule, expected_version)
                session.refresh(rule)
            return rule
        except Exception:
            session.rollback()
            raise

    def materialize(self, session: Session, rule_id: str) -> Task:
        try:
            rule = self.get(session, rule_id)
            pending = self._pending_occurrence(session, rule.id)
            if pending is not None:
                return pending
            if rule.stopped_at_utc is not None:
                raise RecurrenceRuleConflictError("a stopped recurrence rule cannot materialize")
            task = self._materialize_next_in_session(session, rule)
            session.commit()
            session.refresh(task)
            return task
        except IntegrityError as error:
            session.rollback()
            raise RecurrenceRuleConflictError("occurrence creation conflicted; reload and retry") from error
        except Exception:
            session.rollback()
            raise

    def complete_occurrence(
        self,
        session: Session,
        task_id: str,
        expected_version: int,
    ) -> Task:
        try:
            task = self._get_task(session, task_id, include_deleted=False)
            self._check_task_version(task, expected_version)
            if task.recurrence_rule_id is None:
                raise RecurrenceValidationError("Task is not a recurrence occurrence")
            if task.status == TaskStatus.COMPLETED.value:
                return task
            task.status = TaskStatus.COMPLETED.value
            task.completed_at_utc = utc_now()
            self._touch_task(task)
            session.flush()
            rule = session.get(RecurrenceRule, task.recurrence_rule_id)
            if rule is not None and rule.stopped_at_utc is None:
                self._materialize_next_in_session(session, rule)
            session.commit()
            session.refresh(task)
            return task
        except StaleDataError as error:
            session.rollback()
            actual = session.scalar(select(Task.version).where(Task.id == task_id))
            raise TaskVersionConflictError(task_id, expected_version, actual or -1) from error
        except IntegrityError as error:
            session.rollback()
            raise RecurrenceRuleConflictError("occurrence creation conflicted; reload and retry") from error
        except Exception:
            session.rollback()
            raise

    def skip_occurrence(
        self,
        session: Session,
        task_id: str,
        expected_version: int,
    ) -> Task:
        try:
            task = self._get_task(session, task_id, include_deleted=False)
            self._check_task_version(task, expected_version)
            if task.recurrence_rule_id is None:
                raise RecurrenceValidationError("Task is not a recurrence occurrence")
            task.deleted_at_utc = utc_now()
            self._touch_task(task)
            session.flush()
            rule = session.get(RecurrenceRule, task.recurrence_rule_id)
            if rule is not None and rule.stopped_at_utc is None:
                self._materialize_next_in_session(session, rule)
            session.commit()
            session.refresh(task)
            return task
        except StaleDataError as error:
            session.rollback()
            actual = session.scalar(select(Task.version).where(Task.id == task_id))
            raise TaskVersionConflictError(task_id, expected_version, actual or -1) from error
        except IntegrityError as error:
            session.rollback()
            raise RecurrenceRuleConflictError("occurrence creation conflicted; reload and retry") from error
        except Exception:
            session.rollback()
            raise

    def _materialize_next_in_session(
        self,
        session: Session,
        rule: RecurrenceRule,
    ) -> Task:
        pending = self._pending_occurrence(session, rule.id)
        if pending is not None:
            return pending
        # Claim the rule version before generation so a concurrent stop/edit
        # or materialize cannot silently use an obsolete rule snapshot.
        expected_rule_version = rule.version
        rule_id = rule.id
        self._touch_rule(rule)
        try:
            session.flush()
        except StaleDataError as error:
            session.rollback()
            actual = session.scalar(select(RecurrenceRule.version).where(RecurrenceRule.id == rule_id))
            raise RecurrenceVersionConflictError(rule_id, expected_rule_version, actual or -1) from error
        latest = session.scalar(
            select(Task)
            .options(selectinload(Task.tags), selectinload(Task.project))
            .where(
                Task.recurrence_rule_id == rule.id,
                Task.recurrence_occurrence_date.is_not(None),
            )
            .order_by(Task.recurrence_occurrence_date.desc(), Task.created_at_utc.desc())
        )
        if latest is None or latest.recurrence_occurrence_date is None:
            raise RecurrenceRuleConflictError("recurrence rule has no occurrence history")
        today = today_in_timezone(rule.timezone)
        base_date = max(latest.recurrence_occurrence_date, today)
        if rule.starts_on > base_date:
            base_date = rule.starts_on - timedelta(days=1)
        candidate = self._next_date(rule, base_date)
        for _ in range(3661):
            represented = session.scalar(
                select(Task.id).where(
                    Task.recurrence_rule_id == rule.id,
                    Task.recurrence_occurrence_date == candidate,
                )
            )
            if represented is None:
                break
            candidate = self._next_date(rule, candidate)
        else:
            raise RecurrenceRuleConflictError("could not find a free future occurrence date")

        project_id = None
        if latest.project is not None and latest.project.deleted_at_utc is None:
            project_id = latest.project_id
        task = Task(
            title=latest.title,
            description=latest.description,
            planned_date=candidate,
            priority=latest.priority,
            category_id=latest.category_id,
            project_id=project_id,
            tags=list(latest.tags),
            recurrence_rule_id=rule.id,
            recurrence_occurrence_date=candidate,
        )
        session.add(task)
        session.flush()
        return task

    @staticmethod
    def _normalize_values(payload: RecurrenceCreate):
        return RecurrenceService._normalize_values_dict(payload.model_dump())

    @staticmethod
    def _normalize_values_dict(values: dict[str, object]):
        frequency = values.get("frequency")
        frequency_value = frequency.value if isinstance(frequency, RecurrenceFrequencyValue) else str(frequency)
        if frequency_value not in {item.value for item in RecurrenceFrequency}:
            raise RecurrenceValidationError("frequency must be daily, weekly, or monthly")
        starts_on = values.get("starts_on")
        if not isinstance(starts_on, date):
            raise RecurrenceValidationError("starts_on must be a valid date")
        timezone_name = values.get("timezone") or get_settings().timezone
        if not isinstance(timezone_name, str):
            raise RecurrenceValidationError("timezone must be a valid IANA timezone")
        try:
            resolve_timezone(timezone_name)
        except Exception as error:
            raise RecurrenceValidationError(str(error)) from error

        weekdays = values.get("weekdays")
        month_day = values.get("month_day")
        if frequency_value == RecurrenceFrequency.DAILY.value:
            if weekdays is not None or month_day is not None:
                raise RecurrenceValidationError("daily rules do not accept selectors")
            return frequency_value, None, None, starts_on, timezone_name.strip()
        if frequency_value == RecurrenceFrequency.WEEKLY.value:
            if not isinstance(weekdays, list) or not weekdays:
                raise RecurrenceValidationError("weekly rules require weekdays")
            if len(weekdays) != len(set(weekdays)) or any(
                not isinstance(day, int) or day < 0 or day > 6 for day in weekdays
            ):
                raise RecurrenceValidationError("weekdays must contain unique values from 0 through 6")
            if month_day is not None:
                raise RecurrenceValidationError("weekly rules do not accept month_day")
            return frequency_value, RecurrenceService._encode_weekdays(weekdays), None, starts_on, timezone_name.strip()
        if weekdays is not None:
            raise RecurrenceValidationError("monthly rules do not accept weekdays")
        if not isinstance(month_day, int) or not 1 <= month_day <= 28:
            raise RecurrenceValidationError("monthly month_day must be between 1 and 28")
        return frequency_value, None, month_day, starts_on, timezone_name.strip()

    @staticmethod
    def _encode_weekdays(weekdays: Iterable[int]) -> int:
        mask = 0
        for weekday in weekdays:
            mask |= 1 << weekday
        return mask

    @staticmethod
    def _decode_weekdays(mask: int | None) -> list[int] | None:
        if mask is None:
            return None
        return [weekday for weekday in range(7) if mask & (1 << weekday)]

    @staticmethod
    def _next_date(rule: RecurrenceRule, after_date: date) -> date:
        if rule.frequency == RecurrenceFrequency.DAILY.value:
            return after_date + timedelta(days=1)
        if rule.frequency == RecurrenceFrequency.WEEKLY.value:
            weekdays = set(RecurrenceService._decode_weekdays(rule.weekdays_mask) or [])
            for offset in range(1, 8):
                candidate = after_date + timedelta(days=offset)
                if candidate.weekday() in weekdays:
                    return candidate
            raise RecurrenceRuleConflictError("weekly rule has no valid weekday")
        month_day = rule.month_day
        if month_day is None:
            raise RecurrenceRuleConflictError("monthly rule has no month_day")
        year, month = after_date.year, after_date.month
        candidate = date(year, month, month_day)
        if candidate > after_date:
            return candidate
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
        return date(year, month, month_day)

    @staticmethod
    def _pending_occurrence(session: Session, rule_id: str) -> Task | None:
        return session.scalar(
            select(Task)
            .options(selectinload(Task.tags), selectinload(Task.project))
            .where(
                Task.recurrence_rule_id == rule_id,
                Task.status == TaskStatus.PENDING.value,
                Task.deleted_at_utc.is_(None),
            )
            .order_by(Task.recurrence_occurrence_date.desc())
        )

    @staticmethod
    def _get_task(session: Session, task_id: str, *, include_deleted: bool) -> Task:
        statement = (
            select(Task)
            .options(
                selectinload(Task.tags),
                selectinload(Task.project),
                selectinload(Task.category),
            )
            .where(Task.id == task_id)
        )
        if not include_deleted:
            statement = statement.where(Task.deleted_at_utc.is_(None))
        task = session.scalar(statement)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    @staticmethod
    def _touch_task(task: Task) -> None:
        task.version += 1
        task.updated_at_utc = utc_now()

    @staticmethod
    def _touch_rule(rule: RecurrenceRule) -> None:
        rule.version += 1
        rule.updated_at_utc = utc_now()

    @staticmethod
    def _check_task_version(task: Task, expected_version: int) -> None:
        if task.version != expected_version:
            raise TaskVersionConflictError(task.id, expected_version, task.version)

    @staticmethod
    def _check_rule_version(rule: RecurrenceRule, expected_version: int) -> None:
        if rule.version != expected_version:
            raise RecurrenceVersionConflictError(rule.id, expected_version, rule.version)

    @staticmethod
    def _commit_rule(session: Session, rule: RecurrenceRule, expected_version: int) -> None:
        try:
            session.commit()
        except StaleDataError:
            session.rollback()
            actual = session.scalar(select(RecurrenceRule.version).where(RecurrenceRule.id == rule.id))
            raise RecurrenceVersionConflictError(rule.id, expected_version, actual or -1)
        except (IntegrityError, SQLAlchemyError):
            session.rollback()
            logger.exception("Database transaction rolled back during recurrence mutation")
            raise
