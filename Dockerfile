# wiki-pipeline — 단일 포트 통합 이미지 (Control Plane + Frontend SPA)
#
# 4-stage build:
#   1. frontend-builder : Node 20 — npm ci + vite build → frontend/dist
#   2. backend-builder  : Python 3.12 — pip install requirements → site-packages
#   3. runtime          : Python 3.12-slim — backend code + frontend dist + entrypoint
#
# 포트 8420 하나로 API(/api/*) 와 SPA(/) 모두 서빙.
# dist 가 없으면 backend 만 단독으로 기동 (API-only 모드).

# ── Stage 1: Frontend SPA build ──────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /build

# 의존성 먼저 캐시 — 소스만 바뀌면 npm ci 가 재실행되지 않음.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python deps build ───────────────────────────────
FROM python:3.12-slim AS backend-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# cryptography 등 wheel 없는 패키지 대비: gcc/libffi/libssl 헤더.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt

# ── Stage 3: Runtime ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8420

# 런타임 최소 라이브러리 (cryptography → libffi/libssl, healthcheck → curl).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 libssl3 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /bin/bash wpipe

WORKDIR /app

# Python 패키지 (builder 에서 복사 — wheel 캐시 없이 슬림 이미지).
COPY --from=backend-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# 백엔드 코드 + wiki 운영 지침(schema.md).
COPY backend /app/backend
COPY schema.md /app/schema.md

# 프런트 빌드 결과물 — SPA 서빙용.
COPY --from=frontend-builder /build/dist /app/frontend/dist

# 영속 데이터 — 운영 시 bind mount 권장:
#   -v <host_out>:/app/out     # run artifacts + JSONL events
#   -v <host_db>:/app/db       # SQLite (또는 CONTROL_DB_URL 로 외부 PostgreSQL)
#   -v <host_env>:/app/backend/.env:ro  # 시크릿
VOLUME ["/app/out", "/app/db"]

# 단일 포트 노출 — API + SPA + WebSocket + /metrics 모두 8420.
EXPOSE 8420

# /health/live 는 인증 면제 + 가벼움 — 컨테이너 헬스체크에 적합.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT}/health/live || exit 1

# 비루트 실행 + JSON 로그 (운영용).
ENV CONTROL_HOST=0.0.0.0 \
    CONTROL_PORT=8420 \
    LOG_FORMAT=json

USER wpipe

# Control Plane 기동 — uvicorn 은 lifespan shutdown 으로 graceful 처리.
ENTRYPOINT ["python", "-m", "backend.controlplane.app"]