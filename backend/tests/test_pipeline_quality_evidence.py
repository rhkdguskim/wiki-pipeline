"""new endpoints + dedupe/seq/quality/heartbeat/reaper (2026-07-08).

기존 test_controlplane_api 의 fixture 패턴을 그대로 재사용 — tmp_path +
ControlPlaneSettings + TestClient.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import backend.controlplane.app as app_module
from backend.controlplane.db import session_scope
from backend.controlplane.models import (
    Base, ManualScenarioSet, Run, RunEvent, RunQualityReport,
    ScmInstance, Source, SourceBranch, SourceSchedule,
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
    engine = create_engine(settings.control_db_url.replace("sqlite:///", "sqlite:///"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        inst = ScmInstance(id="inst1", kind="gitlab", label="local",
                           base_url="https://gitlab.example.com", token="encrypted",
                           token_header="PRIVATE-TOKEN", enabled=True)
        src = Source(id="src1", instance_id="inst1", label="demo", repo="r",
                     themes="intro,architecture-overview",
                     doc_dir="r", schedule_cron="", enabled=True)
        br = SourceBranch(source_id="src1", role="dev", branch="main",
                          baseline_sha="", last_processed_sha="", enabled=True)
        sch = SourceSchedule(source_id="src1", label="default",
                             pipeline_id="static", mode="auto",
                             branch_role="dev", cron="", enabled=True)
        db.add_all([inst, src, br, sch])
        db.commit()
    app = app_module.create_app(settings)
    with TestClient(app) as c:
        c.app = app
        yield c


def _trigger_run(client, source_id="src1", pipeline_id="static"):
    r = client.post("/api/runs/trigger", headers=ADMIN,
                    json={"source_id": source_id, "mode": "auto",
                          "pipeline_id": pipeline_id, "launch": False})
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


def test_run_status_enum_extension(client):
    """run row 가 done_with_warnings / failed_quality_gate / partial / stale / timeout
    값을 수용하고 그대로 반환되는지 확인."""
    run_id = _trigger_run(client)
    # dummy event so run_summary DB path is taken (file-only path 는 404)
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"ts": "2026-07-08T10:00:00Z", "layer": "run",
                    "stage": "", "status": "running", "event_id": "evt-start"}],
    })
    statuses = ["done_with_warnings", "failed_quality_gate", "partial", "stale", "timeout"]
    for st in statuses:
        with session_scope(client.app.state.session_factory) as db:
            r = db.get(Run, run_id)
            r.status = st
            db.commit()
        rv = client.get(f"/api/run-summary?run={run_id}", headers=ADMIN)
        assert rv.status_code == 200
        assert rv.json()["status"] == st


def test_event_dedupe_by_event_id(client):
    """같은 (run_id, event_id) 재전송은 1건만 저장한다."""
    run_id = _trigger_run(client)
    body = {
        "run_id": run_id,
        "events": [
            {"ts": "2026-07-08T10:00:00Z", "layer": "stage", "stage": "compare",
             "status": "running", "event_id": "evt-A"},
            {"ts": "2026-07-08T10:00:01Z", "layer": "stage", "stage": "compare",
             "status": "done", "event_id": "evt-A"},
        ],
    }
    rv = client.post("/api/webhook/events", headers=RUNNER, json=body)
    assert rv.status_code == 200
    with session_scope(client.app.state.session_factory) as db:
        rows = db.scalars(select(RunEvent).where(RunEvent.run_id == run_id)).all()
        assert len(rows) == 1
        assert rows[0].event_id == "evt-A"
        assert rows[0].seq == 1


def test_event_seq_dedupe_conflict(client):
    """같은 (run_id, seq) 다른 payload 는 reject."""
    run_id = _trigger_run(client)
    body1 = {
        "run_id": run_id,
        "events": [
            {"ts": "2026-07-08T10:00:00Z", "layer": "stage", "stage": "compare",
             "status": "running", "event_id": "evt-A", "seq": 1},
        ],
    }
    body2 = {
        "run_id": run_id,
        "events": [
            {"ts": "2026-07-08T10:00:00Z", "layer": "stage", "stage": "compare",
             "status": "done", "event_id": "evt-B", "seq": 1},
        ],
    }
    rv1 = client.post("/api/webhook/events", headers=RUNNER, json=body1)
    assert rv1.status_code == 200
    rv2 = client.post("/api/webhook/events", headers=RUNNER, json=body2)
    assert rv2.status_code == 200
    with session_scope(client.app.state.session_factory) as db:
        rows = db.scalars(select(RunEvent).where(RunEvent.run_id == run_id)).all()
        assert len(rows) == 1


def test_seq_replay_api(client):
    """seq 기반 replay — afterSeq 이후의 event 만 반환한다."""
    run_id = _trigger_run(client)
    body = {
        "run_id": run_id,
        "events": [
            {"ts": "2026-07-08T10:00:00Z", "layer": "stage", "stage": "compare",
             "status": "running", "event_id": "evt-A"},
            {"ts": "2026-07-08T10:00:01Z", "layer": "stage", "stage": "compare",
             "status": "done", "event_id": "evt-B"},
        ],
    }
    client.post("/api/webhook/events", headers=RUNNER, json=body)
    rv = client.get(f"/api/runs/{run_id}/events?afterSeq=1&limit=10", headers=ADMIN)
    assert rv.status_code == 200
    data = rv.json()
    assert data["latest_seq"] >= 2
    assert data["run_id"] == run_id
    assert isinstance(data["events"], list)


def test_heartbeat_webhook(client):
    run_id = _trigger_run(client)
    body = {"run_id": run_id, "attempt": 1, "stage": "compare", "pid": "1234"}
    rv = client.post("/api/webhook/heartbeat", headers=RUNNER, json=body)
    assert rv.status_code == 200
    assert rv.json()["status"] == "running"
    with session_scope(client.app.state.session_factory) as db:
        r = db.get(Run, run_id)
        assert r.heartbeat_at is not None
        assert r.started_at is not None
        assert r.runner_pid == "1234"


def test_reap_stuck_runs(client):
    run_id = _trigger_run(client)
    with session_scope(client.app.state.session_factory) as db:
        r = db.get(Run, run_id)
        r.created_at = datetime.now(timezone.utc) - timedelta(seconds=7200)
        db.commit()
    rv = client.post("/api/internal/reap-stuck", headers=ADMIN)
    assert rv.status_code == 200
    assert rv.json()["reaped"] >= 1
    with session_scope(client.app.state.session_factory) as db:
        r = db.get(Run, run_id)
        assert r.status == "failed"
        assert r.terminal_at is not None


def test_quality_webhook_upsert_and_summary(client):
    run_id = _trigger_run(client)
    body = {
        "run_id": run_id,
        "status": "pass",
        "score": 91,
        "publishable": True,
        "failed_gate": "",
        "warning_count": 2,
        "error_count": 0,
        "repair_attempts": 1,
        "deterministic_verifier_status": "pass",
        "grounding_critic_status": "pass",
        "schema_status": "pass",
        "mermaid_status": "pass",
        "redaction_status": "pass",
        "gates": [{"name": "schema", "status": "pass"}],
        "findings": [
            {"doc_id": "intro", "gate": "grounding", "code": "minor_grammar",
             "severity": "warning", "blocking": False,
             "message": "minor grammar issue"},
        ],
    }
    rv = client.post("/api/webhook/quality", headers=RUNNER, json=body)
    assert rv.status_code == 200
    with session_scope(client.app.state.session_factory) as db:
        rep = db.scalars(select(RunQualityReport).where(
            RunQualityReport.run_id == run_id)).first()
        assert rep is not None
        assert rep.status == "pass"
        assert rep.score == 91
        run = db.get(Run, run_id)
        assert run.quality_status == "pass"
        assert run.publishable is True
        assert run.publish_state == "publishable"
    rv2 = client.get(f"/api/runs/{run_id}/quality", headers=ADMIN)
    assert rv2.status_code == 200
    data = rv2.json()
    assert data["quality"]["status"] == "pass"
    assert data["quality"]["score"] == 91
    assert len(data["findings"]) == 1
    assert data["findings"][0]["code"] == "minor_grammar"


def test_complete_run_normalizes_quality_fail(client):
    run_id = _trigger_run(client)
    body = {
        "run_id": run_id,
        "status": "done",
        "last_processed_sha": "abc",
        "doc_count": 1,
        "quality_status": "fail",
        "publishable": False,
        "failed_gate": "grounding",
        "blocked_reason": "grounding fail",
    }
    rv = client.post("/api/webhook/complete", headers=RUNNER, json=body)
    assert rv.status_code == 200
    with session_scope(client.app.state.session_factory) as db:
        r = db.get(Run, run_id)
        assert r.status == "failed_quality_gate"
        assert r.publishable is False
        assert r.publish_state == "blocked"
        assert "grounding" in (r.blocked_reason or "")


def test_complete_run_normalizes_warning(client):
    run_id = _trigger_run(client)
    # dummy event for run_summary DB path
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"ts": "2026-07-08T10:00:00Z", "layer": "run",
                    "stage": "", "status": "running", "event_id": "evt-start"}],
    })
    body = {
        "run_id": run_id,
        "status": "done",
        "last_processed_sha": "abc",
        "doc_count": 1,
        "quality_status": "warning",
        "publishable": True,
    }
    rv = client.post("/api/webhook/complete", headers=RUNNER, json=body)
    assert rv.status_code == 200
    rv2 = client.get(f"/api/run-summary?run={run_id}", headers=ADMIN)
    data = rv2.json()
    assert data["status"] == "done_with_warnings"
    assert data["publish_state"] == "review_required"


def test_complete_run_cas_stale(client):
    """pointer 가 snapshot 과 다르면 stale 로 normalize."""
    from backend.controlplane.models import Run
    # set source branch pointer BEFORE trigger so snapshot captures it
    with session_scope(client.app.state.session_factory) as db:
        br = db.scalars(select(SourceBranch).where(
            SourceBranch.source_id == "src1")).first()
        br.last_processed_sha = "snapshot-sha"
        db.commit()
    run_id = _trigger_run(client)
    # now change pointer between trigger and complete
    with session_scope(client.app.state.session_factory) as db:
        br = db.scalars(select(SourceBranch).where(
            SourceBranch.source_id == "src1")).first()
        br.last_processed_sha = "different-sha"
        db.commit()
    # dummy event for run_summary DB path
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"ts": "2026-07-08T10:00:00Z", "layer": "run",
                    "stage": "", "status": "running", "event_id": "evt-start"}],
    })
    body = {
        "run_id": run_id,
        "status": "done",
        "last_processed_sha": "new-sha",
        "from_sha": "old-sha",
        "doc_count": 1,
    }
    rv = client.post("/api/webhook/complete", headers=RUNNER, json=body)
    assert rv.status_code == 200
    rv2 = client.get(f"/api/run-summary?run={run_id}", headers=ADMIN)
    data = rv2.json()
    assert data["status"] == "stale"
    assert data["stale_complete"] is True
    assert data["publish_state"] == "blocked"


def test_evidence_webhook_and_get(client):
    run_id = _trigger_run(client)
    body = {
        "run_id": run_id,
        "pack_id": "evpack-test",
        "version_ref": "v1",
        "item_count": 2,
        "source_file_count": 2,
        "unsupported_claim_count": 0,
        "items": [
            {"id": "e1", "kind": "source_file", "title": "intro",
             "path": "backend/x.py", "line_start": 10, "line_end": 20,
             "content_preview": "print('hi')"},
            {"id": "e2", "kind": "observation", "title": "screen-info",
             "observation_id": "o1", "content_preview": "screen: main"},
        ],
    }
    rv = client.post("/api/webhook/evidence", headers=RUNNER, json=body)
    assert rv.status_code == 200
    rv2 = client.get(f"/api/runs/{run_id}/evidence", headers=ADMIN)
    data = rv2.json()
    assert data["pack_id"] == "evpack-test"
    assert data["item_count"] == 2
    assert len(data["items"]) == 2


def test_coverage_webhook_and_block_on_fail(client):
    run_id = _trigger_run(client)
    # dummy event for run_summary DB path
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"ts": "2026-07-08T10:00:00Z", "layer": "run",
                    "stage": "", "status": "running", "event_id": "evt-start"}],
    })
    body = {
        "run_id": run_id,
        "status": "fail",
        "percentage": 42.0,
        "threshold": 70.0,
        "reached": 8,
        "expected": 19,
        "missed_count": 11,
    }
    rv = client.post("/api/webhook/coverage", headers=RUNNER, json=body)
    assert rv.status_code == 200
    body2 = {
        "run_id": run_id,
        "status": "done",
        "last_processed_sha": "abc",
        "doc_count": 1,
    }
    rv2 = client.post("/api/webhook/complete", headers=RUNNER, json=body2)
    assert rv2.status_code == 200
    rv3 = client.get(f"/api/run-summary?run={run_id}", headers=ADMIN)
    data = rv3.json()
    assert data["status"] == "failed_quality_gate"
    assert data["coverage"]["percentage"] == 42.0
    assert "coverage" in (data["blocked_reason"] or "").lower()


def test_artifact_webhook(client):
    run_id = _trigger_run(client)
    body = {
        "run_id": run_id,
        "release_tag": "v1.8.0",
        "artifact_name": "app.msi",
        "artifact_sha256": "abc123",
        "build_status": "pass",
        "deploy_status": "pass",
        "install_status": "pass",
        "readiness_status": "pass",
        "smoke_status": "pass",
        "installed_version": "1.8.0",
    }
    rv = client.post("/api/webhook/artifact", headers=RUNNER, json=body)
    assert rv.status_code == 200
    rv2 = client.get(f"/api/runs/{run_id}/artifacts", headers=ADMIN)
    data = rv2.json()
    assert data["release_tag"] == "v1.8.0"
    assert data["installed_version"] == "1.8.0"
    assert data["smoke_status"] == "pass"


def test_vnc_webhook_view_only_default(client):
    run_id = _trigger_run(client)
    body = {
        "run_id": run_id,
        "session_id": "vnc-1",
        "status": "connected",
        "host_label": "manual-host-01",
        "host_port": 5901,
        "view_only": True,
    }
    rv = client.post("/api/webhook/vnc-session", headers=RUNNER, json=body)
    assert rv.status_code == 200
    rv2 = client.get(f"/api/runs/{run_id}/vnc-session", headers=ADMIN)
    data = rv2.json()
    assert data["available"] is True
    assert data["view_only"] is True
    assert data["websocket_url"] != ""


def test_vnc_view_only_false_blocks_websocket_url(client):
    run_id = _trigger_run(client)
    body = {
        "run_id": run_id,
        "session_id": "vnc-2",
        "status": "connected",
        "host_port": 5901,
        "view_only": False,
    }
    client.post("/api/webhook/vnc-session", headers=RUNNER, json=body)
    rv = client.get(f"/api/runs/{run_id}/vnc-session", headers=ADMIN)
    data = rv.json()
    assert data["view_only"] is False
    assert data["websocket_url"] == ""


def test_manual_profile_crud(client):
    body = {
        "enabled": True,
        "mcp_endpoint_url": "http://mcp:8765",
        "mcp_transport": "sse",
        "host_label": "manual-host-01",
        "host_ip": "10.0.0.12",
        "host_port": 8080,
        "vnc_enabled": True,
        "vnc_host": "10.0.0.12",
        "vnc_port": 5901,
        "vnc_gateway_policy": "view_only",
        "tool_allowlist": ["screenshot", "click"],
        "secret_refs": {"scm_token": "scm-token-ref"},
        "coverage_threshold": 80,
        "failure_policy": "block",
    }
    rv = client.put("/api/sources/src1/manual-profile", headers=ADMIN, json=body)
    assert rv.status_code == 200, rv.text
    data = rv.json()
    assert data["enabled"] is True
    assert data["tool_allowlist"] == ["screenshot", "click"]
    # secret_refs 는 reference 이름 (env var 이름 등) 만 보관 — 실제 secret 값 아님.
    # frontend 응답에는 ref name 이 그대로 노출되지만 raw secret 는 미저장/미노출.
    assert data["secret_refs"] == {"scm_token": "scm-token-ref"}
    # host_ip 는 masked (운영 정책 — secret value 노출 금지)
    assert "10.0.0.12" not in data["host_ip"]

    rv2 = client.get("/api/sources/src1/manual-profile", headers=ADMIN)
    assert rv2.status_code == 200
    data2 = rv2.json()
    assert data2["host_port"] == 8080


def test_manual_profile_preflight_errors(client):
    body = {"enabled": False, "mcp_endpoint_url": ""}
    client.put("/api/sources/src1/manual-profile", headers=ADMIN, json=body)
    rv = client.post("/api/sources/src1/manual-profile/preflight", headers=ADMIN)
    assert rv.status_code == 200
    data = rv.json()
    assert data["ok"] is False
    assert any("mcp_endpoint_url" in e or "비활성화" in e for e in data["errors"])


def test_scenario_lint_detects_raw_secret(client):
    body = {
        "scenarios": {
            "scenarios": [
                {"id": "login", "action": "click", "tool": "click",
                 "password": "supersecret"},
            ],
        },
    }
    rv = client.post("/api/sources/src1/scenarios/lint", headers=ADMIN, json=body)
    data = rv.json()
    assert data["ok"] is False
    codes = [e.get("code") for e in data["errors"]]
    assert "raw_secret_not_allowed" in codes


def test_scenario_crud_activate(client):
    body = {"name": "smoke", "version": 1, "status": "draft",
            "scenarios": {"scenarios": [{"id": "step1", "action": "click"}]}}
    rv = client.post("/api/sources/src1/scenarios", headers=ADMIN, json=body)
    assert rv.status_code == 200
    sid = rv.json()["id"]
    rv2 = client.post(f"/api/sources/src1/scenarios/{sid}/activate", headers=ADMIN)
    assert rv2.status_code == 200
    assert rv2.json()["status"] == "active"
    with session_scope(client.app.state.session_factory) as db:
        s = db.get(ManualScenarioSet, sid)
        assert s.status == "active"


def test_runner_context_includes_manual_profile(client):
    client.put("/api/sources/src1/manual-profile", headers=ADMIN,
               json={"enabled": True, "mcp_endpoint_url": "http://mcp:8765",
                     "tool_allowlist": ["screenshot", "click"],
                     "coverage_threshold": 80})
    rv = client.post("/api/sources/src1/scenarios", headers=ADMIN,
                     json={"name": "smoke", "version": 1, "status": "draft",
                           "scenarios": {"scenarios": [{"id": "step1"}]}})
    sid = rv.json()["id"]
    client.post(f"/api/sources/src1/scenarios/{sid}/activate", headers=ADMIN)
    r = client.post("/api/runs/trigger", headers=ADMIN,
                    json={"source_id": "src1", "mode": "auto",
                          "pipeline_id": "manual", "launch": False})
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    rv2 = client.get(f"/api/runner/context?run={run_id}", headers=RUNNER)
    assert rv2.status_code == 200
    data = rv2.json()
    assert data["manual_profile"]["mcp_endpoint_url"] == "http://mcp:8765"
    assert data["manual_profile"]["tool_allowlist"] == ["screenshot", "click"]
    assert data["scenario_set"]["id"] == sid
    assert data["output_contract"]["requires_evidence_pack"] is True
    assert data["output_contract"]["requires_coverage_report"] is True


def test_final_pack_webhook(client):
    run_id = _trigger_run(client)
    body = {
        "run_id": run_id,
        "evidence": {"pack_id": "evpack-final", "items": []},
        "quality": {"status": "pass", "score": 90, "publishable": True},
        "coverage": {"status": "pass", "percentage": 90.0, "threshold": 70.0,
                     "reached": 9, "expected": 10},
    }
    rv = client.post("/api/webhook/final-pack", headers=RUNNER, json=body)
    assert rv.status_code == 200
    assert rv.json()["partial"] is False
    assert "evidence" in rv.json()["items"]


def test_run_summary_augmented_with_quality_fields(client):
    run_id = _trigger_run(client)
    # dummy event for run_summary DB path
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"ts": "2026-07-08T10:00:00Z", "layer": "run",
                    "stage": "", "status": "running", "event_id": "evt-start"}],
    })
    client.post("/api/webhook/quality", headers=RUNNER,
                json={"run_id": run_id, "status": "pass", "score": 88,
                      "publishable": True})
    rv = client.get(f"/api/run-summary?run={run_id}", headers=ADMIN)
    data = rv.json()
    assert data["publishable"] is True
    assert data["publish_state"] == "publishable"
    assert data["quality"]["status"] == "pass"
    assert data["quality"]["score"] == 88
    assert "evidence" in data
    assert "coverage" in data
    assert "artifact" in data
    assert "vnc" in data
    assert "mr" in data
    assert data["snapshot_version"] >= 1


def test_quality_summary_endpoint(client):
    run_id = _trigger_run(client)
    client.post("/api/webhook/quality", headers=RUNNER,
                json={"run_id": run_id, "status": "pass", "score": 90,
                      "publishable": True})
    rv = client.get("/api/quality/summary?window=168", headers=ADMIN)
    assert rv.status_code == 200
    data = rv.json()
    assert data["total"] >= 1
    assert data["pass_count"] >= 1


def test_mr_plan_blocks_on_quality_fail(client):
    from backend.controlplane.models import Run
    run_id = _trigger_run(client)
    # pre-set mr_url to simulate post-submission state
    with session_scope(client.app.state.session_factory) as db:
        r = db.get(Run, run_id)
        r.mr_url = "https://gitlab.example.com/grp/hub/-/merge_requests/1"
        db.commit()
    # dummy event for run_summary DB path
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"ts": "2026-07-08T10:00:00Z", "layer": "run",
                    "stage": "", "status": "running", "event_id": "evt-start"}],
    })
    client.post("/api/webhook/quality", headers=RUNNER,
                json={"run_id": run_id, "status": "fail", "publishable": False,
                      "failed_gate": "grounding"})
    client.post("/api/webhook/complete", headers=RUNNER,
                json={"run_id": run_id, "status": "done",
                      "last_processed_sha": "abc", "doc_count": 1,
                      "quality_status": "fail", "publishable": False,
                      "failed_gate": "grounding"})
    # doc_target 직접 생성
    client.post("/api/docs-hub", headers=ADMIN, json={
        "id": "product-common", "label": "hub", "kind": "gitlab",
        "url": "http://gitlab.local/grp/hub",
        "project_id": "grp/hub", "project_path": "grp/hub",
        "token": "t", "default_branch": "master", "enabled": True,
    })
    rv = client.get(f"/api/docs-hub/mr-plan?run={run_id}&target=product-common",
                    headers=ADMIN)
    assert rv.status_code == 200, rv.text
    data = rv.json()
    assert data.get("readiness") == "blocked"
    assert "grounding" in (data.get("blocked_reason") or "")


def test_terminal_guard_idempotent(client):
    run_id = _trigger_run(client)
    # dummy event for run_summary DB path
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"ts": "2026-07-08T10:00:00Z", "layer": "run",
                    "stage": "", "status": "running", "event_id": "evt-start"}],
    })
    body1 = {"run_id": run_id, "status": "done", "last_processed_sha": "abc",
             "doc_count": 1}
    rv1 = client.post("/api/webhook/complete", headers=RUNNER, json=body1)
    assert rv1.status_code == 200
    body2 = {"run_id": run_id, "status": "failed", "error": "stale failed"}
    rv2 = client.post("/api/webhook/complete", headers=RUNNER, json=body2)
    assert rv2.status_code == 200
    assert rv2.json()["idempotent"] is True
    rv3 = client.get(f"/api/run-summary?run={run_id}", headers=ADMIN)
    assert rv3.json()["status"] == "done"


def test_mr_plan_quality_aware_doc_inclusion(client):
    """MR Plan 이 file-level quality-aware 인지 검증.

    raw/2026-07-08-backend-api-ai-pipeline-improvement-plan.md §10.1-10.2:
    - publishable doc만 기본 포함
    - failed quality doc → excluded
    - warning doc → review_required 표시
    - unsupported_claim > 0 → review checklist 추가
    """
    from backend.controlplane.models import Run, RunDocOutput
    run_id = _trigger_run(client)
    client.post("/api/docs-hub", headers=ADMIN, json={
        "id": "product-common", "label": "hub", "kind": "gitlab",
        "url": "http://gitlab.local/grp/hub", "project_id": "grp/hub",
        "project_path": "grp/hub", "token": "t", "default_branch": "master",
        "enabled": True,
    })
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"ts": "2026-07-08T10:00:00Z", "layer": "run",
                    "stage": "", "status": "running", "event_id": "evt-x"}],
    })

    def _mr_setup(sha: str = "abc") -> None:
        client.post("/api/webhook/quality", headers=RUNNER,
                     json={"run_id": run_id, "status": "pass",
                            "publishable": True})
        client.post("/api/webhook/complete", headers=RUNNER,
                     json={"run_id": run_id, "status": "done",
                            "last_processed_sha": sha, "doc_count": 3,
                            "mr_url": "https://gitlab.example.com/grp/hub/-/merge_requests/9"})
    _mr_setup()

    with client.app.state.session_factory() as db:
        db.add_all([
            RunDocOutput(run_id=run_id, path="docs/intro.md",
                         theme="intro", title="Intro",
                         action="create", quality_status="pass",
                         publishable=True, evidence_count=2,
                         mr_inclusion_status="candidate"),
            RunDocOutput(run_id=run_id, path="docs/setup.md",
                         theme="setup", title="Setup",
                         action="update", quality_status="fail",
                         publishable=False, evidence_count=1,
                         unsupported_claim_count=3,
                         mr_inclusion_status="candidate"),
            RunDocOutput(run_id=run_id, path="docs/deprecated.md",
                         theme="legacy", title="Legacy",
                         action="deprecate_candidate", quality_status="warning",
                         publishable=True, evidence_count=1,
                         warning_count=2,
                         mr_inclusion_status="deprecated_candidate"),
            RunDocOutput(run_id=run_id, path="docs/warn.md",
                         theme="guide", title="Guide",
                         action="update", quality_status="warning",
                         publishable=True, evidence_count=1,
                         unsupported_claim_count=1,
                         mr_inclusion_status="candidate"),
        ])
        db.commit()

    rv = client.get(f"/api/docs-hub/mr-plan?run={run_id}&target=product-common",
                     headers=ADMIN)
    assert rv.status_code == 200, rv.text
    data = rv.json()
    assert data["readiness"] == "ready"
    paths_in = {f["path"] for f in data["included_files"]}
    paths_out = {f["path"] for f in data["excluded_files"]}
    assert "docs/setup.md" in paths_out
    assert "docs/setup.md" not in paths_in
    assert "docs/intro.md" in paths_in
    assert "docs/deprecated.md" in paths_in
    assert "docs/warn.md" in paths_in
    assert data["needs_review"] is True
    combined_review = " ".join(data["review_checklist"])
    assert "unsupported_claim" in combined_review
    assert "deprecated 후보" in combined_review
    assert "quality=warning" in combined_review


def test_mr_plan_doc_outputs_excluded_when_run_readiness_blocked(client):
    """run readiness=blocked 이면 모든 doc 이 excluded — raw §10.1."""
    from backend.controlplane.models import Run, RunDocOutput
    run_id = _trigger_run(client)
    target_id = "product-common"
    client.post("/api/docs-hub", headers=ADMIN, json={
        "id": target_id, "label": "hub", "kind": "gitlab",
        "url": "http://gitlab.local/grp/hub", "project_id": "grp/hub",
        "project_path": "grp/hub", "token": "t", "default_branch": "master",
        "enabled": True,
    })
    client.post("/api/webhook/events", headers=RUNNER, json={
        "run_id": run_id,
        "events": [{"ts": "2026-07-08T10:00:00Z", "layer": "run",
                    "stage": "", "status": "running", "event_id": "evt-r"}],
    })
    client.post("/api/webhook/quality", headers=RUNNER,
                 json={"run_id": run_id, "status": "pass",
                        "publishable": True})
    client.post("/api/webhook/complete", headers=RUNNER,
                 json={"run_id": run_id, "status": "done",
                        "last_processed_sha": "abc", "doc_count": 1,
                        "mr_url": "https://gitlab.example.com/grp/hub/-/merge_requests/1"})
    with client.app.state.session_factory() as db:
        run = db.get(Run, run_id)
        run.status = "done"
        run.publishable = False
        run.publish_state = "blocked"
        run.blocked_reason = "coverage below threshold"
        db.add(RunDocOutput(run_id=run_id, path="docs/x.md", theme="t",
                             quality_status="pass", publishable=True,
                             mr_inclusion_status="candidate",
                             evidence_count=1))
        db.commit()

    rv = client.get(f"/api/docs-hub/mr-plan?run={run_id}&target={target_id}",
                     headers=ADMIN)
    assert rv.status_code == 200, rv.text
    data = rv.json()
    assert data["readiness"] == "blocked"
    paths = {f["path"] for f in data["included_files"]}
    assert "docs/x.md" not in paths
    excluded_x = next((f for f in data["excluded_files"] if f["path"] == "docs/x.md"), None)
    assert excluded_x is not None, f"excluded_files: {data['excluded_files']}"
    assert "blocked" in excluded_x["reason"].lower() or "publish_state" in excluded_x["reason"].lower()
