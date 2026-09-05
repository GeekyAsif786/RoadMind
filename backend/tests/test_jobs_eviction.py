"""Tests for the local job queue eviction cap (app.core.jobs.JobQueue).

When Redis/RQ is not configured, jobs are tracked in an in-process dict. These
tests confirm that dict is bounded (oldest terminal jobs evicted) and that
still-running jobs are never dropped.
"""

import pytest


@pytest.fixture()
def queue(monkeypatch, tmp_path):
    from app.core.config import get_settings

    # Force the local (no-Redis) code path.
    monkeypatch.setenv("JOB_QUEUE_ENABLED", "false")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()
    from app.core.jobs import JobQueue

    q = JobQueue()
    yield q
    q._executor.shutdown(wait=True)
    get_settings.cache_clear()


class _InlineExecutor:
    """Runs submitted callables synchronously so job status is deterministic."""

    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)

    def shutdown(self, wait=True):
        pass


def test_eviction_keeps_dict_bounded_and_drops_oldest_finished(queue):
    from app.core.jobs import LOCAL_JOBS_MAX

    # Run jobs inline so each enqueued job is already 'finished' before the next
    # enqueue() runs eviction. This removes any dependence on thread timing.
    queue._executor = _InlineExecutor()

    n = LOCAL_JOBS_MAX + 50
    ids = [queue.enqueue("noop", lambda: {"ok": True}) for _ in range(n)]

    # The dict must never exceed the cap.
    assert len(queue._local_jobs) <= LOCAL_JOBS_MAX

    # Oldest finished jobs evicted; most recent retained.
    assert ids[-1] in queue._local_jobs
    assert ids[0] not in queue._local_jobs


def test_running_jobs_are_not_evicted(queue):
    from app.core.jobs import LOCAL_JOBS_MAX

    # Deterministic: seed two jobs that are 'started' (as if still running), then
    # flood with inline (immediately finished) jobs. Eviction on each enqueue
    # must skip the started jobs even though they are the oldest entries.
    queue._executor = _InlineExecutor()
    queue._local_jobs.clear()
    queue._local_jobs["run1"] = {"id": "run1", "status": "started", "result": None, "error": None}
    queue._local_jobs["run2"] = {"id": "run2", "status": "started", "result": None, "error": None}

    for _ in range(LOCAL_JOBS_MAX + 50):
        queue.enqueue("noop", lambda: {"ok": True})

    assert len(queue._local_jobs) <= LOCAL_JOBS_MAX
    # Running jobs survive despite being the oldest entries.
    assert "run1" in queue._local_jobs
    assert "run2" in queue._local_jobs


def test_evict_directly_skips_running(queue):
    from app.core.jobs import LOCAL_JOBS_MAX

    # Seed the dict manually: first two are 'started' (running), rest finished.
    queue._local_jobs.clear()
    queue._local_jobs["run1"] = {"id": "run1", "status": "started"}
    queue._local_jobs["run2"] = {"id": "run2", "status": "started"}
    for i in range(LOCAL_JOBS_MAX + 10):
        queue._local_jobs[f"fin{i}"] = {"id": f"fin{i}", "status": "finished"}

    queue._evict_local_jobs()

    assert len(queue._local_jobs) <= LOCAL_JOBS_MAX
    # Running jobs preserved.
    assert "run1" in queue._local_jobs
    assert "run2" in queue._local_jobs
    # Oldest finished evicted first.
    assert "fin0" not in queue._local_jobs
