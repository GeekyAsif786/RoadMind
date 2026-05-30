# RoadMind Redis Caching

Date: 2026-05-30

## Goal

Phase 4 adds a Redis cache-aside layer for frequently read operational state while preserving existing behavior if Redis is disabled or unavailable.

## Configuration

```env
REDIS_URL=redis://redis:6379/0
CACHE_ENABLED=true
CACHE_TTL_SECONDS=30
```

`CACHE_ENABLED=false` disables all cache reads/writes. If Redis is unreachable, RoadMind logs a warning and falls back to PostgreSQL without failing API requests.

## Cached Data

| Cache prefix | Data | Invalidation |
| --- | --- | --- |
| `dashboard:summary:` | Dashboard summary including latest density, signal plan, prediction, and emergencies | Traffic writes, signal optimization, prediction writes, emergency writes |
| `traffic:latest:` | Latest traffic observations and density feed | Traffic observation writes |
| `signal_plans:latest:` | Latest signal plans | Signal optimization |
| `prediction:latest:` | Reserved latest prediction state | Prediction writes |
| `emergencies:active:` | Active emergency feed | Emergency create/clear |
| `emergency_corridors:` | Emergency corridor metadata | Corridor create and emergency cache invalidation |
| `intersections:` | Intersection metadata/list | Intersection create |

## Pattern

RoadMind uses cache-aside:

```text
read -> cache hit -> return cached payload
read -> cache miss -> query PostgreSQL -> store JSON payload with TTL -> return payload
write -> commit PostgreSQL -> delete affected cache keys/prefixes
```

This keeps PostgreSQL as the source of truth and avoids correctness dependence on Redis.

## Health Check

```text
GET /api/v1/health/cache
```

Responses:

```json
{"status":"ok"}
{"status":"disabled"}
{"status":"unavailable"}
```

## Operational Notes

- Cache TTL defaults to 30 seconds to reduce dashboard polling load without hiding state changes for long.
- Prefix invalidation uses Redis `SCAN`, not `KEYS`, to avoid blocking Redis on large keyspaces.
- Cached payloads are JSON DTOs, not SQLAlchemy ORM objects.
- Redis failures are logged and never prevent signal generation, emergency handling, or dashboard reads.
