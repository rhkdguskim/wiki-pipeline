"""공통 실행 엔트리 — 그래프 stream(custom)을 소비해 observer로 흘리고 결과 반환.

`python -m poc.common.run --smoke` 로 LLM 1회 왕복 + custom 이벤트 방출을 검증한다 (L0).
"""
from __future__ import annotations

import argparse
import uuid
from typing import Any

from langchain_core.messages import HumanMessage

from . import events as ev
from .agent_spec import AgentSpec
from .config import load_settings
from .graph import build_agent_graph
from .llm import build_chat_model
from .observer import Observer


def run_graph(graph, initial_state: dict | None, observer: Observer, *,
              config: dict | None = None) -> dict:
    """그래프를 custom+values 스트림으로 실행. custom 이벤트는 observer로, 최종 상태는 반환."""
    final_state: dict[str, Any] = {}
    for mode, chunk in graph.stream(
        initial_state, config=config or {}, stream_mode=["custom", "values"]
    ):
        if mode == "custom":
            observer.sink(chunk)
        elif mode == "values":
            final_state = chunk
    return final_state


def final_text(final_state: dict) -> str:
    """그래프 최종 상태의 마지막 메시지 텍스트 (비문자열 콘텐츠 방어) — 공용 추출 경로."""
    messages = final_state.get("messages") or []
    if not messages:
        return ""
    last = messages[-1]
    return last.content if isinstance(last.content, str) else str(last.content)


def _smoke() -> int:
    """공통 런타임 스모크: 도구 없는 에이전트로 LLM 왕복 + 이벤트 방출 확인."""
    settings = load_settings()
    if not settings.llm_api_key:
        print("✗ LLM_API_KEY 가 .env 에 없습니다.")
        return 2

    run_id = "smoke-" + uuid.uuid4().hex[:8]
    observer = Observer(run_id, settings.out_path)
    observer.sink(ev.make_event(
        pipeline_id="smoke", run_id=run_id, layer="run",
        stage="smoke-test", status="running",
    ))

    model = build_chat_model(settings)

    spec = AgentSpec(
        pipeline_id="smoke",
        system_prompt="You are a terse assistant. Answer in one short sentence.",
        tools=[],
        run_id=run_id,
        stage="smoke",
    )
    graph = build_agent_graph(spec, model)

    try:
        final = run_graph(
            graph,
            {"messages": [HumanMessage(content="Reply with exactly: PoC runtime OK")]},
            observer,
        )
        text = final_text(final)
        observer.sink(ev.make_event(
            pipeline_id="smoke", run_id=run_id, layer="run",
            stage="smoke-test", status="done",
            detail={"reply": text[:200]},
        ))
        print(f"\n✓ LLM 응답: {text!r}")
        print(f"✓ 이벤트 로그: {observer.jsonl_path}")
        return 0
    except Exception as e:  # noqa: BLE001
        observer.sink(ev.make_event(
            pipeline_id="smoke", run_id=run_id, layer="run",
            stage="smoke-test", status="failed",
            detail={"error": f"{type(e).__name__}: {e}"},
        ))
        print(f"\n✗ 스모크 실패: {type(e).__name__}: {e}")
        return 1
    finally:
        observer.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="공통 런타임 실행")
    parser.add_argument("--smoke", action="store_true", help="LLM 왕복 + 이벤트 방출 스모크 테스트")
    args = parser.parse_args()
    if args.smoke:
        return _smoke()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
