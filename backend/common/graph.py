"""파라미터화된 tool-use 루프 그래프 빌더.

이 한 빌더가 두 파이프라인의 '판단 루프'를 만든다. 차이는 AgentSpec 뿐.
각 전이에서 agent_step 이벤트(thinking·tool_use·tool_result·usage)를 emit 한다
(decision-agent-step-observability). 결정적 오케스트레이션은 그래프 밖 러너가 소유.
"""
from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from . import events as ev
from .config import cached_settings
from .agent_spec import AgentSpec
from .llm_gate import llm_slot
from .retry import with_retry


def _summarize_ai(msg: AIMessage) -> str:
    """관측 UI에 보낼 안전한 판단 요약을 만든다.

    모델 응답 원문은 문서 본문 또는 provider별 reasoning 블록일 수 있다. 운영 UI에는
    원문 사고 과정을 내보내지 않고, 에이전트가 내린 도구 선택/응답 종류만 기록한다.
    """
    if msg.tool_calls:
        names = ", ".join(tc["name"] for tc in msg.tool_calls)
        return f"도구 사용을 결정: {names}"
    content = msg.content.strip() if isinstance(msg.content, str) else ""
    if not content:
        return "응답을 생성함"
    compact = content.lstrip()
    if compact.startswith("{") or compact.startswith("["):
        return "구조화된 검토 결과를 생성함"
    if compact.startswith("#") or "\n#" in compact or "```" in compact:
        return "문서 초안을 생성함"
    return "텍스트 응답을 생성함"


def _extract_usage(msg: AIMessage) -> tuple[int, int]:
    meta = getattr(msg, "usage_metadata", None) or {}
    if meta:
        return int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))
    response_meta = getattr(msg, "response_metadata", None) or {}
    token_usage = response_meta.get("token_usage") or response_meta.get("usage") or {}
    return (
        int(token_usage.get("input_tokens") or token_usage.get("prompt_tokens") or 0),
        int(token_usage.get("output_tokens") or token_usage.get("completion_tokens") or 0),
    )


def _response_model_name(msg: AIMessage, fallback: str) -> str:
    response_meta = getattr(msg, "response_metadata", None) or {}
    return str(response_meta.get("model_name") or response_meta.get("model") or fallback or "")


