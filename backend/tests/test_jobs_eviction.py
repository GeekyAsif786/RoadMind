"""Tests for the local job queue eviction cap (app.core.jobs.JobQueue).

When Redis/RQ is not configured, jobs are tracked in an in-process dict. These
tests confirm that dict is bounded (oldest terminal jobs evicted) and that
still-running jobs are never dropped.
"""

import threading
import time

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


def test_eviction_keeps_dict_bounded_and_drops_oldest_finished(queue):
    from app.core.jobs import LOCAL_JOBS_MAX

    # Enqueue well over the cap of trivial jobs and let them finish.
    n = LOCAL_JOBS_MAX + 50
    ids = [queue.enqueue("noop", lambda: {"ok": True}) for _ in range(n)]
    queue._executor.shutdown(wait=True)  # ensure all complete

    # The dict must never exceed the cap.
    assert len(queue._local_jobs) <= LOCAL_JOBS_MAX

    # The oldest jobs should have been evicted; the most recent should remain.
    assert ids[-1] in queue._local_jobs
    assert ids[0] not in queue._local_jobs


def test_running_jobs_are_not_evicted(queue):
    from app.core.jobs import LOCAL_JOBS_MAX

    release = threading.Event()

    def _blocking_job():
        release.wait(timeout=10)
        return {"done": True}

    # Start a couple of long-running jobs (they stay "started" until released).
    running_ids = [queue.enqueue("block", _blocking_job) for _ in range(2)]

    # Give the executor a moment to mark them "started".
    for _ in range(50):
        if all(queue._local_jobs[j]["status"] == "started" for j in running_ids):
            break
        time.sleep(0.02)

    # Now flood with fast finished jobs to trigger eviction well past the cap.
    for _ in range(LOCAL_JOBS_MAX + 50):
        queue.enqueue("noop", lambda: {"ok": True})
        # let the fast ones finish so they become terminal (evictable)
        time.sleep(0)
    queue._executor.shutdown(wait=False)

    # Running jobs must survive eviction even though they are the oldest.
    for j in running_ids:
        assert j in queue._local_jobs, "a still-running job was evicted"

    # Release and drain.
    release.set()


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
