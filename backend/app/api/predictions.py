from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import PredictionRead, PredictionRequest, PredictionTrainResponse
from app.services.prediction_service import PredictionService

router = APIRouter()


@router.post("/train", response_model=PredictionTrainResponse)
def train_model(db: Session = Depends(get_db)):
    version, samples, score = PredictionService(db).train()
    return PredictionTrainResponse(model_version=version, samples=samples, score=score)


@router.post("", response_model=PredictionRead, status_code=status.HTTP_201_CREATED)
def create_prediction(payload: PredictionRequest, db: Session = Depends(get_db)):
    return PredictionService(db).predict(payload)
