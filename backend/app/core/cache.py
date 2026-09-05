import json
import logging
from collections.abc import Callable
from functools import lru_cache

from app.core.config import get_settings
from app.core.metrics import get_metrics

try:
    import redis
except ImportError:  # pragma: no cover - production images install redis, local dev may not.
    redis = None

logger = logging.getLogger(__name__)


class CacheClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: object | None = None
        if not self.settings.cache_enabled or not self.settings.redis_url:
            return
        if redis is None:
            logger.warning("CACHE_ENABLED=true but redis package is not installed; cache disabled.")
            return
        try:
            client = redis.Redis.from_url(self.settings.redis_url, decode_responses=True)
            client.ping()
            self._client = client
        except Exception as exc:  # Redis must never take down traffic operations.
            logger.warning("Redis cache unavailable; continuing without cache: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @property
    def raw_client(self) -> object | None:
        """Underlying redis client (or None). Used by the rate limiter so it can
        share the same connection instead of opening its own."""
        return self._client

    def get_json(self, key: str) -> object | None:
        if self._client is None:
            return None
        try:
            raw = self._client.get(key)
            metrics = get_metrics()
            if raw:
                if metrics.enabled:
                    metrics.cache_hits.inc()
                return json.loads(raw)
            if metrics.enabled:
                metrics.cache_misses.inc()
            return None
        except Exception as exc:
            logger.warning("Cache read failed for key=%s: %s", key, exc)
            return None

    def set_json(self, key: str, value: object, ttl_seconds: int | None = None) -> None:
        if self._client is None:
            return
        try:
            ttl = ttl_seconds or self.settings.cache_ttl_seconds
            self._client.setex(key, ttl, json.dumps(value))
        except Exception as exc:
            logger.warning("Cache write failed for key=%s: %s", key, exc)

    def get_or_set(self, key: str, loader: Callable[[], object], ttl_seconds: int | None = None) -> object:
        cached = self.get_json(key)
        if cached is not None:
            return cached
        value = loader()
        self.set_json(key, value, ttl_seconds=ttl_seconds)
        return value

    def delete(self, *keys: str) -> None:
        if self._client is None or not keys:
            return
        try:
            self._client.delete(*keys)
        except Exception as exc:
            logger.warning("Cache delete failed for keys=%s: %s", keys, exc)

    def delete_prefix(self, prefix: str) -> None:
        if self._client is None:
            return
        try:
            keys = list(self._client.scan_iter(f"{prefix}*"))
            if keys:
                self._client.delete(*keys)
        except Exception as exc:
            logger.warning("Cache prefix delete failed for prefix=%s: %s", prefix, exc)

    def health(self) -> dict[str, str]:
        if not self.settings.cache_enabled:
            return {"status": "disabled"}
        if self._client is None:
            return {"status": "unavailable"}
        try:
            self._client.ping()
            return {"status": "ok"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}


@lru_cache
def get_cache() -> CacheClient:
    return CacheClient()