def build_agent_graph(spec: AgentSpec, model: BaseChatModel):
    """공통 tool-use 루프: agent ⇄ tools. 도구호출 없으면 END.

    max_steps: 에이전트 노드가 도구를 요청할 수 있는 최대 횟수. 초과하면 도구를
    바인딩하지 않은 모델로 마지막 1회 호출해 '지금까지 근거로 문서를 완성'하도록
    강제한다 (루프 폭주·무한 탐색 방지).
    """
    llm_with_tools = model.bind_tools(spec.tools) if spec.tools else model
    sys_msg = SystemMessage(content=spec.system_prompt)
    _FORCE = ("\n\n[시스템] 도구 호출 한도에 도달했다. 더는 도구를 쓰지 말고, "
              "지금까지 읽은 근거만으로 최종 문서를 즉시 완성해 출력하라. "
              "도구 호출을 텍스트로 흉내내지 마라(<tool_call> 등 금지) — 문서 본문만 출력한다.")

    def _count_tool_turns(messages: list) -> int:
        return sum(1 for m in messages if isinstance(m, AIMessage) and m.tool_calls)

    def _on_retry(attempt: int, exc: BaseException | None) -> None:
        ev.emit(ev.make_event(
            pipeline_id=spec.pipeline_id, run_id=spec.run_id,
            layer="agent_step", stage=spec.stage,
            detail=ev.llm_retry(attempt, f"{type(exc).__name__}" if exc else ""),
        ))

    def agent_node(state: dict) -> dict[str, Any]:
        messages = state["messages"]
        # 도구 호출 한도 초과 시: 도구 없는 모델 + 강제 지시로 마무리.
        over_budget = spec.tools and _count_tool_turns(messages) >= spec.max_steps
        if over_budget:
            _invoke = lambda: model.invoke(
                [SystemMessage(content=spec.system_prompt + _FORCE), *messages]
            )
        else:
            # 시스템 프롬프트를 매 호출 앞에 (Full Reset 성격 — 컨텍스트는 messages로만).
            _invoke = lambda: llm_with_tools.invoke([sys_msg, *messages])
        # 공급자 concurrency 한도(예: Z.AI=3) 강제: 실제 호출을 전역 게이트로 감싼다.
        # 게이트가 in-flight 호출 수를 눌러 담아 429 자체가 잘 안 나게 하고,
        # 재시도는 그래도 새는 일시 오류를 위한 2차 안전망으로 남는다.
        def call():
            with llm_slot():
                return _invoke()
        # APITimeoutError 등 일시 오류는 지수 백오프로 재시도 (공급자 무관).
        settings = cached_settings()
        resp: AIMessage = with_retry(call, attempts=settings.llm_retry_attempts, on_retry=_on_retry)

        ev.emit(ev.make_event(
            pipeline_id=spec.pipeline_id, run_id=spec.run_id,
            layer="agent_step", stage=spec.stage,
            detail=ev.thinking(_summarize_ai(resp)),
        ))
        in_tok, out_tok = _extract_usage(resp)
        if in_tok or out_tok:
            ev.emit(ev.make_event(
                pipeline_id=spec.pipeline_id, run_id=spec.run_id,
                layer="agent_step", stage=spec.stage,
                detail=ev.usage(
                    in_tok, out_tok,
                    provider=settings.llm_provider,
                    model=_response_model_name(resp, settings.llm_model),
                ),
            ))
        return {"messages": [resp]}

    # handle_tool_errors: 도구 예외(주로 모델의 인자 스키마 위반)를 raise 대신
    # ToolMessage(status="error")로 되돌린다 — 아래 ok 판정과 LLM 자가 정정이
    # 이 계약에 의존하므로 라이브러리 기본값에 맡기지 않고 명시한다.
    base_tool_node = ToolNode(spec.tools, handle_tool_errors=True) if spec.tools else None

    def observed_tools_node(state: dict) -> dict[str, Any]:
        # 마지막 AI 메시지의 tool_calls를 관측용으로 emit.
        last = state["messages"][-1]
        for tc in getattr(last, "tool_calls", []) or []:
            ev.emit(ev.make_event(
                pipeline_id=spec.pipeline_id, run_id=spec.run_id,
                layer="agent_step", stage=spec.stage,
                detail=ev.tool_use(tc["name"], tc.get("args", {})),
            ))
        result = base_tool_node.invoke(state)
        # 도구 결과 emit.
        for m in result.get("messages", []):
            if isinstance(m, ToolMessage):
                content = m.content if isinstance(m.content, str) else str(m.content)
                ev.emit(ev.make_event(
                    pipeline_id=spec.pipeline_id, run_id=spec.run_id,
                    layer="agent_step", stage=spec.stage,
                    detail=ev.tool_result(m.status != "error", content),
                ))
        return result

    def route_after_agent(state: dict) -> str:
        """Route tool calls only while the turn budget still permits execution."""
        last = state["messages"][-1]
        if not getattr(last, "tool_calls", None):
            return END
        # The forced final model call is intentionally tool-free. A provider can
        # nevertheless return a tool call, so enforce the cap in graph routing
        # instead of relying on the prompt or model binding alone.
        if _count_tool_turns(state["messages"]) > spec.max_steps:
            return END
        return "tools"

    builder = StateGraph(spec.state_schema)
    builder.add_node("agent", agent_node)
    builder.add_edge(START, "agent")

    if spec.tools:
        builder.add_node("tools", observed_tools_node)
        builder.add_conditional_edges("agent", route_after_agent, ["tools", END])
        builder.add_edge("tools", "agent")
    else:
        builder.add_edge("agent", END)

    return builder.compile(checkpointer=spec.checkpointer)
