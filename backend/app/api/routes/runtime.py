from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import db_session

from app.core.config import get_settings
from app.core.time import today_in_timezone
from app.schemas.runtime import RuntimeRead

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/runtime", response_model=RuntimeRead)
def runtime_info(session: Session = Depends(db_session)) -> RuntimeRead:
    settings = get_settings()
    return RuntimeRead(
        timezone=settings.timezone,
        local_date=today_in_timezone(settings.timezone),
        app_version=settings.app_version,
        database_schema=session.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none(),
    )
