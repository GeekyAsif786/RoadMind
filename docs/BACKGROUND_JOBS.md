# Background Jobs

RoadMind uses RQ with Redis for production background jobs. If Redis or RQ is unavailable, the API falls back to a local thread executor so requests still return without blocking.

Key behavior:

- `POST /api/v1/predictions/train` enqueues model training and returns `job_id`.
- `POST /api/v1/predictions/train/sync` keeps the old synchronous behavior for development and debugging.
- `GET /api/v1/jobs/{job_id}` returns queued, started, finished, failed, or not_found.
- Worker command: `rq worker roadmind --url redis://redis:6379/0`.

The fallback executor is a degraded mode, not a replacement for production workers. Production should run the `worker` service from `docker-compose.yml`.
