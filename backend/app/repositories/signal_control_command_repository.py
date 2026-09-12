from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import SignalControlCommand


class SignalControlCommandRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        command: SignalControlCommand,
    ) -> SignalControlCommand:
        self.db.add(command)
        self.db.commit()
        self.db.refresh(command)
        return command

    def get(self, command_id: UUID) -> SignalControlCommand | None:
        return self.db.get(SignalControlCommand, command_id)
    def pending_for_device(
        self,
        device_id: UUID,
        limit: int = 10,
    ) -> list[SignalControlCommand]:
        now = datetime.now(UTC)

        statement = (
            select(SignalControlCommand)
            .where(
                SignalControlCommand.device_id == device_id,
                SignalControlCommand.status == "accepted",
                SignalControlCommand.acknowledged_at.is_(None),
            )
            .where(
                (SignalControlCommand.expires_at.is_(None))
                | (SignalControlCommand.expires_at > now)
            )
            .order_by(desc(SignalControlCommand.requested_at))
            .limit(limit)
        )

        return list(self.db.scalars(statement).all())
    def acknowledge(
        self,
        command: SignalControlCommand,
        acknowledged_at: datetime,
    ) -> SignalControlCommand:
        command.acknowledged_at = acknowledged_at
        command.status = "acknowledged"
        self.db.commit()
        self.db.refresh(command)
        return command
    def latest(
        self,
        intersection_id: UUID | None = None,
        limit: int = 10,
    ) -> list[SignalControlCommand]:
        statement = select(SignalControlCommand)

        if intersection_id:
            statement = statement.where(
                SignalControlCommand.intersection_id == intersection_id
            )

        statement = (
            statement
            .order_by(desc(SignalControlCommand.created_at))
            .limit(limit)
        )

        return list(self.db.scalars(statement).all())