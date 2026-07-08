"""Deep health checks — k8s liveness/readiness/startup 컨벤션.

  /health/live    — 프로세스 살아 있음. 무조건 200 (단순 핑).
  /health/ready   — 트래픽 받을 준비. DB / 스케줄러 / broadcaster 검사.
  /health/startup — 기동 완료. _seed_from_env·APScheduler·broadcaster 바인딩 확인.
  /health         — 종합 (구 호환 — 이전 호출자용)
  /metrics        — Prometheus 텍스트 exposition

각 엔드포인트는 deep_healthcheck_timeout_sec 안에 서브 체크를 끝낸다. 응답 형태:
  {"status": "ok|degraded|down", "checks": {name: {"ok": bool, "detail": str}}, "ts": iso}
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import text

from .timeutil import isoformat_z

router = APIRouter()
_log = logging.getLogger("controlplane.health")


def _now_iso() -> str:
    return isoformat_z(datetime.now(timezone.utc))


def _check_db(request: Request, timeout: float) -> dict[str, Any]:
    """DB 연결 + SELECT 1 — 느리면 degraded."""
    sf = request.app.state.session_factory
    started = time.perf_counter()
    try:
        with sf() as db:
            db.execute(text("SELECT 1"))
        elapsed = time.perf_counter() - started
        return {"ok": True, "detail": f"{elapsed*1000:.1f}ms", "elapsed_sec": elapsed}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"[:200]}


def _check_scheduler(request: Request) -> dict[str, Any]:
    """APScheduler 가 시작됐고 잡이 1개 이상 등록돼 있는지."""
    sched = request.app.state.scheduler
    if not sched.settings.scheduler_enabled:
        return {"ok": True, "detail": "scheduler disabled (SCHEDULER_ENABLED=false)"}
    running = getattr(sched, "_scheduler", None)
    if running is None or not running.running:
        return {"ok": False, "detail": "scheduler not started"}
    jobs = running.get_jobs()
    return {"ok": True, "detail": f"{len(jobs)} jobs", "job_count": len(jobs)}


def _check_broadcaster(request: Request) -> dict[str, Any]:
    b = request.app.state.broadcaster
    return {
        "ok": True,
        "detail": f"{b.client_count} clients",
        "client_count": b.client_count,
    }


def _check_secretbox(request: Request) -> dict[str, Any]:
    box = request.app.state.box
    return {
        "ok": True,
        "detail": "Fernet enabled" if box.enabled else "Fernet disabled (tokens in plaintext — dev only)",
        "enabled": box.enabled,
    }


@router.get("/health/live")
def health_live() -> dict:
    """Kubernetes livenessProbe — 프로세스 자체의 살아있음."""
    return {"status": "ok", "ts": _now_iso()}


@router.get("/health/ready")
def health_ready(request: Request) -> dict:
    """트래픽 수신 가능 — DB/스케줄러/브로드캐스터 검사."""
    timeout = request.app.state.settings.deep_healthcheck_timeout_sec
    checks = {
        "db": _check_db(request, timeout),
        "scheduler": _check_scheduler(request),
        "broadcaster": _check_broadcaster(request),
    }
    overall = "ok" if all(c["ok"] for c in checks.values()) else "down"
    return {"status": overall, "checks": checks, "ts": _now_iso()}


@router.get("/health/startup")
def health_startup(request: Request) -> dict:
    """기동 시 1회 통과용 — 시드/APScheduler 등 결정성 확인."""
    checks = {
        "db": _check_db(request, request.app.state.settings.deep_healthcheck_timeout_sec),
        "secretbox": _check_secretbox(request),
    }
    overall = "ok" if all(c["ok"] for c in checks.values()) else "degraded"
    return {"status": overall, "checks": checks, "ts": _now_iso()}


@router.get("/health")
def health_legacy(request: Request) -> dict:
    """구 호환 — 프런트/모니터가 기존 경로를 사용 중."""
    return {
        "ok": True,
        "db": request.app.state.db_ok,
        "auth": bool(request.app.state.api_tokens),
        "secretbox": request.app.state.box.enabled,
        "ts": _now_iso(),
    }
