"""Regression tests for graph routing and deterministic repair behavior."""
from __future__ import annotations

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from backend.common.agent_spec import AgentSpec
from backend.common.graph import _summarize_ai, build_agent_graph
from backend.common_pipeline.verify import DOC_END_MARKER, verified_generate


def test_graph_never_executes_tool_call_after_turn_budget():
    calls = {"model": 0, "tool": 0}

    @tool
    def inspect_state() -> str:
        """Return a deterministic observation."""
        calls["tool"] += 1
        return "observed"

    class ScriptedModel:
        def bind_tools(self, _tools):
            return self

        def invoke(self, _messages):
            calls["model"] += 1
            return AIMessage(content="", tool_calls=[{
                "name": "inspect_state", "args": {},
                "id": f"call-{calls['model']}",
            }])

    graph = build_agent_graph(
        AgentSpec(
            pipeline_id="test", system_prompt="test", tools=[inspect_state],
            run_id="run-1", max_steps=1,
        ),
        ScriptedModel(),
    )
    graph.invoke({"messages": [HumanMessage(content="go")]},
                 config={"recursion_limit": 10})

    assert calls == {"model": 2, "tool": 1}


def test_agent_observability_never_exposes_response_or_reasoning_text():
    summary = _summarize_ai(AIMessage(content="<think>private reasoning</think> final document"))
    assert summary == "텍스트 응답을 생성함"


def test_deterministic_lint_failure_skips_critic_and_remains_gate_failure():
    writes = 0
    critic = MagicMock(return_value={"result": "pass"})
    doc = "---\ntheme: test\n---\n\n" + ("x" * 600) + "\n" + DOC_END_MARKER

    def write(_feedback, _no_tools, _previous):
        nonlocal writes
        writes += 1
        return doc

    result, verdict, warned = verified_generate(
        write=write,
        critic=critic,
        lint=lambda _doc: ["unknown evidence citation"],
        emit_ctx=lambda *_args, **_kwargs: None,
        stage="test",
        max_retry=1,
        end_marker=DOC_END_MARKER,
    )

    assert writes == 2
    assert critic.call_count == 0
    assert warned is True
    assert verdict["result"] == "fail"
    assert verdict["lint_errors"] == ["unknown evidence citation"]
    assert "auto_generated_warning" in result
