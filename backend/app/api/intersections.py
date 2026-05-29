from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.cache import get_cache
from app.db.session import get_db
from app.repositories.intersection_repository import IntersectionRepository
from app.schemas import IntersectionCreate, IntersectionRead

router = APIRouter()


@router.get("", response_model=list[IntersectionRead])
def list_intersections(db: Session = Depends(get_db)):
    cache = get_cache()
    cache_key = "intersections:list"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    intersections = [
        IntersectionRead.model_validate(intersection).model_dump(mode="json")
        for intersection in IntersectionRepository(db).list()
    ]
    cache.set_json(cache_key, intersections)
    return intersections


@router.post(
    "",
    response_model=IntersectionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_intersection(payload: IntersectionCreate, db: Session = Depends(get_db)):
    intersection = IntersectionRepository(db).create(payload)
    cache = get_cache()
    cache.delete_prefix("intersections:")
    cache.delete_prefix("dashboard:summary:")
    return intersection


@router.get("/{intersection_id}", response_model=IntersectionRead)
def get_intersection(intersection_id: UUID, db: Session = Depends(get_db)):
    cache = get_cache()
    cache_key = f"intersections:{intersection_id}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    intersection = IntersectionRepository(db).get(intersection_id)
    if not intersection:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Intersection not found")
    payload = IntersectionRead.model_validate(intersection).model_dump(mode="json")
    cache.set_json(cache_key, payload)
    return payload
