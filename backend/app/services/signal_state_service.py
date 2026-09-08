from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.signal_state_repository import SignalStateRepository


class SignalStateService:
    def __init__(self, db: Session):
        self.signal_states = SignalStateRepository(db)

    def get(self, intersection_id: UUID):
        state = self.signal_states.get(intersection_id)

        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signal state not found",
            )

        return state