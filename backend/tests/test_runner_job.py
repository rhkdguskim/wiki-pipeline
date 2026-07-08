"""Data Plane 러너 테스트 — 가짜 Control Plane(MockTransport) 상대로 전체 잡 흐름 검증."""
from __future__ import annotations

import json
from urllib.parse import urlparse

import httpx
import pytest

import backend.connectors as connectors_pkg
import backend.static_pipeline.init_runner as init_runner_mod
import backend.static_pipeline.runner as static_runner_mod
from backend.common.config import Settings
from backend.connectors.base import ScmAuthError, ScmNotFoundError, ScmError, ScmRateLimitError
from backend.connectors.gitlab import GitLabConnector
from backend.runner.client import ControlPlaneClient, HeartbeatSender, WebhookEventSink
from backend.runner import job

from .fake_scm import HEAD_SHA, OLD_SHA, FakeGitLab


class FakeControlPlane:
    """runner가 쓰는 엔드포인트들을 구현한 가짜 Control Plane."""

    def __init__(self, context: dict):
        self.context = context
        self.event_batches: list[list[dict]] = []
        self.completed: dict | None = None
        self.heartbeats: list[dict] = []
        self.quality_reports: list[dict] = []
        self.evidence_packs: list[dict] = []
        self.coverage_reports: list[dict] = []
        self.artifact_reports: list[dict] = []
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = urlparse(str(request.url)).path
        if path == "/api/runner/context":
            return httpx.Response(200, json=self.context)
        if path == "/api/webhook/events":
            payload = json.loads(request.content.decode())
            self.event_batches.append(payload["events"])
            return httpx.Response(200, json={"ok": True, "ingested": len(payload["events"])})
        if path == "/api/webhook/complete":
            payload = json.loads(request.content.decode())
            self.completed = payload
            return httpx.Response(200, json={"ok": True, "status": payload.get("status"),
                                             "sha_advanced": bool(payload.get("last_processed_sha"))})
        if path == "/api/webhook/heartbeat":
            payload = json.loads(request.content.decode())
            self.heartbeats.append(payload)
            return httpx.Response(200, json={"ok": True})
        if path == "/api/webhook/quality":
            payload = json.loads(request.content.decode())
            self.quality_reports.append(payload)
            return httpx.Response(200, json={"ok": True})
        if path == "/api/webhook/evidence":
            payload = json.loads(request.content.decode())
            self.evidence_packs.append(payload)
            return httpx.Response(200, json={"ok": True})
        if path == "/api/webhook/coverage":
            payload = json.loads(request.content.decode())
            self.coverage_reports.append(payload)
            return httpx.Response(200, json={"ok": True})
        if path == "/api/webhook/artifact":
            payload = json.loads(request.content.decode())
            self.artifact_reports.append(payload)
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"error": path})


def _context(last_processed_sha: str = OLD_SHA, targets: list | None = None) -> dict:
    return {
        "run": {"run_id": "static-demo-12345678", "mode": "auto",
                "branch_role": "dev", "pipeline_id": "static"},
        "source": {"id": "demo", "label": "Demo", "kind": "gitlab",
                   "url": "http://gitlab.local", "repo": "grp/demo", "token": "t",
                   "token_header": "PRIVATE-TOKEN", "themes": "intro", "doc_dir": "grp/demo"},
        "branch": {"role": "dev", "branch": "main", "baseline_sha": "",
                   "last_processed_sha": last_processed_sha, "enabled": True},
        "doc_targets": targets if targets is not None else [{
            "id": "product-common", "label": "product-common", "kind": "gitlab",
            "url": "http://gitlab.local/grp/product-common",
            "project_id": "", "project_path": "grp/demo", "token": "t",
            "token_header": "PRIVATE-TOKEN", "default_branch": "main", "enabled": True,
        }],
    }


