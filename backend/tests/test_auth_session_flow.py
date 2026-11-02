"""
End-to-end session flow against the real auth route functions, a real
PostgreSQL session, and an in-process fake of the Redis session store.

Every database change happens inside an outer transaction that is rolled back.
"""

from http.cookies import SimpleCookie

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.api import auth as auth_api
from app.core import auth as core_auth
from app.core.auth import get_current_user, require_admin, require_authenticated_user
from app.core.config import Settings, get_settings
from app.core.passwords import hash_password
from app.core.sessions import SessionStore
from app.db.session import engine
from app.models.domain import User
from app.schemas.auth import LoginRequest

PASSWORD = "Session-Flow-Password-1"


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, tuple[str, int]] = {}

    def ping(self) -> bool:
        return True

    def setex(self, key: str, ttl: int, value: str) -> bool:
        self.data[key] = (value, ttl)
        return True

    def get(self, key: str) -> str | None:
        item = self.data.get(key)
        return item[0] if item else None

    def delete(self, key: str) -> int:
        return int(self.data.pop(key, None) is not None)


@pytest.fixture
def session_store(monkeypatch):
    store = object.__new__(SessionStore)
    store.settings = get_settings()
    store._client = FakeRedis()
    monkeypatch.setattr(auth_api, "get_session_store", lambda: store)
    monkeypatch.setattr(core_auth, "get_session_store", lambda: store)
    return store


@pytest.fixture
def db():
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


def _add_user(db: Session, *, username: str, role: str, is_active: bool = True) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    return user


def _login(db: Session, identifier: str, password: str = PASSWORD):
    response = Response()
    body = auth_api.login(
        LoginRequest(username_or_email=identifier, password=password),
        response,
        db,
    )
    return body, response


def _set_cookie(response: Response) -> SimpleCookie:
    cookie = SimpleCookie()
    for name, value in response.raw_headers:
        if name.lower() == b"set-cookie":
            cookie.load(value.decode())
    return cookie


def test_login_sets_httponly_session_cookie(db, session_store):
    settings = get_settings()
    user = _add_user(db, username="session-admin", role="admin")

    body, response = _login(db, "session-admin")

    assert body.user.id == str(user.id)
    assert body.user.role == "admin"
    assert "password" not in body.model_dump_json()

    cookie = _set_cookie(response)[settings.session_cookie_name]
    assert cookie.value
    assert cookie["httponly"] is True
    assert cookie["path"] == "/"
    assert cookie["samesite"].lower() == settings.session_cookie_samesite
    assert int(cookie["max-age"]) == settings.session_ttl_seconds
    assert session_store.get_user_id(cookie.value) == str(user.id)


def _raw_set_cookie(response: Response) -> str:
    return next(
        value.decode() for name, value in response.raw_headers if name.lower() == b"set-cookie"
    )


def _use_cookie_settings(monkeypatch, **overrides) -> Settings:
    settings = get_settings().model_copy(update=overrides)
    monkeypatch.setattr(auth_api, "get_settings", lambda: settings)
    return settings


def test_development_default_cookie_is_not_secure():
    # docker-compose.yml does not set SESSION_COOKIE_SECURE, so dev uses this default.
    assert Settings.model_fields["session_cookie_secure"].default is False


@pytest.mark.parametrize("secure", [False, True], ids=["development", "secure"])
def test_cookie_secure_attribute_follows_configuration(db, session_store, monkeypatch, secure):
    settings = _use_cookie_settings(monkeypatch, session_cookie_secure=secure)
    _add_user(db, username="cookie-admin", role="admin")

    _, response = _login(db, "cookie-admin")

    raw = _raw_set_cookie(response)
    attributes = {part.strip().split("=", 1)[0].lower() for part in raw.split(";")[1:]}
    assert ("secure" in attributes) is secure

    cookie = _set_cookie(response)[settings.session_cookie_name]
    assert cookie["secure"] is (True if secure else "")
    assert cookie["httponly"] is True
    assert cookie["path"] == "/"
    assert cookie["samesite"].lower() == "lax"
    assert int(cookie["max-age"]) == settings.session_ttl_seconds == 28800


