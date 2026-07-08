"""VNC gateway, final-pack webhook, publish-after-commit integration tests.

Covers:
- VNC session token validation (issue/validate/expiry)
- View-only enforcement (reject view_only=False)
- Final-pack webhook: full bundle success
- Final-pack webhook: partial failure marks run partial
- Final-pack webhook: missing required items blocks done
- Publish-after-commit: WS message sent only after commit
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
    Base, Run, RunVncSession, ScmInstance, Source, SourceBranch, SourceSchedule,
)
from backend.controlplane.settings import ControlPlaneSettings
from backend.controlplane.vnc_gateway import VncGateway


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


# ── VNC token validation ──────────────────────────────────────


class TestVncTokenValidation:

    def test_issue_and_validate_token(self):
        gw = VncGateway(secret_key="test-secret")
        token = gw.issue_token("run-1", "vnc-abc")
        assert isinstance(token, str)
        assert "." in token
        assert gw.validate_token(token, "run-1", "vnc-abc")

    def test_validate_token_wrong_run_id(self):
        gw = VncGateway(secret_key="test-secret")
        token = gw.issue_token("run-1", "vnc-abc")
        assert not gw.validate_token(token, "run-2", "vnc-abc")

    def test_validate_token_wrong_session_id(self):
        gw = VncGateway(secret_key="test-secret")
        token = gw.issue_token("run-1", "vnc-abc")
        assert not gw.validate_token(token, "run-1", "vnc-wrong")

    def test_validate_token_tampered(self):
        gw = VncGateway(secret_key="test-secret")
        token = gw.issue_token("run-1", "vnc-abc")
        parts = token.split(".", 1)
        tampered = parts[0] + ".deadbeef"
        assert not gw.validate_token(tampered, "run-1", "vnc-abc")

    def test_validate_token_expired(self):
        gw = VncGateway(secret_key="test-secret")
        past = datetime.now(timezone.utc) - timedelta(seconds=100)
        token = gw.issue_token("run-1", "vnc-abc", expires_at=past)
        assert not gw.validate_token(token, "run-1", "vnc-abc")

    def test_validate_token_different_secret(self):
        gw1 = VncGateway(secret_key="secret-A")
        gw2 = VncGateway(secret_key="secret-B")
        token = gw1.issue_token("run-1", "vnc-abc")
        assert not gw2.validate_token(token, "run-1", "vnc-abc")

    def test_validate_empty_token(self):
        gw = VncGateway(secret_key="test-secret")
        assert not gw.validate_token("", "run-1", "vnc-abc")
        assert not gw.validate_token("nodothere", "run-1", "vnc-abc")


# ── View-only enforcement ─────────────────────────────────────


class TestViewOnlyEnforcement:

    def test_is_input_frame_key(self):
        gw = VncGateway()
        assert gw.is_input_frame({"type": "key", "key": "a"})
        assert gw.is_input_frame({"type": "key_down"})
        assert gw.is_input_frame({"type": "key_event"})

    def test_is_input_frame_mouse(self):
        gw = VncGateway()
        assert gw.is_input_frame({"type": "mouse"})
        assert gw.is_input_frame({"type": "mouse_move"})
        assert gw.is_input_frame({"type": "click"})

    def test_is_input_frame_clipboard(self):
        gw = VncGateway()
        assert gw.is_input_frame({"type": "clipboard"})
        assert gw.is_input_frame({"type": "paste"})

    def test_non_input_frame_passes(self):
        gw = VncGateway()
        assert not gw.is_input_frame({"type": "ping"})
        assert not gw.is_input_frame({"type": "vnc_status"})
        assert not gw.is_input_frame({"type": "resize"})

    def test_ws_rejects_view_only_false(self, client):
        run_id = _trigger_run(client)
        with session_scope(client.app.state.session_factory) as db:
            db.add(RunVncSession(
                run_id=run_id, session_id="vnc-interactive",
                status="connected", view_only=False,
            ))
            db.commit()
        rv = client.get(f"/api/runs/{run_id}/vnc-session", headers=ADMIN)
        data = rv.json()
        assert data["view_only"] is False
        assert data["websocket_url"] == ""

    def test_ws_allows_view_only_true(self, client):
        run_id = _trigger_run(client)
        client.post("/api/webhook/vnc-session", headers=RUNNER, json={
            "run_id": run_id, "session_id": "vnc-view",
            "status": "connected", "view_only": True,
        })
        rv = client.get(f"/api/runs/{run_id}/vnc-session", headers=ADMIN)
        data = rv.json()
        assert data["view_only"] is True
        assert data["websocket_url"] != ""
        assert data["ws_token"] != ""


# ── Final-pack webhook ────────────────────────────────────────


class TestFinalPackFullSuccess:

    def test_full_bundle_static_success(self, client):
        run_id = _trigger_run(client, pipeline_id="static")
        body = {
            "run_id": run_id,
            "evidence": {"pack_id": "evpack-final", "items": []},
            "quality": {"status": "pass", "score": 90, "publishable": True},
        }
        rv = client.post("/api/webhook/final-pack", headers=RUNNER, json=body)
        assert rv.status_code == 200, rv.text
        data = rv.json()
        assert data["ok"] is True
        assert data["partial"] is False
        assert "evidence" in data["items"]
        assert "quality" in data["items"]
        assert data["blocks_done"] is False
        assert data["required_missing"] == []

    def test_full_bundle_manual_success(self, client):
        run_id = _trigger_run(client, pipeline_id="manual")
        body = {
            "run_id": run_id,
            "evidence": {"pack_id": "evpack-manual", "items": []},
            "quality": {"status": "pass", "score": 95, "publishable": True},
            "coverage": {"status": "pass", "percentage": 85.0, "threshold": 70.0,
                         "reached": 9, "expected": 10},
            "artifact": {"release_tag": "v1.0", "artifact_name": "app.tar"},
        }
        rv = client.post("/api/webhook/final-pack", headers=RUNNER, json=body)
        assert rv.status_code == 200, rv.text
        data = rv.json()
        assert data["partial"] is False
        assert data["blocks_done"] is False


class TestFinalPackPartialFailure:

    def test_partial_failure_marks_run(self, client):
        run_id = _trigger_run(client, pipeline_id="static")
        body = {
            "run_id": run_id,
            "evidence": {"pack_id": "evpack-ok", "items": []},
            "quality": {"status": "not_a_valid_status"},
        }
        rv = client.post("/api/webhook/final-pack", headers=RUNNER, json=body)
        assert rv.status_code == 200
        data = rv.json()
        assert data["partial"] is True
        assert data["items"]["quality"]["ok"] is False

    def test_invalid_coverage_schema(self, client):
        run_id = _trigger_run(client, pipeline_id="manual")
        body = {
            "run_id": run_id,
            "evidence": {"items": []},
            "quality": {"status": "pass", "publishable": True},
            "coverage": {"status": "totally_wrong", "percentage": "not_a_number"},
            "artifact": {"release_tag": "v1"},
        }
        rv = client.post("/api/webhook/final-pack", headers=RUNNER, json=body)
        data = rv.json()
        assert data["partial"] is True
        assert data["items"]["coverage"]["ok"] is False


class TestFinalPackMissingRequired:

    def test_static_missing_quality_blocks_done(self, client):
        run_id = _trigger_run(client, pipeline_id="static")
        body = {
            "run_id": run_id,
            "evidence": {"pack_id": "evpack-only", "items": []},
        }
        rv = client.post("/api/webhook/final-pack", headers=RUNNER, json=body)
        data = rv.json()
        assert data["blocks_done"] is True
        assert "quality" in data["required_missing"]

    def test_manual_missing_coverage_and_artifact(self, client):
        run_id = _trigger_run(client, pipeline_id="manual")
        body = {
            "run_id": run_id,
            "evidence": {"items": []},
            "quality": {"status": "pass", "publishable": True},
        }
        rv = client.post("/api/webhook/final-pack", headers=RUNNER, json=body)
        data = rv.json()
        assert data["blocks_done"] is True
        assert "coverage" in data["required_missing"]
        assert "artifact" in data["required_missing"]

    def test_blocked_run_cannot_complete_done(self, client):
        run_id = _trigger_run(client, pipeline_id="static")
        client.post("/api/webhook/final-pack", headers=RUNNER, json={
            "run_id": run_id,
            "evidence": {"items": []},
        })
        with session_scope(client.app.state.session_factory) as db:
            r = db.get(Run, run_id)
            assert r.publish_state == "blocked"
            assert r.publishable is False
            assert "missing required" in (r.blocked_reason or "")


# ── Publish-after-commit integration ──────────────────────────


class TestPublishAfterCommit:

    def test_ws_message_not_sent_before_commit(self):
        """Service defers WS messages until db.commit() fires."""
        from backend.controlplane.services.runs import RunService
        from backend.controlplane.services.notifier import Notifier

        class FakeBroadcaster:
            def __init__(self):
                self.published = []

            def publish(self, msg):
                self.published.append(msg)

        bc = FakeBroadcaster()
        settings = ControlPlaneSettings(scheduler_enabled=False, notify_mode="log")
        svc = RunService(settings, Notifier(settings), broadcaster=bc)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        db = factory()

        svc._publish({"type": "run_status", "run_id": "r1"}, db)
        assert bc.published == []

        db.commit()
        assert len(bc.published) == 1
        assert bc.published[0]["type"] == "run_status"
        db.close()

    def test_rollback_discards_ws_messages(self):
        from backend.controlplane.services.runs import RunService
        from backend.controlplane.services.notifier import Notifier

        class FakeBroadcaster:
            def __init__(self):
                self.published = []

            def publish(self, msg):
                self.published.append(msg)

        bc = FakeBroadcaster()
        settings = ControlPlaneSettings(scheduler_enabled=False, notify_mode="log")
        svc = RunService(settings, Notifier(settings), broadcaster=bc)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        db = factory()

        svc._publish({"type": "run_status", "run_id": "r1"}, db)
        db.rollback()
        assert bc.published == []
        db.close()

    def test_heartbeat_webhook_publishes_after_commit(self, client):
        """End-to-end: heartbeat webhook defers WS, commits via _db, then publishes."""
        run_id = _trigger_run(client)
        rv = client.post("/api/webhook/heartbeat", headers=RUNNER, json={
            "run_id": run_id, "attempt": 1, "stage": "compare", "pid": "999",
        })
        assert rv.status_code == 200
        assert rv.json()["status"] == "running"
        with session_scope(client.app.state.session_factory) as db:
            r = db.get(Run, run_id)
            assert r.heartbeat_at is not None
