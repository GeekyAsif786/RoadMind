import pytest

from app.core.sessions import SessionStore


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


def test_create_session(monkeypatch):
    store = object.__new__(SessionStore)

    class Settings:
        session_ttl_seconds = 28800

    store.settings = Settings()
    store._client = FakeRedis()

    session_id = store.create_session("user-123")

    assert session_id
    assert store.get_user_id(session_id) == "user-123"


def test_delete_session(monkeypatch):
    store = object.__new__(SessionStore)

    class Settings:
        session_ttl_seconds = 28800

    store.settings = Settings()
    store._client = FakeRedis()

    session_id = store.create_session("user-123")

    store.delete_session(session_id)

    assert store.get_user_id(session_id) is None


def test_missing_session_returns_none():
    store = object.__new__(SessionStore)

    class Settings:
        session_ttl_seconds = 28800

    store.settings = Settings()
    store._client = FakeRedis()

    assert store.get_user_id("does-not-exist") is None
