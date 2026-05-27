from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.db.session import get_db
from app.schemas import TrafficObservationCreate, TrafficObservationRead
from app.services.traffic_service import TrafficService

router = APIRouter()


@router.get("/observations", response_model=list[TrafficObservationRead])
def latest_observations(
    intersection_id: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return TrafficService(db).latest(intersection_id=intersection_id, limit=limit)


@router.post(
    "/observations",
    response_model=TrafficObservationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_observation(payload: TrafficObservationCreate, db: Session = Depends(get_db)):
    return TrafficService(db).create_observation(payload)
