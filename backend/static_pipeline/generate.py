"""write -> 검증(mermaid lint + critic) -> 재시도 (정적 어댑터, diff/init 러너 공용).

재시도 루프·형식검증·수정모드 프롬프트 합성·JSON 판정 회수는 common_pipeline 공용
(verify·writer). 여기는 정적 고유 부분만 남는다 — mermaid lint, frontmatter
source_files 추출, 소스 대조 critic 그래프 구성.
"""
from __future__ import annotations

import re

from ..common_pipeline.verify import DOC_END_MARKER, run_json_verdict, verified_generate
from ..common_pipeline.writer import compose_write_prompt, run_writer
from .graph import build_critic_graph
from .mermaid_lint import lint_mermaid, sanitize_mermaid


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

    (doc, verdict, warned) 반환 — 루프는 common_pipeline.verify.verified_generate.
    """

    def write(feedback: list[str], no_tools: bool, prev_doc: str | None = None) -> str:
        prompt = compose_write_prompt(base_prompt, feedback=feedback,
                                      prev_doc=prev_doc, no_tools=no_tools)
        doc = run_writer(writer_graph_factory(no_tools=no_tools), prompt, observer)
        # 엣지 라벨 문법(<br/>·괄호)은 재시도 대신 결정적으로 정규화 — lint 전에 고친다.
        return sanitize_mermaid(doc)

    def critic(doc_md: str) -> dict:
        src = _extract_source_files(doc_md)

        def factory(no_tools: bool = False):
            return build_critic_graph(
                model=model, client=client, theme=theme, doc_markdown=doc_md,
                source_files_read=src, ref=ref, run_id=run_id, stage=f"critic:{stage}",
                no_tools=no_tools,
            )

        return run_json_verdict(factory, observer)

    return verified_generate(
        write=write, critic=critic, lint=lint_mermaid, lint_name="mermaid",
        emit_ctx=emit_ctx, stage=stage, end_marker=DOC_END_MARKER,
    )
