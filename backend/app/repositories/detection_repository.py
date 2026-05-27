from sqlalchemy.orm import Session

from app.models import DetectionEvent


class DetectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, event: DetectionEvent) -> DetectionEvent:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
