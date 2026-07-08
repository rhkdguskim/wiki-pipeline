# wiki-pipeline Control Plane — production image
# Multi-stage: builder (deps compile) + runner (slim runtime)
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build deps — gcc, libffi (cryptography wheels handle most but extras needed for some)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt

# Runtime stage
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8420

# Minimal runtime libs (cryptography needs libssl/libffi)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 libssl3 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /bin/bash wpipe

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY backend /app/backend
COPY schema.md /app/schema.md

# Tini-like signal handling via dumb-init would be ideal, but python:3.12-slim
# does not ship it. We rely on uvicorn's SIGTERM handling + lifespan shutdown.

# Non-root execution
USER wpipe

# Persistent state — bind mount in production:
#   -v /var/lib/wpipe/out:/app/out       (run artifacts, JSONL events)
#   -v /var/lib/wpipe/db:/app/db         (SQLite) OR set CONTROL_DB_URL=postgresql://...
#   -v /var/lib/wpipe/.env:/app/backend/.env:ro  (secrets)
VOLUME ["/app/out"]
EXPOSE 8420

# Built-in healthcheck hits our /health/live (cheap, no auth required)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT}/health/live || exit 1

# Defaults overridable at run time
ENV CONTROL_HOST=0.0.0.0 \
    CONTROL_PORT=8420 \
    LOG_FORMAT=json

# Entrypoint — uvicorn picks up CONTROL_HOST/CONTROL_PORT from env
ENTRYPOINT ["python", "-m", "backend.controlplane.app"]
