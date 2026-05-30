from functools import lru_cache
from time import perf_counter

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest
except ImportError:  # pragma: no cover - optional dependency in minimal local environments.
    Counter = None
    Gauge = None
    Histogram = None
    generate_latest = None


class Metrics:
    def __init__(self) -> None:
        if Counter is None or Gauge is None or Histogram is None:
            self.enabled = False
            return

        self.enabled = True
        self.api_latency = Histogram("roadmind_api_latency_seconds", "API request latency", ["method", "path"])
        self.prediction_latency = Histogram("roadmind_prediction_latency_seconds", "Prediction latency")
        self.detection_latency = Histogram("roadmind_detection_latency_seconds", "Detection latency")
        self.db_latency = Histogram("roadmind_db_latency_seconds", "Database operation latency", ["operation"])
        self.cache_hits = Counter("roadmind_cache_hits_total", "Cache hits")
        self.cache_misses = Counter("roadmind_cache_misses_total", "Cache misses")
        self.queue_depth = Gauge("roadmind_detection_queue_depth", "Detection queue depth")
        self.fallbacks = Counter("roadmind_signal_fallbacks_total", "Signal fallback activations", ["source"])
        self.yolo_failures = Counter("roadmind_yolo_failures_total", "YOLO inference failures")
        self.camera_disconnects = Counter("roadmind_camera_disconnects_total", "Camera disconnect count")
        self.detection_freshness = Gauge("roadmind_detection_freshness_seconds", "Detection freshness", ["intersection_id"])

    def render(self) -> bytes:
        if not self.enabled or generate_latest is None:
            return b""
        return generate_latest()

    def observe_api(self, method: str, path: str, seconds: float) -> None:
        if self.enabled:
            self.api_latency.labels(method=method, path=path).observe(seconds)

    def observe_detection(self, seconds: float) -> None:
        if self.enabled:
            self.detection_latency.observe(seconds)

    def observe_prediction(self, seconds: float) -> None:
        if self.enabled:
            self.prediction_latency.observe(seconds)

    def set_queue_depth(self, depth: int) -> None:
        if self.enabled:
            self.queue_depth.set(depth)

    def record_fallback(self, source: str) -> None:
        if self.enabled:
            self.fallbacks.labels(source=source).inc()

    def record_yolo_failure(self) -> None:
        if self.enabled:
            self.yolo_failures.inc()

    def set_detection_freshness(self, intersection_id: str, seconds: float) -> None:
        if self.enabled:
            self.detection_freshness.labels(intersection_id=intersection_id).set(seconds)


class Timer:
    def __init__(self) -> None:
        self.started_at = perf_counter()

    def elapsed(self) -> float:
        return perf_counter() - self.started_at


@lru_cache
def get_metrics() -> Metrics:
    return Metrics()
