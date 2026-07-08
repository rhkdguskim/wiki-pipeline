"""Manual artifact download/deploy + readiness/smoke (2026-07-08 review P0).

artifact.py 의 download_artifact / deploy_via_mcp / check_readiness / run_smoke
각 단계가 실패 시 status='fail' dict 를 반환하고, runner 가 generation 단계로
넘어가지 않게 하는 게 핵심 계약. MCP 브리지는 mock 으로 대체.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


def _make_fake_url(tmp_path: Path, name: str = "app.msi") -> tuple[Path, str, str]:
    src = tmp_path / "src" / name
    src.parent.mkdir(parents=True, exist_ok=True)
    body = b"installer-binary-content-v1.0.0-msi"
    src.write_bytes(body)
    sha = hashlib.sha256(body).hexdigest()
    return src, f"file://{src}", sha


def test_download_artifact_success(tmp_path):
    from backend.manual_pipeline.artifact import download_artifact
    src, url, expected = _make_fake_url(tmp_path)
    dest = tmp_path / "out" / "app.msi"
    result = download_artifact(url, dest, expected_sha256=expected)
    assert result["status"] == "pass"
    assert result["sha256"] == expected
    assert dest.read_bytes() == b"installer-binary-content-v1.0.0-msi"
    assert result["error"] == ""


def test_download_artifact_checksum_mismatch(tmp_path):
    from backend.manual_pipeline.artifact import download_artifact
    src, url, _ = _make_fake_url(tmp_path)
    dest = tmp_path / "out" / "app.msi"
    result = download_artifact(url, dest, expected_sha256="0" * 64)
    assert result["status"] == "fail"
    assert "checksum" in result["error"].lower() or "mismatch" in result["error"].lower()
    assert not dest.exists(), "download should be deleted on checksum fail"


def test_download_artifact_no_checksum(tmp_path):
    from backend.manual_pipeline.artifact import download_artifact
    src, url, _ = _make_fake_url(tmp_path)
    dest = tmp_path / "out" / "app.msi"
    result = download_artifact(url, dest)
    assert result["status"] == "pass"
    assert dest.exists()


def test_download_artifact_invalid_url(tmp_path):
    from backend.manual_pipeline.artifact import download_artifact
    dest = tmp_path / "out" / "app.msi"
    result = download_artifact("http://nonexistent.invalid.local/app.msi", dest)
    assert result["status"] == "fail"
    assert result["error"]


def test_deploy_via_mcp_calls_file_transfer_then_install():
    from backend.manual_pipeline.artifact import deploy_via_mcp

    class FakeBridge:
        def __init__(self):
            self.calls = []
        def call(self, name, args):
            self.calls.append((name, args))
            return True, "ok"

    bridge = FakeBridge()
    result = deploy_via_mcp(
        bridge,
        install_profile={"method": "file_transfer", "install_command": "msiexec /i app.msi /quiet"},
        artifact_path=Path("/tmp/app.msi"),
    )
    assert result["status"] == "pass", result.get("error")
    names_called = [c[0] for c in bridge.calls]
    assert any("file" in n.lower() or "transfer" in n.lower() or "upload" in n.lower() for n in names_called)


def test_deploy_via_mcp_failure_returns_fail():
    from backend.manual_pipeline.artifact import deploy_via_mcp

    class FailingBridge:
        def call(self, name, args):
            return False, "install failed: access denied"

    result = deploy_via_mcp(FailingBridge(),
                            install_profile={"install_command": "echo"},
                            artifact_path=Path("/tmp/app.msi"))
    assert result["status"] == "fail"
    assert "install" in result["error"].lower() or "fail" in result["error"].lower()


def test_check_readiness_returns_pass_when_app_running():
    from backend.manual_pipeline.artifact import check_readiness

    class ReadyBridge:
        def call(self, name, args):
            return True, "Main Window: DemoApp active"

    r = check_readiness(ReadyBridge(), readiness_check={"probe": "window_list"})
    assert r["status"] == "pass"


def test_check_readiness_returns_fail_on_timeout():
    from backend.manual_pipeline.artifact import check_readiness

    class FailingBridge:
        def call(self, name, args):
            return False, "timeout after 30s"

    r = check_readiness(FailingBridge(), readiness_check={"probe": "window_list"})
    assert r["status"] == "fail"


def test_run_smoke_passes_with_successful_call():
    from backend.manual_pipeline.artifact import run_smoke

    class SmokeBridge:
        def call(self, name, args):
            return True, "scenario login:smoke-test passed"

    r = run_smoke(SmokeBridge(), smoke_check={"tool": "run_scenario", "args": {"name": "login:smoke-test"}})
    assert r["status"] == "pass"


def test_run_smoke_returns_fail_on_failure():
    from backend.manual_pipeline.artifact import run_smoke

    class FailingBridge:
        def call(self, name, args):
            return False, "element not found"

    r = run_smoke(FailingBridge(), smoke_check={"tool": "run_scenario", "args": {"name": "login:smoke-test"}})
    assert r["status"] == "fail"
