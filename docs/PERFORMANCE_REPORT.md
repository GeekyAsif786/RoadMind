# Performance Report

Initial benchmark targets:

| Scenario | Intersections | Primary measurement |
| --- | ---: | --- |
| Small arterial grid | 10 | API latency, DB latency |
| District deployment | 50 | Dashboard and signal optimization latency |
| City zone | 100 | Prediction and cache hit behavior |
| Large deployment | 500 | Queue depth, DB indexes, fallback behavior |

Benchmark entry point:

```bash
cd backend
python tests/performance/benchmark_api.py
```

Current expected improvements from Phases 1-12:

- Indexed traffic, signal, prediction, detection, and emergency lookups.
- Redis cache-aside reads for hot dashboard and latest-data paths.
- Background jobs for model training.
- Signal fallback hierarchy so detection backlog does not block timing generation.

Run this report against a deployed environment after loading representative observations for each intersection count.
