"""매뉴얼 파이프라인 에이전트 상태."""
from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class ManualState(TypedDict, total=False):
    messages: Annotated[list, add_messages]   # tool-use 루프 대화
    phase: str                                # scenario | explore | write (관측 라벨)
