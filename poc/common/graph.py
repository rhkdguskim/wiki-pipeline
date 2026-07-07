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
from langgraph.prebuilt import ToolNode, tools_condition

from . import events as ev
from .agent_spec import AgentSpec


def _summarize_ai(msg: AIMessage) -> str:
    """AI 응답에서 사고/의도 요약을 뽑는다 (API가 원문 사고 전체를 안 주므로 요약 수준)."""
    if isinstance(msg.content, str) and msg.content.strip():
        return msg.content.strip()[:200]
    if msg.tool_calls:
        names = ", ".join(tc["name"] for tc in msg.tool_calls)
        return f"(도구 호출 결정: {names})"
    return "(응답)"


def _extract_usage(msg: AIMessage) -> tuple[int, int]:
    meta = getattr(msg, "usage_metadata", None) or {}
    return int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))


def build_agent_graph(spec: AgentSpec, model: BaseChatModel):
    """공통 tool-use 루프: agent ⇄ tools. 도구호출 없으면 END.

    max_steps: 에이전트 노드가 도구를 요청할 수 있는 최대 횟수. 초과하면 도구를
    바인딩하지 않은 모델로 마지막 1회 호출해 '지금까지 근거로 문서를 완성'하도록
    강제한다 (루프 폭주·무한 탐색 방지).
    """
    llm_with_tools = model.bind_tools(spec.tools) if spec.tools else model
    sys_msg = SystemMessage(content=spec.system_prompt)
    _FORCE = ("\n\n[시스템] 도구 호출 한도에 도달했다. 더는 도구를 쓰지 말고, "
              "지금까지 읽은 근거만으로 최종 문서를 즉시 완성해 출력하라.")

    def _count_tool_turns(messages: list) -> int:
        return sum(1 for m in messages if isinstance(m, AIMessage) and m.tool_calls)

    def agent_node(state: dict) -> dict[str, Any]:
        messages = state["messages"]
        # 도구 호출 한도 초과 시: 도구 없는 모델 + 강제 지시로 마무리.
        over_budget = spec.tools and _count_tool_turns(messages) >= spec.max_steps
        if over_budget:
            resp: AIMessage = model.invoke(
                [SystemMessage(content=spec.system_prompt + _FORCE), *messages]
            )
        else:
            # 시스템 프롬프트를 매 호출 앞에 (Full Reset 성격 — 컨텍스트는 messages로만).
            resp = llm_with_tools.invoke([sys_msg, *messages])

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
                detail=ev.usage(in_tok, out_tok),
            ))
        return {"messages": [resp]}

    base_tool_node = ToolNode(spec.tools) if spec.tools else None

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

    builder = StateGraph(spec.state_schema)
    builder.add_node("agent", agent_node)
    builder.add_edge(START, "agent")

    if spec.tools:
        builder.add_node("tools", observed_tools_node)
        builder.add_conditional_edges("agent", tools_condition)
        builder.add_edge("tools", "agent")
    else:
        builder.add_edge("agent", END)

    return builder.compile(checkpointer=spec.checkpointer)
