from app.db.session import SessionLocal
from app.services.prediction_service import PredictionService


def train_traffic_model_task() -> dict[str, object]:
    db = SessionLocal()
    try:
        version, samples, score, metrics = PredictionService(db).train()
        return {
            "model_version": version,
            "samples": samples,
            "score": score,
            "mae": metrics.get("mae"),
            "rmse": metrics.get("rmse"),
            "r2": metrics.get("r2"),
        }
    finally:
        db.close()
