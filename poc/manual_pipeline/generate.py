"""write -> 검증(critic) -> 재시도 (매뉴얼 어댑터).

재시도 정책·형식 검증·JSON 판정 회수는 common.verify 공용. 여기는 매뉴얼 고유 부분만 —
근거가 소스 코드가 아니라 관측 로그라 mermaid lint 없이 관측 grounding critic만 쓰고,
writer/critic 모두 도구 없음 (관측 로그는 불변 기록이라 재탐색이 필요 없다).
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage

from ..common.run import run_graph
from ..common.textproc import strip_reasoning
from ..common.verify import run_json_verdict, verified_generate
from .graph import build_critic_graph, build_manual_writer_graph


def _run_writer(graph, prompt: str, observer) -> str:
    final = run_graph(
        graph,
        {"messages": [HumanMessage(content=prompt)], "phase": "write"},
        observer, config={"recursion_limit": 12},
    )
    last = final["messages"][-1]
    text = last.content if isinstance(last.content, str) else str(last.content)
    return strip_reasoning(text)


def generate_manual_with_critic(
    *, model, theme_key, evidence, scenarios_block, coverage_block,
    run_id, run_ref, stage, observer, emit_ctx,
):
    """write -> 형식검증 -> critic(관측 grounding) -> 재시도. (doc, verdict, warned) 반환."""
    base_prompt = (
        f"'{theme_key}' 매뉴얼을 시스템 프롬프트의 관측 로그를 근거로 작성하라. "
        f"완성되면 frontmatter 포함 마크다운만 출력하라."
    )

    def write(feedback: list[str], _no_tools: bool, prev_doc: str | None = None) -> str:
        # writer는 애초에 도구가 없어 no_tools 플래그는 의미 없음 (형식 검증은 동일 적용).
        prompt = base_prompt
        if prev_doc:
            prompt += (
                "\n\n## 이전 문서 (수정 기반 — 피드백 부분만 고치고 나머지는 유지)\n"
                "<<<DOC_BEGIN>>>\n" + prev_doc + "\n<<<DOC_END>>>\n"
                "지적된 부분만 최소로 수정한 전체 문서를 다시 출력하라."
            )
        if feedback:
            fb = "\n".join(f"  - {f}" for f in feedback)
            prompt += f"\n\n## 검증 피드백 (지적된 부분만 핀포인트 수정, 전면 재작성 금지)\n{fb}"
        graph = build_manual_writer_graph(
            model=model, theme_key=theme_key, evidence_block=evidence,
            scenarios_block=scenarios_block, coverage_block=coverage_block,
            run_ref=run_ref, run_id=run_id,
        )
        return _run_writer(graph, prompt, observer)

    def critic(doc_md: str) -> dict:
        def factory():
            return build_critic_graph(
                model=model, theme_key=theme_key, doc_markdown=doc_md,
                evidence_block=evidence, run_id=run_id, stage=f"critic:{stage}",
            )

        ask = ("이 매뉴얼을 3단계로 검증하라. 최종 출력은 반드시 JSON 오브젝트 하나만 — "
               "그 외 텍스트·설명 금지.")
        return run_json_verdict(factory, ask, observer, recursion_limit=12,
                                extra_state={"phase": "critic"})

    return verified_generate(
        write=write, critic=critic, emit_ctx=emit_ctx, stage=stage, min_len=400,
    )
