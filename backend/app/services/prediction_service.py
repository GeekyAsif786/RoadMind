from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.cache import get_cache
from app.core.metrics import Timer, get_metrics
from app.ml.traffic_predictor import TrafficPredictor
from app.models import ModelEvaluation, Prediction
from app.repositories.intersection_repository import IntersectionRepository
from app.repositories.model_evaluation_repository import ModelEvaluationRepository
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.traffic_repository import TrafficRepository
from app.schemas import PredictionRequest


class PredictionService:
    def __init__(self, db: Session):
        self.intersections = IntersectionRepository(db)
        self.traffic = TrafficRepository(db)
        self.predictions = PredictionRepository(db)
        self.evaluations = ModelEvaluationRepository(db)
        self.predictor = TrafficPredictor()

    def train(self):
        observations = self.traffic.history()
        try:
            version, samples, score, metrics = self.predictor.train(observations)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        self.evaluations.create(
            ModelEvaluation(
                model_version=version,
                model_type=version.split("-", maxsplit=1)[0],
                samples=samples,
                mae=metrics.get("mae"),
                rmse=metrics.get("rmse"),
                r2=metrics.get("r2"),
                metrics_detail=metrics.get("metrics_detail"),
            )
        )
        return version, samples, score, metrics

    def predict(self, payload: PredictionRequest) -> Prediction:
        timer = Timer()
        intersection = self.intersections.get(payload.intersection_id)
        if not intersection:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Intersection not found")

        latest = self.traffic.latest(payload.intersection_id, limit=1)
        latest_count = latest[0].vehicle_count if latest else 0
        latest_density = latest[0].density if latest else 0.0
        latest_speed = latest[0].avg_speed if latest else None
        latest_pcu = latest[0].pcu_total if latest and payload.pcu_total is None else payload.pcu_total
        # Features now describe "now" (the current state). The horizon is passed
        # explicitly as a feature rather than baked into a future timestamp.
        current_time = datetime.now(UTC)

        try:
            density, vehicle_count, version = self.predictor.predict(
                payload.intersection_id,
                current_time,
                latest_count,
                payload.horizon_minutes,
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
        get_metrics().observe_prediction(timer.elapsed())
        return prediction