def test_decide_mode():
    assert job.decide_mode("auto", {"last_processed_sha": ""}) == "init"
    assert job.decide_mode("auto", {"last_processed_sha": OLD_SHA}) == "diff"
    assert job.decide_mode("init", {"last_processed_sha": OLD_SHA}) == "init"
    assert job.decide_mode("diff", {"last_processed_sha": ""}) == "diff"


def test_classify_error():
    assert job.classify_error(ScmNotFoundError("x")) == "not_found"
    assert job.classify_error(ScmAuthError("x")) == "auth"
    assert job.classify_error(ScmRateLimitError("x")) == "rate_limited"
    assert job.classify_error(ScmError("x")) == ""
    assert job.classify_error(RuntimeError("x")) == ""


def test_webhook_sink_batches_and_flushes():
    cp = FakeControlPlane(_context())
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    sink = WebhookEventSink(client, "run-1")
    for i in range(3):
        sink({"layer": "stage", "stage": f"s{i}", "status": "done"})
    sink.close()
    client.close()
    pushed = [e for batch in cp.event_batches for e in batch]
    assert len(pushed) == 3
    assert pushed[0]["stage"] == "s0"


@pytest.fixture()
def fake_submit_connector(monkeypatch):
    """docshub 제출이 쓰는 커넥터를 가짜 GitLab로 대체."""
    fake = FakeGitLab()

    def fake_connector_for_target(target, transport=None):
        return GitLabConnector(base_url="http://gitlab.local", token="t",
                               repo="grp/demo", retry_attempts=1,
                               transport=fake.transport)

    monkeypatch.setattr(connectors_pkg, "connector_for_target", fake_connector_for_target)
    return fake


def _patch_pipeline(monkeypatch, tmp_path, *, fail=False, calls: dict | None = None):
    """LLM 없이 도는 가짜 run_static/run_init — 문서 1건 생성 + sha 전진."""
    def fake_run_static(settings, from_sha, to_sha, themes=None, run_id=None):
        if calls is not None:
            calls["mode"] = "diff"
            calls["from_sha"] = from_sha
        if fail:
            raise ScmNotFoundError("compare 404")
        doc = settings.out_path / "intro.md"
        doc.write_text("# intro\n", encoding="utf-8")
        return {"run_id": run_id, "themes": {"intro": {"file": str(doc)}},
                "last_processed_sha": HEAD_SHA}

    def fake_run_init(settings, *, ref=None, themes=None, max_units=None,
                      reuse_summaries=False, run_id=None):
        if calls is not None:
            calls["mode"] = "init"
        doc = settings.out_path / "init" / "intro.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# intro\n", encoding="utf-8")
        return {"run_id": run_id, "docs": {"intro": {"file": str(doc)}},
                "last_processed_sha": HEAD_SHA}

    monkeypatch.setattr(static_runner_mod, "run_static", fake_run_static)
    monkeypatch.setattr(init_runner_mod, "run_init", fake_run_init)
    monkeypatch.setattr(job, "load_settings",
                        lambda: Settings(_env_file=None, out_dir=str(tmp_path)))


def test_execute_diff_submits_and_reports(monkeypatch, tmp_path, fake_submit_connector):
    calls: dict = {}
    _patch_pipeline(monkeypatch, tmp_path, calls=calls)
    cp = FakeControlPlane(_context(last_processed_sha=OLD_SHA))
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    result = job.execute("static-demo-12345678", "auto", client)
    client.close()

    assert calls["mode"] == "diff"
    assert calls["from_sha"] == OLD_SHA            # DB 포인터가 compare 시작점
    assert cp.completed["status"] == "done"
    assert cp.completed["last_processed_sha"] == HEAD_SHA
    assert cp.completed["doc_count"] == 1
    assert "merge_requests" in cp.completed["mr_url"]   # MR 제출 후 URL 보고
    assert result["sha_advanced"] is True
    # 제출된 MR이 가짜 GitLab에 존재
    assert len(fake_submit_connector.state.change_requests) == 1


