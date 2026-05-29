# Observability And Security

Observability:

- Structured logging is enabled through `structlog` when installed.
- Every HTTP response includes `X-Request-ID`.
- Prometheus metrics are exposed at `/metrics`.
- Health checks are available at `/health`, `/health/db`, `/health/cache`, and `/health/ml` as well as under `/api/v1`.

Security hardening:

- API key authentication behavior is preserved.
- Uploads are limited by `UPLOAD_MAX_BYTES`.
- Image uploads reject non-image content types.
- In-memory rate limiting is controlled by `RATE_LIMIT_PER_MINUTE`.
- Security headers are added to responses.

The in-memory rate limiter is suitable for a single backend process. For multi-worker production deployments, move rate limiting to an edge proxy or Redis-backed limiter.
