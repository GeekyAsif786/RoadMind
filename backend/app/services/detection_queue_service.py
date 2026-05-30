import logging
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Queue
from uuid import UUID

from app.core.config import get_settings
from app.core.metrics import get_metrics

logger = logging.getLogger(__name__)


class DetectionQueueService:
    """
    Bounded worker pool for camera frames.
    Signal generation reads the latest valid state and never waits on this queue.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._executor = ThreadPoolExecutor(
            max_workers=self.settings.detection_worker_count,
            thread_name_prefix="roadmind-detection",
        )
        self._pending: Queue[Future] = Queue()

    def submit_frame(self, intersection_id: UUID, image_bytes: bytes, handler) -> str:
        future = self._executor.submit(handler, image_bytes, intersection_id, True)
        self._pending.put(future)
        self._trim_completed()
        get_metrics().set_queue_depth(self._pending.qsize())
        return str(id(future))

    def status(self) -> dict[str, object]:
        self._trim_completed()
        return {
            "queued_frames": self._pending.qsize(),
            "active_workers": self.settings.detection_worker_count,
            "batch_size": self.settings.detection_batch_size,
            "fallback_mode": f"{self.settings.yolo_device}_then_prediction_or_last_known_good",
        }

    def _trim_completed(self) -> None:
        retained: Queue[Future] = Queue()
        while not self._pending.empty():
            future = self._pending.get()
            if not future.done():
                retained.put(future)
        self._pending = retained


detection_queue = DetectionQueueService()
