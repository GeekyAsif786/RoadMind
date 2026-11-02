# Production Deployment

Services:

- PostgreSQL: primary relational store and Alembic migration target.
- Redis: cache, RQ queue, and degraded-state acceleration.
- Backend: FastAPI API server.
- Worker: RQ worker for training and heavy jobs.
- Frontend: Vite/React operator dashboard.
- Monitoring: scrape `/metrics` from the backend.

Recommended startup:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

Required production settings:

```env
ENVIRONMENT=production
AUTO_CREATE_TABLES=false
ENABLE_AUTH=true
API_KEY=<strong-secret>
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://redis:6379/0
CACHE_ENABLED=true
JOB_QUEUE_ENABLED=true
TRAFFIC_MODEL=xgboost
```

Migration workflow:

```bash
cd backend
alembic upgrade head
```

Production must not rely on SQLAlchemy `create_all`. Startup validation blocks production if `AUTO_CREATE_TABLES=true`.

Operational checks:

- `/health`
- `/health/db`
- `/health/cache`
- `/health/ml`
- `/metrics`

For multi-instance production, move rate limiting to an ingress layer and run multiple RQ workers sized to GPU/CPU capacity.

## Web Admin Authentication

The dashboard authenticates with an HttpOnly session cookie (`roadmind_session`) backed by Redis. Startup validation blocks production unless `SESSION_COOKIE_SECURE=true` and every `CORS_ORIGINS` entry is `https://`, so the dashboard and API must both be served over HTTPS.

Create the first administrator once, after `alembic upgrade head`, from an interactive terminal:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python -m app.db.create_admin
```

The command refuses to run if any user already exists. No default credentials exist.

### Required before public exposure: CSRF protection

**Not implemented yet.** Session-authenticated, state-changing endpoints (`POST`, `PUT`, `PATCH`, `DELETE` under `/api/v1`), plus `/auth/login` (which issues the cookie) and `/auth/logout`, currently rely only on `SameSite=Lax` cookies and the CORS allowlist. That blocks typical cross-site form posts, but it does not protect against requests from other origins on the same site (sibling subdomains or other ports on the same host), and CORS alone is not a CSRF control.

Before the dashboard is reachable from any network you do not fully control, add one of:

- **CSRF tokens**: a per-session token issued by the backend, sent by the frontend in a custom header (for example `X-CSRF-Token`) on every state-changing request, and verified server-side against the session.
- **Strict Origin validation**: backend middleware that rejects every state-changing, cookie-authenticated request whose `Origin` header (or, if absent, `Referer`) is not an exact match for a configured HTTPS dashboard origin. Requests with neither header are rejected.

Device endpoints authenticated with `X-Device-Credential` are not cookie-based and are unaffected. Until one of these controls is in place, keep the deployment on a trusted network or behind an authenticating reverse proxy.
