import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.device_credentials import (
    generate_device_credential,
    hash_device_credential,
)
from app.models.domain import DeviceCredential, Intersection

class DeviceCredentialService:
    def create(
        self,
        db: Session,
        name: str,
        scopes: list[str],
        intersection_id: uuid.UUID | None = None,
    ) -> tuple[DeviceCredential, str]:
        existing = db.scalar(
            select(DeviceCredential).where(
                DeviceCredential.name == name
            )
        )
        if existing is not None:
            raise ValueError("Device credential name already exists")
        if intersection_id is not None:
            intersection = db.scalar(
                select(Intersection).where(
                    Intersection.id == intersection_id
                )
            )

            if intersection is None:
                raise ValueError("Intersection not found")
        credential_id = f"dev_{secrets.token_urlsafe(12)}"
        secret = generate_device_credential()

        device = DeviceCredential(
            intersection_id=intersection_id,
            name=name,
            credential_id=credential_id,
            credential_hash=hash_device_credential(secret),
            scopes=scopes,
            is_active=True,
        )

        db.add(device)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise
        db.refresh(device)
        return device, secret
    def revoke(
        self,
        db: Session,
        device_id: uuid.UUID,
    ) -> DeviceCredential:
        device = db.scalar(
            select(DeviceCredential).where(
                DeviceCredential.id == device_id
            )
        )

        if device is None:
            raise ValueError("Device credential not found")

        if not device.is_active:
            raise ValueError("Device credential already revoked")

        device.is_active = False

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise

        db.refresh(device)

    
        return device
    def list(
        self,
        db: Session,
    ) -> list[DeviceCredential]:
        return list(
            db.scalars(
                select(DeviceCredential).order_by(DeviceCredential.created_at.desc())
            ).all()
        )