"""백엔드 예외처리·중단 복구 회귀 테스트 (2026-07-10).

이 세션에서 메운 구멍들의 회귀 방지:
  - reaper 사각지대: 첫 heartbeat(stage="")로 heartbeat_at 이 채워진 채 죽은
    pending run 이 영구 잔류하던 문제.
  - runner_pid 생존 확인 기반 즉시 회수.
  - Control Plane 재기동 시 crash recovery(require_dead_pid).
  - reaper 가 timeout 을 먼저 박아도 러너의 실패 error 를 보존.
  - /health/ready·startup 이 down 이면 503.
  - complete 전송 실패 시 로컬 보존.

fixture 는 test_pipeline_quality_evidence 와 같은 패턴.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.controlplane.app as app_module
from backend.controlplane.db import session_scope
from backend.controlplane.models import (
    Base, Run, ScmInstance, Source, SourceBranch, SourceSchedule,
)
from backend.controlplane.settings import ControlPlaneSettings

ADMIN = {"Authorization": "Bearer tok-admin"}
RUNNER = {"Authorization": "Bearer tok-runner"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "_seed_from_env", lambda app: None)
    settings = ControlPlaneSettings(
        control_db_url=f"sqlite:///{tmp_path}/cp.sqlite",
        control_api_tokens="admin:tok-admin",
        control_runner_token="tok-runner",
        control_secret_key=Fernet.generate_key().decode(),
        scheduler_enabled=False,
        notify_mode="log",
        admin_email="admin@example.com",
        out_dir=str(tmp_path / "out"),
    )
    engine = create_engine(settings.control_db_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        db.add_all([
            ScmInstance(id="inst1", kind="gitlab", label="local",
                        base_url="https://gitlab.example.com", token="enc",
                        token_header="PRIVATE-TOKEN", enabled=True),
            Source(id="src1", instance_id="inst1", label="demo", repo="r",
                   themes="intro", doc_dir="r", schedule_cron="", enabled=True),
            SourceBranch(source_id="src1", role="dev", branch="main",
                         baseline_sha="", last_processed_sha="", enabled=True),
            SourceSchedule(source_id="src1", label="default", pipeline_id="static",
                           mode="auto", branch_role="dev", cron="", enabled=True),
        ])
        db.commit()
    app = app_module.create_app(settings)
    with TestClient(app) as c:
        c.app = app
        yield c


def _trigger(client):
    r = client.post("/api/runs/trigger", headers=ADMIN,
                    json={"source_id": "src1", "mode": "auto",
                          "pipeline_id": "static", "launch": False})
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


def _run_service(client):
    return client.app.state.run_service


def _factory(client):
    return client.app.state.session_factory


# ── reaper 사각지대: 첫 heartbeat 후 죽은 pending run ─────────────────

def test_reap_pending_with_heartbeat_at_set(client):
    """예전 버그: 첫 heartbeat(stage="")로 heartbeat_at 이 채워지면 status 는
    pending 인데 reaper 의 `heartbeat_at is None` 가드에 걸려 영구 잔류했다.
    이제 pid 무효(빈값) + 마지막 활동 오래됨이면 failed 로 회수돼야 한다."""
    run_id = _trigger(client)
    old = datetime.now(timezone.utc) - timedelta(seconds=7200)
    with session_scope(_factory(client)) as db:
        r = db.get(Run, run_id)
        r.created_at = old
        r.heartbeat_at = old       # 첫 heartbeat 가 채운 상태 재현
        r.runner_pid = ""          # 러너 미기동 / pid 판정 불가
        db.commit()
    with session_scope(_factory(client)) as db:
        n = _run_service(client).reap_stuck_runs(db)
    assert n >= 1
    with session_scope(_factory(client)) as db:
        r = db.get(Run, run_id)
        assert r.status == "failed"
        assert r.terminal_at is not None
        assert r.error


def test_reap_dead_pid_immediate(client):
    """runner_pid 가 죽은 프로세스면 시간 임계값과 무관하게 즉시 회수(posix)."""
    if os.name != "posix":
        pytest.skip("pid 생존 확인은 posix 전용")
    run_id = _trigger(client)
    with session_scope(_factory(client)) as db:
        r = db.get(Run, run_id)
        r.status = "running"
        r.heartbeat_at = datetime.now(timezone.utc)   # 방금 heartbeat (최신)
        r.runner_pid = "2147483646"                    # 존재하지 않을 pid
        db.commit()
    with session_scope(_factory(client)) as db:
        n = _run_service(client).reap_stuck_runs(db)
    assert n >= 1
    with session_scope(_factory(client)) as db:
        r = db.get(Run, run_id)
        assert r.status == "timeout"          # running → timeout
        assert "종료됨" in (r.error or "")


def test_reap_require_dead_pid_spares_unknown(client):
    """require_dead_pid 모드(재기동 회수)는 pid 판정 불가(빈값/원격)면 건드리지
    않는다 — 재기동 순간 고아로 계속 도는 러너를 죽이지 않기 위함."""
    run_id = _trigger(client)
    old = datetime.now(timezone.utc) - timedelta(seconds=99999)
    with session_scope(_factory(client)) as db:
        r = db.get(Run, run_id)
        r.status = "running"
        r.created_at = old
        r.heartbeat_at = old
        r.runner_pid = ""          # 판정 불가
        db.commit()
    with session_scope(_factory(client)) as db:
        n = _run_service(client).reap_stuck_runs(db, require_dead_pid=True)
    assert n == 0
    with session_scope(_factory(client)) as db:
        assert db.get(Run, run_id).status == "running"


# ── 재기동 회수: startup 이 죽은 러너 run 을 정리 ────────────────────

def test_startup_crash_recovery_reaps_dead_pid(tmp_path, monkeypatch):
    """create_app lifespan 이 startup 에서 죽은 pid 의 active run 을 회수한다."""
    if os.name != "posix":
        pytest.skip("pid 생존 확인은 posix 전용")
    monkeypatch.setattr(app_module, "_seed_from_env", lambda app: None)
    db_url = f"sqlite:///{tmp_path}/cp2.sqlite"
    settings = ControlPlaneSettings(
        control_db_url=db_url, control_api_tokens="admin:tok-admin",
        control_runner_token="tok-runner",
        control_secret_key=Fernet.generate_key().decode(),
        scheduler_enabled=False, notify_mode="log",
        admin_email="a@b.c", out_dir=str(tmp_path / "out"),
    )
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        db.add_all([
            ScmInstance(id="i", kind="gitlab", label="l", base_url="x",
                        token="t", token_header="PRIVATE-TOKEN", enabled=True),
            Source(id="src1", instance_id="i", label="d", repo="r", themes="intro",
                   doc_dir="r", schedule_cron="", enabled=True),
            Run(id="static-src1-dead", source_id="src1", pipeline_id="static",
                mode="auto", branch_role="dev", trigger="manual",
                status="running", runner_pid="2147483646"),
        ])
        db.commit()
    app = app_module.create_app(settings)
    with TestClient(app):
        pass  # lifespan startup 이 회수를 실행
    with factory() as db:
        r = db.get(Run, "static-src1-dead")
        assert r.status in ("timeout", "failed")


# ── 최종 error 유실 방지 ────────────────────────────────────────────

def test_late_failed_event_preserves_error_after_timeout(client):
    """reaper 가 먼저 timeout 을 박은 뒤 러너가 failed+error 이벤트를 늦게 보내도
    error 문자열은 보존돼야 한다(프런트 '마지막 오류' 빈칸 방지)."""
    run_id = _trigger(client)
    with session_scope(_factory(client)) as db:
        r = db.get(Run, run_id)
        r.status = "timeout"
        r.error = "stuck timeout: heartbeat 없음 (3600s 경과)"  # reaper 자리표시자
        db.commit()
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"ts": "2026-07-10T10:00:00Z", "layer": "run", "stage": "",
                    "status": "failed", "event_id": "evt-late-fail",
                    "detail": {"error": "MiniMax rate limit 초과"}}],
    })
    with session_scope(_factory(client)) as db:
        r = db.get(Run, run_id)
        assert r.status == "timeout"                 # status 는 안 뒤집힘
        assert "rate limit" in (r.error or "")       # 실제 원인으로 채워짐


# ── /health/ready·startup 503 ──────────────────────────────────────

def test_health_ready_503_when_db_down(client, monkeypatch):
    """DB 체크 실패 시 /health/ready 가 503 을 반환한다(k8s 정합)."""
    from backend.controlplane import health as health_mod
    monkeypatch.setattr(
        health_mod, "_check_db",
        lambda request, timeout: {"ok": False, "detail": "boom"})
    rv = client.get("/health/ready")
    assert rv.status_code == 503
    assert rv.json()["status"] == "down"


def test_health_ready_200_when_ok(client):
    rv = client.get("/health/ready")
    assert rv.status_code == 200
    assert rv.json()["status"] == "ok"


# ── WS overflow 콜백 등록/해제 ─────────────────────────────────────

def test_overflow_callback_unregister():
    from backend.controlplane.ws import Broadcaster
    b = Broadcaster()
    calls = []
    b.register_overflow_callback(lambda m: calls.append(m), key="q1")
    b.register_overflow_callback(lambda m: calls.append(m), key="q2")
    assert len(b._overflow_callbacks) == 2
    b.unregister_overflow_callback("q1")
    assert len(b._overflow_callbacks) == 1
    assert b._overflow_callbacks[0][0] == "q2"
    b.unregister_overflow_callback("q2")
    assert b._overflow_callbacks == []


# ── complete 전송 실패 시 로컬 보존 ─────────────────────────────────

def test_complete_dumps_pending_on_failure(tmp_path, monkeypatch):
    from backend.runner.client import ControlPlaneClient
    monkeypatch.setenv("OUT_DIR", str(tmp_path / "out"))
    c = ControlPlaneClient("http://127.0.0.1:59999", "tok")  # 연결 불가 포트

    with pytest.raises(Exception):
        c.complete("run-xyz", {"status": "done", "last_processed_sha": "abc123"})
    c.close()

    pending = tmp_path / "out" / "pending_completes" / "run-xyz.json"
    assert pending.exists()
    import json
    data = json.loads(pending.read_text(encoding="utf-8"))
    assert data["run_id"] == "run-xyz"
    assert data["report"]["last_processed_sha"] == "abc123"
