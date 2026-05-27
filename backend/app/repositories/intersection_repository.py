from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Intersection
from app.schemas import IntersectionCreate


class IntersectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[Intersection]:
        return list(self.db.scalars(select(Intersection).order_by(Intersection.name)).all())

    def get(self, intersection_id: UUID) -> Intersection | None:
        return self.db.get(Intersection, intersection_id)

    def create(self, payload: IntersectionCreate) -> Intersection:
        entity = Intersection(**payload.model_dump())
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def count(self) -> int:
        return int(self.db.scalar(select(func.count()).select_from(Intersection)) or 0)
