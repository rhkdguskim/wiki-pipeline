"""관측 이벤트 스키마 + emit 헬퍼.

decision-observability-event-contract(표준 스키마 + 가변 단위)와
decision-agent-step-observability(4단 계층: run > stage > engine_call > agent_step)를
그대로 구현한다. 노드는 emit()만 부르고, 수신·표시는 observer.py가 담당한다.
대시보드는 나중에 이 스키마(=계약)를 그대로 소비하도록 갈아끼우면 된다.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Literal, TypedDict

from langgraph.config import get_stream_writer

from .redaction import redact_data, redact_text

Layer = Literal["run", "stage", "engine_call", "agent_step"]
Status = Literal["running", "done", "failed"]

SCHEMA_VERSION = "progress.v1"


class ProgressEvent(TypedDict, total=False):
    schema: str            # "progress.v1" (계약 버전)
    pipeline_id: str       # "static" | "manual"
    run_id: str
    layer: str             # run | stage | engine_call | agent_step
    stage: str             # "compare" | "theme:architecture-overview" | "traversal" ...
    status: str            # running | done | failed
    progress: dict         # {"n": 3, "m": 4, "unit": "theme"}  ← 가변 단위
    ts: str                # ISO8601
    detail: dict           # 계층별 페이로드


def _now() -> str:
    # 스크립트 환경 제약(argless datetime 금지)이 없는 런타임이므로 표준 사용.
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def make_event(
    *,
    pipeline_id: str,
    run_id: str,
    layer: Layer,
    stage: str,
    status: Status = "running",
    progress: dict | None = None,
    detail: dict | None = None,
) -> ProgressEvent:
    return ProgressEvent(
        schema=SCHEMA_VERSION,
        pipeline_id=pipeline_id,
        run_id=run_id,
        layer=layer,
        stage=stage,
        status=status,
        progress=progress or {},
        ts=_now(),
        detail=detail or {},
    )


def emit(event: ProgressEvent) -> None:
    """LangGraph 노드 컨텍스트 안에서만 호출 — custom 스트림에 흘린다.

    노드 밖(결정적 러너)에서 부르면 get_stream_writer()가 없으므로,
    러너는 emit() 대신 observer를 직접 쓴다 (observer.sink 참조).
    """
    try:
        writer = get_stream_writer()
    except Exception:
        # 노드 컨텍스트가 아니면 조용히 무시 (러너 측 직접 sink 경로가 있음).
        return
    if writer is not None:
        writer(event)


# ── agent_step detail 빌더 (decision-agent-step-observability 매핑) ──

def feedback(title: str, body: str = "", severity: str = "info") -> dict:
    return {"title": title, "body": body or title, "severity": severity}


def thinking(summary: str) -> dict:
    summary = redact_text(summary)
    return {
        "kind": "thinking",
        "summary": summary,
        "feedback": feedback("Agent response", summary),
    }


def tool_use(tool: str, tool_input: Any) -> dict:
    return {
        "kind": "tool_use",
        "tool": tool,
        "input": redact_data(tool_input),
        "feedback": feedback("Tool call", f"{tool} 실행"),
    }


def tool_result(ok: bool, preview: str = "") -> dict:
    preview = redact_text(preview)
    return {
        "kind": "tool_result",
        "ok": ok,
        "preview": preview[:500],
        "feedback": feedback("Tool result", preview[:160], "info" if ok else "error"),
    }


def usage(input_tokens: int, output_tokens: int, **extra: Any) -> dict:
    total_tokens = input_tokens + output_tokens
    return {
        "kind": "usage",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "feedback": feedback("Token usage", f"in={input_tokens} out={output_tokens} total={total_tokens}"),
        **extra,
    }


def llm_retry(attempt: int, error: str = "") -> dict:
    return {
        "kind": "llm_retry",
        "attempt": attempt,
        "error": error,
        "feedback": feedback("LLM retry", f"attempt={attempt} {error}".strip(), "warning"),
    }
