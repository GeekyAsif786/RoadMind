import secrets
import uuid

from sqlalchemy.orm import Session

from app.core.device_credentials import (
    generate_device_credential,
    hash_device_credential,
)
from app.models.domain import DeviceCredential


class DeviceCredentialService:
    def create(
        self,
        db: Session,
        name: str,
        scopes: list[str],
        intersection_id: uuid.UUID | None = None,
    ) -> tuple[DeviceCredential, str]:
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
        db.commit()
        db.refresh(device)

        return device, secret