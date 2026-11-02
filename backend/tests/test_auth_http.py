"""
HTTP-level integration tests for the session authentication flow.

Requests go through the real FastAPI application (routing, dependencies,
middleware, cookie handling) via TestClient/httpx. Isolation:

- Database: every request shares one session inside an outer transaction that
  is always rolled back, so no user or other row survives a test.
- Redis: the session store is backed by an in-process fake, so no Redis
  instance is needed or touched.
"""

from http.cookies import SimpleCookie

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import auth as auth_api
from app.core import auth as core_auth
from app.core import security
from app.core.config import get_settings
from app.core.passwords import hash_password
from app.core.sessions import SessionStore
from app.db.session import engine, get_db
from app.main import app
from app.models.domain import User

PASSWORD = "Http-Flow-Password-1"
COOKIE = get_settings().session_cookie_name


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


@pytest.fixture
def session_store(monkeypatch):
    store = object.__new__(SessionStore)
    store.settings = get_settings()
    store._client = FakeRedis()
    monkeypatch.setattr(auth_api, "get_session_store", lambda: store)
    monkeypatch.setattr(core_auth, "get_session_store", lambda: store)
    return store


@pytest.fixture
def make_client(db, session_store):
    """Build TestClients bound to the isolated database session."""

    def override_get_db():
        yield db

    # Start each test with an empty in-process rate-limit window.
    security._REQUEST_TIMES.clear()
    app.dependency_overrides[get_db] = override_get_db
    clients: list[TestClient] = []

    def factory(base_url: str = "http://testserver") -> TestClient:
        client = TestClient(app, base_url=base_url)
        clients.append(client)
        return client

    try:
        yield factory
    finally:
        for client in clients:
            client.close()
        app.dependency_overrides.pop(get_db, None)
        security._REQUEST_TIMES.clear()


def _add_user(db: Session, *, username: str, role: str = "admin") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _login(client: TestClient, identifier: str, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"username_or_email": identifier, "password": password},
    )


def _session_cookie(response) -> tuple[str, dict[str, str | bool], set[str]]:
    """Return (value, morsel attributes, raw attribute names) of the session Set-Cookie."""
    headers = [value for value in response.headers.get_list("set-cookie") if value.startswith(f"{COOKIE}=")]
    assert len(headers) == 1, headers
    raw = headers[0]
    parsed = SimpleCookie()
    parsed.load(raw)
    morsel = parsed[COOKIE]
    names = {part.strip().split("=", 1)[0].lower() for part in raw.split(";")[1:]}
    return morsel.value, morsel, names


def test_full_session_lifecycle_over_http(db, session_store, make_client):
    user = _add_user(db, username="http-admin")
    client = make_client()

    # 1. No session yet.
    anonymous = client.get("/api/v1/auth/me")
    assert anonymous.status_code == 401
    assert anonymous.json() == {"detail": "Not authenticated"}

    # 2. Login issues the session cookie.
    login = _login(client, "http-admin")
    assert login.status_code == 200
    assert login.json()["user"] == {
        "id": str(user.id),
        "username": "http-admin",
        "email": "http-admin@example.com",
        "role": "admin",
        "is_active": True,
    }
    assert "password" not in login.text

    session_id, morsel, names = _session_cookie(login)
    assert session_id
    assert morsel["httponly"] is True
    assert morsel["samesite"].lower() == "lax"
    assert morsel["path"] == "/"
    assert int(morsel["max-age"]) == 28800
    assert "secure" not in names  # development default
    assert session_store.get_user_id(session_id) == str(user.id)
    assert client.cookies.get(COOKIE) == session_id

    # 3. The cookie authenticates /me.
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json() == login.json()["user"]

    # 4. Logout deletes the server-side session and clears the cookie.
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert logout.content == b""
    cleared_value, cleared, _ = _session_cookie(logout)
    assert cleared_value == ""
    assert int(cleared["max-age"]) == 0
    assert cleared["path"] == "/"
    assert session_store.get_user_id(session_id) is None
    assert COOKIE not in client.cookies

    # 5. The cleared jar no longer authenticates...
    assert client.get("/api/v1/auth/me").status_code == 401

    # ...and replaying the old session id is rejected server-side.
    replay = client.get("/api/v1/auth/me", headers={"Cookie": f"{COOKIE}={session_id}"})
    assert replay.status_code == 401
    assert replay.json() == {"detail": "Not authenticated"}


def test_secure_cookie_configuration_over_https(db, session_store, make_client, monkeypatch):
    secure_settings = get_settings().model_copy(update={"session_cookie_secure": True})
    monkeypatch.setattr(auth_api, "get_settings", lambda: secure_settings)
    _add_user(db, username="https-admin")
    client = make_client("https://testserver")

    login = _login(client, "https-admin")

    assert login.status_code == 200
    _, morsel, names = _session_cookie(login)
    assert "secure" in names
    assert morsel["secure"] is True
    assert morsel["httponly"] is True
    assert morsel["samesite"].lower() == "lax"
    assert morsel["path"] == "/"
    assert int(morsel["max-age"]) == 28800

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "https-admin"


def test_secure_cookie_is_not_sent_over_plain_http(db, session_store, make_client, monkeypatch):
    secure_settings = get_settings().model_copy(update={"session_cookie_secure": True})
    monkeypatch.setattr(auth_api, "get_settings", lambda: secure_settings)
    _add_user(db, username="plain-http-admin")
    client = make_client("http://testserver")

    assert _login(client, "plain-http-admin").status_code == 200

    # The client keeps the Secure cookie but must not send it over HTTP.
    assert client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize(
    ("identifier", "password"),
    [("http-wrong-password", "not-the-password-1"), ("no-such-user", PASSWORD)],
)
def test_bad_credentials_get_401_without_cookie(db, session_store, make_client, identifier, password):
    _add_user(db, username="http-wrong-password")
    client = make_client()

    response = _login(client, identifier, password)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username/email or password"}
    assert response.headers.get_list("set-cookie") == []
    assert session_store._client.data == {}


def test_viewer_session_gets_403_on_admin_route(db, session_store, make_client):
    _add_user(db, username="http-viewer", role="viewer")
    client = make_client()
    assert _login(client, "http-viewer").status_code == 200

    assert client.get("/api/v1/auth/me").json()["role"] == "viewer"
    response = client.post(
        "/api/v1/intersections",
        json={"name": "Never Created Junction", "latitude": 28.6, "longitude": 77.2},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}
