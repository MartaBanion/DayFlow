from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.schemas.backup import BackupRead, BackupVerification
from app.services.backup_service import BackupService

router = APIRouter(prefix="/api/v1/backups", tags=["backups"])


def backup_service(settings: Settings = Depends(get_settings)) -> BackupService:
    return BackupService(settings.resolved_database_path, settings.backup_root, settings.app_version)


def allowed_origin(request: Request, settings: Settings = Depends(get_settings)) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        return
    configured = urlsplit(settings.frontend_origin)
    # Permit localhost/127.0.0.1 aliases only for the configured Frontend port.
    allowed = {settings.frontend_origin}
    if configured.scheme == "http" and configured.hostname in ("localhost", "127.0.0.1"):
        port = configured.port or 80
        allowed.update(f"http://{host}:{port}" for host in ("localhost", "127.0.0.1"))
    if origin not in allowed:
        raise AppError("backup_origin_rejected", "Request Origin is not allowed", 403)


@router.get("", response_model=list[BackupRead])
def list_backups(service: BackupService = Depends(backup_service)) -> list[BackupRead]:
    return service.list()


@router.post("", response_model=BackupRead, status_code=201, dependencies=[Depends(allowed_origin)])
async def create_backup(request: Request, service: BackupService = Depends(backup_service)) -> BackupRead:
    if request.query_params or await request.body():
        raise AppError("backup_request_invalid", "Backup creation accepts no parameters or body", 422)
    # Keep blocking filesystem/SQLite work off the async request loop.
    return await run_in_threadpool(service.create)


@router.post("/{backup_id}/verify", response_model=BackupVerification, dependencies=[Depends(allowed_origin)])
def verify_backup(backup_id: str, service: BackupService = Depends(backup_service)) -> BackupVerification:
    return service.verify(backup_id)
