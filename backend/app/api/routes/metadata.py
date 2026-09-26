from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.task import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    TagCreate,
    TagRead,
    TagUpdate,
)
from app.services.task_service import TaskService


router = APIRouter(prefix="/api/v1", tags=["organization"])
service = TaskService()


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(session: Session = Depends(db_session)) -> list[CategoryRead]:
    return service.list_categories(session)


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: CategoryCreate, session: Session = Depends(db_session)
) -> CategoryRead:
    return service.create_category(session, payload)


@router.patch("/categories/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    session: Session = Depends(db_session),
) -> CategoryRead:
    return service.update_category(session, str(category_id), payload)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID, session: Session = Depends(db_session)
) -> Response:
    service.delete_category(session, str(category_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tags", response_model=list[TagRead])
def list_tags(session: Session = Depends(db_session)) -> list[TagRead]:
    return service.list_tags(session)


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, session: Session = Depends(db_session)) -> TagRead:
    return service.create_tag(session, payload)


@router.patch("/tags/{tag_id}", response_model=TagRead)
def update_tag(
    tag_id: UUID,
    payload: TagUpdate,
    session: Session = Depends(db_session),
) -> TagRead:
    return service.update_tag(session, str(tag_id), payload)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: UUID, session: Session = Depends(db_session)) -> Response:
    service.delete_tag(session, str(tag_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
