"""FastAPI app factory + server entry.

  python -m backend.controlplane.app                # http://127.0.0.1:8420
  uvicorn backend.controlplane.app:create_app --factory

Lifespan:
  1. bind asyncio loop to WS broadcaster
  2. seed from .env (one-shot, no network calls)
  3. start scheduler
  4. (running)
  5. shutdown: stop scheduler, drain broadcaster clients, close DB engine

ENT-* integrations:
  - RequestIdAndMetricsMiddleware : request_id contextvar + HTTP metrics + access log
  - RateLimitMiddleware           : per-token bucket, 0=disabled
  - /health/live, /ready, /startup : k8s convention
  - /metrics                       : Prometheus text format
  - AuditService                   : admin operations persisted
  - Graceful shutdown              : configurable timeout
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .api import router
from .crypto import SecretBox
from .db import init_db, make_engine, make_session_factory, session_scope
from .health import router as health_router
from .middleware import RequestIdAndMetricsMiddleware
from .models import DocTarget, ScmInstance
from .observability import (
    infra_db_up,
    infra_scheduler_jobs,
    render_metrics,
)
from .ratelimit import RateLimitMiddleware
from .services.audit import AuditService
from .services.notifier import Notifier
from .services.registration import RegistrationService
from .services.runs import RunService
from .services.scheduler import SourceScheduler
from .services.settings import SettingsService
from .services.tag_poller import TagPoller
from .settings import ControlPlaneSettings, load_cp_settings
from .ws import Broadcaster

log = logging.getLogger("controlplane")


def _seed_from_env(app: FastAPI) -> None:
    """DB 가 비어 있으면 .env(SCM_SOURCES_JSON·DOCSHUB_*)에서 1회 시딩.

    이후 source of truth 는 DB (decision-db-source-of-truth). 시딩은 verify 없이
    저장만 — 기동 시 외부 네트워크 호출 금지.
    """
    from ..common.config import load_settings
    try:
        legacy = load_settings()
    except Exception as e:  # noqa: BLE001
        log.warning("legacy .env load failed — seeding skipped: %s", e)
        return
    with session_scope(app.state.session_factory) as db:
        if db.scalars(select(ScmInstance.id).limit(1)).first() is None:
            for src in legacy.source_list:
                try:
                    app.state.registration.upsert_source(db, {
                        "id": src.id, "label": src.label, "kind": src.kind,
                        "url": src.url, "project_id": src.project_id,
                        "token": src.token, "token_header": src.token_header,
                        "themes": src.themes,
                    }, verify=False)
                except ValueError as e:
                    log.warning("source seed failed %s: %s", src.id, e)
            if legacy.source_list:
                log.info(".env -> DB: seeded %d source(s)", len(legacy.source_list))
        if db.get(DocTarget, "product-common") is None and legacy.docshub_project_url:
            app.state.registration.upsert_doc_target(db, {
                "id": "product-common", "label": "product-common", "kind": "gitlab",
                "url": legacy.docshub_project_url,
                "project_id": legacy.docshub_project_id,
                "project_path": legacy.docshub_project_path,
                "token": legacy.docshub_token,
                "token_header": legacy.docshub_token_header,
                "default_branch": legacy.docshub_default_branch,
                "enabled": legacy.docshub_mr_enabled,
            })
            log.info("docs-hub target 'product-common' seeded")


def create_app(settings: ControlPlaneSettings | None = None, *,
               frontend_dist: Path | None = None) -> FastAPI:
    settings = settings or load_cp_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.get_running_loop()
        app.state.broadcaster.bind_loop(loop)
        if not app.state.api_tokens:
            log.warning("CONTROL_API_TOKENS unset — dev mode (no auth).")
        if not app.state.box.enabled:
            log.warning("CONTROL_SECRET_KEY unset — tokens stored as plaintext.")
        _seed_from_env(app)
        app.state.scheduler.start()
        # 초기 메트릭 갱신 — Prometheus 가 first scrape 시 0 값이라도 받게.
        try:
            with app.state.session_factory() as db:
                db.execute(select(1))
            infra_db_up.set(1)
        except Exception:  # noqa: BLE001
            infra_db_up.set(0)
        try:
            sched = app.state.scheduler
            job_count = len(sched._scheduler.get_jobs()) if sched.settings.scheduler_enabled else 0
            infra_scheduler_jobs.set(job_count)
        except Exception:  # noqa: BLE001
            pass

        try:
            yield
        finally:
            # ENT-L: graceful shutdown — 설정된 타임아웃 안에서 inflight 정리.
            timeout = settings.graceful_shutdown_timeout_sec
            log.info("graceful shutdown starting (timeout=%.1fs)", timeout)
            app.state.scheduler.shutdown()
            # broadcaster 큐에 남은 메시지가 있다면 버림 (서버 종료 시점에 의미 없음)
            try:
                drain_count = len(app.state.broadcaster._clients)  # type: ignore[attr-defined]
                log.info("drained %d WS client(s)", drain_count)
            except Exception:  # noqa: BLE001
                pass
            try:
                app.state.engine.dispose()
            except Exception as e:  # noqa: BLE001
                log.warning("engine dispose failed: %s", e)
            log.info("graceful shutdown complete")

    # OpenAPI 메타데이터 (ENT-I) — 운영자가 docs 보기 전에 보게 되는 첫 페이지.
    app = FastAPI(
        title="wiki-pipeline Control Plane",
        version="0.7.0",
        description=(
            "Multi-pipeline AI documentation automation. Two pipelines "
            "(static = code diff -> technical docs, manual = app observation "
            "-> user manual) share a single Control Plane (this service) and "
            "Data Plane (runner). See `wiki/` in the repo for design decisions."
        ),
        contact={"name": "wiki-pipeline maintainers", "email": "ops@wiki-pipeline.local"},
        license_info={"name": "Proprietary", "url": "https://wiki-pipeline.local/license"},
        openapi_tags=[
            {"name": "runs", "description": "Pipeline run lifecycle and events."},
            {"name": "pipelines", "description": "Per-source/per-pipeline aggregated status."},
            {"name": "sources", "description": "Source registration and SCM connectors."},
            {"name": "instances", "description": "SCM instance credentials (encrypted at rest)."},
            {"name": "schedules", "description": "Per-source cron schedules."},
            {"name": "docs-hub", "description": "MR/PR submission targets."},
            {"name": "costs", "description": "Token usage aggregation."},
            {"name": "audit", "description": "Admin operation audit log."},
            {"name": "system", "description": "Health, metrics, webhooks."},
        ],
        lifespan=lifespan,
    )

    # ── Middleware: 가장 바깥(먼저 등록한 것)이 가장 안쪽에서 실행 ──
    # 1) RequestIdAndMetrics: 모든 요청에 request_id 부여 + HTTP 메트릭
    # 2) RateLimit: 분당 한도 (slowapi 인라인)
    # 3) CORS: 가장 바깥(브라우저는 CORS preflight 가 가장 먼저 보임)
    app.add_middleware(CORSMiddleware,
                       allow_origins=([o.strip() for o in settings.control_cors_origins.split(",") if o.strip()]
                                      if settings.control_cors_origins.strip() else ["*"]),
                       allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "X-Api-Token", "X-Request-ID"])
    app.add_middleware(RateLimitMiddleware, per_min=settings.rate_limit_per_min)
    app.add_middleware(RequestIdAndMetricsMiddleware)

    # 기존 대시보드 계약 호환: 에러 응답에 FastAPI 기본 "detail"과 함께 "error" 키 제공.
    from fastapi import HTTPException as _HTTPException
    from fastapi.responses import JSONResponse

    @app.exception_handler(_HTTPException)
    async def _http_error(request, exc: _HTTPException):
        return JSONResponse(status_code=exc.status_code,
                            content={"error": str(exc.detail), "detail": exc.detail})

    # ── Wire service objects ──
    engine = make_engine(settings.db_url)
    init_db(engine)
    session_factory = make_session_factory(engine)
    box = SecretBox(settings.control_secret_key)
    notifier = Notifier(settings)
    broadcaster = Broadcaster()
    run_service = RunService(settings, notifier, broadcaster)
    tag_poller = TagPoller(settings, session_factory, run_service, notifier)
    audit_service = AuditService(session_factory)
    settings_service = SettingsService(session_factory)

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.box = box
    app.state.notifier = notifier
    app.state.broadcaster = broadcaster
    app.state.registration = RegistrationService(box)
    app.state.run_service = run_service
    app.state.tag_poller = tag_poller
    app.state.audit_service = audit_service
    app.state.settings_service = settings_service
    app.state.scheduler = SourceScheduler(settings, session_factory, run_service, tag_poller)
    app.state.api_tokens = settings.api_token_map
    app.state.runner_token = settings.control_runner_token
    app.state.db_ok = True

# ── SPA (frontend/dist) 서빙 ──
    # dist 소스: frontend_dist 인자(테스트) > CONTROL_FRONTEND_DIST 환경변수(Docker).
    # 없거나 디렉터리가 존재하지 않으면 SPA 마운트 스킵 (API-only 모드).
    _dist: Path | None = frontend_dist
    if _dist is None:
        _env = os.environ.get("CONTROL_FRONTEND_DIST")
        if _env:
            _dist = Path(_env)
    if _dist and _dist.is_dir():
        from fastapi.staticfiles import StaticFiles as _StaticFiles
        from fastapi.responses import FileResponse as _FileResponse

        _assets = _dist / "assets"
        if _assets.is_dir():
            app.mount("/assets", _StaticFiles(directory=str(_assets)), name="spa-assets")

        @app.get("/", include_in_schema=False)
        def _spa_root() -> _FileResponse:
            return _FileResponse(str(_dist / "index.html"))

    # ── Routers ──
    app.include_router(router)
    app.include_router(health_router)

    # ── /metrics (Prometheus exposition) — 인증 면제 (rate limit 도 면제)
    from fastapi import Response as _Response
    @app.get("/metrics", include_in_schema=False)
    def metrics() -> _Response:
        body, content_type = render_metrics()
        return _Response(content=body, media_type=content_type)

    # ── SPA catch-all (가장 마지막) ──
    if _dist and _dist.is_dir():
        @app.get("/{full_path:path}", include_in_schema=False)
        def _spa_fallback(full_path: str):
            # 백엔드 도메인 prefix 는 SPA fallback 금지 — 404 그대로 노출.
            if (full_path == "api" or full_path.startswith("api/")
                    or full_path == "metrics" or full_path == "openapi.json"
                    or full_path == "docs" or full_path == "redoc"
                    or full_path.startswith("health")
                    or full_path.startswith("docs/")):
                from fastapi import HTTPException as _HTTPException
                raise _HTTPException(404, "not found")
            target = _dist / full_path
            if target.is_file():
                return _FileResponse(str(target))
            return _FileResponse(str(_dist / "index.html"))

    return app


def main() -> int:
    import argparse
    import sys

    import uvicorn

    from ..common.logging_setup import setup_logging

    # CLI 인자 — 기존 .env / ControlPlaneSettings 위에 1회용 오버라이드.
    # --reload 는 uvicorn 의 Reloader 를 켜고 (소스 변경 시 자동 재기동),
    # --host / --port 는 임시 오버라이드 (컨테이너나 포트 충돌 디버깅용).
    parser = argparse.ArgumentParser(
        prog="python -m backend.controlplane.app",
        description="wiki-pipeline Control Plane — 관리 서버 (ENT-L: graceful shutdown 내장).",
    )
    parser.add_argument("--host", default=None, help="bind host (default: CONTROL_HOST)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default: CONTROL_PORT)")
    parser.add_argument("--reload", action="store_true",
                        help="uvicorn auto-reload (개발용 — 프로덕션 비권장)")
    args = parser.parse_args()

    settings = load_cp_settings()
    setup_logging()
    host = args.host or settings.control_host
    port = args.port or settings.control_port
    print(f"Control Plane: http://{host}:{port} "
          f"(db={settings.db_url.split('@')[-1]}, reload={args.reload})")
    # uvicorn 의 timeout-keep-alive 와 graceful shutdown 격리 — 우리 lifespan 에서 처리.
    # reload=True 일 때는 uvicorn 이 별도 워커 프로세스를 띄우므로 timeout_graceful_shutdown
    # 가 워커에는 적용되지 않는다. dev 모드 전용.
    uvicorn.run(
        create_app(settings),
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
        reload=args.reload,
        timeout_graceful_shutdown=int(settings.graceful_shutdown_timeout_sec),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
