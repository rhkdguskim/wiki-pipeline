"""writer 에이전트 실행 패턴 — 수정모드 프롬프트 합성 + 그래프 1회 실행.

verified_generate의 write 콜러블이 두 파이프라인에서 같은 모양으로 반복되던 부분:
직전 형식-유효 문서(prev_doc)를 기반으로 한 핀포인트 수정 지시, 검증 피드백 블록,
도구 비활성화 안내를 base_prompt 뒤에 합성하고, 그래프를 돌려 정제된 문서를 얻는다.
재시도는 재작성이 아니라 **수정**이다 — 매번 처음부터 다시 쓰면 다른 곳에 새 오류가
생기는 두더지잡기가 된다 (원본 Docu-Automatic의 draft 핀포인트 수정 이식).
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage

from ..common.run import final_text, run_graph
from ..common.textproc import strip_reasoning

_EDIT_BLOCK = (
    "\n\n## 이전 문서 (수정 기반 — 아래 피드백 부분만 고치고 나머지는 그대로 유지하라)\n"
    "<<<DOC_BEGIN>>>\n{prev_doc}\n<<<DOC_END>>>\n"
    "위 문서에서 지적된 부분만 최소로 수정한 **전체 문서**를 다시 출력하라. "
    "지적되지 않은 문장·표·다이어그램은 바꾸지 마라."
)
_NO_TOOLS_BLOCK = (
    "\n\n## 이번 턴 제약\n도구가 비활성화됐다. 추가 탐색 없이 지금 가진 근거"
    "(요약·피드백)만으로 완전한 문서를 즉시 출력하라."
)


def compose_write_prompt(base_prompt: str, *, feedback: list[str],
                         prev_doc: str | None = None, no_tools: bool = False) -> str:
    """write/수정 프롬프트 합성 — verified_generate의 write 콜러블용 표준 조립."""
    prompt = base_prompt
    if prev_doc:
        prompt += _EDIT_BLOCK.format(prev_doc=prev_doc)
    if feedback:
        fb = "\n".join(f"  - {f}" for f in feedback)
        prompt += f"\n\n## 검증 피드백 (지적된 부분만 핀포인트 수정, 전면 재작성 금지)\n{fb}"
    if no_tools:
        prompt += _NO_TOOLS_BLOCK
    return prompt


def run_writer(graph, prompt: str, observer, *, recursion_limit: int = 25) -> str:
    """writer 그래프 1회 실행 -> 문서 마크다운(<think>·서문 제거) 반환."""
    final = run_graph(
        graph, {"messages": [HumanMessage(content=prompt)]},
        observer, config={"recursion_limit": recursion_limit},
    )
    return strip_reasoning(final_text(final))
