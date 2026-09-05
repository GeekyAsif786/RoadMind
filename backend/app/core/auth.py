import secrets

from fastapi import Cookie, Header, HTTPException, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.sessions import get_session_store
from app.db.session import SessionLocal
from app.models.domain import User


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


def get_current_user(
    roadmind_session: str | None = Cookie(default=None),
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

    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(User.id == user_id)
        )

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return user