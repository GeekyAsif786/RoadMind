import logging
import secrets
from functools import lru_cache

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self) -> None:
        self.settings = get_settings()

        if not self.settings.redis_url:
            raise RuntimeError(
                "REDIS_URL must be configured for Web Admin sessions."
            )

        try:
            self._client = redis.Redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
            )
            self._client.ping()
        except Exception as exc:
            raise RuntimeError(
                "Redis is required for Web Admin sessions but is unavailable."
            ) from exc

    def create_session(self, user_id: str) -> str:
        session_id = secrets.token_urlsafe(32)
        key = self._key(session_id)

        self._client.setex(
            key,
            self.settings.session_ttl_seconds,
            user_id,
        )

        return session_id

    def get_user_id(self, session_id: str) -> str | None:
        if not session_id:
            return None

        return self._client.get(self._key(session_id))

    def delete_session(self, session_id: str) -> None:
        if not session_id:
            return

        self._client.delete(self._key(session_id))

    @staticmethod
    def _key(session_id: str) -> str:
        return f"roadmind:session:{session_id}"


@lru_cache
def get_session_store() -> SessionStore:
    return SessionStore()
