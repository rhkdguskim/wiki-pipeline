"""정적 파이프라인 그래프 빌더 — writer(diff/init) + critic.

common.graph.build_agent_graph(tool-use 루프)를 재사용하고, AgentSpec만 갈아끼운다.
critic도 read_file 도구를 쥐고 grounding 검증을 하므로 같은 루프 구조를 쓴다.
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from ..common.agent_spec import AgentSpec
from ..common.graph import build_agent_graph
from .gitlab_client import GitLabClient
from .prompts import (
    critic_prompt,
    deep_writer_prompt,
    diff_writer_prompt,
    init_writer_prompt,
)
from .state import StaticState
from .tools import make_tools


def build_diff_writer_graph(
    *, model, client, theme, changed_files, from_sha, to_sha, run_id, max_steps=6,
):
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=diff_writer_prompt(theme, changed_files, from_sha, to_sha),
        tools=make_tools(client, ref=to_sha),
        state_schema=StaticState, run_id=run_id,
        stage=f"write:{theme}", max_steps=max_steps,
    )
    return build_agent_graph(spec, model)


def build_init_writer_graph(
    *, model, client, theme, unit, unit_files, ref, run_id, max_steps=6,
):
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=init_writer_prompt(theme, unit, unit_files, ref),
        tools=make_tools(client, ref=ref),
        state_schema=StaticState, run_id=run_id,
        stage=f"write:{unit}:{theme}", max_steps=max_steps,
    )
    return build_agent_graph(spec, model)


def build_deep_writer_graph(
    *, model, client, theme, unit, ref, summaries_block, source_files, run_id, max_steps=4,
):
    """deep init reduce 단계 writer — 하위 요약을 근거로 단위 문서 합성."""
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=deep_writer_prompt(theme, unit, ref, summaries_block, source_files),
        tools=make_tools(client, ref=ref),
        state_schema=StaticState, run_id=run_id,
        stage=f"reduce:{unit}:{theme}", max_steps=max_steps,
    )
    return build_agent_graph(spec, model)


def build_critic_graph(
    *, model, client, theme, doc_markdown, source_files_read, ref, run_id, stage, max_steps=5,
):
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=critic_prompt(theme, doc_markdown, source_files_read),
        tools=make_tools(client, ref=ref),
        state_schema=StaticState, run_id=run_id,
        stage=stage, max_steps=max_steps,
    )
    return build_agent_graph(spec, model)
