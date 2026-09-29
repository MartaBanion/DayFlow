from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.recurrence import (
    RecurrenceCreate,
    RecurrenceRead,
    RecurrenceUpdate,
    RecurrenceVersionRequest,
)
from app.schemas.task import TaskRead
from app.services.recurrence_service import RecurrenceService
from app.services.task_service import TaskService


router = APIRouter(prefix="/api/v1", tags=["recurrence"])
service = RecurrenceService()
task_service = TaskService()


def _read(rule) -> RecurrenceRead:
    return RecurrenceRead(
        id=rule.id,
        frequency=rule.frequency,
        weekdays=service._decode_weekdays(rule.weekdays_mask),
        month_day=rule.month_day,
        starts_on=rule.starts_on,
        timezone=rule.timezone,
        stopped_at_utc=rule.stopped_at_utc,
        created_at_utc=rule.created_at_utc,
        updated_at_utc=rule.updated_at_utc,
        version=rule.version,
    )


@router.post(
    "/tasks/{task_id}/recurrence",
    response_model=RecurrenceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_recurrence(
    task_id: UUID,
    payload: RecurrenceCreate,
    session: Session = Depends(db_session),
) -> RecurrenceRead:
    return _read(service.create(session, str(task_id), payload))


@router.get("/recurrence-rules/{rule_id}", response_model=RecurrenceRead)
def get_recurrence(
    rule_id: UUID,
    session: Session = Depends(db_session),
) -> RecurrenceRead:
    return _read(service.get(session, str(rule_id)))


@router.patch("/recurrence-rules/{rule_id}", response_model=RecurrenceRead)
def update_recurrence(
    rule_id: UUID,
    payload: RecurrenceUpdate,
    version: int,
    session: Session = Depends(db_session),
) -> RecurrenceRead:
    return _read(service.update(session, str(rule_id), version, payload))


@router.post("/recurrence-rules/{rule_id}/stop", response_model=RecurrenceRead)
def stop_recurrence(
    rule_id: UUID,
    payload: RecurrenceVersionRequest,
    session: Session = Depends(db_session),
) -> RecurrenceRead:
    return _read(service.stop(session, str(rule_id), payload.version))


@router.post("/recurrence-rules/{rule_id}/materialize", response_model=TaskRead)
def materialize_recurrence(
    rule_id: UUID,
    session: Session = Depends(db_session),
) -> TaskRead:
    return service.materialize(session, str(rule_id))


@router.post("/tasks/{task_id}/skip", response_model=TaskRead)
def skip_task(
    task_id: UUID,
    payload: RecurrenceVersionRequest,
    session: Session = Depends(db_session),
) -> TaskRead:
    return service.skip_occurrence(session, str(task_id), payload.version)
