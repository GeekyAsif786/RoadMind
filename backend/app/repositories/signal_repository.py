from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import SignalPlan


class SignalRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, plan: SignalPlan) -> SignalPlan:
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def latest(self, intersection_id: UUID | None = None, limit: int = 10) -> list[SignalPlan]:
        statement = select(SignalPlan)
        if intersection_id:
            statement = statement.where(SignalPlan.intersection_id == intersection_id)
        statement = statement.order_by(desc(SignalPlan.created_at)).limit(limit)
        return list(self.db.scalars(statement).all())
