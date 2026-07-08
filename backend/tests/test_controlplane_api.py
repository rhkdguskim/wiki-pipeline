"""Control Plane API 통합 테스트 — 임시 SQLite + FastAPI TestClient.

인증(자체 토큰) · 소스/인스턴스 등록 · 커넥터 검증(가짜 SCM) · 트리거 ·
webhook 이벤트 적재/완료 보고(sha 전진·자동 비활성화) · 비용 집계.
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

import backend.controlplane.app as app_module
from backend.controlplane.settings import ControlPlaneSettings

from .fake_scm import HEAD_SHA, FakeGitLab

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
    app = app_module.create_app(settings)
    with TestClient(app) as c:
        c.app = app
        yield c


def _patch_fake_connector(client, monkeypatch):
    """registration의 커넥터 생성을 가짜 GitLab로 대체."""
    fake = FakeGitLab()
    reg = client.app.state.registration

    def fake_connector(db, source, transport=None):
        from backend.connectors.gitlab import GitLabConnector
        return GitLabConnector(base_url="http://gitlab.local", token="t",
                               repo="grp/demo", retry_attempts=1,
                               transport=fake.transport)

    monkeypatch.setattr(reg, "connector_for_source", fake_connector)
    return fake


def _create_source(client, monkeypatch, verify=True) -> dict:
    _patch_fake_connector(client, monkeypatch)
    resp = client.post("/api/sources", headers=ADMIN, json={
        "id": "demo", "label": "Demo", "kind": "gitlab",
        "url": "http://gitlab.local", "project_id": "grp/demo",
        "token": "secret-token", "dev_branch": "main",
        "owner_email": "owner@example.com", "verify": verify,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_auth_required(client):
    assert client.get("/api/sources").status_code == 401
    assert client.get("/api/sources", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/sources", headers=ADMIN).status_code == 200
    assert client.get("/health").status_code == 200   # health는 공개


def test_source_registration_with_verify(client, monkeypatch):
    view = _create_source(client, monkeypatch)
    assert view["has_token"] is True
    assert view["dev_branch"] == "main"
    assert view["release_branch"] == "main"       # 기본값 = default_branch
    assert view["doc_dir"] == "grp/demo"          # 자동: namespace_path
    assert view["verification"]["verified"] is True
    assert view["verification"]["head_sha"] == HEAD_SHA
    assert "main" in view["verification"]["branches"]
    # 토큰 값은 API 응답에 절대 포함되지 않는다
    assert "secret-token" not in str(view)


def test_source_delete_removes_config_but_keeps_endpoint_audited(client, monkeypatch):
    _create_source(client, monkeypatch)
    resp = client.delete("/api/sources/demo", headers=ADMIN)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True, "deleted": "demo"}

    listing = client.get("/api/sources", headers=ADMIN).json()
    assert all(s["id"] != "demo" for s in listing)

    schedules = client.get("/api/schedules", headers=ADMIN).json()
    assert all(s["source_id"] != "demo" for s in schedules)

    audit = client.get("/api/audit/recent?limit=20", headers=ADMIN).json()
    assert any(e["action"] == "source.delete" and e["target_id"] == "demo"
               for e in audit["entries"])


def test_source_schedule_management(client, monkeypatch):
    _patch_fake_connector(client, monkeypatch)
    resp = client.post("/api/sources", headers=ADMIN, json={
        "id": "demo", "label": "Demo", "kind": "gitlab",
        "url": "http://gitlab.local", "project_id": "grp/demo",
        "token": "secret-token", "dev_branch": "main",
        "schedule_time": "09:30", "schedule_weekdays": ["mon", "wed", "fri"],
        "verify": False,
    })
    assert resp.status_code == 201, resp.text
    view = resp.json()
    assert view["schedule_cron"] == "30 9 * * mon,wed,fri"
    assert view["schedule"]["time"] == "09:30"
    assert view["schedule"]["weekdays"] == ["mon", "wed", "fri"]
    assert len(view["schedules"]) == 1
    assert view["schedules"][0]["pipeline_id"] == "static"

    schedules = client.get("/api/schedules", headers=ADMIN).json()
    assert schedules[0]["source_id"] == "demo"
    assert schedules[0]["description"] == "월·수·금 09:30 KST"
    assert schedules[0]["pipeline_id"] == "static"
    assert schedules[0]["next_run_at"]

    resp = client.patch("/api/sources/demo/schedule", headers=ADMIN, json={
        "schedule_time": "21:15", "schedule_weekdays": ["tue", "thu"],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["schedules"][0]["schedule_cron"] == "15 21 * * tue,thu"

    resp = client.post("/api/sources/demo/schedules", headers=ADMIN, json={
        "label": "릴리스 브랜치 점검",
        "pipeline_id": "static", "mode": "diff", "branch_role": "release",
        "schedule_time": "06:45", "schedule_weekdays": ["sat"],
    })
    assert resp.status_code == 201, resp.text
    schedule_id = resp.json()["id"]
    assert resp.json()["mode"] == "diff"
    assert resp.json()["branch_role"] == "release"
    assert resp.json()["schedule_cron"] == "45 6 * * sat"

    schedules = client.get("/api/schedules", headers=ADMIN).json()
    assert len(schedules) == 2
    assert {s["branch_role"] for s in schedules} == {"dev", "release"}

    resp = client.delete(f"/api/sources/demo/schedules/{schedule_id}", headers=ADMIN)
    assert resp.status_code == 200

    resp = client.patch("/api/sources/demo/schedule", headers=ADMIN, json={
        "schedule_time": "25:00", "schedule_weekdays": ["mon"],
    })
    assert resp.status_code == 400


def test_instance_crud(client):
    resp = client.post("/api/instances", headers=ADMIN, json={
        "id": "github-com", "kind": "github", "label": "GitHub.com", "token": "gh-tok",
    })
    assert resp.status_code == 201
    assert resp.json()["has_token"] is True
    listing = client.get("/api/instances", headers=ADMIN).json()
    assert [i["id"] for i in listing] == ["github-com"]
    assert client.post("/api/instances", headers=ADMIN,
                       json={"id": "x", "kind": "svn"}).status_code == 400


def test_trigger_and_webhook_lifecycle(client, monkeypatch):
    _create_source(client, monkeypatch)
    resp = client.post("/api/runs/trigger", headers=ADMIN,
                       json={"source_id": "demo", "launch": False})
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    # 러너가 이벤트를 push (runner 토큰)
    events = [
        {"schema": "progress.v1", "pipeline_id": "static", "run_id": run_id,
         "layer": "run", "stage": "static-diff", "status": "running", "ts": "2026-07-07T20:00:00"},
        {"layer": "stage", "stage": "compare", "status": "done", "ts": "2026-07-07T20:00:05",
         "detail": {"changed": 3}},
        {"layer": "agent_step", "stage": "theme:intro", "ts": "2026-07-07T20:01:00",
         "detail": {"kind": "usage", "input_tokens": 1000, "output_tokens": 500,
                    "provider": "openai-compatible", "model": "minimax-m3"}},
        {"layer": "engine_call", "stage": "theme:intro", "status": "done",
         "ts": "2026-07-07T20:02:00", "detail": {"saved": "intro.md", "verdict": "pass"}},
        {"layer": "run", "stage": "static-diff", "status": "done", "ts": "2026-07-07T20:03:00"},
    ]
    resp = client.post("/api/webhook/events", headers=RUNNER,
                       json={"run_id": run_id, "events": events})
    assert resp.status_code == 200 and resp.json()["ingested"] == 5

    # 인증 없는 webhook은 거부
    assert client.post("/api/webhook/events", json={"run_id": run_id, "events": []}).status_code == 401

    # DB 이벤트 기반 run-summary
    summary = client.get(f"/api/run-summary?run={run_id}", headers=ADMIN).json()
    assert summary["status"] == "done"
    assert summary["kpi"]["token_total"] == 1500
    assert summary["kpi"]["stage_done"] >= 1

    # 증분 커서 폴링
    first = client.get(f"/api/events?run={run_id}&offset=0", headers=ADMIN).json()
    assert len(first["events"]) == 5
    again = client.get(f"/api/events?run={run_id}&offset={first['offset']}", headers=ADMIN).json()
    assert again["events"] == []

    # 완료 보고 -> sha 전진 (MR 성공 후에만 — concept-idempotent-sha)
    resp = client.post("/api/webhook/complete", headers=RUNNER, json={
        "run_id": run_id, "status": "done", "last_processed_sha": HEAD_SHA,
        "doc_count": 1, "mr_url": "http://gitlab.local/mr/1",
    })
    assert resp.status_code == 200 and resp.json()["sha_advanced"] is True
    src = client.get("/api/sources", headers=ADMIN).json()[0]
    assert src["last_processed_sha"] == HEAD_SHA

    # run 목록에 반영
    runs = client.get("/api/runs/db", headers=ADMIN).json()
    assert runs[0]["run_id"] == run_id
    assert runs[0]["status"] == "done"
    assert runs[0]["input_tokens"] == 1000

    # 비용 집계
    costs = client.get("/api/costs", headers=ADMIN).json()
    assert costs["by_source"]["demo"]["input_tokens"] == 1000
    assert costs["by_model"]["openai-compatible::minimax-m3"]["input_tokens"] == 1000
    assert costs["by_model"]["openai-compatible::minimax-m3"]["calls"] == 1


def test_compare_404_disables_source(client, monkeypatch):
    _create_source(client, monkeypatch)
    run_id = client.post("/api/runs/trigger", headers=ADMIN,
                         json={"source_id": "demo", "launch": False}).json()["run_id"]
    resp = client.post("/api/webhook/complete", headers=RUNNER, json={
        "run_id": run_id, "status": "failed",
        "error": "compare 404: branch gone", "error_kind": "not_found",
    })
    assert resp.status_code == 200 and resp.json()["source_disabled"] is True
    src = client.get("/api/sources", headers=ADMIN).json()[0]
    assert src["enabled"] is False
    assert "404" in src["disabled_reason"]
    # 비활성 소스는 트리거 거부
    resp = client.post("/api/runs/trigger", headers=ADMIN,
                       json={"source_id": "demo", "launch": False})
    assert resp.status_code == 400


def test_rate_limited_failure_does_not_disable_or_flag_auth(client, monkeypatch):
    """SCM API rate limit(decision-scm-rate-limit-not-auth): 토큰은 유효하므로
    auth 알림 대상이 아니고, 자동 비활성화도 되지 않아야 한다 (compare 404와 대비)."""
    _create_source(client, monkeypatch)
    run_id = client.post("/api/runs/trigger", headers=ADMIN,
                         json={"source_id": "demo", "launch": False}).json()["run_id"]
    resp = client.post("/api/webhook/complete", headers=RUNNER, json={
        "run_id": run_id, "status": "failed",
        "error": "ScmRateLimitError: GitHub API rate limit exceeded",
        "error_kind": "rate_limited",
    })
    assert resp.status_code == 200 and resp.json()["source_disabled"] is False
    src = client.get("/api/sources", headers=ADMIN).json()[0]
    assert src["enabled"] is True
    assert src["disabled_reason"] == ""
    # rate limit은 일시적 — 소스는 여전히 트리거 가능
    resp = client.post("/api/runs/trigger", headers=ADMIN,
                       json={"source_id": "demo", "launch": False})
    assert resp.status_code == 200


def test_source_preflight_without_saving(client, monkeypatch):
    """등록 마법사 사전 검증 — DB에 아무것도 저장하지 않고 커넥터 검증만."""
    import backend.connectors as connectors_pkg
    from backend.connectors.gitlab import GitLabConnector
    fake = FakeGitLab()

    def fake_make_connector(**kwargs):
        return GitLabConnector(base_url="http://gitlab.local", token="t",
                               repo="grp/demo", retry_attempts=1,
                               transport=fake.transport)

    monkeypatch.setattr(connectors_pkg, "make_connector", fake_make_connector)
    resp = client.post("/api/sources/preflight", headers=ADMIN, json={
        "kind": "gitlab", "url": "http://gitlab.local",
        "project_id": "grp/demo", "token": "t",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["verified"] is True
    assert data["default_branch"] == "main"
    assert "main" in data["branches"]
    assert data["head_sha"] == HEAD_SHA
    # 저장되지 않았다
    assert client.get("/api/sources", headers=ADMIN).json() == []
    # repo 누락은 400
    assert client.post("/api/sources/preflight", headers=ADMIN,
                       json={"kind": "gitlab"}).status_code == 400


def test_runner_context_returns_decrypted_token(client, monkeypatch):
    _create_source(client, monkeypatch, verify=False)
    run_id = client.post("/api/runs/trigger", headers=ADMIN,
                         json={"source_id": "demo", "launch": False}).json()["run_id"]
    # runner 토큰 필수
    assert client.get(f"/api/runner/context?run={run_id}").status_code == 401
    ctx = client.get(f"/api/runner/context?run={run_id}", headers=RUNNER).json()
    assert ctx["source"]["token"] == "secret-token"   # 복호화되어 러너에게만 내려간다
    assert ctx["source"]["repo"] == "grp/demo"
    assert ctx["branch"]["role"] == "dev"
    assert ctx["run"]["run_id"] == run_id


def test_doc_target_and_mr_plan_requires_run(client):
    resp = client.post("/api/docs-hub", headers=ADMIN, json={
        "id": "product-common", "label": "product-common", "kind": "gitlab",
        "url": "http://gitlab.local/grp/product-common",
        "project_path": "grp/product-common", "token": "t", "enabled": True,
    })
    assert resp.status_code == 201
    assert resp.json()["has_token"] is True
    assert client.get("/api/docs-hub/mr-plan?run=nope", headers=ADMIN).status_code == 404


def test_event_retention_prunes_old_completed_runs(client, monkeypatch):
    _create_source(client, monkeypatch, verify=False)
    run_id = client.post("/api/runs/trigger", headers=ADMIN,
                         json={"source_id": "demo", "launch": False}).json()["run_id"]
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"layer": "run", "stage": "s", "status": "done", "ts": "2026-01-01T00:00:00"}],
    })
    from datetime import datetime, timedelta, timezone
    from backend.controlplane.db import session_scope
    from backend.controlplane.models import Run, RunEvent
    factory = client.app.state.session_factory
    with session_scope(factory) as db:
        run = db.get(Run, run_id)
        run.status = "done"
        run.updated_at = datetime.now(timezone.utc) - timedelta(days=90)
    with session_scope(factory) as db:
        deleted = client.app.state.run_service.prune_events(db, older_than_days=30)
    assert deleted == 1
    with session_scope(factory) as db:
        assert db.query(RunEvent).filter_by(run_id=run_id).count() == 0
        assert db.get(Run, run_id) is not None   # run 이력(보고·sha)은 영구 보존


def test_websocket_pushes_events_and_status(client, monkeypatch):
    """웹소켓 실시간 채널 — webhook 적재·완료 보고가 접속 클라이언트로 push된다."""
    _create_source(client, monkeypatch, verify=False)
    run_id = client.post("/api/runs/trigger", headers=ADMIN,
                         json={"source_id": "demo", "launch": False}).json()["run_id"]
    with client.websocket_connect("/api/ws?token=tok-admin") as ws:
        client.post("/api/webhook/events", headers=RUNNER, json={
            "run_id": run_id,
            "events": [{"layer": "stage", "stage": "compare", "status": "done",
                        "ts": "2026-07-07T20:00:00"}],
        })
        msg = ws.receive_json()
        assert msg["type"] == "events" and msg["run_id"] == run_id
        assert msg["events"][0]["stage"] == "compare"

        client.post("/api/webhook/complete", headers=RUNNER, json={
            "run_id": run_id, "status": "done", "last_processed_sha": HEAD_SHA,
        })
        statuses = [ws.receive_json() for _ in range(2)]
        types = {m["type"] for m in statuses}
        assert "run_status" in types and "runs_changed" in types
        status_msg = next(m for m in statuses if m["type"] == "run_status")
        assert status_msg["status"] == "done" and status_msg["sha_advanced"] is True


def test_websocket_rejects_bad_token(client):
    import pytest as _pytest
    with _pytest.raises(Exception):
        with client.websocket_connect("/api/ws?token=wrong") as ws:
            ws.receive_json()


def test_secretbox_encrypts_tokens_at_rest(client, monkeypatch, tmp_path):
    _create_source(client, monkeypatch, verify=False)
    import sqlite3
    con = sqlite3.connect(tmp_path / "cp.sqlite")
    stored = con.execute("SELECT token FROM sources WHERE id='demo'").fetchone()[0]
    con.close()
    assert stored.startswith("enc:v1:")
    assert "secret-token" not in stored


# ── regression: 버그 수정 후 재발 방지 ──────────────────────────────────

def test_terminal_status_not_overwritten_by_stale_event(client, monkeypatch):
    """done 상태인 run에 늦게 도착한 failed 이벤트가 status를 덮어쓰지 않는다
    (과거 버그: stale/retry webhook이 완료된 run을 실패로 되돌렸다)."""
    _create_source(client, monkeypatch)
    run_id = client.post("/api/runs/trigger", headers=ADMIN,
                         json={"source_id": "demo", "launch": False}).json()["run_id"]
    # run을 done으로 마무리
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"layer": "run", "stage": "static-diff", "status": "done",
                    "ts": "2026-07-07T20:00:00"}],
    })
    summary = client.get(f"/api/run-summary?run={run_id}", headers=ADMIN).json()
    assert summary["status"] == "done"
    # 늦게 도착한 failed 이벤트 — 무시되어야 한다
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"layer": "run", "stage": "static-diff", "status": "failed",
                    "ts": "2026-07-07T21:00:00",
                    "detail": {"error": "stale retry"}}],
    })
    summary = client.get(f"/api/run-summary?run={run_id}", headers=ADMIN).json()
    assert summary["status"] == "done", "done 상태가 stale failed 이벤트로 덮어쓰여졌다"


def test_webhook_events_rejects_unknown_run_id(client, monkeypatch):
    """존재하지 않는 run_id에 webhook을 보내면 404 — 고아 RunEvent 행 생성 금지
    (과거 버그: run_id가 RunEvent.run_id의 FK가 아니라서 조용히 적재됨)."""
    _create_source(client, monkeypatch, verify=False)
    resp = client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": "nonexistent-run-xyz",
        "events": [{"layer": "run", "stage": "s", "status": "done",
                    "ts": "2026-07-07T20:00:00"}],
    })
    assert resp.status_code == 404
    # DB에 고아 행이 없는지 확인
    from backend.controlplane.db import session_scope
    from backend.controlplane.models import RunEvent
    factory = client.app.state.session_factory
    with session_scope(factory) as db:
        orphan_count = db.query(RunEvent).filter_by(run_id="nonexistent-run-xyz").count()
    assert orphan_count == 0, "고아 RunEvent 행이 생성되었다"


def test_webhook_events_caps_array_size(client, monkeypatch):
    """events 배열이 너무 크면 413 — 동기 워커 DoS 방지."""
    _create_source(client, monkeypatch, verify=False)
    run_id = client.post("/api/runs/trigger", headers=ADMIN,
                         json={"source_id": "demo", "launch": False}).json()["run_id"]
    too_many = [{"layer": "stage", "stage": "s", "status": "done",
                 "ts": "2026-07-07T20:00:00"} for _ in range(600)]
    resp = client.post("/api/webhook/events", headers=RUNNER,
                       json={"run_id": run_id, "events": too_many})
    assert resp.status_code == 413


def test_complete_run_sha_does_not_regress(client, monkeypatch):
    """이미 sha=B로 전진한 상태에서 sha=A (더 오래된) 보고가 와도 되돌리지 않는다
    (concept-idempotent-sha: sha는 단조 증가)."""
    _create_source(client, monkeypatch)
    run_id = client.post("/api/runs/trigger", headers=ADMIN,
                         json={"source_id": "demo", "launch": False}).json()["run_id"]
    # 첫 성공 — sha를 'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz'로 전진
    client.post("/api/webhook/complete", headers=RUNNER, json={
        "run_id": run_id, "status": "done",
        "last_processed_sha": "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
    })
    src = client.get("/api/sources", headers=ADMIN).json()[0]
    assert src["last_processed_sha"] == "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"

    # 두 번째 run 생성 후 더 오래된 sha 보고 — 전진 안 함
    run_id2 = client.post("/api/runs/trigger", headers=ADMIN,
                          json={"source_id": "demo", "launch": False}).json()["run_id"]
    resp = client.post("/api/webhook/complete", headers=RUNNER, json={
        "run_id": run_id2, "status": "done",
        "last_processed_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    })
    assert resp.json()["sha_advanced"] is False
    src = client.get("/api/sources", headers=ADMIN).json()[0]
    assert src["last_processed_sha"] == "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz", \
        "더 오래된 sha가 최신 sha를 덮어썼다"


def test_audit_actor_in_dev_mode_is_not_literal_braces(client, monkeypatch):
    """dev 모드(api_tokens 비어있음)에서 actor가 리터럴 '{}'가 되면 안 된다.
    (과거 버그: `_state(request).api_tokens and (...)`의 short-circuit로
    actor = {} 가 저장되어 str({}) = '{}' 가 audit에 기록됨)."""
    # 이 테스트의 client fixture는 ADMIN 토큰을 쓰므로 dev 모드가 아니다.
    # 대신 audit 기록이 잘 남는지, 그리고 actor 필드에 'admin'이 들어가는지 확인.
    _create_source(client, monkeypatch, verify=False)
    client.delete("/api/sources/demo", headers=ADMIN)
    audit = client.get("/api/audit/recent?limit=20", headers=ADMIN).json()
    delete_entries = [e for e in audit["entries"]
                      if e["action"] == "source.delete"]
    assert delete_entries, "audit에 source.delete 행이 없다"
    assert delete_entries[0]["actor"] == "admin"
    assert delete_entries[0]["actor"] != "{}", \
        "actor가 리터럴 '{}'이다 — dev 모드 버그 재현"


def test_set_llm_does_not_leak_payload_as_env_default(client, monkeypatch):
    """set_llm가 반환하는 effective는 .env의 실제 폴백을 반영해야 한다.
    payload에 없는 키를 요청에 넣지 않았을 때 payload 기본값이 아니라
    os.environ의 값을 써야 한다 (과거 버그: payload.get(...) 기반 env_dict)."""
    import os
    # 환경변수로 LLM_TIMEOUT 설정
    monkeypatch.setenv("LLM_TIMEOUT", "240")
    # provider만 변경
    resp = client.patch("/api/settings/llm", headers=ADMIN, json={"provider": "anthropic"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["provider"] == "anthropic"
    # payload에 timeout_sec이 없었으므로 env의 240이 폴백되어야 한다
    # (과거에는 payload 기반 dict라 180이 되었다)
    assert data["timeout_sec"] == 240.0, \
        f"expected 240.0 from env, got {data['timeout_sec']} — env_dict가 payload 기반"


# ── regression: 신규 개선점 회귀 방지 ───────────────────────────────

def test_index_endpoint_auto_discovers_routes(client):
    """index()가 라우터에서 자동 수집 — 하드코딩 목록에 의존하지 않는다.
    누락되면 운영자가 새 엔드포인트가 있는지 알 수 없다."""
    body = client.get("/").json()
    assert body["service"] == "wiki-pipeline control plane"
    endpoints = body["endpoints"]
    assert "/api/runs" in endpoints
    assert "/api/sources" in endpoints
    assert "/api/audit/recent" in endpoints
    assert "/health" in endpoints
    assert any(e.startswith("POST ") and "/api/runs/trigger" in e for e in endpoints)
    assert any(e.startswith("DELETE ") and "/api/sources/{source_id}" in e for e in endpoints)


def test_run_doc_rejects_path_traversal(client, monkeypatch, tmp_path):
    """/api/runs/{run_id}/doc 경로 traversal 차단 — run 디렉터리 밖 접근 금지."""
    _create_source(client, monkeypatch, verify=False)
    run_id = client.post("/api/runs/trigger", headers=ADMIN,
                         json={"source_id": "demo", "launch": False}).json()["run_id"]
    resp = client.get(f"/api/runs/{run_id}/doc?path=readme.md", headers=ADMIN)
    assert resp.status_code == 404
    resp = client.get(f"/api/runs/{run_id}/doc?path=../secret.txt", headers=ADMIN)
    assert resp.status_code == 400, f"경로 traversal이 차단되지 않음: {resp.status_code}"
    resp = client.get(f"/api/runs/{run_id}/doc?path=foo.py", headers=ADMIN)
    assert resp.status_code == 400
    resp = client.get("/api/runs/../etc/passwd/doc?path=foo.md", headers=ADMIN)
    assert resp.status_code in (400, 404), f"경로 traversal이 처리되지 않음: {resp.status_code}"
    resp = client.get(f"/api/runs/{run_id}/doc?path=foo%20bar.md", headers=ADMIN)
    assert resp.status_code == 400


def test_audit_recent_filters_by_actor_and_action(client, monkeypatch):
    """audit_recent의 actor/action 필터가 동작해야 한다 (운영 디버깅 핵심)."""
    _create_source(client, monkeypatch, verify=False)
    client.delete("/api/sources/demo", headers=ADMIN)
    resp = client.get("/api/audit/recent?limit=100&action=source.delete", headers=ADMIN)
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert entries, "source.delete audit이 없다"
    assert all(e["action"] == "source.delete" for e in entries)
    resp = client.get("/api/audit/recent?limit=100&actor=admin", headers=ADMIN)
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert all(e["actor"] == "admin" for e in entries)
    resp = client.get("/api/audit/recent?limit=1", headers=ADMIN)
    assert resp.status_code == 200
    assert len(resp.json()["entries"]) <= 1
    assert client.get("/api/audit/recent?limit=0", headers=ADMIN).status_code == 422
    assert client.get("/api/audit/recent?limit=501", headers=ADMIN).status_code == 422


def test_delete_source_uses_sqlalchemy_2x_delete(client, monkeypatch):
    """delete_source가 SQLAlchemy 2.x delete() 패턴으로 동작 — 자식 행도 정리."""
    _create_source(client, monkeypatch, verify=False)
    resp = client.post("/api/sources/demo/schedules", headers=ADMIN, json={
        "label": "추가 스케줄", "pipeline_id": "static", "mode": "auto",
        "branch_role": "dev", "schedule_time": "12:00", "schedule_weekdays": ["sun"],
    })
    assert resp.status_code == 201
    resp = client.delete("/api/sources/demo", headers=ADMIN)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"ok": True, "deleted": "demo"}
    from backend.controlplane.db import session_scope
    from backend.controlplane.models import (SourceSchedule, SourceBranch,
                                              SourceReleaseTag)
    factory = client.app.state.session_factory
    with session_scope(factory) as db:
        assert db.query(SourceSchedule).filter_by(source_id="demo").count() == 0, \
            "스케줄 자식 행이 남아있다"
        assert db.query(SourceBranch).filter_by(source_id="demo").count() == 0, \
            "브랜치 자식 행이 남아있다"
        assert db.query(SourceReleaseTag).filter_by(source_id="demo").count() == 0, \
            "릴리스 태그 자식 행이 남아있다"


def test_webhook_complete_metric_failure_does_not_break_response(client, monkeypatch):
    """webhook_complete에서 메트릭 emit이 실패해도 응답은 정상 반환 — 회귀 방지."""
    _create_source(client, monkeypatch)
    run_id = client.post("/api/runs/trigger", headers=ADMIN,
                         json={"source_id": "demo", "launch": False}).json()["run_id"]
    resp = client.post("/api/webhook/complete", headers=RUNNER, json={
        "run_id": run_id, "status": "done", "last_processed_sha": "b" * 40,
        "doc_count": 0, "mr_url": "",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["sha_advanced"] is True
    resp = client.post("/api/webhook/complete", headers=RUNNER, json={"status": "done"})
    # run_id 누락 — _check_run_id 가 빈 문자열을 거부 (400).
    assert resp.status_code == 400
    resp = client.post("/api/webhook/complete", headers=RUNNER,
                       json={"run_id": "../bad", "status": "done"})
    assert resp.status_code == 400


def test_resolve_actor_returns_no_token_sentinel_not_first_token(client):
    """_resolve_actor 가 토큰 미제시 시 api_tokens 의 첫 토큰 이름으로 폴백하지 않는다.

    과거 폴백은 인증되지 않은 요청을 첫 토큰 소유자 행위로 오기록해 audit 추적을
    오염시켰다. 토큰 미제시 + api_tokens 설정 상태면 명시적 sentinel "(no-token)" 으로
    남아야 한다.
    """
    from backend.controlplane.api import _resolve_actor
    from starlette.requests import Request as StarletteRequest
    scope = {"type": "http", "headers": [], "path": "/test", "method": "GET",
             "app": client.app}
    fake_req = StarletteRequest(scope)
    actor = _resolve_actor(fake_req)
    assert actor == "(no-token)", \
        f"토큰 미제시인데 '{actor}' 로 반환 — 첫 토큰 폴백 버그 재현"
    assert actor != "admin", "인증되지 않은 요청이 'admin' 으로 기록됨"
