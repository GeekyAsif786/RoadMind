from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import SignalPhase, SignalPlan


class SignalRepository:
    def __init__(self, db: Session):
        self.db = db
    def get(self, plan_id: UUID) -> SignalPlan | None:
        return self.db.get(SignalPlan, plan_id)
    def get_phase(self, plan_id: UUID, phase_number: int) -> SignalPhase | None:
        statement = select(SignalPhase).where(
            SignalPhase.plan_id == plan_id,
            SignalPhase.phase_number == phase_number,
        )
        return self.db.scalar(statement)
    def create(self, plan: SignalPlan) -> SignalPlan:
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def create_phases(self, phases: list[SignalPhase]) -> list[SignalPhase]:
        self.db.add_all(phases)
        self.db.commit()
        for phase in phases:
            self.db.refresh(phase)
        return phases

    def latest(self, intersection_id: UUID | None = None, limit: int = 10) -> list[SignalPlan]:
        statement = select(SignalPlan)
        if intersection_id:
            statement = statement.where(SignalPlan.intersection_id == intersection_id)
        statement = statement.order_by(desc(SignalPlan.created_at)).limit(limit)
        return list(self.db.scalars(statement).all())
