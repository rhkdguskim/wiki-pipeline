"""매뉴얼 파이프라인 컴포넌트 테스트 — 시나리오 required 플래그, 도구 allowlist,
관측 secret redaction."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.manual_pipeline.observation import (
    ObservationLog,
    _redact,
    _redact_args,
)
from backend.manual_pipeline.scenarios import (
    Scenario,
    ScenarioSet,
    load_scenarios,
    scenarios_from_dict,
)
from backend.manual_pipeline.traversal import run_scenarios


# ── scenario required / continue_on_failure ──────────────────────


def test_scenarios_from_dict_parses_required_flag():
    data = {
        "app": "Test",
        "scenarios": [
            {"id": "s1", "title": "optional", "tool": "t"},
            {"id": "s2", "title": "required", "required": True,
             "continue_on_failure": False, "steps": [{"tool": "t"}]},
        ],
    }
    ss = scenarios_from_dict(data)
    assert len(ss.scenarios) == 2
    assert ss.scenarios[0].required is False
    assert ss.scenarios[0].continue_on_failure is True
    assert ss.scenarios[1].required is True
    assert ss.scenarios[1].continue_on_failure is False


def test_load_scenarios_parses_required_from_file(tmp_path):
    p = tmp_path / "sc.json"
    p.write_text(json.dumps({
        "app": "A",
        "scenarios": [
            {"id": "x", "title": "X", "required": True},
        ],
    }), encoding="utf-8")
    ss = load_scenarios(p)
    assert ss.scenarios[0].required is True


def test_required_scenario_failure_stops_traversal(tmp_path):
    """required=True 시나리오가 실패하면 즉시 중단하고 terminal_failure 를 기록."""
    bridge = MagicMock()
    bridge.call = MagicMock(side_effect=[
        (False, "error on step 1"),
        (True, "ok"),          # s2 step — should not be reached
    ])
    log = ObservationLog(tmp_path / "obs.jsonl")
    log.set_phase("test")

    rev = MagicMock()
    scenario_set = ScenarioSet(app="Test", scenarios=[
        Scenario(id="s1", title="required", required=True,
                 steps=[MagicMock(tool="t1", args={})]),
        Scenario(id="s2", title="after", steps=[MagicMock(tool="t2", args={})]),
    ])

    # Mock steps to have proper attributes
    from backend.manual_pipeline.scenarios import ScenarioStep
    scenario_set.scenarios[0].steps = [ScenarioStep(tool="t1")]
    scenario_set.scenarios[1].steps = [ScenarioStep(tool="t2")]

    result = run_scenarios(bridge, scenario_set, log, rev)

    assert "s1" in result["failed"]
    assert result["terminal_failure"] == "s1"
    # s2 should NOT have been attempted (terminal break)
    assert "s2" not in result["completed"]
    assert "s2" not in result["failed"]
    bridge.call.assert_called_once()  # only s1's step


def test_non_required_failure_continues(tmp_path):
    """required=False 시나리오가 실패해도 다음 시나리오를 계속 실행한다."""
    bridge = MagicMock()
    bridge.call = MagicMock(side_effect=[
        (False, "error"),  # s1 fails
        (True, "ok"),      # s2 succeeds
    ])
    log = ObservationLog(tmp_path / "obs.jsonl")
    log.set_phase("test")

    from backend.manual_pipeline.scenarios import ScenarioStep
    rev = MagicMock()
    scenario_set = ScenarioSet(app="Test", scenarios=[
        Scenario(id="s1", title="opt", required=False,
                 steps=[ScenarioStep(tool="t1")]),
        Scenario(id="s2", title="next",
                 steps=[ScenarioStep(tool="t2")]),
    ])

    result = run_scenarios(bridge, scenario_set, log, rev)

    assert "s1" in result["failed"]
    assert "s2" in result["completed"]
    assert result["terminal_failure"] == ""
    assert bridge.call.call_count == 2


def test_continue_on_failure_false_stops_within_scenario(tmp_path):
    """continue_on_failure=False 면 스텝 실패 시 해당 시나리오의 남은 스텝을 건너뛴다."""
    bridge = MagicMock()
    bridge.call = MagicMock(side_effect=[
        (False, "err on step 1"),  # s1 step1 fails → stop scenario
        (True, "ok"),              # s2 step1 succeeds
    ])
    log = ObservationLog(tmp_path / "obs.jsonl")
    log.set_phase("test")

    from backend.manual_pipeline.scenarios import ScenarioStep
    rev = MagicMock()
    scenario_set = ScenarioSet(app="Test", scenarios=[
        Scenario(id="s1", title="strict", required=False,
                 continue_on_failure=False,
                 steps=[ScenarioStep(tool="t1"), ScenarioStep(tool="t2")]),
        Scenario(id="s2", title="next",
                 steps=[ScenarioStep(tool="t3")]),
    ])

    result = run_scenarios(bridge, scenario_set, log, rev)

    assert "s1" in result["failed"]
    assert "s2" in result["completed"]
    # only 2 calls: s1 step1 (fail, stop) + s2 step1
    assert bridge.call.call_count == 2


# ── tool allowlist enforcement ───────────────────────────────────


def test_sync_tools_blocks_destructive_by_default():
    from backend.common.mcp_bridge import McpBridge
    from langchain_core.tools import BaseTool

    class FakeTool(BaseTool):
        name: str = ""
        description: str = ""

        def _run(self, **kwargs):
            return "ok"

    bridge = McpBridge.__new__(McpBridge)
    bridge._raw_tools = {
        "screen_info": FakeTool(name="screen_info"),
        "click_ui": FakeTool(name="click_ui"),
        "delete_file": FakeTool(name="delete_file"),
        "save_screenshot": FakeTool(name="save_screenshot"),
        "terminal_exec": FakeTool(name="terminal_exec"),
        "install_app": FakeTool(name="install_app"),
        "close_app": FakeTool(name="close_app"),
        "file_write": FakeTool(name="file_write"),
    }

    tools = bridge.sync_tools(allowlist=None)
    names = {t.name for t in tools}
    assert "screen_info" in names
    assert "click_ui" in names
    assert "delete_file" not in names
    assert "save_screenshot" not in names
    assert "terminal_exec" not in names
    assert "install_app" not in names
    assert "close_app" not in names
    assert "file_write" not in names


def test_sync_tools_allowlist_explicit_allows_destructive():
    from backend.common.mcp_bridge import McpBridge
    from langchain_core.tools import BaseTool

    class FakeTool(BaseTool):
        name: str = ""
        description: str = ""

        def _run(self, **kwargs):
            return "ok"

    bridge = McpBridge.__new__(McpBridge)
    bridge._raw_tools = {
        "screen_info": FakeTool(name="screen_info"),
        "delete_file": FakeTool(name="delete_file"),
    }

    tools = bridge.sync_tools(allowlist=["screen_info", "delete_file"])
    names = {t.name for t in tools}
    assert "delete_file" in names  # explicitly allowed


def test_sync_tools_strict_empty_allowlist_raises():
    from backend.common.mcp_bridge import McpBridge
    from langchain_core.tools import BaseTool

    class FakeTool(BaseTool):
        name: str = ""
        description: str = ""

        def _run(self, **kwargs):
            return "ok"

    bridge = McpBridge.__new__(McpBridge)
    bridge._raw_tools = {"screen_info": FakeTool(name="screen_info")}

    with pytest.raises(ValueError, match="allowlist"):
        bridge.sync_tools(allowlist=None, strict=True)


# ── observation secret redaction ─────────────────────────────────


def test_redact_masks_password():
    assert "***REDACTED***" in _redact("password=secret123")
    assert "secret123" not in _redact("password=secret123")


def test_redact_masks_token():
    result = _redact("token=abc-xyz-123")
    assert "abc-xyz-123" not in result
    assert "***REDACTED***" in result


def test_redact_masks_api_key():
    result = _redact("api_key=sk-1234567890")
    assert "sk-1234567890" not in result
    assert "***REDACTED***" in result


def test_redact_masks_authorization_bearer():
    result = _redact("Authorization: Bearer eyJhbGciOi")
    assert "eyJhbGciOi" not in result
    assert "***REDACTED***" in result


def test_redact_preserves_non_secret_text():
    assert _redact("hello world") == "hello world"
    assert _redact("") == ""


def test_redact_args_masks_credential_values():
    args = {"username": "admin", "password": "supersecret", "url": "http://x"}
    result = _redact_args(args)
    assert result["username"] == "admin"
    assert "supersecret" not in result["password"]
    assert result["url"] == "http://x"


def test_observation_record_redacts_secrets(tmp_path):
    log = ObservationLog(tmp_path / "obs.jsonl")
    log.set_phase("test")
    obs = log.record(
        tool="login",
        args={"password": "my-secret-pass", "user": "admin"},
        ok=True,
        preview="token=abc-123-xyz returned",
    )
    assert "my-secret-pass" not in json.dumps(obs.args)
    assert "***REDACTED***" in obs.args["password"]
    assert "abc-123-xyz" not in obs.preview
    assert "***REDACTED***" in obs.preview


def test_observation_jsonl_file_contains_redacted(tmp_path):
    p = tmp_path / "obs.jsonl"
    log = ObservationLog(p)
    log.set_phase("test")
    log.record(
        tool="auth",
        args={"api_key": "sk-real-key"},
        ok=True,
        preview="success",
    )
    log.close()
    content = p.read_text(encoding="utf-8")
    assert "sk-real-key" not in content
    assert "***REDACTED***" in content


def test_evidence_block_redacts_secrets(tmp_path):
    log = ObservationLog(tmp_path / "obs.jsonl")
    log.set_phase("scenario:s1")
    log.record(
        tool="login",
        args={"password": "secret-val"},
        ok=True,
        preview="token=returned-token",
    )
    block = log.evidence_block()
    assert "secret-val" not in block
    assert "returned-token" not in block
    assert "***REDACTED***" in block
