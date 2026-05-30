from uuid import UUID

from sqlalchemy.orm import Session

from app.core.cache import get_cache
from app.repositories.emergency_repository import EmergencyRepository
from app.repositories.intersection_repository import IntersectionRepository
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.signal_state_repository import SignalStateRepository
from app.repositories.traffic_repository import TrafficRepository
from app.schemas import DashboardSummary


class DashboardService:
    def __init__(self, db: Session):
        self.intersections = IntersectionRepository(db)
        self.traffic = TrafficRepository(db)
        self.signals = SignalRepository(db)
        self.signal_states = SignalStateRepository(db)
        self.emergencies = EmergencyRepository(db)
        self.predictions = PredictionRepository(db)

    def summary(self, intersection_id: UUID | None = None) -> DashboardSummary:
        cache = get_cache()
        cache_key = f"dashboard:summary:{intersection_id or 'all'}"
        cached = cache.get_json(cache_key)
        if cached is not None:
            return DashboardSummary.model_validate(cached)

        observations = self.traffic.latest(intersection_id=intersection_id, limit=12)
        signal_plans = self.signals.latest(intersection_id=intersection_id, limit=8)
        emergencies = self.emergencies.latest(intersection_id=intersection_id, limit=8)
        predictions = self.predictions.latest(intersection_id=intersection_id, limit=8)
        latest = observations[0] if observations else None
        signal_state = self.signal_states.get(intersection_id) if intersection_id else None
        summary = DashboardSummary(
            intersections=self.intersections.count(),
            active_emergencies=len(self.emergencies.active(intersection_id)),
            latest_density=latest.density if latest else None,
            latest_vehicle_count=latest.vehicle_count if latest else None,
            signal_plans=signal_plans,
            observations=observations,
            emergencies=emergencies,
            predictions=predictions,
            metadata={
                "status": "operational",
                "intersection_id": str(intersection_id) if intersection_id else None,
                "signal_decision_source": signal_state.decision_source if signal_state else None,
            },
        )
        cache.set_json(cache_key, summary.model_dump(mode="json"))
        return summary
