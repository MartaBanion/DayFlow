from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.reminder import (
    ReminderCreate,
    ReminderRead,
    ReminderUpdate,
    ReminderVersionRequest,
)
from app.services.reminder_service import ReminderService


router = APIRouter(prefix="/api/v1", tags=["reminders"])
service = ReminderService()


@router.get("/tasks/{task_id}/reminders", response_model=list[ReminderRead])
def list_reminders(
    task_id: UUID,
    session: Session = Depends(db_session),
) -> list[ReminderRead]:
    return service.list_for_task(session, str(task_id))


@router.post(
    "/tasks/{task_id}/reminders",
    response_model=ReminderRead,
    status_code=status.HTTP_201_CREATED,
)
def create_reminder(
    task_id: UUID,
    payload: ReminderCreate,
    session: Session = Depends(db_session),
) -> ReminderRead:
    return service.create(session, str(task_id), payload)


@router.get("/reminders/due", response_model=list[ReminderRead])
def due_reminders(session: Session = Depends(db_session)) -> list[ReminderRead]:
    return service.due(session)


@router.patch("/reminders/{reminder_id}", response_model=ReminderRead)
def update_reminder(
    reminder_id: UUID,
    payload: ReminderUpdate,
    version: int,
    session: Session = Depends(db_session),
) -> ReminderRead:
    return service.update(session, str(reminder_id), version, payload)


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: UUID,
    payload: ReminderVersionRequest,
    session: Session = Depends(db_session),
) -> Response:
    service.delete(session, str(reminder_id), payload.version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reminders/{reminder_id}/acknowledge", response_model=ReminderRead)
def acknowledge_reminder(
    reminder_id: UUID,
    payload: ReminderVersionRequest,
    session: Session = Depends(db_session),
) -> ReminderRead:
    return service.acknowledge(session, str(reminder_id), payload.version)


@router.post("/reminders/{reminder_id}/dismiss", response_model=ReminderRead)
def dismiss_reminder(
    reminder_id: UUID,
    payload: ReminderVersionRequest,
    session: Session = Depends(db_session),
) -> ReminderRead:
    return service.dismiss(session, str(reminder_id), payload.version)
