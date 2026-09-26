from datetime import date as date_type
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.config import get_settings
from app.core.time import today_in_timezone
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate, TaskVersionRequest
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/v1", tags=["tasks"])
service = TaskService()


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, session: Session = Depends(db_session)) -> TaskRead:
    return service.create(session, payload)


@router.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    planned_date: date_type | None = None,
    session: Session = Depends(db_session),
) -> list[TaskRead]:
    return service.list(session, planned_date)


@router.get("/today", response_model=list[TaskRead])
def today_tasks(
    target_date: date_type | None = Query(default=None, alias="date"),
    session: Session = Depends(db_session),
) -> list[TaskRead]:
    target_date = target_date or today_in_timezone(get_settings().timezone)
    return service.today(session, target_date)


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, session: Session = Depends(db_session)) -> TaskRead:
    return service.get(session, str(task_id))


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    version: int,
    session: Session = Depends(db_session),
) -> TaskRead:
    return service.update(session, str(task_id), version, payload)


@router.post("/tasks/{task_id}/complete", response_model=TaskRead)
def complete_task(
    task_id: UUID,
    payload: TaskVersionRequest,
    session: Session = Depends(db_session),
) -> TaskRead:
    return service.complete(session, str(task_id), payload.version)


@router.post("/tasks/{task_id}/restore", response_model=TaskRead)
def restore_task(
    task_id: UUID,
    payload: TaskVersionRequest,
    session: Session = Depends(db_session),
) -> TaskRead:
    return service.restore(session, str(task_id), payload.version)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    payload: TaskVersionRequest,
    session: Session = Depends(db_session),
) -> Response:
    service.soft_delete(session, str(task_id), payload.version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
