"""AgentSpec — 파이프라인이 공통 그래프 빌더에 넘기는 파라미터 묶음.

common/은 파이프라인을 모른다. 이 스펙(프롬프트+도구+상태스키마)만 받아 그래프를 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, TypedDict

from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """기본 에이전트 상태 — tool-use 루프는 messages만 읽고 쓴다 (두 파이프라인 공용)."""
    messages: Annotated[list, add_messages]


@dataclass
class AgentSpec:
    pipeline_id: str                        # "static" | "manual"
    system_prompt: str
    tools: list[BaseTool]                   # 파이프라인별 도구세트
    run_id: str
    stage: str = "agent"                    # 이벤트 stage 라벨 (engine_call 계층)
    max_steps: int = 12                     # tool-use 루프 폭주 방지
    state_schema: type = AgentState         # 특수 상태가 필요할 때만 교체
    checkpointer: BaseCheckpointSaver | None = None   # 매뉴얼 explorer만 주입