def test_execute_auto_init_when_no_pointer(monkeypatch, tmp_path, fake_submit_connector):
    calls: dict = {}
    _patch_pipeline(monkeypatch, tmp_path, calls=calls)
    cp = FakeControlPlane(_context(last_processed_sha=""))
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("static-demo-12345678", "auto", client)
    client.close()
    assert calls["mode"] == "init"                  # decision-registration-baseline
    assert cp.completed["status"] == "done"


def test_execute_failure_reports_error_kind(monkeypatch, tmp_path):
    _patch_pipeline(monkeypatch, tmp_path, fail=True)
    cp = FakeControlPlane(_context())
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("static-demo-12345678", "auto", client)
    client.close()
    assert cp.completed["status"] == "failed"
    assert cp.completed["error_kind"] == "not_found"   # -> 소스 자동 비활성화 경로
    assert "last_processed_sha" not in cp.completed     # 실패는 sha를 건드리지 않는다


def test_execute_no_targets_still_advances(monkeypatch, tmp_path):
    _patch_pipeline(monkeypatch, tmp_path)
    cp = FakeControlPlane(_context(targets=[]))
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("static-demo-12345678", "auto", client)
    client.close()
    assert cp.completed["status"] == "done"
    assert cp.completed["mr_url"] == ""
    assert cp.completed["last_processed_sha"] == HEAD_SHA


# ── manual pipeline dispatch (Track A-2) ─────────────────────────

def _manual_context(*, last_processed_sha: str = "", targets: list | None = None) -> dict:
    ctx = _context(last_processed_sha=last_processed_sha, targets=targets)
    ctx["run"]["run_id"] = "manual-demo-abcdef01"
    ctx["run"]["pipeline_id"] = "manual"
    ctx["run"]["branch_role"] = "release"
    return ctx


def _patch_manual(monkeypatch, tmp_path, *, calls: dict | None = None,
                  fail: bool = False):
    """LLM 없이 도는 가짜 run_manual — themes 1건 생성, run_id 그대로 echo."""
    from backend.manual_pipeline.runner import run_manual as real_run_manual
    import backend.runner.job as job_mod

    def fake_run_manual(settings, *, run_id=None, scenarios_file=None,
                        themes=None, explore_steps=None, resume=False,
                        no_explore=False):
        if calls is not None:
            calls["run_id"] = run_id
            calls["themes_param"] = themes
        if fail:
            raise RuntimeError("manual pipeline simulated failure")
        # 매뉴얼 summary 는 out_dir/manual 하위에 저장. CP 의 out_path 와 일치시키자.
        manual_dir = settings.out_path / "manual"
        manual_dir.mkdir(parents=True, exist_ok=True)
        doc = manual_dir / "user-manual.md"
        doc.write_text("# user manual\n", encoding="utf-8")
        return {"run_id": run_id, "themes": {"user-manual": {"file": str(doc)}},
                "observations": 5, "warned": []}

    # manual_pipeline.runner 모듈의 run_manual 만 갈아끼우면 job 모듈이 직접
    # import 하는 run_manual 참조도 같이 바뀌는지 검증하기 위해 job 모듈에서도
    # 갈아끼운다 (job 모듈은 import 시점에 from ..manual_pipeline.runner 로 가져옴).
    monkeypatch.setattr("backend.manual_pipeline.runner.run_manual", fake_run_manual)
    monkeypatch.setattr("backend.runner.job._run_manual_pipeline",
                        lambda settings, ctx, *, run_id: fake_run_manual(settings, run_id=run_id))
    monkeypatch.setattr(job, "load_settings",
                        lambda: Settings(_env_file=None, out_dir=str(tmp_path),
                                         mcp_endpoint_url="http://mcp.local:9100"))


