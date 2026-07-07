"""Control Plane HTTP API.

기존 대시보드 프런트 계약(/api/runs·run-summary·events·sources·overview·docs-hub)을
유지하면서, 소스는 DB source of truth로, 이벤트는 DB(webhook 적재) 우선 + 레거시
JSONL 파일 폴백으로 서빙한다. 쓰기·webhook은 자체 토큰 인증 (decision-server-vm-self-token).
"""
from __future__ import annotations

import asyncio
import re
import secrets
from typing import Any

from fastapi import (APIRouter, Body, Depends, HTTPException, Query, Request,
                     WebSocket, WebSocketDisconnect)

from ..common.docshub import build_mr_plan, submit_change_request
from . import projection
from .models import DocTarget, ScmInstance, Source

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

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


# ── 메타 ─────────────────────────────────────────────────────

@router.get("/")
@router.get("/api")
def index() -> dict:
    return {
        "service": "wiki-pipeline control plane",
        "endpoints": [
            "/api/runs", "/api/runs/db", "POST /api/runs/trigger",
            "/api/sources", "POST /api/sources", "PATCH /api/sources/{id}",
            "POST /api/sources/validate", "POST /api/sources/{id}/verify",
            "/api/instances", "POST /api/instances",
            "/api/docs-hub", "/api/docs-hub/mr-plan?run=<id>&target=<id>",
            "POST /api/docs-hub/submit-mr",
            "/api/overview", "/api/run-summary?run=<id>",
            "/api/events?run=<id>&offset=<cursor>",
            "POST /api/webhook/events", "POST /api/webhook/complete",
            "/api/costs", "/health",
        ],
    }


@router.get("/health")
def health(request: Request) -> dict:
    return {"ok": True, "db": request.app.state.db_ok,
            "auth": bool(request.app.state.api_tokens),
            "secretbox": request.app.state.box.enabled}


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
    launched = st.run_service.launch_runner(run) is not None if payload.get("launch", True) else False
    return {"ok": True, "run_id": run.id, "launched": launched}


@router.get("/api/run-summary", dependencies=[Depends(require_api_token)])
def run_summary(request: Request, db=Depends(_db), run: str = Query("")) -> dict:
    st = _state(request)
    run = _check_run_id(run)
    if st.run_service.has_db_events(db, run):
        events = st.run_service.all_db_events(db, run)
        row = next((r for r in st.run_service.list_runs(db, limit=1000)
                    if r["run_id"] == run), None)
        return projection.summarize_events(
            events, run_id=run, source_id=(row or {}).get("source_id", ""))
    path = projection.find_run_path(st.settings.out_path, run)
    if not path:
        raise HTTPException(404, "run 없음")
    return projection.summarize_events(
        projection.read_all_file_events(path),
        run_id=run,
        source_id=projection.source_from_path(st.settings.out_path, path),
        path=str(path.relative_to(st.settings.out_path)),
        artifacts=projection.list_artifacts(path, st.settings.out_path),
    )


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


@router.get("/api/overview", dependencies=[Depends(require_api_token)])
def overview(request: Request, db=Depends(_db)) -> dict:
    st = _state(request)
    runs = list_runs(request, db)
    summaries = []
    for r in runs[:20]:
        try:
            summaries.append(run_summary(request, db, run=r["run_id"]))
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
    sources = db.query(Source).order_by(Source.id).all()
    return [st.registration.source_view(db, s) for s in sources]


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
    return view


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
            "updated_at": inst.updated_at.isoformat() if inst.updated_at else ""}


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
    return st.registration.doc_target_view(target)


def _mr_plan(request: Request, db, run: str, target_id: str) -> dict:
    st = _state(request)
    summary = run_summary(request, db, run=run)
    target = db.get(DocTarget, target_id)
    if target is None:
        raise HTTPException(404, f"docs-hub target 없음: {target_id}")
    source_row = db.get(Source, summary.get("source_id") or "")
    source = st.registration.source_view(db, source_row) if source_row else None
    return build_mr_plan(
        summary,
        target=st.registration.doc_target_view(target, with_token=True),
        source=source, out_dir=st.settings.out_path,
    )


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
async def ws_channel(websocket: WebSocket):
    state = websocket.app.state
    tokens: dict[str, str] = state.api_tokens
    if tokens:
        presented = websocket.query_params.get("token", "")
        if not any(secrets.compare_digest(presented, t) for t in tokens):
            await websocket.close(code=4401)
            return
    await websocket.accept()
    q = state.broadcaster.register()

    async def _pump():
        while True:
            await websocket.send_json(await q.get())

    sender = asyncio.create_task(_pump())
    try:
        while True:
            await websocket.receive_text()   # keepalive/ping — 서버는 브로드캐스트 전용
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        state.broadcaster.unregister(q)


# ── runner 컨텍스트 (Data Plane 전용 — 토큰이 복호화되어 내려간다) ──

@router.get("/api/runner/context", dependencies=[Depends(require_runner_token)])
def runner_context(request: Request, db=Depends(_db), run: str = Query("")) -> dict:
    """러너가 실행에 필요한 전부를 1회 조회 — 소스·인스턴스·브랜치·doc target.

    runner 토큰 전용. 일반 API와 달리 커넥터 토큰을 복호화해 포함하므로
    이 엔드포인트는 절대 프런트가 호출하지 않는다.
    """
    st = _state(request)
    run = _check_run_id(run)
    from .models import Run, SourceBranch
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
    return {
        "run": {"run_id": run_row.id, "mode": run_row.mode,
                "branch_role": run_row.branch_role, "pipeline_id": run_row.pipeline_id},
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
    }


# ── webhook (Data Plane -> Control Plane) ───────────────────

@router.post("/api/webhook/events", dependencies=[Depends(require_runner_token)])
def webhook_events(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    st = _state(request)
    run_id = _check_run_id(str(payload.get("run_id") or ""))
    events = payload.get("events") or []
    if not isinstance(events, list):
        raise HTTPException(400, "events는 배열이어야 합니다.")
    count = st.run_service.ingest_events(db, run_id, events)
    return {"ok": True, "ingested": count}


@router.post("/api/webhook/complete", dependencies=[Depends(require_runner_token)])
def webhook_complete(request: Request, db=Depends(_db), payload: dict = Body(...)) -> dict:
    st = _state(request)
    run_id = _check_run_id(str(payload.get("run_id") or ""))
    try:
        return st.run_service.complete_run(db, run_id, payload)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


# ── 비용 집계 (question-cost-estimation 실측) ────────────────

@router.get("/api/costs", dependencies=[Depends(require_api_token)])
def costs(request: Request, db=Depends(_db)) -> dict:
    rows = _state(request).run_service.list_runs(db, limit=1000)
    by_source: dict[str, dict[str, Any]] = {}
    for r in rows:
        agg = by_source.setdefault(r["source_id"] or "(unknown)", {
            "runs": 0, "input_tokens": 0, "output_tokens": 0, "failed": 0,
        })
        agg["runs"] += 1
        agg["input_tokens"] += r["input_tokens"]
        agg["output_tokens"] += r["output_tokens"]
        agg["failed"] += 1 if r["status"] == "failed" else 0
    return {
        "by_source": by_source,
        "total_input_tokens": sum(a["input_tokens"] for a in by_source.values()),
        "total_output_tokens": sum(a["output_tokens"] for a in by_source.values()),
    }
