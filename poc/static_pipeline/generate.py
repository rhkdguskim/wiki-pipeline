"""write -> 검증(mermaid lint + critic) -> 재시도 (정적 어댑터, diff/init 러너 공용).

재시도 정책·형식 검증·JSON 판정 회수는 common.verify로 이동했다. 여기는 정적 고유
부분만 남는다 — writer 그래프 실행(도구 유출 시 no_tools 재시도 프롬프트), mermaid lint,
frontmatter source_files 추출, 소스 대조 critic 그래프 구성.
"""
from __future__ import annotations

import re

from langchain_core.messages import HumanMessage

from ..common.run import run_graph
from ..common.textproc import strip_reasoning
from ..common.verify import run_json_verdict, verified_generate
from .graph import build_critic_graph
from .mermaid_lint import lint_mermaid

# StaticState 초기값 (그래프는 messages만 읽지만 스키마 계약 유지).
_STATE_EXTRA = {"theme": "", "changed_files": [], "from_sha": "", "to_sha": ""}


def _run_writer(writer_graph_factory, base_prompt, feedback, observer, *, no_tools=False):
    """writer 그래프 1회 실행 -> 문서 마크다운(<think>·서문 제거) 반환."""
    prompt = base_prompt
    if feedback:
        fb = "\n".join(f"  - {f}" for f in feedback)
        prompt += f"\n\n## 검증 피드백 (지적된 부분만 핀포인트 수정, 전면 재작성 금지)\n{fb}"
    if no_tools:
        prompt += ("\n\n## 이번 턴 제약\n도구가 비활성화됐다. 추가 탐색 없이 지금 가진 근거"
                   "(요약·피드백)만으로 완전한 문서를 즉시 출력하라.")
    graph = writer_graph_factory(no_tools=no_tools)
    final = run_graph(
        graph,
        {"messages": [HumanMessage(content=prompt)], **_STATE_EXTRA},
        observer, config={"recursion_limit": 25},
    )
    last = final["messages"][-1]
    text = last.content if isinstance(last.content, str) else str(last.content)
    return strip_reasoning(text)


def _extract_source_files(doc_md: str) -> list[str]:
    """문서 frontmatter의 source_files 목록 추출 (critic grounding 대상)."""
    m = re.search(r"source_files:\s*\[([^\]]*)\]", doc_md)
    if m:
        return [s.strip().strip('"\'') for s in m.group(1).split(",") if s.strip()]
    # YAML 리스트 형식 (- path) 도 지원
    m2 = re.search(r"source_files:\s*\n((?:\s*-\s*[^\n]+\n)+)", doc_md)
    if m2:
        return [ln.strip().lstrip("- ").strip() for ln in m2.group(1).splitlines() if ln.strip()]
    return []


def generate_with_critic(
    *, model, client, theme, ref, run_id, stage, writer_graph_factory,
    base_prompt, observer, emit_ctx,
):
    """write -> 형식검증 -> mermaid lint -> critic(grounding) -> 재시도.

    (doc, verdict, warned) 반환 — 루프 자체는 common.verify.verified_generate.
    """

    def write(feedback: list[str], no_tools: bool) -> str:
        return _run_writer(writer_graph_factory, base_prompt, feedback, observer,
                           no_tools=no_tools)

    def critic(doc_md: str) -> dict:
        src = _extract_source_files(doc_md)

        def factory():
            return build_critic_graph(
                model=model, client=client, theme=theme, doc_markdown=doc_md,
                source_files_read=src, ref=ref, run_id=run_id, stage=f"critic:{stage}",
            )

        ask = ("이 문서를 3단계로 검증하라. 최종 출력은 반드시 JSON 오브젝트 하나만 — "
               "그 외 텍스트·설명·도구 호출 흉내 금지.")
        return run_json_verdict(factory, ask, observer, extra_state=_STATE_EXTRA)

    return verified_generate(
        write=write, critic=critic, lint=lint_mermaid, lint_name="mermaid",
        emit_ctx=emit_ctx, stage=stage,
    )
