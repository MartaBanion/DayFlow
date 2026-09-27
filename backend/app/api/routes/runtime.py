from fastapi import APIRouter

from app.core.config import get_settings
from app.core.time import today_in_timezone
from app.schemas.runtime import RuntimeRead

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/runtime", response_model=RuntimeRead)
def runtime_info() -> RuntimeRead:
    settings = get_settings()
    return RuntimeRead(
        timezone=settings.timezone,
        local_date=today_in_timezone(settings.timezone),
    )
