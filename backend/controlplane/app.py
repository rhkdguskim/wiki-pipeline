"""FastAPI 앱 팩토리 + 서버 엔트리.

    python -m backend.controlplane.app                # http://127.0.0.1:8420
    uvicorn backend.controlplane.app:create_app --factory

기동 시: DB 스키마 부트스트랩 -> .env 소스 시딩(1회) -> 스케줄러 시작.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .api import router
from .crypto import SecretBox
from .db import init_db, make_engine, make_session_factory, session_scope
from .models import DocTarget, ScmInstance
from .services.notifier import Notifier
from .services.registration import RegistrationService
from .services.runs import RunService
from .services.scheduler import SourceScheduler
from .settings import ControlPlaneSettings, load_cp_settings

log = logging.getLogger("controlplane")


def _seed_from_env(app: FastAPI) -> None:
    """DB가 비어 있으면 .env(SCM_SOURCES_JSON·DOCSHUB_*)에서 1회 시딩 — 마이그레이션 편의.

    이후 source of truth는 DB다 (decision-db-source-of-truth). 시딩은 verify 없이
    저장만 한다 (기동 시 외부 네트워크 호출 금지).
    """
    from ..common.config import load_settings
    try:
        legacy = load_settings()
    except Exception as e:  # noqa: BLE001
        log.warning("레거시 .env 로드 실패 — 시딩 생략: %s", e)
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
                    log.warning("소스 시딩 실패 %s: %s", src.id, e)
            if legacy.source_list:
                log.info(".env에서 소스 %d건 시딩", len(legacy.source_list))
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
            log.info("docs-hub target 'product-common' 시딩")


def create_app(settings: ControlPlaneSettings | None = None) -> FastAPI:
    settings = settings or load_cp_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not app.state.api_tokens:
            log.warning("CONTROL_API_TOKENS 미설정 — 개발 모드(무인증)로 기동합니다.")
        if not app.state.box.enabled:
            log.warning("CONTROL_SECRET_KEY 미설정 — 토큰이 평문으로 저장됩니다.")
        _seed_from_env(app)
        app.state.scheduler.start()
        try:
            yield
        finally:
            app.state.scheduler.shutdown()

    app = FastAPI(title="wiki-pipeline control plane", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_methods=["*"],
        allow_headers=["*"],
    )

    # 기존 대시보드 계약 호환: 에러 응답에 FastAPI 기본 "detail"과 함께 "error" 키 제공.
    from fastapi import HTTPException as _HTTPException
    from fastapi.responses import JSONResponse

    @app.exception_handler(_HTTPException)
    async def _http_error(request, exc: _HTTPException):
        return JSONResponse(status_code=exc.status_code,
                            content={"error": str(exc.detail), "detail": exc.detail})

    engine = make_engine(settings.db_url)
    init_db(engine)
    session_factory = make_session_factory(engine)
    box = SecretBox(settings.control_secret_key)
    notifier = Notifier(settings)
    run_service = RunService(settings, notifier)

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.box = box
    app.state.notifier = notifier
    app.state.registration = RegistrationService(box)
    app.state.run_service = run_service
    app.state.scheduler = SourceScheduler(settings, session_factory, run_service)
    app.state.api_tokens = settings.api_token_map
    app.state.runner_token = settings.control_runner_token
    app.state.db_ok = True

    app.include_router(router)
    return app


def main() -> int:
    import uvicorn

    from ..common.logging_setup import setup_logging

    settings = load_cp_settings()
    setup_logging()
    print(f"Control Plane: http://{settings.control_host}:{settings.control_port} "
          f"(db={settings.db_url.split('@')[-1]})")
    uvicorn.run(create_app(settings), host=settings.control_host,
                port=settings.control_port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
