from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Prediction


class PredictionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, prediction: Prediction) -> Prediction:
        self.db.add(prediction)
        self.db.commit()
        self.db.refresh(prediction)
        return prediction

    def latest(self, intersection_id: UUID | None = None, limit: int = 10) -> list[Prediction]:
        statement = select(Prediction)
        if intersection_id:
            statement = statement.where(Prediction.intersection_id == intersection_id)
        statement = statement.order_by(desc(Prediction.created_at)).limit(limit)
        return list(self.db.scalars(statement).all())
