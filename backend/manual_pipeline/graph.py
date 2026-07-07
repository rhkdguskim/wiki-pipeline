"""매뉴얼 파이프라인 그래프 빌더 — explorer / writer / critic.

common.graph.build_agent_graph(tool-use 루프)를 재사용하고 AgentSpec만 갈아끼운다
(정적 graph.py와 같은 계약). explorer만 MCP 도구 + 체크포인터를 쥔다 —
writer/critic은 관측 로그(불변 기록)가 근거라 도구가 필요 없다.
상태는 공용 AgentState(messages) — 매뉴얼 고유 상태 필드는 없다.
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver

from ..common.agent_spec import AgentSpec
from ..common.graph import build_agent_graph
from .prompts import explorer_prompt, manual_critic_prompt, manual_writer_prompt


def build_explorer_graph(
    *, model: BaseChatModel, tools: list[BaseTool], run_id: str,
    app: str, max_steps: int, scenario_titles: list[str],
    checkpointer: BaseCheckpointSaver | None = None,
):
    """자율 탐색 그래프. checkpointer(SqliteSaver)로 중단 재개를 지원한다 (L4)."""
    spec = AgentSpec(
        pipeline_id="manual",
        system_prompt=explorer_prompt(app, max_steps, scenario_titles),
        tools=tools, run_id=run_id,
        stage="explore", max_steps=max_steps, checkpointer=checkpointer,
    )
    return build_agent_graph(spec, model)


def build_manual_writer_graph(
    *, model: BaseChatModel, theme_key: str, evidence_block: str,
    scenarios_block: str, coverage_block: str, run_ref: str, run_id: str,
):
    spec = AgentSpec(
        pipeline_id="manual",
        system_prompt=manual_writer_prompt(
            theme_key, evidence_block, scenarios_block, coverage_block, run_ref),
        tools=[], run_id=run_id,
        stage=f"write:{theme_key}",
    )
    return build_agent_graph(spec, model)


def build_critic_graph(
    *, model: BaseChatModel, theme_key: str, doc_markdown: str,
    evidence_block: str, run_id: str, stage: str,
):
    spec = AgentSpec(
        pipeline_id="manual",
        system_prompt=manual_critic_prompt(theme_key, doc_markdown, evidence_block),
        tools=[], run_id=run_id,
        stage=stage,
    )
    return build_agent_graph(spec, model)
