from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import require_admin,require_operator_or_admin
from app.core.jobs import get_job_queue
from app.db.session import get_db
from app.schemas import PredictionRead, PredictionRequest, PredictionTrainResponse
from app.services.prediction_service import PredictionService
from app.tasks import train_traffic_model_task

router = APIRouter()


@router.post(
    "/train",
    response_model=PredictionTrainResponse,
    dependencies=[Depends(require_admin)],
)
def train_model():
    job_id = get_job_queue().enqueue("train_traffic_model", train_traffic_model_task)
    return PredictionTrainResponse(model_version="queued", samples=0, score=None, job_id=job_id, status="queued")


@router.post(
    "/train/sync",
    response_model=PredictionTrainResponse,
    dependencies=[Depends(require_admin)],
)
def train_model_sync(db: Session = Depends(get_db)):
    version, samples, score, metrics = PredictionService(db).train()
    return PredictionTrainResponse(
        model_version=version,
        samples=samples,
        score=score,
        status="finished",
        mae=metrics.get("mae"),
        rmse=metrics.get("rmse"),
        r2=metrics.get("r2"),
    )


@router.post(
    "",
    response_model=PredictionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_operator_or_admin)],
)
def create_prediction(payload: PredictionRequest, db: Session = Depends(get_db)):
    return PredictionService(db).predict(payload)
