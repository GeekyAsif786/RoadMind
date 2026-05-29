from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.cache import get_cache
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
    cache = get_cache()
    cache_key = f"signal_plans:latest:{intersection_id or 'all'}:{limit}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    plans = [
        SignalPlanRead.model_validate(plan).model_dump(mode="json")
        for plan in SignalOptimizationService(db).latest(intersection_id=intersection_id, limit=limit)
    ]
    cache.set_json(cache_key, plans)
    return plans


@router.post("/optimize", response_model=SignalPlanRead, dependencies=[Depends(require_api_key)])
def optimize_signal(payload: OptimizationRequest, db: Session = Depends(get_db)):
    plan = SignalOptimizationService(db).optimize(
        intersection_id=payload.intersection_id,
        horizon_minutes=payload.horizon_minutes,
    )
    cache = get_cache()
    cache.delete_prefix("signal_plans:latest:")
    cache.delete_prefix("dashboard:summary:")
    return plan
