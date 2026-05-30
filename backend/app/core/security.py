from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_REQUEST_TIMES: dict[str, deque[datetime]] = defaultdict(deque)


def validate_rate_limit(request: Request) -> None:
    settings = get_settings()
    if settings.rate_limit_per_minute <= 0:
        return

    client_host = request.client.host if request.client else "unknown"
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=1)
    request_times = _REQUEST_TIMES[client_host]
    while request_times and request_times[0] < window_start:
        request_times.popleft()
    if len(request_times) >= settings.rate_limit_per_minute:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")
    request_times.append(now)


def security_headers() -> dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
