from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import SignalControllerState
from app.repositories.signal_controller_state_repository import (
    SignalControllerStateRepository,
)
from app.repositories.signal_control_command_repository import (
    SignalControlCommandRepository,
)
from app.repositories.signal_repository import SignalRepository
from app.schemas import SignalControllerStateCreate


class SignalControllerStateService:
    def __init__(self, db: Session):
        self.db = db
        self.controller_states = SignalControllerStateRepository(db)
        self.controller_states = SignalControllerStateRepository(db)
        self.signals = SignalRepository(db)
        self.commands = SignalControlCommandRepository(db)

    def update(
        self,
        intersection_id: UUID,
        payload: SignalControllerStateCreate,
        *,
        commit: bool = True
    ) -> SignalControllerState:
        if payload.reported_plan_id is not None:
            plan = self.signals.get(payload.reported_plan_id)

            if plan is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Signal plan not found",
                )

            if plan.intersection_id != intersection_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Signal plan does not belong to this intersection",
                )

            if plan.expires_at is not None and plan.expires_at <= datetime.now(UTC):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Signal plan has expired",
                )

        return self.controller_states.upsert(
            intersection_id=intersection_id,
            current_phase=payload.current_phase,
            phase_state=payload.phase_state,
            controller_status=payload.controller_status,
            reported_plan_id=payload.reported_plan_id,
            phase_started_at=payload.phase_started_at,
            commit=commit,
        )

    def report_command_execution(
        self,
        command_id: UUID,
        device_id: UUID,
        intersection_id: UUID,
        payload: SignalControllerStateCreate,
    ) -> SignalControllerState:
        command = self.commands.get_for_update(command_id)

        if command is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signal control command not found",
            )

        if command.device_id != device_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device is not authorized to report this command",
            )

        if command.intersection_id != intersection_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Signal control command does not belong to this intersection",
            )

        if command.status != "acknowledged":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Signal control command must be acknowledged before execution is reported",
            )

        now = datetime.now(UTC)

        if command.expires_at is not None and command.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Signal control command has expired",
            )

        if payload.reported_plan_id != command.plan_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reported signal plan does not match the control command",
            )

        if payload.current_phase != command.phase_number:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reported phase does not match the control command",
            )
        if command.execution_reported_at is not None:
            existing_state = self.controller_states.get(intersection_id)

            if existing_state is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Execution was already reported but controller state is unavailable",
                )

            return existing_state
        command.execution_reported_at = now
        try:
            state = self.update(
                intersection_id=intersection_id,
                payload=payload,
                commit=False,
            )

            self.db.commit()
            self.db.refresh(state)

            return state

        except Exception:
            self.db.rollback()
            raise
        # return self.update(
        #     intersection_id=intersection_id,
        #     payload=payload,
        # )