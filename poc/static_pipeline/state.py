"""정적 파이프라인 에이전트 상태."""
from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class StaticState(TypedDict):
    messages: Annotated[list, add_messages]   # tool-use 루프 대화
    theme: str                                # 현재 테마
    changed_files: list[str]                  # compare 결과 (프롬프트 컨텍스트)
    from_sha: str
    to_sha: str
