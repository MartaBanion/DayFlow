from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.config import get_settings
from app.schemas.review import ReviewRead, ReviewScope
from app.services.review_service import ReviewService

router = APIRouter(prefix="/api/v1", tags=["review"])
service = ReviewService()


@router.get("/review", response_model=ReviewRead)
def get_review(
    scope: ReviewScope = Query(),
    session: Session = Depends(db_session),
) -> ReviewRead:
    return service.get(session, scope, get_settings().timezone)
