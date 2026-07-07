"""AgentSpec — 파이프라인이 공통 그래프 빌더에 넘기는 파라미터 묶음.

common/은 파이프라인을 모른다. 이 스펙(프롬프트+도구+상태스키마)만 받아 그래프를 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver


@dataclass
class AgentSpec:
    pipeline_id: str                        # "static" | "manual"
    system_prompt: str
    tools: list[BaseTool]                   # 파이프라인별 도구세트
    state_schema: type                      # StaticState | ManualState (TypedDict)
    run_id: str
    stage: str = "agent"                    # 이벤트 stage 라벨 (engine_call 계층)
    max_steps: int = 12                     # tool-use 루프 폭주 방지
    checkpointer: BaseCheckpointSaver | None = None   # 매뉴얼만 주입
    extra: dict[str, Any] = field(default_factory=dict)
