import secrets
from collections.abc import Callable
from typing import Final
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.sessions import get_session_store
from app.db.session import get_db
from app.models.domain import User
from datetime import UTC, datetime

from app.core.device_credentials import (
    parse_device_credential,
    verify_device_credential,
)
from app.models.domain import DeviceCredential
ROLE_ADMIN: Final[str] = "admin"
ROLE_OPERATOR: Final[str] = "operator"
ROLE_VIEWER: Final[str] = "viewer"

async def require_api_key(
    x_api_key: str = Header(default=""),
) -> None:
    settings = get_settings()

    if not settings.enable_auth:
        return

    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

def get_current_device(
    x_device_credential: str = Header(default=""),
    db: Session = Depends(get_db),
) -> DeviceCredential:
    if not x_device_credential:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device credential",
        )

    try:
        credential_id, secret = parse_device_credential(
            x_device_credential
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credential",
        )

    device = db.scalar(
        select(DeviceCredential).where(
            DeviceCredential.credential_id == credential_id,
            DeviceCredential.is_active.is_(True),
        )
    )

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credential",
        )

    now = datetime.now(UTC)

    if device.expires_at is not None and device.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device credential expired",
        )

    if not verify_device_credential(
        secret,
        device.credential_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credential",
        )

    device.last_used_at = now
    db.commit()

    return device

def get_current_user(
    roadmind_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not roadmind_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    session_store = get_session_store()
    user_id = session_store.get_user_id(roadmind_session)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = db.scalar(
        select(User).where(User.id == user_id)
    )

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return user

def check_role(
    user: User,
    allowed_roles: set[str],
) -> User:
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return user


def require_authenticated_user(
    user: User = Depends(get_current_user),
) -> User:
    return check_role(
        user,
        {
            ROLE_VIEWER,
            ROLE_OPERATOR,
            ROLE_ADMIN,
        },
    )


def require_operator_or_admin(
    user: User = Depends(get_current_user),
) -> User:
    return check_role(
        user,
        {
            ROLE_OPERATOR,
            ROLE_ADMIN,
        },
    )


def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    return check_role(
        user,
        {
            ROLE_ADMIN,
        },
    )

def require_device_scope(required_scope: str):
    def dependency(
        device: DeviceCredential = Depends(get_current_device),
    ) -> DeviceCredential:
        if required_scope not in device.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device lacks required scope",
            )

        return device

    return dependency