def test_login_accepts_email(db, session_store):
    _add_user(db, username="email-login", role="viewer")

    body, _ = _login(db, "email-login@example.com")

    assert body.user.username == "email-login"


@pytest.mark.parametrize(
    ("identifier", "password"),
    [("wrong-password", "not-the-password"), ("no-such-user", PASSWORD)],
)
def test_bad_credentials_rejected_without_cookie(db, session_store, identifier, password):
    _add_user(db, username="wrong-password", role="admin")
    response = Response()

    with pytest.raises(HTTPException) as exc:
        auth_api.login(
            LoginRequest(username_or_email=identifier, password=password), response, db
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid username/email or password"
    assert not _set_cookie(response)
    assert session_store._client.data == {}


def test_inactive_user_cannot_log_in(db, session_store):
    _add_user(db, username="disabled-user", role="admin", is_active=False)

    with pytest.raises(HTTPException) as exc:
        _login(db, "disabled-user")

    assert exc.value.status_code == 401


def test_me_requires_session(db, session_store):
    with pytest.raises(HTTPException) as exc:
        get_current_user(roadmind_session=None, db=db)
    assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        get_current_user(roadmind_session="forged-session-id", db=db)
    assert exc.value.status_code == 401


def test_me_after_login_returns_user(db, session_store):
    settings = get_settings()
    user = _add_user(db, username="me-operator", role="operator")
    _, response = _login(db, "me-operator")
    session_id = _set_cookie(response)[settings.session_cookie_name].value

    current = get_current_user(roadmind_session=session_id, db=db)
    me = auth_api.me(current)

    assert me.id == str(user.id)
    assert me.username == "me-operator"
    assert me.role == "operator"
    assert me.is_active is True


def test_logout_deletes_cookie_and_invalidates_session(db, session_store):
    settings = get_settings()
    _add_user(db, username="logout-admin", role="admin")
    _, login_response = _login(db, "logout-admin")
    session_id = _set_cookie(login_response)[settings.session_cookie_name].value
    assert get_current_user(roadmind_session=session_id, db=db)

    logout_response = Response()
    result = auth_api.logout(logout_response, roadmind_session=session_id)

    assert result is None
    cleared = _set_cookie(logout_response)[settings.session_cookie_name]
    assert cleared.value == ""
    assert int(cleared["max-age"]) == 0
    assert session_store.get_user_id(session_id) is None

    # Replaying the old session id after logout must be rejected.
    with pytest.raises(HTTPException) as exc:
        get_current_user(roadmind_session=session_id, db=db)
    assert exc.value.status_code == 401


def test_logout_without_session_is_harmless(session_store):
    response = Response()

    assert auth_api.logout(response, roadmind_session=None) is None
    assert get_settings().session_cookie_name in _set_cookie(response)


def test_deactivated_user_session_is_rejected(db, session_store):
    settings = get_settings()
    user = _add_user(db, username="soon-disabled", role="admin")
    _, response = _login(db, "soon-disabled")
    session_id = _set_cookie(response)[settings.session_cookie_name].value

    user.is_active = False
    db.commit()

    with pytest.raises(HTTPException) as exc:
        get_current_user(roadmind_session=session_id, db=db)
    assert exc.value.status_code == 401


def test_viewer_session_is_read_only(db, session_store):
    settings = get_settings()
    _add_user(db, username="session-viewer", role="viewer")
    _, response = _login(db, "session-viewer")
    session_id = _set_cookie(response)[settings.session_cookie_name].value
    viewer = get_current_user(roadmind_session=session_id, db=db)

    assert require_authenticated_user(viewer) is viewer
    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)
    assert exc.value.status_code == 403
