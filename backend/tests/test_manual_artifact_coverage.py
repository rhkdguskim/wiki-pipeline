"""매뉴얼 파이프라인 artifact + coverage 단위 테스트.

download_artifact checksum pass/fail, deploy_via_mcp 실패가 generation 을 차단하는지,
readiness check, coverage denominator building, coverage measurement + threshold 판정을
검증한다. MCP bridge 는 MagicMock 으로 대체해 LLM/MCP 없이 결정적 흐름만 본다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

from backend.manual_pipeline.artifact import (
    check_readiness,
    deploy_via_mcp,
    download_artifact,
    run_smoke,
)
from backend.manual_pipeline.coverage import (
    assess_coverage,
    build_denominator,
    measure_coverage,
)
from backend.manual_pipeline.scenarios import Scenario, ScenarioSet


# ── artifact download + checksum ─────────────────────────────────


def _write_file(tmp_path: Path, name: str, data: bytes) -> str:
    src = tmp_path / name
    src.write_bytes(data)
    return f"file://{src}"


def test_download_artifact_passes_with_matching_checksum(tmp_path):
    payload = b"installer-payload-v1"
    url = _write_file(tmp_path, "app.msi", payload)
    expected = hashlib.sha256(payload).hexdigest()
    dest = tmp_path / "out" / "app.msi"

    result = download_artifact(url, dest, expected)

    assert result["status"] == "pass"
    assert result["sha256"] == expected
    assert dest.read_bytes() == payload


def test_download_artifact_fails_on_checksum_mismatch(tmp_path):
    payload = b"installer-payload-v1"
    url = _write_file(tmp_path, "app.msi", payload)
    dest = tmp_path / "out" / "app.msi"

    result = download_artifact(url, dest, "0" * 64)

    assert result["status"] == "fail"
    assert "checksum mismatch" in result["error"]
    assert not dest.exists(), "checksum 불일치 시 다운로드 파일이 삭제돼야 함"


def test_download_artifact_no_checksum_still_passes(tmp_path):
    payload = b"no-checksum-payload"
    url = _write_file(tmp_path, "app.exe", payload)
    dest = tmp_path / "out" / "app.exe"

    result = download_artifact(url, dest)

    assert result["status"] == "pass"
    assert len(result["sha256"]) == 64


def test_download_artifact_reports_failure_on_bad_url(tmp_path):
    dest = tmp_path / "out" / "missing.msi"
    result = download_artifact("file:///nonexistent/path/missing.msi", dest)

    assert result["status"] == "fail"
    assert result["error"]


# ── deploy_via_mcp ───────────────────────────────────────────────


def _bridge_with_calls(calls: list[tuple[bool, str]]) -> MagicMock:
    bridge = MagicMock()
    bridge.call = MagicMock(side_effect=calls)
    return bridge


def test_deploy_via_mcp_success(tmp_path):
    artifact = tmp_path / "installer.msi"
    artifact.write_bytes(b"payload")
    bridge = _bridge_with_calls([
        (True, "transferred to C:\\Temp"),
        (True, "install exit code 0"),
        (True, "app launched"),
    ])
    profile = {
        "file_transfer_tool": "file_transfer",
        "remote_path": "C:\\Temp\\installer.msi",
        "exec_tool": "terminal_exec",
        "install_command": "msiexec /i {artifact} /quiet",
        "launch_command": "start myapp",
    }

    result = deploy_via_mcp(bridge, profile, artifact)

    assert result["status"] == "pass"
    assert result["deploy_detail"]
    assert result["install_detail"]
    assert result["launch_detail"]
    assert bridge.call.call_count == 3


def test_deploy_via_mcp_transfer_failure_blocks_generation(tmp_path):
    bridge = _bridge_with_calls([(False, "connection refused")])
    profile = {"file_transfer_tool": "file_transfer", "remote_path": "/tmp/x"}

    result = deploy_via_mcp(bridge, profile, tmp_path / "installer.msi")

    assert result["status"] == "fail"
    assert "file_transfer" in result["error"]
    bridge.call.assert_called_once()


def test_deploy_via_mcp_install_failure_blocks_generation(tmp_path):
    bridge = _bridge_with_calls([
        (True, "ok transfer"),
        (False, "install failed exit 1603"),
    ])
    profile = {"install_command": "msiexec /i {artifact}"}

    result = deploy_via_mcp(bridge, profile, tmp_path / "installer.msi")

    assert result["status"] == "fail"
    assert "install" in result["error"]
    assert bridge.call.call_count == 2


def test_deploy_via_mcp_without_install_command_only_transfers(tmp_path):
    bridge = _bridge_with_calls([(True, "transfer ok")])
    profile = {"file_transfer_tool": "file_transfer", "remote_path": "/tmp/x"}

    result = deploy_via_mcp(bridge, profile, tmp_path / "installer.msi")

    assert result["status"] == "pass"
    bridge.call.assert_called_once()


# ── readiness check ──────────────────────────────────────────────


def test_check_readiness_pass_when_pattern_found():
    bridge = _bridge_with_calls([(True, "Windows: MyApp Main Window")])
    result = check_readiness(bridge, {"tool": "window_list", "match_pattern": "MyApp"})
    assert result["status"] == "pass"


def test_check_readiness_fails_when_pattern_missing():
    bridge = _bridge_with_calls([(True, "Windows: Notepad")])
    result = check_readiness(bridge, {"tool": "window_list", "match_pattern": "MyApp"})
    assert result["status"] == "fail"
    assert "MyApp" in result["detail"]


def test_check_readiness_fails_on_tool_error():
    bridge = _bridge_with_calls([(False, "MCP timeout")])
    result = check_readiness(bridge, {"tool": "window_list"})
    assert result["status"] == "fail"


def test_check_readiness_defaults_to_window_list():
    bridge = _bridge_with_calls([(True, "ok")])
    check_readiness(bridge, {})
    bridge.call.assert_called_with("window_list", {})


# ── smoke check ──────────────────────────────────────────────────


def test_run_smoke_passes_all_steps():
    bridge = _bridge_with_calls([(True, "ok1"), (True, "ok2")])
    result = run_smoke(bridge, {"steps": [
        {"tool": "screen_info", "args": {}},
        {"tool": "screenshot", "args": {}},
    ]})
    assert result["status"] == "pass"


def test_run_smoke_fails_on_step_error():
    bridge = _bridge_with_calls([(True, "ok1"), (False, "timeout")])
    result = run_smoke(bridge, {"steps": [
        {"tool": "screen_info"},
        {"tool": "screenshot"},
    ]})
    assert result["status"] == "fail"


def test_run_smoke_single_tool_shorthand():
    bridge = _bridge_with_calls([(True, "ok")])
    result = run_smoke(bridge, {"tool": "screen_info", "args": {}})
    assert result["status"] == "pass"
    bridge.call.assert_called_once()


def test_run_smoke_skips_when_no_steps():
    bridge = MagicMock()
    result = run_smoke(bridge, {})
    assert result["status"] == "pass"
    bridge.call.assert_not_called()


# ── coverage denominator building ────────────────────────────────


def test_build_denominator_combines_scenarios_and_uia():
    scenario_set = ScenarioSet(app="Test", scenarios=[
        Scenario(id="login", title="Login Flow"),
        Scenario(id="settings", title="Open Settings"),
    ])
    uia_text = (
        "Name: Main Window\n"
        "Name: Settings Panel\n"
        'Window: "Help Dialog"\n'
    )
    bridge = _bridge_with_calls([(True, uia_text)])

    denom = build_denominator(bridge, scenario_set)

    assert denom["count"] >= 2
    assert "login" in denom["expected"]
    assert "settings" in denom["expected"]
    assert any("Main" in e or "Settings" in e or "Help" in e
               for e in denom["sources"]["uia"])


def test_build_denominator_handles_empty_uia_response():
    scenario_set = ScenarioSet(app="Test", scenarios=[
        Scenario(id="s1", title="T"),
    ])
    bridge = _bridge_with_calls([(True, ""), (True, "")])

    denom = build_denominator(bridge, scenario_set)

    assert "s1" in denom["expected"]
    assert denom["count"] >= 1


def test_build_denominator_falls_back_to_window_list():
    scenario_set = ScenarioSet(app="Test")
    window_text = "Window: MyApp\nWindow: Dialog\n"
    bridge = _bridge_with_calls([(True, ""), (True, window_text)])

    denom = build_denominator(bridge, scenario_set)

    assert any("MyApp" in e or "Dialog" in e for e in denom["sources"]["uia"])


# ── coverage measurement + threshold ─────────────────────────────


def test_measure_coverage_full_visit():
    denom = {"expected": ["login", "settings", "help"]}
    result = measure_coverage(["login", "settings", "help"], denom)
    assert result["percentage"] == 100.0
    assert result["missed_count"] == 0
    assert result["unreached"] == []


def test_measure_coverage_partial_visit():
    denom = {"expected": ["login", "settings", "help"]}
    result = measure_coverage(["login"], denom)
    assert result["percentage"] < 50.0
    assert result["missed_count"] == 2
    assert set(result["unreached"]) == {"settings", "help"}


def test_measure_coverage_empty_denominator_safe():
    result = measure_coverage(["a"], {"expected": []})
    assert result["percentage"] == 0.0
    assert result["expected_count"] == 0


def test_assess_coverage_pass_above_threshold():
    denom = {"expected": ["a", "b", "c", "d"], "sources": {"scenario_meta": []}}
    sc_result = {"completed": ["a", "b", "c"], "failed": []}
    explore = {"visited": ["d"]}

    assessment = assess_coverage(sc_result, explore, denom, threshold=70.0)

    assert assessment["status"] == "pass"
    assert assessment["percentage"] == 100.0
    assert assessment["missed_count"] == 0


def test_assess_coverage_warning_below_threshold():
    denom = {"expected": ["a", "b", "c", "d"], "sources": {"scenario_meta": []}}
    sc_result = {"completed": ["a"], "failed": []}
    explore = {"visited": []}

    assessment = assess_coverage(sc_result, explore, denom, threshold=70.0)

    assert assessment["status"] in ("warning", "fail")
    assert assessment["percentage"] < 70.0


def test_assess_coverage_fail_when_required_scenario_failed():
    denom = {
        "expected": ["login", "main"],
        "sources": {"scenario_meta": [
            {"id": "login", "title": "Login", "required": True},
        ]},
    }
    sc_result = {"completed": ["main"], "failed": ["login"]}
    explore = {"visited": []}

    assessment = assess_coverage(sc_result, explore, denom, threshold=70.0)

    assert assessment["status"] == "fail"
    assert assessment["scenario_required_failed"] is True


def test_assess_coverage_fail_when_very_low_percentage():
    denom = {"expected": ["a", "b", "c", "d", "e", "f", "g", "h"],
             "sources": {"scenario_meta": []}}
    sc_result = {"completed": ["a"], "failed": []}
    explore = {"visited": []}

    assessment = assess_coverage(sc_result, explore, denom, threshold=70.0)

    assert assessment["status"] == "fail"
    assert assessment["percentage"] < 35.0


# ── runner integration: artifact/deploy failure blocks generation ─


def _profile_with_artifact(url: str, sha256: str = "") -> dict:
    return {
        "artifact_selector": {"url": url, "sha256": sha256},
        "install_profile": {},
        "readiness_check": {},
        "smoke_check": {},
        "coverage_threshold": 70,
    }


def test_runner_artifact_checksum_failure_returns_without_generation(tmp_path,
                                                                     monkeypatch):
    from backend.manual_pipeline import runner as runner_mod

    payload = b"corrupted"
    src = tmp_path / "src.msi"
    src.write_bytes(payload)
    url = f"file://{src}"

    profile = _profile_with_artifact(url, sha256="0" * 64)

    def _noop(*a, **kw):
        return []

    monkeypatch.setattr(runner_mod, "build_chat_model",
                        lambda settings: MagicMock())
    monkeypatch.setattr(runner_mod, "generate_with_critic",
                        lambda **kw: ("", {"result": "fail"}, False))

    from backend.common.config import Settings
    settings = Settings(_env_file=None, out_dir=str(tmp_path),
                        mcp_endpoint_url="http://mcp:9100")
    summary = runner_mod.run_manual(settings, manual_profile=profile)

    assert "error" in summary
    assert "artifact" in summary["error"]
    assert summary["artifact"]["status"] == "fail"
    assert summary["themes"] == {}, "artifact 실패 시 매뉴얼이 생성돼선 안 됨"


def test_runner_deploy_failure_blocks_generation(tmp_path, monkeypatch):
    from backend.manual_pipeline import runner as runner_mod
    from backend.common.mcp_bridge import McpBridge

    payload = b"installer"
    src = tmp_path / "app.msi"
    src.write_bytes(payload)
    sha = hashlib.sha256(payload).hexdigest()
    url = f"file://{src}"

    profile = {
        "artifact_selector": {"url": url, "sha256": sha},
        "install_profile": {
            "file_transfer_tool": "file_transfer",
            "remote_path": "/tmp/app.msi",
            "exec_tool": "terminal_exec",
            "install_command": "msiexec /i {artifact}",
        },
        "readiness_check": {},
        "smoke_check": {},
    }

    fake_bridge = MagicMock(spec=McpBridge)
    fake_bridge.connect = MagicMock(return_value=["file_transfer", "terminal_exec"])
    fake_bridge.call = MagicMock(side_effect=[
        (False, "transfer failed — host unreachable"),
    ])
    fake_bridge.close = MagicMock()

    monkeypatch.setattr(runner_mod, "_bridge_for",
                        lambda *a, **kw: fake_bridge)

    from backend.common.config import Settings
    settings = Settings(_env_file=None, out_dir=str(tmp_path),
                        mcp_endpoint_url="http://mcp:9100")
    summary = runner_mod.run_manual(settings, manual_profile=profile)

    assert "error" in summary
    assert "deploy" in summary["error"]
    assert summary["deploy"]["status"] == "fail"
    assert summary["themes"] == {}


def test_runner_without_profile_skips_artifact_and_proceeds(tmp_path,
                                                            monkeypatch):
    """manual_profile=None 이면 artifact/deploy stage 를 skip 하고 traversal 로 진입.

    로컬 CLI fallback 경로 — 기존 동작(앱 이미 실행 중 가정)을 보존한다.
    관측이 0건이면 관측 부족으로 failed 되지만, artifact/deploy stage 는 통과한다.
    """
    from backend.manual_pipeline import runner as runner_mod
    from backend.common.mcp_bridge import McpBridge

    fake_bridge = MagicMock(spec=McpBridge)
    fake_bridge.connect = MagicMock(return_value=["screen_info"])
    fake_bridge.call = MagicMock(return_value=(True, "ok"))
    fake_bridge.close = MagicMock()
    monkeypatch.setattr(runner_mod, "_bridge_for",
                        lambda *a, **kw: fake_bridge)
    monkeypatch.setattr(runner_mod, "build_chat_model",
                        lambda settings: MagicMock())
    monkeypatch.setattr(runner_mod, "run_scenarios",
                        lambda *a, **kw: {"completed": [], "failed": [],
                                          "skipped": [], "steps": 0,
                                          "terminal_failure": ""})
    monkeypatch.setattr(runner_mod, "run_exploration",
                        lambda **kw: {"visited": [], "unreached": []})

    from backend.common.config import Settings
    settings = Settings(_env_file=None, out_dir=str(tmp_path),
                        mcp_endpoint_url="http://mcp:9100")
    summary = runner_mod.run_manual(settings, manual_profile=None)

    assert summary["artifact"]["status"] == "skip"
    assert summary["deploy"]["status"] == "skip"
