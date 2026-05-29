from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.cache import get_cache
from app.ml.traffic_predictor import TrafficPredictor
from app.models import Prediction
from app.repositories.intersection_repository import IntersectionRepository
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.traffic_repository import TrafficRepository
from app.schemas import PredictionRequest


class PredictionService:
    def __init__(self, db: Session):
        self.intersections = IntersectionRepository(db)
        self.traffic = TrafficRepository(db)
        self.predictions = PredictionRepository(db)
        self.predictor = TrafficPredictor()

    def train(self):
        observations = self.traffic.history()
        try:
            return self.predictor.train(observations)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    def predict(self, payload: PredictionRequest) -> Prediction:
        intersection = self.intersections.get(payload.intersection_id)
        if not intersection:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Intersection not found")

        latest = self.traffic.latest(payload.intersection_id, limit=1)
        latest_count = latest[0].vehicle_count if latest else 0
        latest_density = latest[0].density if latest else 0.0
        latest_speed = latest[0].avg_speed if latest else None
        latest_pcu = latest[0].pcu_total if latest and payload.pcu_total is None else payload.pcu_total
        target_time = datetime.now(UTC) + timedelta(minutes=payload.horizon_minutes)

        try:
            density, vehicle_count, version = self.predictor.predict(
                payload.intersection_id,
                target_time,
                latest_count,
                payload.weather_condition,
                latest_pcu,
                payload.direction,
                latest_density,
                latest_speed,
                payload.hour_of_day,
                payload.day_of_week,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

        prediction = self.predictions.create(
            Prediction(
                intersection_id=payload.intersection_id,
                horizon_minutes=payload.horizon_minutes,
                predicted_density=density,
                predicted_vehicle_count=vehicle_count,
                model_version=version,
            )
        )
        cache = get_cache()
        cache.delete_prefix("dashboard:summary:")
        cache.delete_prefix("prediction:latest:")
        return prediction
