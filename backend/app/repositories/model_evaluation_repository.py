from sqlalchemy.orm import Session

from app.models import ModelEvaluation


class ModelEvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, evaluation: ModelEvaluation) -> ModelEvaluation:
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation
