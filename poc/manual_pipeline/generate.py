"""write -> 검증(critic) -> 재시도 (매뉴얼 어댑터).

재시도 루프·형식검증·수정모드 프롬프트 합성·JSON 판정 회수는 common_pipeline 공용
(verify·writer — 정적 generate.py와 같은 계약). 여기는 매뉴얼 고유 부분만 —
근거가 소스 코드가 아니라 관측 로그라 mermaid lint 없이 관측 grounding critic만 쓰고,
writer/critic 모두 도구 없음 (관측 로그는 불변 기록이라 재탐색이 필요 없다).
"""
from __future__ import annotations

from ..common_pipeline.verify import run_json_verdict, verified_generate
from ..common_pipeline.writer import compose_write_prompt, run_writer
from .graph import build_critic_graph, build_manual_writer_graph


def generate_with_critic(
    *, model, theme_key, evidence, scenarios_block, coverage_block,
    run_id, run_ref, stage, observer, emit_ctx,
):
    """write -> 형식검증 -> critic(관측 grounding) -> 재시도. (doc, verdict, warned) 반환."""
    base_prompt = (
        f"'{theme_key}' 매뉴얼을 시스템 프롬프트의 관측 로그를 근거로 작성하라. "
        f"완성되면 frontmatter 포함 마크다운만 출력하라."
    )

    def write(feedback: list[str], no_tools: bool, prev_doc: str | None = None) -> str:
        # writer는 애초에 도구가 없다 — no_tools 시 '즉시 완성' 안내만 프롬프트에 더해진다.
        prompt = compose_write_prompt(base_prompt, feedback=feedback,
                                      prev_doc=prev_doc, no_tools=no_tools)
        graph = build_manual_writer_graph(
            model=model, theme_key=theme_key, evidence_block=evidence,
            scenarios_block=scenarios_block, coverage_block=coverage_block,
            run_ref=run_ref, run_id=run_id,
        )
        return run_writer(graph, prompt, observer, recursion_limit=12)

    def critic(doc_md: str) -> dict:
        def factory(no_tools: bool = False):
            # critic도 도구가 없어 no_tools는 의미 없음 (판정 재시도 계약만 맞춘다).
            return build_critic_graph(
                model=model, theme_key=theme_key, doc_markdown=doc_md,
                evidence_block=evidence, run_id=run_id, stage=f"critic:{stage}",
            )

        return run_json_verdict(factory, observer, recursion_limit=12)

    return verified_generate(
        write=write, critic=critic, emit_ctx=emit_ctx, stage=stage, min_len=400,
    )
