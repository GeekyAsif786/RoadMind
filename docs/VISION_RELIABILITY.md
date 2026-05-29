# Vision Reliability

Signal timing does not depend on a single live YOLO inference.

Decision hierarchy:

1. Fresh vehicle detection
2. Latest ML prediction
3. Latest valid historical observation
4. Static safe fallback plan

`DETECTION_FRESHNESS_SECONDS` controls how long a detection can drive timing. If YOLO is unavailable, crashes, or optional dependencies are missing, detection falls back to the existing OpenCV path and the signal optimizer continues using prediction or last-known-good state.

Last-known-good state is stored per intersection in `intersection_signal_states` and mirrored in Redis when cache is enabled.

Queue policy:

- Camera ingestion should submit frames to `DetectionQueueService`.
- Signal generation never waits for the queue.
- Queue status is exposed at `GET /api/v1/detections/queue/status`.

Metrics:

- Detection freshness
- Detection latency
- Prediction latency
- Queue depth
- Fallback activation count
- YOLO failure count
