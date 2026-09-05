from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.passwords import verify_password
from app.models.domain import User


class AuthService:
    def authenticate_user(
        self,
        db: Session,
        username_or_email: str,
        password: str,
    ) -> User | None:
        identifier = username_or_email.strip()

        statement = select(User).where(
            (User.username == identifier) | (User.email == identifier)
        )

        user = db.scalar(statement)

        if user is None:
            return None

        if not user.is_active:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user
