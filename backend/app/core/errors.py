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
