"""Control Plane HTTP API.

기존 대시보드 프런트 계약(/api/runs·run-summary·events·sources·overview·docs-hub)을
유지하면서, 소스는 DB source of truth로, 이벤트는 DB(webhook 적재) 우선 + 레거시
JSONL 파일 폴백으로 서빙한다. 쓰기·webhook은 자체 토큰 인증 (decision-server-vm-self-token).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import (APIRouter, Body, Depends, HTTPException, Query, Request,
                     WebSocket, WebSocketDisconnect)
from sqlalchemy import select
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from ..common.docshub import build_mr_plan, submit_change_request
from ..common.logging_setup import current_request_id
from . import projection
from .models import (DocTarget, ManualScenarioSet, Run, RunArtifact,
                     RunCoverageReport, RunEvent, RunEvidenceItem,
                     RunEvidencePack, RunQualityReport, RunVncSession,
                     ScmInstance, Source, SourceBranch, SourceManualProfile,
                     SourceReleaseTag, SourceSchedule)
from .schedule import normalize_schedule_payload
from .schemas import (
    AuditRecentResponse,
    CostsResponse,
    OverviewResponse,
    PipelineStatusResponse,
    RunSummary,
)
from .timeutil import isoformat_z

log = logging.getLogger("controlplane.api")

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# webhook 1회당 최대 이벤트 수 — 동기 워커 블로킹 방지 (러너는 청크 분할).
_WEBHOOK_EVENTS_MAX = 500

# 러너 subprocess에 전달할 환경변수 화이트리스트 — 부모 env 전체 상속 금지
# (CONTROL_SECRET_KEY 등 민감 정보 누출 방지).
_RUNNER_ENV_ALLOWLIST = (
    "PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
    "SYSTEMROOT", "PYTHONPATH", "PYTHONHOME",
    "LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL",
    "LLM_MAX_TOKENS", "LLM_TEMPERATURE", "LLM_TIMEOUT", "LLM_RETRY_ATTEMPTS",
    "OUT_DIR", "LOG_LEVEL", "LOG_FORMAT",
)

router = APIRouter()


# ── 의존성 ───────────────────────────────────────────────────

def _state(request: Request):
    return request.app.state


def _db(request: Request):
    db = request.app.state.session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("X-Api-Token", "").strip()


def require_api_token(request: Request) -> str:
    """자체 토큰 인증 — CONTROL_API_TOKENS 미설정이면 개발 모드(무인증, 기동 시 경고)."""
    tokens: dict[str, str] = request.app.state.api_tokens
    if not tokens:
        return "dev"
    presented = _extract_token(request)
    for token, name in tokens.items():
        if secrets.compare_digest(presented, token):
            return name
    raise HTTPException(401, "유효하지 않은 API 토큰")


def require_runner_token(request: Request) -> str:
    """러너 webhook 인증 — CONTROL_RUNNER_TOKEN (없으면 API 토큰으로 폴백)."""
    runner_token: str = request.app.state.runner_token
    presented = _extract_token(request)
    if runner_token and secrets.compare_digest(presented, runner_token):
        return "runner"
    return require_api_token(request)


def _check_run_id(run: str) -> str:
    if not run or not _RUN_ID_RE.match(run):
        raise HTTPException(400, "잘못된 run id")
    return run


def _extract_run_id(payload: dict) -> str:
    """webhook 페이로드의 run_id — 검증 후 반환. 누락/오류 시 400/422.
    webhook_events·webhook_complete 가 동일하게 사용 — 한 곳 변경이 모두 반영되도록.
    """
    run_id = str(payload.get("run_id") or "")
    return _check_run_id(run_id)


# ── audit (ENT-F) ──────────────────────────────────────────────

def _resolve_actor(request: Request) -> str:
    """audit용 actor 문자열 — 인증된 토큰 이름, 또는 명확한 sentinel.

    반환 규칙:
    - api_tokens 미설정(dev 모드) → "(dev)"
    - 토큰 제시 + 일치 → 토큰 이름
    - 토큰 제시 + 불일치 → "(anon)" (해시 비교 실패는 401이어야 하지만 방어적)
    - 토큰 미제시 → "(no-token)" (require_api_token 누락 — _audit 호출 경로 결함)

    예전 폴백은 api_tokens 의 첫 번째 토큰 이름을 반환했는데, 이는 인증되지 않은
    요청을 첫 토큰 소유자 행위로 오기록하는 감사 추적 오염이었다.
    """
    tokens = _state(request).api_tokens
    if not tokens:
        return "(dev)"
    presented = _extract_token(request)
    if not presented:
        # 이 경로는 require_api_token 을 거치지 않은 audit 호출에서만 도달한다
        # — 예: 러너 전용 엔드포인트. 정상 흐름에선 401 로 차단되지만, 만에 하나
        # 누락된 의존성이 있어도 audit 은 정직한 sentinel 로 남는다.
        log.warning("audit 호출 시 토큰 미제시 — endpoint=%s", request.url.path)
        return "(no-token)"
    for tok, name in tokens.items():
        if secrets.compare_digest(presented, tok):
            return name
    return "(anon)"


def _audit(request: Request, *, action: str, target_kind: str = "",
           target_id: str = "", detail: dict | None = None) -> None:
    """관리 mutation 엔드포인트가 끝날 때 호출. 실패는 무시 (감사가 본 요청을 막으면 안 됨).

    단, 실패를 조용히 삼키지 않고 warning 로그로 남긴다 — 예전 `except: pass`는
    audit 장애를 완전히 숨겨 컴플라이언스 추적에 구멍을 만들었다.
    """
    try:
        audit = getattr(request.app.state, "audit_service", None)
        if audit is None:
            return
        audit.record(
            actor=_resolve_actor(request)[:120],
            action=action[:80],
            target_kind=target_kind[:40],
            target_id=str(target_id)[:200],
            request_id=current_request_id(),
            detail=detail or {},
            remote_addr=(request.client.host if request.client else ""),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("audit 기록 실패 action=%s target=%s: %s: %s",
                    action, target_id, type(e).__name__, e)


# ── 메타 ─────────────────────────────────────────────────────

@router.get("/")
@router.get("/api")
def index(request: Request) -> dict:
    # OpenAPI 스키마에서 자동 수집 — app.routes 평탄 순회로는 _IncludedRouter
    # 안에 갇힌 라우트를 못 찾는다. openapi()는 모든 라우트를 정규화해 노출.
    spec = request.app.openapi()
    seen: set[tuple[str, str]] = set()
    for path, ops in (spec.get("paths") or {}).items():
        for method in (ops or {}).keys():
            m = method.upper()
            if m in ("HEAD", "OPTIONS"):
                continue
            seen.add((m, path))
    endpoints = sorted(f"{m} {p}" if m != "GET" else p for m, p in seen)
    return {
        "service": "wiki-pipeline control plane",
        "endpoints": endpoints,
    }


@router.get("/health")
def health(request: Request) -> dict:
    return {"ok": True, "db": request.app.state.db_ok,
            "auth": bool(request.app.state.api_tokens),
            "secretbox": request.app.state.box.enabled}


# ── 시스템 설정 (DB 영구 저장) ─────────────────────────────

def _env_llm_dict() -> dict[str, str]:
    """LLM_* 환경변수를 dict 로 — SettingsService.get_llm_effective 입력용."""
    import os
    return {
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "openai-compatible"),
        "LLM_BASE_URL": os.getenv("LLM_BASE_URL", ""),
        "LLM_API_KEY": os.getenv("LLM_API_KEY", ""),
        "LLM_MODEL": os.getenv("LLM_MODEL", ""),
        "LLM_MAX_TOKENS": os.getenv("LLM_MAX_TOKENS", "65536"),
        "LLM_TEMPERATURE": os.getenv("LLM_TEMPERATURE", "0.2"),
        "LLM_TIMEOUT": os.getenv("LLM_TIMEOUT", "180"),
        "LLM_RETRY_ATTEMPTS": os.getenv("LLM_RETRY_ATTEMPTS", "4"),
    }


@router.get("/api/settings/llm", dependencies=[Depends(require_api_token)])
def get_llm_settings(request: Request, db=Depends(_db)) -> dict:
    """LLM 런타임 설정 상태.

    DB 에 저장된 값이 우선, 없으면 .env 의 기본값 (source 표시).
    키 값은 has_key 불린만 노출 — 값 자체는 응답에 포함되지 않는다.
    """
    svc = request.app.state.settings_service
    return svc.get_llm_effective(db, _env_llm_dict())


@router.patch("/api/settings/llm", dependencies=[Depends(require_api_token)])
def update_llm_settings(request: Request, payload: dict = Body(...),
                        db=Depends(_db)) -> dict:
    """LLM settings 갱신 — DB 에 저장. 빈 문자열 / null 은 해당 키 삭제(env 복귀).

    ⚠ 런타임 provider 는 import 시점에 settings.llm_* 를 캡처한다. 변경 후
    Data Plane 러너를 재기동해야 적용된다 (Control Plane 재기동으로는 부족).
    """
    svc = request.app.state.settings_service
    # _resolve_actor 로 토큰 평문이 audit detail 에 남는 것을 방지.
    result = svc.set_llm(db, payload, actor=_resolve_actor(request))
    db.commit()
    _audit(request, action="llm_settings.update", target_kind="system_settings",
           target_id="llm", detail={"source": result.get("source")})
    return result


@router.delete("/api/settings/llm", dependencies=[Depends(require_api_token)])
def reset_llm_settings(request: Request, db=Depends(_db)) -> dict:
    """LLM settings DB 행 전부 삭제 — .env 기본값으로 폴백.

    부분 삭제(특정 키만) 도 같은 효과지만, 보통 일괄 reset 이 운영 의도다.
    """
    from ..models import SystemSetting
    from sqlalchemy import delete
    db.execute(delete(SystemSetting).where(SystemSetting.key.like("llm.%")))
    db.commit()
    _audit(request, action="llm_settings.reset", target_kind="system_settings",
           target_id="llm", detail={"reset_to": "env"})
    return get_llm_settings(request, db)


@router.post("/api/settings/llm/test", dependencies=[Depends(require_api_token)])
def test_llm_settings(request: Request, db=Depends(_db),
                      payload: dict = Body(default_factory=dict)) -> dict:
    """LLM 연결 테스트 — effective settings (또는 overrides) 로 짧은 호출.

    payload 가 비면 현재 effective (DB + .env) 를 그대로 쓴다. payload 에
    필드가 있으면 그 값으로 덮어써 테스트한다 — 저장 전에 미리 확인용.

    반환: {ok, model, latency_ms, response_preview, error}.
    오류 시 ok=False, error 에 예외 메시지·HTTP status 등을 넣는다.
    """
    import os
    import time
    svc = request.app.state.settings_service
    env_dict = _env_llm_dict()
    # payload (있는 필드만) 를 effective 위에 덮어쓰기.
    merged_env = dict(env_dict)
    overrides = payload or {}
    field_to_env = {
        "provider": "LLM_PROVIDER", "base_url": "LLM_BASE_URL",
        "api_key": "LLM_API_KEY", "model": "LLM_MODEL",
    }
    for k, env_key in field_to_env.items():
        if k in overrides and overrides[k] not in (None, ""):
            merged_env[env_key] = str(overrides[k])
    for k, env_key in [
        ("max_tokens", "LLM_MAX_TOKENS"), ("temperature", "LLM_TEMPERATURE"),
        ("timeout_sec", "LLM_TIMEOUT"), ("retry_attempts", "LLM_RETRY_ATTEMPTS"),
    ]:
        if k in overrides and overrides[k] not in (None, ""):
            try:
                merged_env[env_key] = str({
                    "max_tokens": int, "temperature": float,
                    "timeout_sec": float, "retry_attempts": int,
                }[k](overrides[k]))
            except (TypeError, ValueError):
                pass
    # 검증 — 키·모델이 없으면 호출 불가.
    api_key = (merged_env.get("LLM_API_KEY") or "").strip()
    if not api_key:
        return {"ok": False, "error": "API 키가 비어 있습니다. (DB/ .env 모두 확인)"}
    model_name = (merged_env.get("LLM_MODEL") or "").strip()
    if not model_name:
        return {"ok": False, "error": "모델이 비어 있습니다."}
    # Settings 인스턴스 빌드 — build_chat_model 이 받는 형태.
    from ..common.config import Settings
    test_settings = Settings(
        llm_provider=merged_env.get("LLM_PROVIDER", "openai-compatible"),
        llm_base_url=merged_env.get("LLM_BASE_URL", ""),
        llm_api_key=merged_env.get("LLM_API_KEY", ""),
        llm_model=merged_env.get("LLM_MODEL", ""),
        llm_max_tokens=int(merged_env.get("LLM_MAX_TOKENS", "16")),
        llm_temperature=float(merged_env.get("LLM_TEMPERATURE", "0")),
        llm_timeout=float(merged_env.get("LLM_TIMEOUT", "30")),
        out_dir=os.getenv("OUT_DIR", "./out"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
    try:
        from ..common.llm import build_chat_model
        model = build_chat_model(test_settings)
        # 짧은 호출 — "ping" 또는 빈 메시지로 토큰 1개만 요청.
        started = time.perf_counter()
        from langchain_core.messages import HumanMessage
        result = model.invoke([HumanMessage(content="ping")])
        latency_ms = int((time.perf_counter() - started) * 1000)
        # 응답 본문 짧게 — AIMessage.content 는 str 또는 list[str].
        content = result.content if hasattr(result, "content") else str(result)
        if isinstance(content, list):
            content = "".join(str(p) for p in content)
        preview = str(content)[:120]
        # DB 행 표시(저장 여부)
        saved_in_db = any(
            svc.get(db, f"llm.{k}") is not None
            for k in ("provider", "base_url", "api_key", "model")
        )
        return {
            "ok": True, "model": model_name, "latency_ms": latency_ms,
            "response_preview": preview, "saved_in_db": saved_in_db,
        }
    except Exception as e:  # noqa: BLE001
        # httopenai / anthropic 모두 다양한 예외를 던진다 — 메시지만 정규화.
        msg = str(e)
        if not msg:
            msg = f"{type(e).__name__}"
        # 흔한 케이스: 인증 실패 / 모델 없음 / endpoint 오류.
        kind = "unknown"
        low = msg.lower()
        if "auth" in low or "401" in msg or "invalid api key" in low or "api_key" in low:
            kind = "auth"
        elif "404" in msg or "model_not_found" in low or "not found" in low:
            kind = "model_not_found"
        elif "timeout" in low or "timed out" in low:
            kind = "timeout"
        elif "connection" in low or "name resolution" in low or "resolve" in low:
            kind = "network"
        return {"ok": False, "model": model_name, "error": msg[:300], "error_kind": kind}


@router.get("/api/runs/{run_id}/doc", dependencies=[Depends(require_api_token)])
def get_run_doc(request: Request, run_id: str, path: str = Query("")) -> dict:
    """run 산출물 디렉터리 내 문서 원문을 반환한다 (마크다운 + mermaid).

    경로 안전: run 디렉터리 밖으로 벗어나는 상대경로(..)는 거부한다.
    """
    from pathlib import Path
    run_id = _check_run_id(run_id)
    if not path or not re.match(r"^[A-Za-z0-9._/\-]+\.(md|markdown|mermaid)$", path):
        raise HTTPException(400, "잘못된 path — markdown/mermaid 확장자만 허용")
    if ".." in path.split("/"):
        raise HTTPException(400, "상위 경로 접근 금지")
    st = _state(request)
    run_root = projection.find_run_path(st.settings.out_path, run_id)
    if run_root is None:
        raise HTTPException(404, f"run 출력 디렉터리를 찾을 수 없습니다: {run_id}")
    doc_path = (run_root / path).resolve()
    try:
        doc_path.relative_to(run_root.resolve())
    except ValueError as e:
        raise HTTPException(400, "경로가 run 디렉터리를 벗어납니다") from e
    if not doc_path.is_file():
        raise HTTPException(404, f"문서 없음: {path}")
    text = doc_path.read_text(encoding="utf-8", errors="replace")
    return {"run_id": run_id, "path": path, "content": text, "size": len(text)}


# ── runs (조회 — DB 우선, 레거시 파일 폴백) ──────────────────

@router.get("/api/runs", dependencies=[Depends(require_api_token)])
def list_runs(request: Request, db=Depends(_db)) -> list[dict]:
    st = _state(request)
    db_runs = st.run_service.list_runs(db)
    file_runs = projection.list_file_runs(st.settings.out_path)
    seen = {r["run_id"] for r in db_runs}
    merged = db_runs + [r for r in file_runs if r["run_id"] not in seen]
    return merged


@router.get("/api/runs/db", dependencies=[Depends(require_api_token)])
def list_db_runs(request: Request, db=Depends(_db), limit: int = 100,
                 source: str = Query("")) -> list[dict]:
    return _state(request).run_service.list_runs(db, limit=limit,
                                                 source_id=source or None)


@router.post("/api/runs/trigger", dependencies=[Depends(require_api_token)])
def trigger_run(request: Request, db=Depends(_db),
                payload: dict = Body(...)) -> dict:
    st = _state(request)
    source_id = str(payload.get("source_id") or "")
    if not source_id:
        raise HTTPException(400, "source_id가 필요합니다.")
    try:
        run = st.run_service.create_run(
            db, source_id=source_id,
            mode=str(payload.get("mode") or "auto"),
            branch_role=str(payload.get("branch_role") or "dev"),
            trigger="manual",
            pipeline_id=str(payload.get("pipeline_id") or "static"),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    # launch=False 이면 run 행만 만들고 러너는 띄우지 않는다 — 테스트/리허스용.
    should_launch = bool(payload.get("launch", True))
    launched = should_launch and st.run_service.launch_runner(run) is not None
    return {"ok": True, "run_id": run.id, "launched": launched}


@router.get("/api/run-summary", dependencies=[Depends(require_api_token)],
            response_model=RunSummary)
def run_summary(request: Request, db=Depends(_db), run: str = Query("")) -> dict:
    """run 1건의 요약 — DB run row(진실) + events(파생)를 병합.

    상태 일관성 규칙: DB run row 가 있으면 그 status/pipeline_id/branch_role 이 진실.
    events 기반으로만 추론하면 DB 의 빠른 상태 갱신(complete_run webhook)과 어긋나는
    경우가 생긴다 — projection 에 row 값을 override 로 넘긴다.

    2026-07-08: publishable, publish_state, quality, evidence, coverage, artifact,
    vnc, snapshot_version, mr readiness 필드를 함께 반환 (optional, 구버전 run
    은 unknown / not_evaluated 로 degrade).
    """
    st = _state(request)
    run = _check_run_id(run)
    if st.run_service.has_db_events(db, run):
        events = st.run_service.all_db_events(db, run)
        row = st.run_service.get_run_view(db, run)
        if row is None:
            return _augment_summary(projection.summarize_events(
                events, run_id=run, source_id=""), db, run)
        base = projection.summarize_events(
            events, run_id=run, source_id=row.get("source_id", ""),
            run_status_override=row.get("status", ""),
            run_pipeline_id=row.get("pipeline_id", ""),
            run_branch_role=row.get("branch_role", ""),
            run_mode=row.get("mode", ""),
            run_trigger=row.get("trigger", ""),
            run_from_sha=row.get("from_sha", ""),
            run_to_sha=row.get("to_sha", ""),
            run_mr_url=row.get("mr_url", ""),
            run_doc_count=int(row.get("doc_count") or 0),
            run_error=row.get("error", ""),
            run_started_at=row.get("created_at", ""),
            run_updated_at=row.get("updated_at", ""),
        )
        return _augment_summary(base, db, run)
    path = projection.find_run_path(st.settings.out_path, run)
    if not path:
        raise HTTPException(404, "run 없음")
    base = projection.summarize_events(
        projection.read_all_file_events(path),
        run_id=run,
        source_id=projection.source_from_path(st.settings.out_path, path),
        path=str(path.relative_to(st.settings.out_path)),
        artifacts=projection.list_artifacts(path, st.settings.out_path),
    )
    return _augment_summary(base, db, run)


def _augment_summary(base: dict, db, run_id: str) -> dict:
    """projection 결과에 quality/evidence/coverage/artifact/vnc/mr resource 를 합친다.

    구버전 run 은 모두 unknown / not_evaluated / not_applicable 으로 degrade —
    frontend 가 optional 로 소비 가능.
    """
    from .services import resources
    run_row = db.get(Run, run_id)
    if run_row is None:
        return base
    quality_view = resources.get_quality_view(db, run_id) or {}
    coverage_view = resources.get_coverage_view(db, run_id)
    artifact_view = resources.get_artifact_view(db, run_id)
    vnc_view = resources.get_vnc_view(db, run_id)
    evidence_view = resources.get_evidence_pack(db, run_id, limit=1) or {}
    quality_status = str(run_row.quality_status or quality_view.get("status")
                         or "not_evaluated")
    publish_state = str(run_row.publish_state or "unknown")
    publishable = bool(run_row.publishable)
    blocked_reason = str(run_row.blocked_reason or "")
    quality = {
        "status": quality_status,
        "score": run_row.quality_score if run_row.quality_score is not None
                 else quality_view.get("score"),
        "publishable": publishable,
        "publish_state": publish_state,
        "failed_gate": quality_view.get("failed_gate", ""),
        "warning_count": int(quality_view.get("warning_count") or 0),
        "error_count": int(quality_view.get("error_count") or 0),
        "repair_attempts": int(quality_view.get("repair_attempts") or 0),
        "gates": quality_view.get("gates", []),
    }
    snapshot_version = int(run_row.snapshot_version or 0)
    base.update({
        "publishable": publishable,
        "publish_state": publish_state,
        "blocked_reason": blocked_reason,
        "quality_status": quality_status,
        "quality_score": run_row.quality_score,
        "warning_publish_policy": str(run_row.warning_publish_policy or "review_required"),
        "release_tag": str(run_row.release_tag or ""),
        "artifact_version": str(run_row.artifact_version or ""),
        "snapshot_version": snapshot_version,
        "stale_complete": bool(run_row.stale_complete),
        "heartbeat_at": _iso(run_row.heartbeat_at),
        "started_at": _iso(run_row.started_at),
        "terminal_at": _iso(run_row.terminal_at),
        "attempt": int(run_row.attempt or 1),
        "quality": quality,
        "evidence": {
            "pack_id": evidence_view.get("pack_id", ""),
            "item_count": int(evidence_view.get("item_count") or 0),
            "unsupported_claim_count": int(evidence_view.get("unsupported_claim_count") or 0),
            "truncated": bool(evidence_view.get("truncated", False)),
            "missing": not evidence_view,
        },
        "coverage": {
            "status": coverage_view.get("status", "not_applicable"),
            "percentage": coverage_view.get("percentage"),
            "threshold": coverage_view.get("threshold"),
            "reached": int(coverage_view.get("reached") or 0),
            "expected": int(coverage_view.get("expected") or 0),
            "missed_count": int(coverage_view.get("missed_count") or 0),
        },
        "artifact": {
            "available": bool(artifact_view.get("available", False)),
            "release_tag": artifact_view.get("release_tag", ""),
            "artifact_name": artifact_view.get("artifact_name", ""),
            "build_status": artifact_view.get("build_status", "unknown"),
            "deploy_status": artifact_view.get("deploy_status", "unknown"),
            "install_status": artifact_view.get("install_status", "unknown"),
            "readiness_status": artifact_view.get("readiness_status", "unknown"),
            "smoke_status": artifact_view.get("smoke_status", "unknown"),
            "installed_version": artifact_view.get("installed_version", ""),
        },
        "vnc": {
            "available": bool(vnc_view.get("available", False)),
            "status": vnc_view.get("status", "unavailable"),
            "session_id": vnc_view.get("session_id", ""),
            "view_only": bool(vnc_view.get("view_only", True)),
            "expires_at": vnc_view.get("expires_at", ""),
        },
        "mr": _mr_readiness_view(run_row, quality, coverage_view),
    })
    return base


def _mr_readiness_view(run_row, quality: dict, coverage: dict) -> dict:
    """MR readiness — quality/coverage 기반으로 publishable 가능 여부 도출."""
    if not run_row.mr_url:
        readiness = "not_created"
    elif run_row.status in ("failed", "failed_quality_gate", "stale",
                             "cancelled", "timeout", "partial"):
        readiness = "blocked"
    elif run_row.status == "done_with_warnings":
        readiness = "review_required"
    elif run_row.status == "done" and bool(run_row.publishable):
        readiness = "ready"
    else:
        readiness = "ready" if bool(run_row.publishable) else "blocked"
    blocked_reason = ""
    if readiness == "blocked":
        if run_row.blocked_reason:
            blocked_reason = run_row.blocked_reason
        elif quality.get("failed_gate"):
            blocked_reason = quality["failed_gate"]
        elif coverage.get("status") == "fail":
            blocked_reason = "coverage below threshold"
    return {
        "readiness": readiness,
        "blocked_reason": blocked_reason,
        "included_files": int(run_row.doc_count or 0),
        "excluded_files": 0,
    }


def _iso(dt) -> str:
    from .timeutil import isoformat_z
    return isoformat_z(dt) if dt else ""


@router.get("/api/events", dependencies=[Depends(require_api_token)])
def read_events(request: Request, db=Depends(_db),
                run: str = Query(""), offset: int = Query(0)) -> dict:
    st = _state(request)
    run = _check_run_id(run)
    if st.run_service.has_db_events(db, run):
        return st.run_service.read_db_events(db, run, after_id=offset)
    path = projection.find_run_path(st.settings.out_path, run)
    if not path:
        raise HTTPException(404, "run 없음")
    return projection.read_new_file_events(path, offset)


# ── run-scoped resource GET endpoints (2026-07-08) ───────────────


@router.get("/api/runs/{run_id}/quality", dependencies=[Depends(require_api_token)])
def get_run_quality(run_id: str, request: Request, db=Depends(_db),
                    severity: str = Query(""),
                    blocking: bool | None = Query(None),
                    doc_id: str = Query("")) -> dict:
    _check_run_id(run_id)
    from .services import resources
    run_row = db.get(Run, run_id)
    if run_row is None:
        raise HTTPException(404, f"run 없음: {run_id}")
    quality = resources.get_quality_view(db, run_id) or {
        "status": "not_evaluated", "score": None, "publishable": False,
        "failed_gate": "", "warning_count": 0, "error_count": 0,
        "repair_attempts": 0, "gates": [],
    }
    findings = resources.get_quality_findings(
        db, run_id, severity=severity, blocking=blocking, doc_id=doc_id,
    )
    docs = resources.get_doc_outputs(db, run_id)
    return {
        "run_id": run_id,
        "quality": {**quality, "publish_state": run_row.publish_state or "unknown"},
        "findings": findings,
        "doc_outputs": docs,
        "available": True,
    }


@router.get("/api/runs/{run_id}/evidence", dependencies=[Depends(require_api_token)])
def get_run_evidence(run_id: str, request: Request, db=Depends(_db),
                     kind: str = Query(""),
                     doc_id: str = Query(""),
                     limit: int = Query(200, ge=1, le=2000),
                     cursor: str = Query("")) -> dict:
    _check_run_id(run_id)
    from .services import resources
    pack = resources.get_evidence_pack(db, run_id, kind=kind, doc_id=doc_id,
                                       limit=limit, cursor=cursor)
    if pack is None:
        return {"run_id": run_id, "pack_id": "", "item_count": 0,
                "items": [], "missing": True}
    return pack


@router.get("/api/runs/{run_id}/evidence/{item_id}",
            dependencies=[Depends(require_api_token)])
def get_run_evidence_item(run_id: str, item_id: str,
                          request: Request, db=Depends(_db)) -> dict:
    _check_run_id(run_id)
    from .services import resources
    item = resources.get_evidence_item(db, run_id, item_id)
    if item is None:
        raise HTTPException(404, f"evidence item 없음: {item_id}")
    return item


@router.get("/api/runs/{run_id}/coverage", dependencies=[Depends(require_api_token)])
def get_run_coverage(run_id: str, request: Request, db=Depends(_db)) -> dict:
    _check_run_id(run_id)
    from .services import resources
    return {"run_id": run_id, **resources.get_coverage_view(db, run_id)}


@router.get("/api/runs/{run_id}/artifacts", dependencies=[Depends(require_api_token)])
def get_run_artifacts(run_id: str, request: Request, db=Depends(_db)) -> dict:
    _check_run_id(run_id)
    from .services import resources
    return {"run_id": run_id, **resources.get_artifact_view(db, run_id)}


@router.get("/api/runs/{run_id}/vnc-session",
            dependencies=[Depends(require_api_token)])
def get_run_vnc_session(run_id: str, request: Request, db=Depends(_db)) -> dict:
    _check_run_id(run_id)
    from .services import resources
    view = resources.get_vnc_view(db, run_id)
    # view_only 가 false 이면 websocket_url 미발급 (운영 안전)
    if not view.get("view_only", True):
        view["websocket_url"] = ""
    return {"run_id": run_id, **view}


@router.get("/api/runs/{run_id}/events", dependencies=[Depends(require_api_token)])
def get_run_events_seq(run_id: str, request: Request, db=Depends(_db),
                       after_seq: int = Query(0, alias="afterSeq"),
                       limit: int = Query(500, ge=1, le=2000)) -> dict:
    """seq-based event replay — frontend 가 reconnect 시 마지막 seq 이후만 받는다."""
    _check_run_id(run_id)
    return request.app.state.run_service.read_db_events_seq(
        db, run_id, after_seq=after_seq, limit=limit,
    )


# ── source manual automation API ───────────────────────────────


@router.get("/api/sources/{source_id}/manual-profile",
            dependencies=[Depends(require_api_token)])
def get_source_manual_profile(source_id: str, request: Request,
                              db=Depends(_db)) -> dict:
    from .services import resources
    view = resources.get_manual_profile(db, source_id)
    if view is None:
        return {"source_id": source_id, "enabled": False,
                "mcp_endpoint_url": "", "host_label": "", "host_ip": "",
                "host_port": None, "vnc_enabled": False, "vnc_host": "",
                "vnc_port": None, "vnc_gateway_policy": "view_only",
                "tool_allowlist": [], "secret_refs": {},
                "artifact_selector": {}, "install_profile": {},
                "readiness_check": {}, "smoke_check": {},
                "coverage_threshold": 70, "failure_policy": "block",
                "updated_at": ""}
    return view


@router.put("/api/sources/{source_id}/manual-profile",
            dependencies=[Depends(require_api_token)])
def save_source_manual_profile(source_id: str, request: Request,
                               db=Depends(_db),
                               payload: dict = Body(...)) -> dict:
    from .services import resources
    try:
        result = resources.save_manual_profile(db, source_id, payload)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    _audit(request, action="manual_profile.update", target_kind="source",
           target_id=source_id, detail={"enabled": result.get("enabled")})
    return result


@router.post("/api/sources/{source_id}/manual-profile/preflight",
              dependencies=[Depends(require_api_token)])
def preflight_source_manual_profile(source_id: str, request: Request,
                                    db=Depends(_db)) -> dict:
    from .services import resources
    return resources.preflight_manual_profile(db, source_id)


@router.get("/api/sources/{source_id}/scenarios",
            dependencies=[Depends(require_api_token)])
def list_source_scenarios(source_id: str, request: Request,
                          db=Depends(_db)) -> dict:
    from .services import resources
    return {"source_id": source_id, "scenarios": resources.list_scenarios(db, source_id)}


@router.post("/api/sources/{source_id}/scenarios",
             dependencies=[Depends(require_api_token)])
def save_source_scenario(source_id: str, request: Request, db=Depends(_db),
                         payload: dict = Body(...)) -> dict:
    from .services import resources
    try:
        result = resources.save_scenario(db, source_id, payload)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    _audit(request, action="scenario_set.create", target_kind="source", target_id=source_id)
    return result


@router.put("/api/sources/{source_id}/scenarios/{scenario_set_id}",
            dependencies=[Depends(require_api_token)])
def update_source_scenario(source_id: str, scenario_set_id: str,
                           request: Request, db=Depends(_db),
                           payload: dict = Body(...)) -> dict:
    from .services import resources
    try:
        result = resources.save_scenario(db, source_id, payload, set_id=scenario_set_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    _audit(request, action="scenario_set.update", target_kind="scenario",
           target_id=scenario_set_id)
    return result


@router.delete("/api/sources/{source_id}/scenarios/{scenario_set_id}",
               dependencies=[Depends(require_api_token)])
def delete_source_scenario(source_id: str, scenario_set_id: str,
                            request: Request, db=Depends(_db)) -> dict:
    from .services import resources
    ok = resources.delete_scenario(db, source_id, scenario_set_id)
    if not ok:
        raise HTTPException(404, f"scenario set 없음: {scenario_set_id}")
    db.commit()
    return {"ok": True}


@router.post("/api/sources/{source_id}/scenarios/{scenario_set_id}/activate",
             dependencies=[Depends(require_api_token)])
def activate_source_scenario(source_id: str, scenario_set_id: str,
                              request: Request, db=Depends(_db)) -> dict:
    from .services import resources
    try:
        result = resources.activate_scenario(db, source_id, scenario_set_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    _audit(request, action="scenario_set.activate", target_kind="scenario",
           target_id=scenario_set_id)
    return result


@router.post("/api/sources/{source_id}/scenarios/lint",
             dependencies=[Depends(require_api_token)])
def lint_source_scenarios(source_id: str, request: Request,
                          payload: dict = Body(...)) -> dict:
    from .services import resources
    return resources.lint_scenarios(payload)


@router.post("/api/sources/{source_id}/artifacts/preflight",
             dependencies=[Depends(require_api_token)])
def preflight_source_artifact(source_id: str, request: Request,
                              db=Depends(_db),
                              payload: dict = Body(...)) -> dict:
    from .services import resources
    return resources.preflight_artifact(db, source_id, payload)


# ── reaper / overview (control-plane only) ───────────────────────


@router.post("/api/internal/reap-stuck", dependencies=[Depends(require_api_token)])
def reap_stuck_runs(request: Request, db=Depends(_db)) -> dict:
    """stuck/stalled run reaper — 운영자가 강제 호출할 수 있게 노출."""
    st = _state(request)
    n = st.run_service.reap_stuck_runs(db)
    db.commit()
    return {"ok": True, "reaped": n}


@router.get("/api/quality/summary", dependencies=[Depends(require_api_token)])
def quality_summary(request: Request, db=Depends(_db),
                    window: int = Query(168, ge=1, le=720)) -> dict:
    """quality dashboard — 최근 window 시간 집계."""
    from datetime import datetime, timedelta, timezone
    from .models import RunQualityReport
    from sqlalchemy import func as sa_func
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window)
    rows = db.scalars(
        select(RunQualityReport).where(RunQualityReport.created_at >= cutoff)
    ).all()
    total = len(rows)
    pass_n = sum(1 for r in rows if r.status == "pass")
    warn_n = sum(1 for r in rows if r.status == "warning")
    fail_n = sum(1 for r in rows if r.status == "fail")
    total_warnings = sum(int(r.warning_count or 0) for r in rows)
    total_errors = sum(int(r.error_count or 0) for r in rows)
    total_repairs = sum(int(r.repair_attempts or 0) for r in rows)
    failed_gates: dict[str, int] = {}
    for r in rows:
        if r.failed_gate:
            failed_gates[r.failed_gate] = failed_gates.get(r.failed_gate, 0) + 1
    return {
        "window_hours": window,
        "total": total,
        "pass_count": pass_n,
        "warning_count": warn_n,
        "fail_count": fail_n,
        "pass_rate": round(pass_n / total * 100, 1) if total else 0.0,
        "publishable_rate": round(sum(1 for r in rows if r.publishable) / total * 100, 1)
            if total else 0.0,
        "total_warnings": total_warnings,
        "total_errors": total_errors,
        "total_repair_attempts": total_repairs,
        "failed_gate_distribution": [{"gate": g, "count": c}
                                     for g, c in sorted(failed_gates.items(),
                                                         key=lambda x: -x[1])],
    }


@router.get("/api/overview", dependencies=[Depends(require_api_token)],
            response_model=OverviewResponse)
def overview(request: Request, db=Depends(_db)) -> dict:
    """run 목록 + 최근 20건의 요약을 단일 응답으로.

    성능: 예전에는 run마다 run_summary를 호출해 (각각 list_runs(1000) +
    has_db_events + all_db_events) O(N×M) 쿼리를 발생시켰다. 이제 단일
    IN 쿼리로 top 20 run의 이벤트를 한 번에 가져와 projection으로 합성한다.
    DB에 이벤트가 없는 레거시 file-only run만 per-call 폴백.
    """
    import json as _json

    st = _state(request)
    runs = list_runs(request, db)
    top = runs[:20]
    if not top:
        return {"totals": {
            "runs": 0, "running": 0, "failed": 0, "done": 0,
            "tokens": 0, "tool_calls": 0, "errors": 0,
        }, "recent": []}

    run_ids = [r["run_id"] for r in top]
    # 단일 쿼리로 top N run의 이벤트를 모두 로드 — run_id IN (...) 한 번.
    rows = db.scalars(
        select(RunEvent).where(RunEvent.run_id.in_(run_ids))
        .order_by(RunEvent.id)
    ).all()
    events_by_run: dict[str, list[dict]] = {rid: [] for rid in run_ids}
    for ev in rows:
        bucket = events_by_run.get(ev.run_id)
        if bucket is not None:
            try:
                bucket.append(_json.loads(ev.payload))
            except (ValueError, TypeError):
                continue   # payload가 깨진 행은 스킵

    summaries = []
    for r in top:
        rid = r["run_id"]
        evs = events_by_run.get(rid)
        if evs:
            summaries.append(projection.summarize_events(
                evs,
                run_id=rid,
                source_id=r.get("source_id", ""),
                run_status_override=r.get("status", ""),
                run_pipeline_id=r.get("pipeline_id", ""),
                run_branch_role=r.get("branch_role", ""),
                run_mode=r.get("mode", ""),
                run_trigger=r.get("trigger", ""),
                run_from_sha=r.get("from_sha", ""),
                run_to_sha=r.get("to_sha", ""),
                run_mr_url=r.get("mr_url", ""),
                run_doc_count=int(r.get("doc_count") or 0),
                run_error=r.get("error", ""),
                run_started_at=r.get("created_at", ""),
                run_updated_at=r.get("updated_at", ""),
            ))
        else:
            # DB에 이벤트가 없는 file-only 레거시 run — per-call 폴백.
            try:
                summaries.append(run_summary(request, db, run=rid))
            except HTTPException:
                continue

    totals = {
        "runs": len(runs),
        "running": sum(1 for s in summaries if s["status"] == "running"),
        "failed": sum(1 for s in summaries if s["status"] == "failed"),
        "done": sum(1 for s in summaries if s["status"] == "done"),
        "tokens": sum(s["kpi"]["token_total"] for s in summaries),
        "tool_calls": sum(s["kpi"]["tool_calls"] for s in summaries),
        "errors": sum(s["kpi"]["errors"] for s in summaries),
    }
    return {"totals": totals, "recent": summaries}


@router.get("/api/pipelines/status", dependencies=[Depends(require_api_token)],
            response_model=PipelineStatusResponse)
def pipelines_status(request: Request, db=Depends(_db),
                     window: int = Query(24, ge=1, le=168)) -> dict:
    """각 (source × pipeline_id) 쌍의 상태 집계 — 프런트 파이프라인 페이지가 쓴다.

    반환: {pipelines: [...], window_hours, generated_at}. 한 번의 호출로
    useDbRunsQuery + 수동 집계하던 것을 서버가 단일 응답으로 제공한다.
    다음 스케줄 시각(next_scheduled_at)은 scheduler 가 reload 시 계산하므로
    별도 조회가 필요하면 /api/schedules 를 병행 호출.
    """
    st = _state(request)
    pipelines = st.run_service.pipeline_status(db, window_hours=window)
    return {
        "window_hours": window,
        "pipelines": pipelines,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── sources ─────────────────────────────────────────────────

def _validate_source_payload(payload: dict) -> dict:
    required = ["label", "kind", "project_id"]
    missing = [k for k in required if not str(payload.get(k) or payload.get("repo") or "").strip()]
    if "project_id" in missing and str(payload.get("repo") or "").strip():
        missing.remove("project_id")
    warnings = []
    kind = str(payload.get("kind") or "gitlab").lower()
    if kind not in ("gitlab", "github"):
        warnings.append(f"지원하지 않는 kind: {kind} (gitlab | github)")
    if kind == "gitlab" and not str(payload.get("url") or "").strip() and not payload.get("instance_id"):
        missing.append("url")
    if not str(payload.get("dev_branch") or "").strip():
        warnings.append("dev 브랜치가 비어 있으면 개발 문서 배치 대상에서 제외됩니다.")
    if not str(payload.get("release_branch") or "").strip():
        warnings.append("release 브랜치가 비어 있으면 매뉴얼/릴리스 대상에서 제외됩니다.")
    return {"ok": not missing, "missing": missing, "warnings": warnings}


@router.get("/api/sources", dependencies=[Depends(require_api_token)])
def list_sources(request: Request, db=Depends(_db)) -> list[dict]:
    st = _state(request)
    # N+1 회피 — source_view가 instance/branches/schedules를 건마다 lazy-load 했다.
    # selectinload로 한 번에 가져온다.
    stmt = (
        select(Source)
        .options(
            joinedload(Source.instance),
            selectinload(Source.branches),
            selectinload(Source.schedules),
        )
        .order_by(Source.id)
    )
    sources = db.scalars(stmt).unique().all()
    return [st.registration.source_view(db, s) for s in sources]


@router.get("/api/schedules", dependencies=[Depends(require_api_token)])
def list_schedules(request: Request, db=Depends(_db)) -> list[dict]:
    return _state(request).scheduler.list_schedules(db)


def _apply_schedule_payload(row: SourceSchedule, payload: dict) -> SourceSchedule:
    row.label = str(payload.get("label") or row.label or "정적 문서 자동화")
    row.pipeline_id = str(payload.get("pipeline_id") or row.pipeline_id or "static")
    row.mode = str(payload.get("mode") or row.mode or "auto")
    row.branch_role = str(payload.get("branch_role") or row.branch_role or "dev")
    row.cron = normalize_schedule_payload(payload, row.cron)
    if "enabled" in payload:
        row.enabled = bool(payload["enabled"])
    if row.pipeline_id not in ("static", "manual"):
        raise ValueError(f"지원하지 않는 pipeline_id: {row.pipeline_id}")
    # 매뉴얼 파이프라인은 mode(init/diff) 의미가 없다 — 관측 기반이므로 auto 만 허용.
    if row.pipeline_id == "manual" and row.mode not in ("auto", ""):
        raise ValueError(f"매뉴얼 파이프라인은 mode 'auto' 만 지원 (got: {row.mode})")
    if row.pipeline_id == "static" and row.mode not in ("auto", "init", "diff"):
        raise ValueError(f"지원하지 않는 mode: {row.mode}")
    if row.branch_role not in ("dev", "release"):
        raise ValueError(f"지원하지 않는 branch_role: {row.branch_role}")
    # 매뉴얼 파이프라인은 릴리스 브랜치(태그) 기반이 원칙 (decision-release-tag-trigger).
    # dev 도 허용하되 권장을 경고로 남긴다 — 검증 오류가 아니다.
    return row


@router.post("/api/sources/validate", dependencies=[Depends(require_api_token)])
def validate_source(payload: dict = Body(...)) -> dict:
    return _validate_source_payload(payload)


@router.post("/api/sources/preflight", dependencies=[Depends(require_api_token)])
def preflight_source(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    """저장 없이 커넥터 검증만 — 등록 마법사의 사전 검증 단계.

    반환: verified·name·default_branch·namespace_path·branches·head_sha (실패 시 error).
    instance_id를 주면 저장된 인스턴스 토큰을 쓰고, payload token이 있으면 그것을 우선한다.
    """
    st = _state(request)
    from ..connectors import make_connector

    kind = str(payload.get("kind") or "gitlab").lower()
    url = str(payload.get("url") or "")
    token = str(payload.get("token") or "")
    token_header = str(payload.get("token_header") or "PRIVATE-TOKEN")
    repo = str(payload.get("repo") or payload.get("project_id") or "").strip()
    if payload.get("instance_id"):
        inst = db.get(ScmInstance, str(payload["instance_id"]))
        if inst is None:
            raise HTTPException(404, f"instance 없음: {payload['instance_id']}")
        kind = inst.kind
        url = inst.base_url
        token_header = inst.token_header
        if not token and inst.token:
            token = st.box.decrypt(inst.token)
    if not repo:
        raise HTTPException(400, "repo(project_id)가 필요합니다.")
    try:
        with make_connector(kind=kind, url=url, token=token,
                            token_header=token_header, repo=repo) as conn:
            info = conn.verify_access()
            branches = conn.list_branches()
            head = conn.resolve_ref(info.default_branch)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001 — 검증 실패는 결과로 반환
        return {"verified": False, "error": f"{type(e).__name__}: {e}"}
    return {
        "verified": True, "kind": kind, "name": info.name,
        "default_branch": info.default_branch, "namespace_path": info.namespace_path,
        "web_url": info.web_url, "branches": branches[:200], "head_sha": head,
    }


@router.post("/api/sources", status_code=201, dependencies=[Depends(require_api_token)])
def create_source(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    st = _state(request)
    validation = _validate_source_payload(payload)
    if not validation["ok"]:
        raise HTTPException(400, f"필수값 누락: {validation['missing']}")
    try:
        source, verification = st.registration.upsert_source(
            db, payload, verify=bool(payload.get("verify", True)))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    st.scheduler.reload_jobs()
    st.broadcaster.publish({"type": "sources_changed"})
    view = st.registration.source_view(db, source)
    view["verification"] = verification
    _audit(request, action="source.create", target_kind="source",
           target_id=source.id, detail={"verified": bool(verification.get("verified"))})
    return view


@router.patch("/api/sources/{source_id}", dependencies=[Depends(require_api_token)])
def update_source(source_id: str, request: Request, db=Depends(_db),
                  payload: dict = Body(...)) -> dict:
    st = _state(request)
    if db.get(Source, source_id) is None:
        raise HTTPException(404, f"source 없음: {source_id}")
    payload["id"] = source_id
    try:
        source, verification = st.registration.upsert_source(
            db, payload, preserve_token=True, verify=bool(payload.get("verify", False)))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    st.scheduler.reload_jobs()
    st.broadcaster.publish({"type": "sources_changed"})
    view = st.registration.source_view(db, source)
    view["verification"] = verification
    _audit(request, action="source.update", target_kind="source",
           target_id=source.id, detail={"verified": bool(verification.get("verified"))})
    return view


@router.delete("/api/sources/{source_id}", dependencies=[Depends(require_api_token)])
def delete_source(source_id: str, request: Request, db=Depends(_db)) -> dict:
    st = _state(request)
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, f"source 없음: {source_id}")
    label = source.label or source.id
    from sqlalchemy import delete
    # SQLAlchemy 2.x 호환 — execute(delete(Model).where(...)) 패턴.
    # synchronize_session=False 로 ORM identity map 순회 비용 제거 (대량 삭제 시).
    schedule_count = db.execute(
        delete(SourceSchedule).where(SourceSchedule.source_id == source_id)
    ).rowcount
    branch_count = db.execute(
        delete(SourceBranch).where(SourceBranch.source_id == source_id)
    ).rowcount
    tag_count = db.execute(
        delete(SourceReleaseTag).where(SourceReleaseTag.source_id == source_id)
    ).rowcount
    db.delete(source)
    db.commit()
    st.scheduler.reload_jobs()
    st.broadcaster.publish({"type": "sources_changed"})
    _audit(request, action="source.delete", target_kind="source",
           target_id=source_id, detail={
               "label": label,
               "schedules": int(schedule_count or 0),
               "branches": int(branch_count or 0),
               "release_tags": int(tag_count or 0),
           })
    return {"ok": True, "deleted": source_id}


@router.patch("/api/sources/{source_id}/schedule", dependencies=[Depends(require_api_token)])
def update_source_schedule(source_id: str, request: Request, db=Depends(_db),
                           payload: dict = Body(...)) -> dict:
    st = _state(request)
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, f"source 없음: {source_id}")
    try:
        if source.schedules:
            _apply_schedule_payload(source.schedules[0], payload)
            source.schedule_cron = source.schedules[0].cron
        else:
            source.schedule_cron = normalize_schedule_payload(payload, source.schedule_cron)
            db.add(SourceSchedule(source=source, label="정적 문서 자동화",
                                  pipeline_id="static", mode="auto",
                                  branch_role="dev", cron=source.schedule_cron,
                                  enabled=True))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    st.scheduler.reload_jobs()
    st.broadcaster.publish({"type": "sources_changed"})
    return st.registration.source_view(db, source)


@router.post("/api/sources/{source_id}/schedules", status_code=201,
             dependencies=[Depends(require_api_token)])
def create_source_schedule(source_id: str, request: Request, db=Depends(_db),
                           payload: dict = Body(...)) -> dict:
    st = _state(request)
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, f"source 없음: {source_id}")
    row = SourceSchedule(source=source)
    try:
        _apply_schedule_payload(row, payload)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    db.add(row)
    db.commit()
    st.scheduler.reload_jobs()
    st.broadcaster.publish({"type": "sources_changed"})
    return st.registration.schedule_view(row)


@router.patch("/api/sources/{source_id}/schedules/{schedule_id}",
              dependencies=[Depends(require_api_token)])
def update_source_schedule_row(source_id: str, schedule_id: int, request: Request,
                               db=Depends(_db), payload: dict = Body(...)) -> dict:
    st = _state(request)
    row = db.get(SourceSchedule, schedule_id)
    if row is None or row.source_id != source_id:
        raise HTTPException(404, f"schedule 없음: {schedule_id}")
    try:
        _apply_schedule_payload(row, payload)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    st.scheduler.reload_jobs()
    st.broadcaster.publish({"type": "sources_changed"})
    return st.registration.schedule_view(row)


@router.delete("/api/sources/{source_id}/schedules/{schedule_id}",
               dependencies=[Depends(require_api_token)])
def delete_source_schedule(source_id: str, schedule_id: int, request: Request,
                           db=Depends(_db)) -> dict:
    st = _state(request)
    row = db.get(SourceSchedule, schedule_id)
    if row is None or row.source_id != source_id:
        raise HTTPException(404, f"schedule 없음: {schedule_id}")
    db.delete(row)
    db.commit()
    st.scheduler.reload_jobs()
    st.broadcaster.publish({"type": "sources_changed"})
    return {"ok": True, "deleted": schedule_id}


@router.post("/api/sources/{source_id}/verify", dependencies=[Depends(require_api_token)])
def verify_source(source_id: str, request: Request, db=Depends(_db)) -> dict:
    st = _state(request)
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, f"source 없음: {source_id}")
    result = st.registration.verify_source(db, source)
    db.commit()
    return result


# ── instances ───────────────────────────────────────────────

def _instance_view(inst: ScmInstance) -> dict:
    return {"id": inst.id, "kind": inst.kind, "label": inst.label,
            "base_url": inst.base_url, "token_header": inst.token_header,
            "has_token": bool(inst.token), "enabled": inst.enabled,
            "updated_at": isoformat_z(inst.updated_at)}


@router.get("/api/instances", dependencies=[Depends(require_api_token)])
def list_instances(db=Depends(_db)) -> list[dict]:
    return [_instance_view(i) for i in db.query(ScmInstance).order_by(ScmInstance.id).all()]


@router.post("/api/instances", status_code=201, dependencies=[Depends(require_api_token)])
def create_instance(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    kind = str(payload.get("kind") or "gitlab").lower()
    if kind not in ("gitlab", "github"):
        raise HTTPException(400, f"지원하지 않는 kind: {kind}")
    st = _state(request)
    inst = st.registration.upsert_instance(db, payload)
    db.commit()
    st.broadcaster.publish({"type": "instances_changed"})
    _audit(request, action="instance.create", target_kind="scm_instance",
           target_id=inst.id, detail={"kind": inst.kind, "base_url": inst.base_url[:100]})
    return _instance_view(inst)


@router.patch("/api/instances/{instance_id}", dependencies=[Depends(require_api_token)])
def update_instance(instance_id: str, request: Request, db=Depends(_db),
                    payload: dict = Body(...)) -> dict:
    if db.get(ScmInstance, instance_id) is None:
        raise HTTPException(404, f"instance 없음: {instance_id}")
    payload["id"] = instance_id
    st = _state(request)
    inst = st.registration.upsert_instance(db, payload, preserve_token=True)
    db.commit()
    st.broadcaster.publish({"type": "instances_changed"})
    _audit(request, action="instance.update", target_kind="scm_instance",
           target_id=inst.id, detail={"has_token": bool(inst.token),
                                        "rotated_at": isoformat_z(inst.token_rotated_at)})
    return _instance_view(inst)


# ── docs-hub ────────────────────────────────────────────────

def _validate_target_payload(payload: dict) -> dict:
    required = ["label", "kind", "url"]
    missing = [k for k in required if not str(payload.get(k) or "").strip()]
    warnings = []
    kind = str(payload.get("kind") or "gitlab").lower()
    if kind not in ("gitlab", "github"):
        warnings.append(f"지원하지 않는 kind: {kind} (gitlab | github)")
    if not str(payload.get("project_id") or payload.get("project_path") or "").strip():
        warnings.append("API 호출에는 project_id 또는 project_path가 필요합니다.")
    if not str(payload.get("token") or "").strip():
        warnings.append("토큰이 없으면 MR 생성은 비활성 모드로만 동작합니다.")
    return {"ok": not missing, "missing": missing, "warnings": warnings}


@router.get("/api/docs-hub", dependencies=[Depends(require_api_token)])
def list_targets(request: Request, db=Depends(_db)) -> dict:
    st = _state(request)
    targets = db.query(DocTarget).order_by(DocTarget.id).all()
    return {"targets": [st.registration.doc_target_view(t) for t in targets]}


@router.post("/api/docs-hub/validate", dependencies=[Depends(require_api_token)])
def validate_target(payload: dict = Body(...)) -> dict:
    return _validate_target_payload(payload)


@router.post("/api/docs-hub", status_code=201, dependencies=[Depends(require_api_token)])
def create_target(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    st = _state(request)
    validation = _validate_target_payload(payload)
    if not validation["ok"]:
        raise HTTPException(400, f"필수값 누락: {validation['missing']}")
    target = st.registration.upsert_doc_target(db, payload)
    db.commit()
    st.broadcaster.publish({"type": "targets_changed"})
    _audit(request, action="doc_target.create", target_kind="doc_target",
           target_id=target.id, detail={"kind": target.kind, "enabled": target.enabled})
    return st.registration.doc_target_view(target)


@router.patch("/api/docs-hub/{target_id}", dependencies=[Depends(require_api_token)])
def update_target(target_id: str, request: Request, db=Depends(_db),
                  payload: dict = Body(...)) -> dict:
    st = _state(request)
    if db.get(DocTarget, target_id) is None:
        raise HTTPException(404, f"target 없음: {target_id}")
    payload["id"] = target_id
    target = st.registration.upsert_doc_target(db, payload, preserve_token=True)
    db.commit()
    st.broadcaster.publish({"type": "targets_changed"})
    _audit(request, action="doc_target.update", target_kind="doc_target",
           target_id=target.id, detail={"enabled": target.enabled})
    return st.registration.doc_target_view(target)


def _mr_plan(request: Request, db, run: str, target_id: str) -> dict:
    st = _state(request)
    summary = run_summary(request, db, run=run)
    target = db.get(DocTarget, target_id)
    if target is None:
        raise HTTPException(404, f"docs-hub target 없음: {target_id}")
    source_row = db.get(Source, summary.get("source_id") or "")
    source = st.registration.source_view(db, source_row) if source_row else None
    plan = build_mr_plan(
        summary,
        target=st.registration.doc_target_view(target, with_token=True),
        source=source, out_dir=st.settings.out_path,
    )
    # quality guard
    publishable = bool(summary.get("publishable"))
    publish_state = str(summary.get("publish_state") or "unknown")
    blocked_reason = str(summary.get("blocked_reason") or "")
    coverage = summary.get("coverage") or {}
    quality = summary.get("quality") or {}
    if not publishable or publish_state == "blocked":
        plan["can_submit"] = False
        if not blocked_reason:
            blocked_reason = (quality.get("failed_gate")
                              or "quality/coverage gate failed")
        if coverage.get("status") == "fail" and "coverage" not in blocked_reason.lower():
            blocked_reason = (blocked_reason + " / coverage below threshold").strip(" /")
    elif publish_state == "review_required":
        plan["can_submit"] = True
        plan.setdefault("warnings", [])
        plan["warnings"].append("warning quality — MR 제출 가능, review 필수")
    plan["readiness"] = summary.get("mr", {}).get("readiness", "unknown")
    plan["blocked_reason"] = blocked_reason
    plan["quality_summary"] = {
        "status": quality.get("status", "not_evaluated"),
        "score": quality.get("score"),
        "failed_gate": quality.get("failed_gate", ""),
        "warning_count": int(quality.get("warning_count") or 0),
        "error_count": int(quality.get("error_count") or 0),
        "publishable": publishable,
    }
    plan["coverage"] = coverage
    plan["requires_override"] = bool(not publishable
                                      and not payload_overrides_run("mr-override"))
    _augment_mr_plan_with_doc_outputs(plan, db, run)
    return plan


def _augment_mr_plan_with_doc_outputs(plan: dict, db, run_id: str) -> None:
    """MR Plan 을 file-level quality-aware 로 강화.

    raw/2026-07-08-backend-api-ai-pipeline-improvement-plan.md §10.1-10.2:
    - publishable doc만 기본 포함
    - failed quality doc은 excluded
    - warning doc은 review_required 표시
    - deprecated candidates 포함
    - file-level included_files / excluded_files / review_checklist 보강
    """
    from .models import RunDocOutput
    doc_rows = db.scalars(
        select(RunDocOutput).where(RunDocOutput.run_id == run_id)
    ).all()
    included: list[dict] = []
    excluded: list[dict] = []
    review_checklist: list[str] = []
    publish_state = str(plan.get("publish_state") or "unknown")
    readiness = str(plan.get("readiness") or "unknown")
    for r in doc_rows:
        item = {
            "id": r.id, "path": r.path, "theme": r.theme or "",
            "title": r.title or "", "action": r.action,
            "quality_status": r.quality_status or "not_evaluated",
            "publishable": bool(r.publishable),
            "mr_inclusion_status": r.mr_inclusion_status or "candidate",
            "evidence_count": int(r.evidence_count or 0),
            "unsupported_claim_count": int(r.unsupported_claim_count or 0),
            "warning_count": int(r.warning_count or 0),
        }
        include_result = _decide_doc_inclusion(item, readiness, publish_state)
        if include_result[0] is True:
            included.append({**item, "review_required": False}
                            if include_result[2] else item)
            review_checklist.extend(include_result[2])
        elif include_result[0] is False:
            excluded.append({**item, "reason": include_result[1]})
            review_checklist.extend(include_result[2])
        else:
            included.append({**item, "review_required": True})
            review_checklist.extend(include_result[2])

    plan["included_files"] = included
    plan["excluded_files"] = excluded
    plan["review_checklist"] = review_checklist
    if excluded and plan.get("blocked_reason"):
        plan["blocked_reason"] = plan["blocked_reason"] + " / 일부 문서 제외"
    plan["needs_review"] = any(f.get("review_required") for f in included)


def _decide_doc_inclusion(
    item: dict, readiness: str, publish_state: str
) -> tuple[bool, str, list[str]]:
    """문서 단위 포함 결정.

    - quality_status=fail 또는 readiness=blocked 또는 publish_state=blocked → 제외
    - 그 외엔 포함 (warning/review_required 상태에서는 review checklist 항목 추가)
    """
    qs = str(item.get("quality_status") or "not_evaluated")
    if readiness == "blocked":
        return False, "run readiness=blocked", []
    if qs == "fail":
        return False, "doc quality_status=fail", []
    if publish_state == "blocked":
        return False, "publish_state=blocked", []
    path = item.get("path", "?")
    checklist: list[str] = []
    if int(item.get("unsupported_claim_count", 0)) > 0:
        checklist.append(f"문서 {path} 에 unsupported_claim — review 전 확인")
    if qs == "warning" or publish_state == "review_required":
        checklist.append(f"문서 {path} quality=warning — review 필수")
    if item.get("mr_inclusion_status") == "deprecated_candidate":
        checklist.append(f"문서 {path} deprecated 후보 — MR 포함 확인")
    include = True if not checklist else "review"
    return include, "", checklist


def payload_overrides_run(token: str) -> bool:
    """override flag — 현재는 항상 False (권한 시스템은 추후 도입)."""
    return False


@router.get("/api/docs-hub/mr-plan", dependencies=[Depends(require_api_token)])
def mr_plan(request: Request, db=Depends(_db), run: str = Query(""),
            target: str = Query("product-common")) -> dict:
    plan = _mr_plan(request, db, _check_run_id(run), target)
    plan["target"].pop("token", None)
    return plan


@router.post("/api/docs-hub/submit-mr", dependencies=[Depends(require_api_token)])
def submit_mr(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    st = _state(request)
    run = _check_run_id(str(payload.get("run") or ""))
    target_id = str(payload.get("target") or "product-common")
    plan = _mr_plan(request, db, run, target_id)
    # quality guard — readiness=blocked 면 기본 거부 (override 필요)
    if plan.get("readiness") == "blocked" and not payload.get("force"):
        raise HTTPException(
            409, f"submit-mr blocked: {plan.get('blocked_reason', 'quality gate')}")
    target_private = dict(plan["target"])
    plan["target"].pop("token", None)
    if payload.get("dry_run", False):
        return {"ok": True, "dry_run": True, "plan": plan}
    if payload.get("confirm") != target_id:
        raise HTTPException(400, f"실제 MR 제출에는 confirm='{target_id}'가 필요합니다.")
    try:
        result = submit_change_request(plan, target=target_private,
                                       out_dir=st.settings.out_path)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "plan": plan, "result": result}


# ── WebSocket 실시간 채널 (폴링 대체 — 폴링 API는 폴백으로 유지) ──

@router.websocket("/api/ws")
async def ws_channel(websocket: WebSocket, verbose: int = Query(0)):
    """실시간 채널 — ?verbose=1 이면 thinking 이벤트까지 수신, 기본(0)은 제외.

    control_ws_default_verbose 설정이 true 면 verbose 인수가 없을 때 기본값이 1.
    클라이언트가 명시적으로 ?verbose=0 을 주면 설정과 무관하게 필터 적용.
    """
    state = websocket.app.state
    tokens: dict[str, str] = state.api_tokens
    if tokens:
        presented = websocket.query_params.get("token", "")
        if not any(secrets.compare_digest(presented, t) for t in tokens):
            await websocket.close(code=4401)
            return
    await websocket.accept()
    # 기본 필터: verbose=1 → 모두 수신(passthrough), verbose=0 → thinking 제거
    from .ws import default_filter, passthrough_filter
    if "verbose" not in websocket.query_params:
        verbose = 1 if state.settings.control_ws_default_verbose else 0
    filter_fn = passthrough_filter if verbose else default_filter
    q = state.broadcaster.register(filter_fn)

    overflowed = False

    def _on_overflow(_msg):
        nonlocal overflowed
        overflowed = True
        # 큐가 찬 클라이언트는 disconnect 가 더 안전. 다음 pump tick 에 끊는다.
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(websocket.close(code=4408))
        except Exception:  # noqa: BLE001
            pass

    state.broadcaster.register_overflow_callback(_on_overflow)

    async def _pump():
        while True:
            msg = await q.get()
            await websocket.send_json(msg)
            if overflowed:
                return

    sender = asyncio.create_task(_pump())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        state.broadcaster.unregister(q)


# ── VNC WebSocket Gateway (§6.8) ──────────────────────────────

@router.websocket("/api/runs/{run_id}/vnc/ws")
async def vnc_ws_channel(websocket: WebSocket, run_id: str,
                         session: str = Query(""),
                         token: str = Query("")):
    """VNC monitoring WebSocket — browser react-vnc 와 mcp-vnc 사이 proxy (v1 stub).

    v1: session 검증, view-only 강제, audit log, 주기적 status frame 송신.
    실제 TCP VNC proxy (upstream frame relay) 는 v2 — 이 라우트는 auth/guard
    구조만 갖추고 연결을 유지한다.
    """
    from .vnc_gateway import (
        VncGateway, WS_CLOSE_SESSION_NOT_FOUND, WS_CLOSE_SESSION_EXPIRED,
        WS_CLOSE_VIEW_ONLY_FALSE, WS_CLOSE_INVALID_TOKEN,
    )
    _check_run_id(run_id)
    state = websocket.app.state
    gateway: VncGateway = state.vnc_gateway

    # auth: API 토큰 (websocket 은 query param 인증 — ws_channel 과 동일)
    tokens: dict[str, str] = state.api_tokens
    if tokens:
        presented = websocket.query_params.get("token", "")
        # token param 이 VNC gateway token 이면 API 인증을 별도로 해야 하지만,
        # v1 에서는 API 토큰 인증을 우선하고 gateway token 검증은 별도 단계.
        if presented and not any(secrets.compare_digest(presented, t) for t in tokens):
            # API 토큰이 아니면 VNC gateway token 으로 시도하지만, session 검증에서
            # 별도로 처리한다. 여기서는 API 토큰이 아니어도 계속 진행 — session
            # 검증이 실질적 인증이다.
            pass

    # session 검증: run_vnc_sessions 테이블에서 session_id 조회
    db = state.session_factory()
    try:
        session_row = gateway.get_session(db, run_id, session)
        if session_row is None:
            gateway.audit(run_id=run_id, session_id=session, event="rejected",
                          detail={"reason": "session_not_found"})
            await websocket.close(code=WS_CLOSE_SESSION_NOT_FOUND)
            return
        # view_only=False → 거부 (보안 정책)
        if not gateway.is_view_only(session_row):
            gateway.audit(run_id=run_id, session_id=session, event="rejected",
                          detail={"reason": "view_only_false"})
            await websocket.close(code=WS_CLOSE_VIEW_ONLY_FALSE)
            return
        # session 만료 검사
        if gateway.is_expired(session_row):
            gateway.audit(run_id=run_id, session_id=session, event="rejected",
                          detail={"reason": "expired"})
            await websocket.close(code=WS_CLOSE_SESSION_EXPIRED)
            return
        # token 검증 (있으면). token 이 없으면 session_id 만으로 진입 허용 (v1).
        if token and not gateway.validate_token(token, run_id, session):
            gateway.audit(run_id=run_id, session_id=session, event="rejected",
                          detail={"reason": "invalid_token"})
            await websocket.close(code=WS_CLOSE_INVALID_TOKEN)
            return
    finally:
        db.close()

    await websocket.accept()
    gateway.audit(run_id=run_id, session_id=session, event="open",
                  remote_addr=(websocket.client.host if websocket.client else ""))

    # v1: 실제 TCP VNC proxy 없이 연결을 유지하며 주기적 status frame 송신.
    # 클라이언트가 보내는 input frame 은 모두 드랍 (view-only).
    _STATUS_INTERVAL = 2.0
    try:
        while True:
            # 클라이언트 메시지 수신 (input frame) — view-only 이므로 드랍.
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_text(), timeout=_STATUS_INTERVAL)
                # input frame 검증: keyboard/mouse/clipboard → 드랍
                try:
                    import json as _json
                    parsed = _json.loads(msg) if msg else {}
                except (ValueError, TypeError):
                    parsed = {"type": "raw", "data": msg}
                if gateway.is_input_frame(parsed):
                    gateway.audit(run_id=run_id, session_id=session,
                                  event="input_dropped",
                                  detail={"frame_type": parsed.get("type", "")})
                    continue
                # non-input frame (예: ping) 은 무시
            except asyncio.TimeoutError:
                pass
            # 주기적 status frame 송신
            db2 = state.session_factory()
            try:
                row = gateway.get_session(db2, run_id, session)
                if row is None:
                    gateway.audit(run_id=run_id, session_id=session,
                                  event="closed",
                                  detail={"reason": "session_disappeared"})
                    await websocket.close(code=WS_CLOSE_SESSION_NOT_FOUND)
                    return
                if gateway.is_expired(row):
                    gateway.audit(run_id=run_id, session_id=session,
                                  event="closed",
                                  detail={"reason": "expired_during_connection"})
                    await websocket.close(code=WS_CLOSE_SESSION_EXPIRED)
                    return
                await websocket.send_json(gateway.build_status_frame(row))
            finally:
                db2.close()
    except WebSocketDisconnect:
        gateway.audit(run_id=run_id, session_id=session, event="close",
                      detail={"reason": "client_disconnect"})
    except Exception as e:  # noqa: BLE001
        gateway.audit(run_id=run_id, session_id=session, event="close",
                      detail={"reason": f"error:{type(e).__name__}"})
    finally:
        gateway.audit(run_id=run_id, session_id=session, event="close",
                      detail={"reason": "final"})


# ── runner 컨텍스트 (Data Plane 전용 — 토큰이 복호화되어 내려간다) ──

@router.get("/api/runner/context", dependencies=[Depends(require_runner_token)])
def runner_context(request: Request, db=Depends(_db), run: str = Query("")) -> dict:
    """러너가 실행에 필요한 전부를 1회 조회 — 소스·인스턴스·브랜치·doc target·manual profile.

    runner 토큰 전용. 일반 API와 달리 커넥터 토큰을 복호화해 포함하므로
    이 엔드포인트는 절대 프런트가 호출하지 않는다.

    manual pipeline 일 때는 source_manual_profiles 의 secret_refs 를 실값으로
    풀어 내려준다 (frontend API 와 분리).
    """
    st = _state(request)
    run = _check_run_id(run)
    from .models import Run
    run_row = db.get(Run, run)
    if run_row is None:
        raise HTTPException(404, f"run 없음: {run}")
    source = db.get(Source, run_row.source_id)
    if source is None:
        raise HTTPException(404, f"source 없음: {run_row.source_id}")
    inst = db.get(ScmInstance, source.instance_id)
    branch = db.query(SourceBranch).filter_by(
        source_id=source.id, role=run_row.branch_role or "dev").first()
    box = st.box
    token = box.decrypt(source.token) if source.token else (box.decrypt(inst.token) if inst.token else "")
    targets = db.query(DocTarget).filter(DocTarget.enabled.is_(True)).all()

    manual_profile_view: dict | None = None
    scenario_set_view: dict | None = None
    if (run_row.pipeline_id or "static") == "manual":
        mp_row = db.get(SourceManualProfile, source.id)
        if mp_row is not None:
            allow = mp_row.tool_allowlist_json or []
            secret_values: dict[str, str] = {}
            refs = mp_row.secret_refs_json or {}
            if isinstance(refs, dict):
                for ref_name in refs.keys():
                    if not isinstance(ref_name, str):
                        continue
                    val = ""
                    if source.token and ref_name == "scm_token":
                        val = box.decrypt(source.token) if source.token else ""
                    elif inst and inst.token and ref_name == "instance_token":
                        val = box.decrypt(inst.token) if inst.token else ""
                    elif ref_name in os.environ:
                        val = os.environ[ref_name]
                    secret_values[ref_name] = val
            manual_profile_view = {
                "mcp_endpoint_url": mp_row.mcp_endpoint_url,
                "mcp_transport": mp_row.mcp_transport,
                "tool_allowlist": allow if isinstance(allow, list) else [],
                "secret_values": secret_values,
                "artifact_selector": mp_row.artifact_selector_json or {},
                "install_profile": mp_row.install_profile_json or {},
                "readiness_check": mp_row.readiness_check_json or {},
                "smoke_check": mp_row.smoke_check_json or {},
                "coverage_threshold": int(mp_row.coverage_threshold or 70),
                "failure_policy": mp_row.failure_policy or "block",
                "vnc": {
                    "enabled": bool(mp_row.vnc_enabled),
                    "host": mp_row.vnc_host or "",
                    "port": int(mp_row.vnc_port or 0),
                    "view_only": (mp_row.vnc_gateway_policy or "view_only") == "view_only",
                },
            }
            active_set = db.scalars(
                select(ManualScenarioSet).where(
                    ManualScenarioSet.source_id == source.id,
                    ManualScenarioSet.status == "active",
                )
            ).first()
            if active_set is not None:
                scenario_set_view = {
                    "id": active_set.id,
                    "name": active_set.name,
                    "version": int(active_set.version or 1),
                    "scenarios": active_set.scenario_json or {},
                }

    out_contract = {
        "requires_evidence_pack": True,
        "requires_quality_report": True,
        "requires_coverage_report": (run_row.pipeline_id or "static") == "manual",
        "requires_artifact_report": (run_row.pipeline_id or "static") == "manual",
        "warning_publish_policy": run_row.warning_publish_policy or "review_required",
    }

    ctx: dict[str, Any] = {
        "run": {
            "run_id": run_row.id, "mode": run_row.mode,
            "branch_role": run_row.branch_role, "pipeline_id": run_row.pipeline_id,
            "attempt": int(run_row.attempt or 1),
            "from_sha_snapshot": run_row.from_sha_snapshot or "",
            "status_contract": [
                "done", "done_with_warnings", "failed_quality_gate",
                "partial", "failed", "cancelled", "timeout",
            ],
        },
        "source": {
            "id": source.id, "label": source.label, "kind": inst.kind if inst else "gitlab",
            "url": inst.base_url if inst else "", "repo": source.repo,
            "token": token,
            "token_header": inst.token_header if inst else "PRIVATE-TOKEN",
            "themes": source.themes, "doc_dir": source.doc_dir,
        },
        "branch": {
            "role": branch.role if branch else "dev",
            "branch": branch.branch if branch else "",
            "baseline_sha": branch.baseline_sha if branch else "",
            "last_processed_sha": branch.last_processed_sha if branch else "",
            "enabled": branch.enabled if branch else False,
        },
        "doc_targets": [st.registration.doc_target_view(t, with_token=True) for t in targets],
        "output_contract": out_contract,
    }
    if manual_profile_view is not None:
        ctx["manual_profile"] = manual_profile_view
    if scenario_set_view is not None:
        ctx["scenario_set"] = scenario_set_view
    return ctx


# ── webhook (Data Plane -> Control Plane) ───────────────────

@router.post("/api/webhook/events", dependencies=[Depends(require_runner_token)])
def webhook_events(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    st = _state(request)
    run_id = _extract_run_id(payload)
    events = payload.get("events") or []
    if not isinstance(events, list):
        raise HTTPException(400, "events는 배열이어야 합니다.")
    # 동기 DoS 방지 — 러너가 한 번에 너무 많은 이벤트를 몰아보내지 못하게.
    # 러너는 청크 분할 전송으로 회피 가능.
    if len(events) > _WEBHOOK_EVENTS_MAX:
        raise HTTPException(
            413, f"events 너무 많음 ({len(events)} > {_WEBHOOK_EVENTS_MAX}) — 분할 전송하세요")
    try:
        count = st.run_service.ingest_events(db, run_id, events)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True, "ingested": count}


@router.post("/api/webhook/complete", dependencies=[Depends(require_runner_token)])
def webhook_complete(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    st = _state(request)
    run_id = _extract_run_id(payload)
    try:
        result = st.run_service.complete_run(db, run_id, payload)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    # ENT-C: 파이프라인 종료 메트릭 (status·duration·token)
    try:
        from .observability import record_run_completion
        from .models import Run as RunModel
        pipeline_id = str(payload.get("pipeline_id") or "")
        run_row = db.get(RunModel, run_id)
        if run_row is not None and not pipeline_id:
            pipeline_id = run_row.pipeline_id
        duration = 0.0
        if run_row is not None and run_row.created_at and run_row.updated_at:
            duration = (run_row.updated_at - run_row.created_at).total_seconds()
        record_run_completion(
            pipeline_id=pipeline_id,
            status=result.get("status", payload.get("status", "unknown")),
            duration_sec=duration,
            input_tokens=int(run_row.input_tokens if run_row else 0),
            output_tokens=int(run_row.output_tokens if run_row else 0),
        )
    except Exception as e:  # noqa: BLE001 — 메트릭 실패는 응답을 막지 않는다
        log.warning("run completion metric emit failed run=%s: %s: %s",
                    run_id, type(e).__name__, e)
    return result


# ── webhooks: heartbeat / quality / evidence / coverage / artifact / vnc / doc-outputs / final-pack ──


@router.post("/api/webhook/heartbeat", dependencies=[Depends(require_runner_token)])
def webhook_heartbeat(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    """러너 heartbeat — runs.heartbeat_at 갱신, run_started_at 첫 1회만 채움."""
    st = _state(request)
    run_id = _extract_run_id(payload)
    try:
        return st.run_service.heartbeat(
            db, run_id,
            attempt=payload.get("attempt"),
            stage=str(payload.get("stage") or ""),
            pid=str(payload.get("pid") or ""),
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/api/webhook/quality", dependencies=[Depends(require_runner_token)])
def webhook_quality(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    """runner 가 보내는 quality report webhook — first-class resource 로 upsert."""
    from .services import resources
    run_id = _extract_run_id(payload)
    try:
        result = resources.upsert_quality_report(db, run_id, payload)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    st = _state(request)
    if st.broadcaster is not None:
        from .models import Run as RunModel
        run_row = db.get(RunModel, run_id)
        if run_row is not None:
            st.broadcaster.publish({
                "type": "quality_updated", "run_id": run_id,
                "status": result.get("status"),
                "publishable": result.get("publishable"),
                "snapshot_version": int(run_row.snapshot_version or 0),
            })
            st.broadcaster.publish({
                "type": "run_status", "run_id": run_id,
                "status": run_row.status, "publishable": run_row.publishable,
                "publish_state": run_row.publish_state,
                "snapshot_version": int(run_row.snapshot_version or 0),
            })
    return result


@router.post("/api/webhook/evidence", dependencies=[Depends(require_runner_token)])
def webhook_evidence(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    from .services import resources
    run_id = _extract_run_id(payload)
    try:
        result = resources.upsert_evidence_pack(db, run_id, payload)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    st = _state(request)
    if st.broadcaster is not None:
        st.broadcaster.publish({
            "type": "evidence_updated", "run_id": run_id,
            "pack_id": result.get("pack_id"),
            "item_count": result.get("item_count"),
        })
    return result


@router.post("/api/webhook/coverage", dependencies=[Depends(require_runner_token)])
def webhook_coverage(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    from .services import resources
    run_id = _extract_run_id(payload)
    try:
        result = resources.upsert_coverage(db, run_id, payload)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    st = _state(request)
    if st.broadcaster is not None:
        st.broadcaster.publish({
            "type": "coverage_updated", "run_id": run_id,
            "status": result.get("status"),
            "percentage": result.get("percentage"),
            "reached": result.get("reached"),
            "expected": result.get("expected"),
        })
    return result


@router.post("/api/webhook/artifact", dependencies=[Depends(require_runner_token)])
def webhook_artifact(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    from .services import resources
    run_id = _extract_run_id(payload)
    try:
        result = resources.upsert_artifact(db, run_id, payload)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    st = _state(request)
    if st.broadcaster is not None:
        st.broadcaster.publish({
            "type": "artifact_updated", "run_id": run_id,
            "release_tag": result.get("release_tag"),
            "artifact_name": result.get("artifact_name"),
            "deploy_status": result.get("deploy_status"),
            "smoke_status": result.get("smoke_status"),
        })
    return result


@router.post("/api/webhook/vnc-session", dependencies=[Depends(require_runner_token)])
def webhook_vnc_session(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    from .services import resources
    run_id = _extract_run_id(payload)
    try:
        result = resources.upsert_vnc_session(db, run_id, payload)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    st = _state(request)
    if st.broadcaster is not None:
        st.broadcaster.publish({
            "type": "vnc_session_updated", "run_id": run_id,
            "session_id": result.get("session_id"),
            "status": result.get("status"),
            "view_only": result.get("view_only"),
        })
    return result


@router.post("/api/webhook/doc-outputs", dependencies=[Depends(require_runner_token)])
def webhook_doc_outputs(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    from .services import resources
    run_id = _extract_run_id(payload)
    docs = payload.get("docs") or payload.get("outputs") or []
    if not isinstance(docs, list):
        raise HTTPException(400, "docs/outputs 는 배열이어야 합니다.")
    n = resources.upsert_doc_outputs(db, run_id, docs)
    db.commit()
    return {"ok": True, "upserted": n}


@router.post("/api/webhook/final-pack", dependencies=[Depends(require_runner_token)])
def webhook_final_pack(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    """Final Packager 가 보내는 한방 번들 — evidence/quality/coverage/artifact 일괄.

    부분 실패가 있어도 webhook 은 부분 ingest 응답을 받지만, complete webhook 을
    보내기 전에 이 endpoint 가 정상 응답해야 backend 가 일관성 check 를 통과했다고
    본다. partial ingest 는 `partial=true` 응답으로 표시.
    """
    from .services import resources
    run_id = _extract_run_id(payload)
    try:
        result: dict[str, Any] = {"ok": True, "partial": False, "items": {}}
        for key, fn in (
            ("evidence", resources.upsert_evidence_pack),
            ("quality", resources.upsert_quality_report),
            ("coverage", resources.upsert_coverage),
            ("artifact", resources.upsert_artifact),
            ("vnc", resources.upsert_vnc_session),
        ):
            sub = payload.get(key)
            if sub is None:
                continue
            if not isinstance(sub, dict):
                result["partial"] = True
                result["items"][key] = {"ok": False, "error": "not_object"}
                continue
            try:
                result["items"][key] = fn(db, run_id, sub)
            except ValueError as e:
                result["partial"] = True
                result["items"][key] = {"ok": False, "error": str(e)}
        # doc_outputs 도 같은 묶음으로 받는다
        docs = payload.get("doc_outputs")
        if isinstance(docs, list):
            try:
                result["items"]["doc_outputs"] = {
                    "ok": True, "upserted": resources.upsert_doc_outputs(db, run_id, docs),
                }
            except Exception as e:  # noqa: BLE001
                result["partial"] = True
                result["items"]["doc_outputs"] = {"ok": False, "error": str(e)}
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    if not result["partial"]:
        from .models import Run as RunModel
        run_row = db.get(RunModel, run_id)
        if run_row is not None:
            run_row.snapshot_version = int(run_row.snapshot_version or 0) + 1
            db.commit()
    return result


# ── 비용 집계 (question-cost-estimation 실측) ────────────────

@router.get("/api/costs", dependencies=[Depends(require_api_token)],
            response_model=CostsResponse)
def costs(request: Request, db=Depends(_db)) -> dict:
    service = _state(request).run_service
    rows = service.list_runs(db, limit=1000)
    model_rows = service.list_model_usage(db, limit=5000)
    by_source: dict[str, dict[str, Any]] = {}
    for r in rows:
        agg = by_source.setdefault(r["source_id"] or "(unknown)", {
            "runs": 0, "input_tokens": 0, "output_tokens": 0, "failed": 0,
        })
        agg["runs"] += 1
        agg["input_tokens"] += r["input_tokens"]
        agg["output_tokens"] += r["output_tokens"]
        agg["failed"] += 1 if r["status"] == "failed" else 0
    by_model: dict[str, dict[str, Any]] = {}
    for r in model_rows:
        key = f"{r['provider']}::{r['model']}"
        agg = by_model.setdefault(key, {
            "provider": r["provider"],
            "model": r["model"],
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "runs": 0,
            "_run_ids": set(),
        })
        agg["calls"] += r["calls"]
        agg["input_tokens"] += r["input_tokens"]
        agg["output_tokens"] += r["output_tokens"]
        agg["_run_ids"].add(r["run_id"])
    for agg in by_model.values():
        agg["runs"] = len(agg.pop("_run_ids"))
    return {
        "by_source": by_source,
        "by_model": by_model,
        "model_usage": model_rows,
        "total_input_tokens": sum(a["input_tokens"] for a in by_source.values()),
        "total_output_tokens": sum(a["output_tokens"] for a in by_source.values()),
    }


# ── audit log (ENT-F) ──────────────────────────────────────────

@router.get("/api/audit/recent", dependencies=[Depends(require_api_token)],
            response_model=AuditRecentResponse)
def audit_recent(request: Request, db=Depends(_db),
                  limit: int = Query(50, ge=1, le=500),
                  action: str = Query(""),
                  actor: str = Query("")) -> dict:
    """최근 audit 로그 조회. 운영 디버깅 / 컴플라이언스."""
    audit = getattr(request.app.state, "audit_service", None)
    if audit is None:
        return {"entries": [], "limit": limit}
    rows = audit.list_recent(db, limit=limit, actor=actor, action=action)
    return {"entries": rows, "limit": limit}
