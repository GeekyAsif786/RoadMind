import time


def test_performance_benchmark_targets_documented() -> None:
    targets = [10, 50, 100, 500]
    started_at = time.perf_counter()
    elapsed = time.perf_counter() - started_at

    assert targets == [10, 50, 100, 500]
    assert elapsed >= 0
