from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("dayflow.api")


@dataclass
class AppError(Exception):
    code: str
    message: str
    status_code: int
    details: Any = None

    def __post_init__(self) -> None:
        super().__init__(self.message)


class TaskNotFoundError(AppError):
    def __init__(self, task_id: str):
        super().__init__("task_not_found", f"Task '{task_id}' was not found", 404)


class TaskVersionConflictError(AppError):
    def __init__(self, task_id: str, expected: int, actual: int):
        super().__init__(
            "task_version_conflict",
            "Task changed since it was loaded; refresh before saving",
            409,
            {"task_id": task_id, "expected_version": expected, "actual_version": actual},
        )


class ProjectNotFoundError(AppError):
    def __init__(self, project_id: str):
        super().__init__(
            "project_not_found", f"Project '{project_id}' was not found", 404
        )


class ProjectVersionConflictError(AppError):
    def __init__(self, project_id: str, expected: int, actual: int):
        super().__init__(
            "project_version_conflict",
            "Project changed since it was loaded; refresh before saving",
            409,
            {
                "project_id": project_id,
                "expected_version": expected,
                "actual_version": actual,
            },
        )


class ProjectNameConflictError(AppError):
    def __init__(self, name: str):
        super().__init__(
            "project_name_conflict",
            f"A project named '{name}' already exists",
            409,
        )


class CategoryNotFoundError(AppError):
    def __init__(self, category_id: str):
        super().__init__(
            "category_not_found", f"Category '{category_id}' was not found", 404
        )


class TagNotFoundError(AppError):
    def __init__(self, tag_id: str):
        super().__init__("tag_not_found", f"Tag '{tag_id}' was not found", 404)


class CategoryNameConflictError(AppError):
    def __init__(self, name: str):
        super().__init__(
            "category_name_conflict",
            f"A category named '{name}' already exists",
            409,
        )


class TagNameConflictError(AppError):
    def __init__(self, name: str):
        super().__init__("tag_name_conflict", f"A tag named '{name}' already exists", 409)


class ScheduleValidationError(AppError):
    def __init__(self, message: str):
        super().__init__("schedule_validation_error", message, 422)


class ScheduleConflictError(AppError):
    def __init__(self, task_ids: list[str]):
        super().__init__(
            "schedule_conflict",
            "The requested time overlaps another task",
            409,
            {"task_ids": task_ids},
        )


class CalendarRangeError(AppError):
    def __init__(self, message: str):
        super().__init__("calendar_range_invalid", message, 422)


class DeadlineValidationError(AppError):
    def __init__(self, message: str):
        super().__init__("deadline_validation_error", message, 422)


class ReviewConfigurationError(AppError):
    def __init__(self):
        super().__init__(
            "review_configuration_error",
            "Review timezone configuration is invalid",
            500,
        )


class TaskQueryConfigurationError(AppError):
    def __init__(self):
        super().__init__(
            "task_query_configuration_error",
            "Task query timezone configuration is invalid",
            500,
        )


class RecurrenceValidationError(AppError):
    def __init__(self, message: str):
        super().__init__("recurrence_validation_error", message, 422)


class RecurrenceRuleNotFoundError(AppError):
    def __init__(self, rule_id: str):
        super().__init__("recurrence_rule_not_found", f"Recurrence rule '{rule_id}' was not found", 404)


class RecurrenceRuleConflictError(AppError):
    def __init__(self, message: str, details: Any = None):
        super().__init__("recurrence_rule_conflict", message, 409, details)


class RecurrenceVersionConflictError(AppError):
    def __init__(self, rule_id: str, expected: int, actual: int):
        super().__init__(
            "recurrence_version_conflict",
            "The recurrence rule changed since it was loaded; refresh before saving",
            409,
            {"rule_id": rule_id, "expected_version": expected, "actual_version": actual},
        )


class ReminderValidationError(AppError):
    def __init__(self, message: str):
        super().__init__("reminder_validation_error", message, 422)


class ReminderNotFoundError(AppError):
    def __init__(self, reminder_id: str):
        super().__init__("reminder_not_found", f"Reminder '{reminder_id}' was not found", 404)


class ReminderVersionConflictError(AppError):
    def __init__(self, reminder_id: str, expected: int, actual: int):
        super().__init__(
            "reminder_version_conflict",
            "The Reminder changed since it was loaded; refresh before saving",
            409,
            {"reminder_id": reminder_id, "expected_version": expected, "actual_version": actual},
        )


class ReminderStateError(AppError):
    def __init__(self, message: str):
        super().__init__("reminder_state_conflict", message, 409)


def error_response(code: str, message: str, details: Any = None, status_code: int = 500) -> JSONResponse:
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=payload)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.code, exc.message, exc.details, exc.status_code)


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = []
    for error in exc.errors():
        normalized = dict(error)
        if "ctx" in normalized:
            normalized["ctx"] = {
                key: str(value) for key, value in normalized["ctx"].items()
            }
        details.append(normalized)
    return error_response("validation_error", "Request validation failed", details, 422)


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Unhandled database error for %s %s", request.method, request.url.path)
    return error_response("database_error", "The database operation failed", status_code=500)


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error for %s %s", request.method, request.url.path)
    return error_response("internal_error", "An unexpected error occurred", status_code=500)
