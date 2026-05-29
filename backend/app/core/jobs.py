import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from uuid import uuid4

from app.core.config import get_settings

try:
    import redis
    from rq import Queue
    from rq.job import Job
except ImportError:  # pragma: no cover - optional queue dependencies are installed in production images.
    redis = None
    Queue = None
    Job = None

logger = logging.getLogger(__name__)


class JobQueue:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="roadmind-job")
        self._local_jobs: dict[str, dict[str, object]] = {}
        self._queue: object | None = None
        self._redis_connection: object | None = None

        if not self.settings.job_queue_enabled or not self.settings.redis_url:
            return
        if redis is None or Queue is None:
            logger.warning("JOB_QUEUE_ENABLED=true but RQ dependencies are unavailable; using local background jobs.")
            return
        try:
            connection = redis.Redis.from_url(self.settings.redis_url)
            connection.ping()
            self._redis_connection = connection
            self._queue = Queue("roadmind", connection=connection)
        except Exception as exc:
            logger.warning("RQ unavailable; using local background jobs: %s", exc)

    def enqueue(self, job_name: str, func, *args: object, **kwargs: object) -> str:
        if self._queue is not None:
            queued = self._queue.enqueue(func, *args, **kwargs, job_timeout="30m")
            return str(queued.id)

        job_id = str(uuid4())
        self._local_jobs[job_id] = {"id": job_id, "status": "queued", "result": None, "error": None}
        self._executor.submit(self._run_local, job_id, func, *args, **kwargs)
        return job_id

    def status(self, job_id: str) -> dict[str, object]:
        if self._redis_connection is not None and Job is not None:
            try:
                job = Job.fetch(job_id, connection=self._redis_connection)
                result = job.result if isinstance(job.result, dict) else None
                error = self._format_error(job.exc_info) if job.is_failed else None
                return {"id": job_id, "status": job.get_status(), "result": result, "error": error}
            except Exception as exc:
                logger.warning("Unable to fetch RQ job status for job=%s: %s", job_id, exc)

        return self._local_jobs.get(
            job_id,
            {"id": job_id, "status": "not_found", "result": None, "error": "Job not found"},
        )

    def _run_local(self, job_id: str, func, *args: object, **kwargs: object) -> None:
        self._local_jobs[job_id]["status"] = "started"
        try:
            result = func(*args, **kwargs)
            self._local_jobs[job_id]["result"] = result if isinstance(result, dict) else {"value": result}
            self._local_jobs[job_id]["status"] = "finished"
        except Exception as exc:
            logger.exception("Local background job failed: job=%s", job_id)
            self._local_jobs[job_id]["status"] = "failed"
            self._local_jobs[job_id]["error"] = self._format_error(traceback.format_exc()) or str(exc)

    @staticmethod
    def _format_error(error: str | None) -> str | None:
        if not error:
            return None
        lines = [line.strip() for line in error.splitlines() if line.strip()]
        return lines[-1] if lines else error


@lru_cache
def get_job_queue() -> JobQueue:
    return JobQueue()
