FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
ARG INSTALL_YOLO=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-vision.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_YOLO" = "true" ]; then pip install --no-cache-dir -r requirements-vision.txt; fi

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app

# Run as a non-root user. Create the writable model dir (MODEL_DIR defaults to
# /app/runtime_models) BEFORE dropping privileges and give appuser ownership of
# /app so the app can create/write model artifacts. Docker seeds a fresh named
# volume mounted here from the image path, inheriting this ownership.
RUN useradd -m appuser \
    && mkdir -p /app/runtime_models \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
