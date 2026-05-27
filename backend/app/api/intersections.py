from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.db.session import get_db
from app.repositories.intersection_repository import IntersectionRepository
from app.schemas import IntersectionCreate, IntersectionRead

router = APIRouter()


@router.get("", response_model=list[IntersectionRead])
def list_intersections(db: Session = Depends(get_db)):
    return IntersectionRepository(db).list()


@router.post(
    "",
    response_model=IntersectionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_intersection(payload: IntersectionCreate, db: Session = Depends(get_db)):
    return IntersectionRepository(db).create(payload)


@router.get("/{intersection_id}", response_model=IntersectionRead)
def get_intersection(intersection_id: UUID, db: Session = Depends(get_db)):
    intersection = IntersectionRepository(db).get(intersection_id)
    if not intersection:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Intersection not found")
    return intersection
