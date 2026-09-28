from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectStatusValue,
    ProjectUpdate,
    ProjectVersionRequest,
)
from app.services.project_service import ProjectService, ProjectView


router = APIRouter(prefix="/api/v1", tags=["projects"])
service = ProjectService()


def _project_read(view: ProjectView) -> ProjectRead:
    project = view.project
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_at_utc=project.created_at_utc,
        updated_at_utc=project.updated_at_utc,
        completed_at_utc=project.completed_at_utc,
        deleted_at_utc=project.deleted_at_utc,
        version=project.version,
        task_count=view.task_count,
        completed_task_count=view.completed_task_count,
        progress_percent=view.progress_percent,
    )


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(
    status: ProjectStatusValue | None = Query(default=None),
    session: Session = Depends(db_session),
) -> list[ProjectRead]:
    return [_project_read(view) for view in service.list(session, status)]


@router.post(
    "/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(db_session),
) -> ProjectRead:
    return _project_read(service.create(session, payload))


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: UUID,
    session: Session = Depends(db_session),
) -> ProjectRead:
    return _project_read(service.get(session, str(project_id)))


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    version: int,
    session: Session = Depends(db_session),
) -> ProjectRead:
    return _project_read(service.update(session, str(project_id), version, payload))


@router.post("/projects/{project_id}/complete", response_model=ProjectRead)
def complete_project(
    project_id: UUID,
    payload: ProjectVersionRequest,
    session: Session = Depends(db_session),
) -> ProjectRead:
    return _project_read(service.complete(session, str(project_id), payload.version))


@router.post("/projects/{project_id}/reopen", response_model=ProjectRead)
def reopen_project(
    project_id: UUID,
    payload: ProjectVersionRequest,
    session: Session = Depends(db_session),
) -> ProjectRead:
    return _project_read(service.reopen(session, str(project_id), payload.version))


@router.post("/projects/{project_id}/restore", response_model=ProjectRead)
def restore_project(
    project_id: UUID,
    payload: ProjectVersionRequest,
    session: Session = Depends(db_session),
) -> ProjectRead:
    return _project_read(service.restore(session, str(project_id), payload.version))


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    payload: ProjectVersionRequest,
    session: Session = Depends(db_session),
) -> Response:
    service.soft_delete(session, str(project_id), payload.version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
