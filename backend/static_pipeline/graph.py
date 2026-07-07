"""정적 파이프라인 그래프 빌더 — writer(diff/init) + critic.

common.graph.build_agent_graph(tool-use 루프)를 재사용하고, AgentSpec만 갈아끼운다.
critic도 read_file 도구를 쥐고 grounding 검증을 하므로 같은 루프 구조를 쓴다.
상태는 공용 AgentState(messages) — 정적 고유 상태 필드는 없다.
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from ..common.agent_spec import AgentSpec
from ..common.graph import build_agent_graph
from .gitlab_client import GitLabClient
from .prompts import (
    critic_prompt,
    diff_writer_prompt,
    init_writer_prompt,
    repo_writer_prompt,
)
from .tools import make_tools


def build_diff_writer_graph(
    *, model: BaseChatModel, client: GitLabClient, theme: str,
    changed_files: list[str], from_sha: str, to_sha: str, run_id: str,
    max_steps: int = 6, no_tools: bool = False,
):
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=diff_writer_prompt(theme, changed_files, from_sha, to_sha),
        tools=[] if no_tools else make_tools(client, ref=to_sha),
        run_id=run_id, stage=f"write:{theme}", max_steps=max_steps,
    )
    return build_agent_graph(spec, model)


def build_init_writer_graph(
    *, model: BaseChatModel, client: GitLabClient, theme: str,
    unit: str, unit_files: list[str], ref: str, run_id: str,
    max_steps: int = 6, no_tools: bool = False,
):
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=init_writer_prompt(theme, unit, unit_files, ref),
        tools=[] if no_tools else make_tools(client, ref=ref),
        run_id=run_id, stage=f"write:{unit}:{theme}", max_steps=max_steps,
    )
    return build_agent_graph(spec, model)


def build_repo_writer_graph(
    *, model: BaseChatModel, client: GitLabClient, theme: str,
    repo_name: str, ref: str, summaries_block: str, run_id: str,
    max_steps: int = 8, no_tools: bool = False,
):
    """init reduce 단계 writer — 단위 요약들을 근거로 레포 전체 테마 문서 합성.

    no_tools=True 면 도구를 아예 바인딩하지 않는다 — 모델이 도구 호출을 텍스트로
    유출(형식 실패)한 뒤의 재시도에서 요약만으로 합성을 강제하는 안전판.
    """
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=repo_writer_prompt(theme, repo_name, ref, summaries_block),
        tools=[] if no_tools else make_tools(client, ref=ref),
        run_id=run_id, stage=f"reduce:{theme}", max_steps=max_steps,
    )
    return build_agent_graph(spec, model)


def build_critic_graph(
    *, model: BaseChatModel, client: GitLabClient, theme: str,
    doc_markdown: str, source_files_read: list[str], ref: str,
    run_id: str, stage: str, max_steps: int = 5, no_tools: bool = False,
):
    """critic 그래프 — no_tools는 판정 마지막 라운드의 탐색 차단 안전판 (run_json_verdict)."""
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=critic_prompt(theme, doc_markdown, source_files_read),
        tools=[] if no_tools else make_tools(client, ref=ref),
        run_id=run_id, stage=stage, max_steps=max_steps,
    )
    return build_agent_graph(spec, model)