def test_manual_dispatch_runs_manual_pipeline(monkeypatch, tmp_path, fake_submit_connector):
    """pipeline_id='manual' → run_manual 호출, CP run_id 그대로 전달."""
    calls: dict = {}
    _patch_manual(monkeypatch, tmp_path, calls=calls)
    cp = FakeControlPlane(_manual_context())
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("manual-demo-abcdef01", "auto", client)
    client.close()

    assert calls["run_id"] == "manual-demo-abcdef01"
    assert cp.completed["status"] == "done"
    # 매뉴얼 파이프라인은 sha 포인터를 쓰지 않는다 (버전 포인터 별도 — PoC).
    assert cp.completed.get("last_processed_sha") in ("", None)
    # user-manual.md 가 매뉴얼 theme 으로 잡혀 MR 제출 대상이 됐는지
    assert cp.completed["doc_count"] >= 1
    assert "merge_requests" in cp.completed["mr_url"]


def test_manual_dispatch_fails_without_mcp_endpoint(monkeypatch, tmp_path):
    """MCP_ENDPOINT_URL 없으면 매뉴얼 실행은 명시적 ValueError."""
    from backend.manual_pipeline.runner import run_manual as real_run_manual
    import backend.runner.job as job_mod
    monkeypatch.setattr(job, "load_settings",
                        lambda: Settings(_env_file=None, out_dir=str(tmp_path),
                                         mcp_endpoint_url=""))
    cp = FakeControlPlane(_manual_context())
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("manual-demo-abcdef01", "auto", client)
    client.close()

    assert cp.completed["status"] == "failed"
    assert "MCP_ENDPOINT_URL" in cp.completed["error"]


def test_static_dispatch_unchanged_when_pipeline_static(monkeypatch, tmp_path, fake_submit_connector):
    """pipeline_id='static' (기본) → run_static 경로 그대로 (회귀 방지)."""
    calls: dict = {}
    _patch_pipeline(monkeypatch, tmp_path, calls=calls)
    cp = FakeControlPlane(_context(last_processed_sha=OLD_SHA))  # pipeline_id=static
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("static-demo-12345678", "auto", client)
    client.close()

    assert calls["mode"] == "diff"  # 정적 경로가 그대로 호출됐다
    assert cp.completed["status"] == "done"
    assert cp.completed["last_processed_sha"] == HEAD_SHA  # sha 전진도 정상


# ── heartbeat sending ──────────────────────────────────────────

def test_heartbeat_sent_during_execute(monkeypatch, tmp_path, fake_submit_connector):
    """execute() 중 heartbeat 가 전송된다."""
    _patch_pipeline(monkeypatch, tmp_path)
    cp = FakeControlPlane(_context(last_processed_sha=OLD_SHA))
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("static-demo-12345678", "auto", client)
    client.close()

    assert len(cp.heartbeats) >= 1
    hb = cp.heartbeats[0]
    assert hb["run_id"] == "static-demo-12345678"
    assert "pid" in hb
    assert "timestamp" in hb


def test_heartbeat_sender_start_stop():
    """HeartbeatSender 가 start 후 전송하고 stop 후 멈춘다."""
    cp = FakeControlPlane(_context())
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    hb = HeartbeatSender(client, "run-hb-test", interval=0.05)
    hb.start()
    import time
    time.sleep(0.15)
    hb.stop()
    client.close()
    assert len(cp.heartbeats) >= 1
    assert cp.heartbeats[0]["run_id"] == "run-hb-test"


# ── quality/evidence/coverage/artifact webhooks ─────────────────

def test_quality_evidence_webhooks_emitted_after_run(monkeypatch, tmp_path, fake_submit_connector):
    """파이프라인 실행 후 quality/evidence webhook 이 전송된다."""
    _patch_pipeline(monkeypatch, tmp_path)
    cp = FakeControlPlane(_context(last_processed_sha=OLD_SHA))
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("static-demo-12345678", "auto", client)
    client.close()

    assert len(cp.quality_reports) == 1
    assert cp.quality_reports[0]["run_id"] == "static-demo-12345678"
    assert cp.quality_reports[0]["status"] == "pass"

    assert len(cp.evidence_packs) == 1
    assert cp.evidence_packs[0]["run_id"] == "static-demo-12345678"
    assert cp.evidence_packs[0]["item_count"] >= 1


