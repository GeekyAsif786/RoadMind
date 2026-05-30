import statistics
import time
from dataclasses import dataclass
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class BenchmarkResult:
    intersections: int
    endpoint: str
    samples: int
    p50_ms: float
    p95_ms: float


def measure_endpoint(base_url: str, endpoint: str, samples: int = 20) -> tuple[float, float]:
    latencies: list[float] = []
    for _ in range(samples):
        started_at = time.perf_counter()
        request = Request(f"{base_url.rstrip('/')}{endpoint}", method="GET")
        with urlopen(request, timeout=10) as response:
            response.read()
        latencies.append((time.perf_counter() - started_at) * 1000)
    return statistics.median(latencies), statistics.quantiles(latencies, n=20)[18]


def run_benchmarks(base_url: str = "http://localhost:8000/api/v1") -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []
    for intersections in (10, 50, 100, 500):
        p50_ms, p95_ms = measure_endpoint(base_url, "/dashboard/summary")
        results.append(
            BenchmarkResult(
                intersections=intersections,
                endpoint="/dashboard/summary",
                samples=20,
                p50_ms=p50_ms,
                p95_ms=p95_ms,
            )
        )
    return results


if __name__ == "__main__":
    for result in run_benchmarks():
        print(result)
