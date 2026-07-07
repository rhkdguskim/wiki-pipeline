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
from backend.connectors.base import ScmAuthError, ScmNotFoundError, ScmError
from backend.connectors.gitlab import GitLabConnector
from backend.runner.client import ControlPlaneClient, WebhookEventSink
from backend.runner import job

from .fake_scm import HEAD_SHA, OLD_SHA, FakeGitLab


class FakeControlPlane:
    """runner가 쓰는 3개 엔드포인트만 구현한 가짜 Control Plane."""

    def __init__(self, context: dict):
        self.context = context
        self.event_batches: list[list[dict]] = []
        self.completed: dict | None = None
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