def test_quality_webhook_reports_failure_on_theme_error(monkeypatch, tmp_path):
    """theme 에 error 가 있으면 quality webhook status=fail."""
    def fake_run_static(settings, from_sha, to_sha, themes=None, run_id=None):
        doc = settings.out_path / "intro.md"
        doc.write_text("# intro\n", encoding="utf-8")
        return {"run_id": run_id,
                "themes": {"intro": {"file": str(doc), "error": "LLM timeout"}},
                "last_processed_sha": HEAD_SHA}

    monkeypatch.setattr(static_runner_mod, "run_static", fake_run_static)
    monkeypatch.setattr(init_runner_mod, "run_init", fake_run_static)
    monkeypatch.setattr(job, "load_settings",
                        lambda: Settings(_env_file=None, out_dir=str(tmp_path)))
    cp = FakeControlPlane(_context(last_processed_sha=OLD_SHA))
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("static-demo-12345678", "auto", client)
    client.close()

    assert cp.completed["status"] == "failed"
    assert len(cp.quality_reports) == 1
    assert cp.quality_reports[0]["status"] == "fail"


def test_coverage_artifact_webhooks_only_for_manual(monkeypatch, tmp_path, fake_submit_connector):
    """manual 파이프라인에서만 coverage/artifact webhook 이 전송된다."""
    calls: dict = {}
    _patch_manual(monkeypatch, tmp_path, calls=calls)
    cp = FakeControlPlane(_manual_context())
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("manual-demo-abcdef01", "auto", client)
    client.close()

    assert len(cp.coverage_reports) == 1
    assert len(cp.artifact_reports) == 1


def test_static_does_not_emit_coverage_artifact(monkeypatch, tmp_path, fake_submit_connector):
    """static 파이프라인에서는 coverage/artifact webhook 이 전송되지 않는다."""
    _patch_pipeline(monkeypatch, tmp_path)
    cp = FakeControlPlane(_context(last_processed_sha=OLD_SHA))
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("static-demo-12345678", "auto", client)
    client.close()

    assert len(cp.coverage_reports) == 0
    assert len(cp.artifact_reports) == 0


# ── manual profile from context ─────────────────────────────────

def _manual_context_with_profile(*, mcp_url="http://mcp.db:9100",
                                 tool_allowlist=None,
                                 scenarios=None) -> dict:
    ctx = _manual_context()
    ctx["manual_profile"] = {
        "mcp_endpoint_url": mcp_url,
        "mcp_transport": "sse",
        "tool_allowlist": tool_allowlist or ["screen_info", "screenshot"],
        "secret_values": {},
        "artifact_selector": {},
        "install_profile": {},
        "readiness_check": {},
        "smoke_check": {},
        "coverage_threshold": 70,
        "failure_policy": "block",
        "vnc": {"enabled": False, "host": "", "port": 0, "view_only": True},
    }
    if scenarios:
        ctx["scenario_set"] = {
            "id": "scset-test", "name": "test", "version": 1,
            "scenarios": scenarios,
        }
    return ctx


