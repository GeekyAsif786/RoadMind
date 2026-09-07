from uuid import UUID

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session
from app.core.auth import require_authenticated_user
from app.core.auth import require_operator_or_admin
from app.core.auth import require_api_key
from app.core.cache import get_cache
from app.db.session import get_db
from app.schemas import EmergencyCorridorRead, EmergencyCreate, EmergencyRead, SignalPlanRead
from app.services.emergency_service import EmergencyService

router = APIRouter()


@router.get("", response_model=list[EmergencyRead],dependencies=[Depends(require_authenticated_user)])
def active_emergencies(intersection_id: UUID | None = None, db: Session = Depends(get_db)):
    cache = get_cache()
    cache_key = f"emergencies:active:{intersection_id or 'all'}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    emergencies = [
        EmergencyRead.model_validate(emergency).model_dump(mode="json")
        for emergency in EmergencyService(db).active(intersection_id=intersection_id)
    ]
    cache.set_json(cache_key, emergencies)
    return emergencies


@router.post(
    "",
    response_model=EmergencyRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_operator_or_admin)],
)
def create_emergency(payload: EmergencyCreate, db: Session = Depends(get_db)):
    return EmergencyService(db).create(payload)


@router.post("/clear-active", response_model=SignalPlanRead, dependencies=[Depends(require_operator_or_admin)])
def clear_active_emergencies(intersection_id: UUID, db: Session = Depends(get_db)):
    return EmergencyService(db).clear_active_for_intersection(intersection_id)


@router.post("/{event_id}/clear", response_model=EmergencyRead, dependencies=[Depends(require_operator_or_admin)])
def clear_emergency(event_id: UUID, db: Session = Depends(get_db)):
    return EmergencyService(db).clear(event_id)


@router.patch("/{event_id}/clear", response_model=EmergencyRead, dependencies=[Depends(require_operator_or_admin)])
def patch_clear_emergency(event_id: UUID, db: Session = Depends(get_db)):
    return EmergencyService(db).clear(event_id)


@router.get(
    "/{emergency_id}/corridor",
    response_model=list[EmergencyCorridorRead],
    dependencies=[Depends(require_authenticated_user)],
)
def get_emergency_corridor(emergency_id: UUID, db: Session = Depends(get_db)):
    return EmergencyService(db).corridors(emergency_id)


@router.post(
    "/{emergency_id}/corridor",
    response_model=list[EmergencyCorridorRead],
    dependencies=[Depends(require_operator_or_admin)],
)
def create_emergency_corridor(
    emergency_id: UUID,
    intersection_ids: list[UUID] = Body(...),
    avg_speed_kmh: float = 30.0,
    db: Session = Depends(get_db),
):
    """
    Create a green corridor for an emergency vehicle.
    intersection_ids: list in travel order.
    avg_speed_kmh: estimated vehicle speed to calculate time offsets.
    """
    return EmergencyService(db).create_corridor(
        emergency_id=emergency_id,
        intersection_ids=intersection_ids,
        avg_speed_kmh=avg_speed_kmh,
    )
