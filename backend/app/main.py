from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.tasks import router as task_router
from app.api.routes.metadata import router as metadata_router
from app.api.routes.projects import router as project_router
from app.api.routes.recurrence import router as recurrence_router
from app.api.routes.reminders import router as reminder_router
from app.api.routes.review import router as review_router
from app.api.routes.runtime import router as runtime_router
from app.api.routes.backups import router as backup_router
from app.core.config import get_settings
from app.core.errors import (
    AppError,
    app_error_handler,
    database_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging
from app.core.maintenance import MaintenanceSafety
from app.db.session import database_lifetime
from app.services.backup_service import BackupService
from app.services.recovery_service import RecoveryService
from app.services.restore_service import RestoreService

settings = get_settings()
configure_logging(settings.log_level)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    runtime_settings = get_settings()
    safety = MaintenanceSafety(runtime_settings.maintenance_root, runtime_settings.app_version)
    recovery = RecoveryService(RestoreService(BackupService(
        runtime_settings.resolved_database_path,
        runtime_settings.backup_root,
        runtime_settings.app_version,
    )))
    with recovery.backend_usage():
        try:
            with database_lifetime(runtime_settings.database_url):
                yield
        except Exception:
            # Failure to drain/dispose must not silently admit a Restore.
            safety.block_shutdown()
            raise


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(SQLAlchemyError, database_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)
app.include_router(task_router)
app.include_router(metadata_router)
app.include_router(project_router)
app.include_router(recurrence_router)
app.include_router(reminder_router)
app.include_router(review_router)
app.include_router(runtime_router)
app.include_router(backup_router)


@app.get("/healthz", tags=["system"])
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
