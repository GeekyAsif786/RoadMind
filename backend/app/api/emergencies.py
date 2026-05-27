from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import EmergencyCreate, EmergencyRead, SignalPlanRead
from app.services.emergency_service import EmergencyService

router = APIRouter()


@router.get("", response_model=list[EmergencyRead])
def active_emergencies(intersection_id: UUID | None = None, db: Session = Depends(get_db)):
    return EmergencyService(db).active(intersection_id=intersection_id)


@router.post("", response_model=EmergencyRead, status_code=status.HTTP_201_CREATED)
def create_emergency(payload: EmergencyCreate, db: Session = Depends(get_db)):
    return EmergencyService(db).create(payload)


@router.post("/clear-active", response_model=SignalPlanRead)
def clear_active_emergencies(intersection_id: UUID, db: Session = Depends(get_db)):
    return EmergencyService(db).clear_active_for_intersection(intersection_id)


@router.post("/{event_id}/clear", response_model=EmergencyRead)
def clear_emergency(event_id: UUID, db: Session = Depends(get_db)):
    return EmergencyService(db).clear(event_id)
