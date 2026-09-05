"""Tests for the rate limiter (in-memory fallback + Redis global enforcement).

Full multi-process verification requires two live uvicorn workers sharing one
Redis; that is documented as a manual check in the commit message. These tests
prove the two code paths behave correctly in isolation:

- The in-memory fallback enforces a per-worker sliding window.
- The Redis path uses INCR+EXPIRE on a shared client, so two *separate* limiter
  invocations (standing in for two workers) share the same counter -> the limit
  is global, not multiplied by worker count.
"""

import app.core.security as security


class _FakeRequest:
    def __init__(self, host="1.2.3.4"):
        self.client = type("C", (), {"host": host})()


class _FakeRedis:
    """Minimal INCR/EXPIRE store shared across 'workers'."""

    def __init__(self):
        self.store = {}

    def incr(self, key):
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def expire(self, key, ttl):
        return True


def _set_limit(monkeypatch, tmp_path, limit, cache_enabled):
    from app.core.config import get_settings

    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", str(limit))
    monkeypatch.setenv("CACHE_ENABLED", "true" if cache_enabled else "false")
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()


def test_memory_fallback_enforces_limit(monkeypatch, tmp_path):
    from fastapi import HTTPException
    from app.core.config import get_settings

    _set_limit(monkeypatch, tmp_path, limit=3, cache_enabled=False)
    # Reset in-process state for the test host.
    security._REQUEST_TIMES.clear()
    monkeypatch.setattr(security, "_redis_client", lambda: None)

    req = _FakeRequest("mem-host")
    # First 3 allowed.
    for _ in range(3):
        security.validate_rate_limit(req)
    # 4th rejected.
    try:
        security.validate_rate_limit(req)
        raised = False
    except HTTPException as exc:
        raised = exc.status_code == 429
    assert raised, "in-memory limiter should reject the 4th request over limit=3"
    get_settings.cache_clear()


def test_redis_path_is_global_across_workers(monkeypatch, tmp_path):
    from fastapi import HTTPException
    from app.core.config import get_settings

    _set_limit(monkeypatch, tmp_path, limit=5, cache_enabled=True)

    shared = _FakeRedis()
    # Both "workers" see the same shared redis client.
    monkeypatch.setattr(security, "_redis_client", lambda: shared)

    req = _FakeRequest("redis-host")

    # Worker A serves 3 requests, worker B serves 2 -> total 5, all allowed.
    for _ in range(3):
        security.validate_rate_limit(req)  # worker A
    for _ in range(2):
        security.validate_rate_limit(req)  # worker B

    # The 6th request (either worker) must be rejected because the counter is
    # shared globally, not per-worker.
    try:
        security.validate_rate_limit(req)
        raised = False
    except HTTPException as exc:
        raised = exc.status_code == 429
    assert raised, "shared Redis counter should enforce the limit globally"
    get_settings.cache_clear()


def test_redis_failure_falls_back_to_memory(monkeypatch, tmp_path):
    from app.core.config import get_settings

    _set_limit(monkeypatch, tmp_path, limit=100, cache_enabled=True)

    class _BrokenRedis:
        def incr(self, key):
            raise RuntimeError("redis down")

        def expire(self, key, ttl):
            raise RuntimeError("redis down")

    security._REQUEST_TIMES.clear()
    monkeypatch.setattr(security, "_redis_client", lambda: _BrokenRedis())

    req = _FakeRequest("broken-host")
    # Should not raise despite Redis errors (falls back to in-memory).
    security.validate_rate_limit(req)
    get_settings.cache_clear()
