from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.signal_control_command_repository import (
    SignalControlCommandRepository,
)
from app.repositories.signal_repository import SignalRepository
from app.schemas import SignalControlCommandRead


class SignalControlAckService:
    def __init__(self, db: Session):
        self.commands = SignalControlCommandRepository(db)
        self.signals = SignalRepository(db)

    def acknowledge(
        self,
        command_id: UUID,
        device_id: UUID,
    ) -> SignalControlCommandRead:
        command = self.commands.get(command_id)

        if command is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signal control command not found",
            )

        if command.device_id != device_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device is not authorized to acknowledge this command",
            )

        if command.status != "accepted":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Signal control command is not awaiting acknowledgement",
            )

        now = datetime.now(UTC)

        if command.expires_at is not None and command.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Signal control command has expired",
            )

        acknowledged = self.commands.acknowledge(
            command=command,
            acknowledged_at=now,
        )

        phase = self.signals.get_phase(
            plan_id=acknowledged.plan_id,
            phase_number=acknowledged.phase_number,
        )

        if phase is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signal control command phase not found",
            )

        return SignalControlCommandRead(
            command_id=acknowledged.id,
            intersection_id=acknowledged.intersection_id,
            plan_id=acknowledged.plan_id,
            phase_number=acknowledged.phase_number,
            direction=phase.direction,
            green_seconds=phase.green_seconds,
            yellow_seconds=phase.yellow_seconds,
            expires_at=acknowledged.expires_at,
            status=acknowledged.status,
        )