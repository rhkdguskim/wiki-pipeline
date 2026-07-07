"""정적 AgentSpec 조립 -> common.graph.build_agent_graph 호출."""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from ..common.agent_spec import AgentSpec
from ..common.graph import build_agent_graph
from .gitlab_client import GitLabClient
from .prompts import system_prompt
from .state import StaticState
from .tools import make_tools


def build_static_graph(
    *,
    model: BaseChatModel,
    client: GitLabClient,
    theme: str,
    changed_files: list[str],
    from_sha: str,
    to_sha: str,
    run_id: str,
    max_steps: int = 6,
):
    tools = make_tools(client, ref=to_sha)
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=system_prompt(theme, changed_files, from_sha, to_sha),
        tools=tools,
        state_schema=StaticState,
        run_id=run_id,
        stage=f"theme:{theme}",
        max_steps=max_steps,
    )
    return build_agent_graph(spec, model)
