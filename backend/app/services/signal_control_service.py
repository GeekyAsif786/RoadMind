from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import SignalControlCommand as SignalControlCommandModel
from app.repositories.signal_control_command_repository import (
    SignalControlCommandRepository,
)
from app.repositories.signal_repository import SignalRepository
from app.schemas import SignalControlCommand, SignalControlCommandRead


class SignalControlService:
    def __init__(self, db: Session):
        self.commands = SignalControlCommandRepository(db)
        self.signals = SignalRepository(db)
    def pending_commands(
        self,
        device_id: UUID,
        limit: int = 10,
    ) -> list[SignalControlCommandRead]:
        commands = self.commands.pending_for_device(
            device_id=device_id,
            limit=limit,
        )

        results: list[SignalControlCommandRead] = []

        for command in commands:
            phase = self.signals.get_phase(
                plan_id=command.plan_id,
                phase_number=command.phase_number,
            )

            if phase is None:
                continue

            results.append(
                SignalControlCommandRead(
                    command_id=command.id,
                    intersection_id=command.intersection_id,
                    plan_id=command.plan_id,
                    phase_number=command.phase_number,
                    direction=phase.direction,
                    green_seconds=phase.green_seconds,
                    yellow_seconds=phase.yellow_seconds,
                    expires_at=command.expires_at,
                    status=command.status,
                )
            )

        return results
    def create_command(
        self,
        device_id: UUID,
        intersection_id: UUID,
        payload: SignalControlCommand,
    ) -> SignalControlCommandRead:
        plan = self.signals.get(payload.plan_id)

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

        now = datetime.now(UTC)

        if plan.expires_at is not None and plan.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Signal plan has expired",
            )

        phase = self.signals.get_phase(
            plan_id=payload.plan_id,
            phase_number=payload.phase_number,
        )

        if phase is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signal phase not found",
            )

        command = SignalControlCommandModel(
            intersection_id=intersection_id,
            device_id=device_id,
            plan_id=plan.id,
            phase_number=phase.phase_number,
            status="accepted",
            expires_at=plan.expires_at,
        )

        saved = self.commands.create(command)

        return SignalControlCommandRead(
            command_id=saved.id,
            intersection_id=saved.intersection_id,
            plan_id=saved.plan_id,
            phase_number=saved.phase_number,
            direction=phase.direction,
            green_seconds=phase.green_seconds,
            yellow_seconds=phase.yellow_seconds,
            expires_at=saved.expires_at,
            status=saved.status,
        )