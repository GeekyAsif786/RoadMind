from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import OptimizationRequest, SignalPlanRead
from app.services.optimization_service import SignalOptimizationService

router = APIRouter()


@router.get("/plans", response_model=list[SignalPlanRead])
def latest_signal_plans(
    intersection_id: UUID | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return SignalOptimizationService(db).latest(intersection_id=intersection_id, limit=limit)


@router.post("/optimize", response_model=SignalPlanRead)
def optimize_signal(payload: OptimizationRequest, db: Session = Depends(get_db)):
    return SignalOptimizationService(db).optimize(
        intersection_id=payload.intersection_id,
        horizon_minutes=payload.horizon_minutes,
    )
