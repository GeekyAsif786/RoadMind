"""Request hardening helpers: rate limiting and security headers.

Rate limiting is enforced **globally** across all workers when Redis is
available (INCR + EXPIRE on a per-client, per-minute key). With multiple uvicorn
workers, an in-process counter would let each worker enforce the limit
independently, making the effective limit N x the configured value. When Redis
is unavailable (local dev without Redis), it falls back to the original
in-process sliding-window implementation so local development still works.
"""

import logging
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# In-process fallback state (per-worker) used only when Redis is unavailable.
_REQUEST_TIMES: dict[str, deque[datetime]] = defaultdict(deque)


def _redis_client():
    """Return the shared redis client if cache/redis is available, else None."""
    try:
        from app.core.cache import get_cache

        return get_cache().raw_client
    except Exception as exc:  # never let rate-limiting infra take down requests
        logger.debug("Rate limiter could not obtain redis client: %s", exc)
        return None


def _rate_limited_redis(client, client_host: str, limit: int) -> bool:
    """Fixed-window limiter shared across workers.

    Uses one key per client per calendar minute. INCR returns the running count;
    EXPIRE is set on first hit so the key self-cleans after the window. Returns
    True if the request should be rejected.
    """
    minute_bucket = datetime.now(UTC).strftime("%Y%m%d%H%M")
    key = f"ratelimit:{client_host}:{minute_bucket}"
    try:
        count = client.incr(key)
        if count == 1:
            # Slightly longer than the window so the key outlives clock skew,
            # then expires on its own.
            client.expire(key, 70)
        return count > limit
    except Exception as exc:
        # If Redis misbehaves mid-request, fail open to the in-memory limiter
        # rather than rejecting or crashing the request.
        logger.warning("Redis rate limiter failed; falling back in-process: %s", exc)
        return _rate_limited_memory(client_host, limit)


def _rate_limited_memory(client_host: str, limit: int) -> bool:
    """Original per-worker sliding-window limiter. Returns True to reject."""
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=1)
    request_times = _REQUEST_TIMES[client_host]
    while request_times and request_times[0] < window_start:
        request_times.popleft()
    if len(request_times) >= limit:
        return True
    request_times.append(now)
    return False


def validate_rate_limit(request: Request) -> None:
    settings = get_settings()
    if settings.rate_limit_per_minute <= 0:
        return

    client_host = request.client.host if request.client else "unknown"
    limit = settings.rate_limit_per_minute

    client = _redis_client() if settings.cache_enabled else None
    if client is not None:
        rejected = _rate_limited_redis(client, client_host, limit)
    else:
        rejected = _rate_limited_memory(client_host, limit)

    if rejected:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")


def security_headers() -> dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