def test_manual_pipeline_uses_mcp_endpoint_from_context(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_run_manual(settings, *, run_id=None, scenarios_data=None,
                        scenarios_file=None, themes=None, explore_steps=None,
                        resume=False, no_explore=False, strict_allowlist=False):
        captured["mcp_endpoint_url"] = settings.mcp_endpoint_url
        captured["manual_allowlist"] = settings.manual_allowlist
        captured["strict"] = strict_allowlist
        captured["scenarios_data"] = scenarios_data
        manual_dir = settings.out_path / "manual"
        manual_dir.mkdir(parents=True, exist_ok=True)
        doc = manual_dir / "user-manual.md"
        doc.write_text("# user manual\n", encoding="utf-8")
        return {"run_id": run_id, "themes": {"user-manual": {"file": str(doc)}},
                "observations": 3, "warned": []}

    monkeypatch.setattr("backend.manual_pipeline.runner.run_manual", fake_run_manual)
    monkeypatch.setattr(job, "load_settings",
                        lambda: Settings(_env_file=None, out_dir=str(tmp_path),
                                         mcp_endpoint_url=""))

    scenarios_json = {"app": "Test", "scenarios": [{"id": "s1", "title": "t", "tool": "x"}]}
    cp = FakeControlPlane(_manual_context_with_profile(
        mcp_url="http://from-db:9999",
        tool_allowlist=["screen_info"],
        scenarios=scenarios_json))
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("manual-demo-abcdef01", "auto", client)
    client.close()

    assert captured["mcp_endpoint_url"] == "http://from-db:9999"
    assert "screen_info" in captured["manual_allowlist"]
    assert captured["strict"] is True
    assert captured["scenarios_data"] is not None


def test_manual_pipeline_falls_back_to_env_when_no_profile(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_run_manual(settings, *, run_id=None, scenarios_data=None,
                        scenarios_file=None, themes=None, explore_steps=None,
                        resume=False, no_explore=False, strict_allowlist=False):
        captured["mcp_endpoint_url"] = settings.mcp_endpoint_url
        captured["strict"] = strict_allowlist
        return {"run_id": run_id, "themes": {}, "observations": 0, "warned": []}

    monkeypatch.setattr("backend.manual_pipeline.runner.run_manual", fake_run_manual)
    monkeypatch.setattr(job, "load_settings",
                        lambda: Settings(_env_file=None, out_dir=str(tmp_path),
                                         mcp_endpoint_url="http://from-env:9100"))
    cp = FakeControlPlane(_manual_context())
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("manual-demo-abcdef01", "auto", client)
    client.close()

    assert captured["mcp_endpoint_url"] == "http://from-env:9100"
    assert captured["strict"] is False


# ── static partial failure status ────────────────────────────────

def test_static_partial_failure_reports_failed(monkeypatch, tmp_path):
    """theme 에 error 가 있으면 status=failed (done 아님)."""
    def fake_run_static(settings, from_sha, to_sha, themes=None, run_id=None):
        doc = settings.out_path / "intro.md"
        doc.write_text("# intro\n", encoding="utf-8")
        return {"run_id": run_id,
                "themes": {"intro": {"file": str(doc), "error": "critic reject"}},
                "last_processed_sha": HEAD_SHA}

    monkeypatch.setattr(static_runner_mod, "run_static", fake_run_static)
    monkeypatch.setattr(init_runner_mod, "run_init", fake_run_static)
    monkeypatch.setattr(job, "load_settings",
                        lambda: Settings(_env_file=None, out_dir=str(tmp_path)))
    cp = FakeControlPlane(_context(last_processed_sha=OLD_SHA))
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("static-demo-12345678", "auto", client)
    client.close()

    assert cp.completed["status"] == "failed"
    assert "critic reject" in cp.completed["error"]


def test_static_warned_reports_done_with_warnings(monkeypatch, tmp_path,
                                                   fake_submit_connector):
    """theme 에 warned 플래그가 있으면 status=done_with_warnings."""
    def fake_run_static(settings, from_sha, to_sha, themes=None, run_id=None):
        doc = settings.out_path / "intro.md"
        doc.write_text("# intro\n", encoding="utf-8")
        return {"run_id": run_id,
                "themes": {"intro": {"file": str(doc), "warned": True}},
                "last_processed_sha": HEAD_SHA, "warned": ["intro"]}

    monkeypatch.setattr(static_runner_mod, "run_static", fake_run_static)
    monkeypatch.setattr(init_runner_mod, "run_init", fake_run_static)
    monkeypatch.setattr(job, "load_settings",
                        lambda: Settings(_env_file=None, out_dir=str(tmp_path)))
    cp = FakeControlPlane(_context(last_processed_sha=OLD_SHA))
    client = ControlPlaneClient("http://cp.local", "rtok", transport=cp.transport)
    job.execute("static-demo-12345678", "auto", client)
    client.close()

    assert cp.completed["status"] == "done_with_warnings"
