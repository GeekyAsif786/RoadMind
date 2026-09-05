from unittest.mock import Mock

from app.core.passwords import hash_password
from app.models.domain import User
from app.services.auth_service import AuthService


def make_user(
    *,
    username: str = "admin",
    email: str = "admin@example.com",
    password: str = "TestPassword123!",
    role: str = "admin",
    is_active: bool = True,
) -> User:
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    return user


def test_authenticate_valid_user():
    user = make_user()

    db = Mock()
    db.scalar.return_value = user

    service = AuthService()

    authenticated = service.authenticate_user(
        db=db,
        username_or_email="admin",
        password="TestPassword123!",
    )

    assert authenticated is user
    assert authenticated.username == "admin"
    db.scalar.assert_called_once()


def test_authenticate_wrong_password():
    user = make_user()

    db = Mock()
    db.scalar.return_value = user

    service = AuthService()

    authenticated = service.authenticate_user(
        db=db,
        username_or_email="admin",
        password="WrongPassword!",
    )

    assert authenticated is None


def test_authenticate_inactive_user():
    user = make_user(is_active=False)

    db = Mock()
    db.scalar.return_value = user

    service = AuthService()

    authenticated = service.authenticate_user(
        db=db,
        username_or_email="admin",
        password="TestPassword123!",
    )

    assert authenticated is None