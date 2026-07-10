"""write -> 검증(deterministic verifier + critic) -> 재시도 (매뉴얼 어댑터).

재시도 루프·형식검증·수정모드 프롬프트 합성·JSON 판정 회수는 common_pipeline 공용
(verify·writer — 정적 generate.py와 같은 계약). 여기는 매뉴얼 고유 부분만 —
근거가 소스 코드가 아니라 관측 로그라 mermaid lint 없이 관측 grounding critic만 쓰고,
writer/critic 모두 도구 없음 (관측 로그는 불변 기록이라 재탐색이 필요 없다).

7단계 품질 파이프라인 통합 (raw/2026-07-08-ai-agent-output-quality-plan.md):
evidence_pack 이 주어지면 deterministic_verifier 가 추가되고 chunked_critic 로 9k
단절 한계를 넘어선다. evidence_pack 이 없으면 기존 동작 유지 (하위 호환).
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage

from ..common_pipeline.deterministic_verifier import verify as deterministic_verify
from ..common_pipeline.evidence_builder import (
    build_evidence_pack, evidence_block_text, evidence_ids,
)
from ..common_pipeline.grounding_critic import chunked_critic
from ..common_pipeline.verify import DOC_END_MARKER, run_json_verdict, verified_generate
from ..common_pipeline.writer import compose_write_prompt, run_writer
from .graph import build_critic_graph, build_manual_writer_graph
from .themes import get_theme


def _make_critic_fn(model, observer, *, stage: str, recursion_limit: int = 12):
    """chunked_critic 용 critic_fn — messages list → LLM raw 텍스트."""

    def critic_fn(messages: list[dict]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"[{role}]\n{content}")
        prompt = "\n\n".join(parts)
        try:
            from ..common.run import run_graph, final_text
            from ..common.agent_spec import AgentSpec
            from ..common.graph import build_agent_graph
            spec = AgentSpec(
                pipeline_id="manual",
                system_prompt="\n\n".join(
                    m["content"] for m in messages if m.get("role") == "system"
                ) or "critic",
                tools=[],
                run_id="", stage=f"chunked:{stage}", max_steps=1,
            )
            graph = build_agent_graph(spec, model)
            user_content = "\n\n".join(
                m["content"] for m in messages if m.get("role") == "user"
            ) or prompt
            final = run_graph(
                graph, {"messages": [HumanMessage(content=user_content)]},
                observer, config={"recursion_limit": recursion_limit},
            )
            return final_text(final)
        except Exception:  # noqa: BLE001
            try:
                from ..common.llm_gate import llm_slot
                with llm_slot():  # 폴백 직접 호출도 공급자 concurrency 한도를 지킨다.
                    resp = model.invoke([HumanMessage(content=prompt)])
                return resp.content if isinstance(resp.content, str) else str(resp.content)
            except Exception as e:  # noqa: BLE001
                return f'{{"result": "fail", "score": 0.0, "blocking_findings": [], "nonblocking_notes": ["critic 호출 실패: {type(e).__name__}"]}}'

    return critic_fn


def _build_manual_evidence_pack(evidence: str, run_id: str, theme_key: str) -> dict | None:
    """관측 로그 텍스트에서 observation id 를 추출해 evidence pack 구축.

    evidence_block 텍스트([oN|phase] tool(args) -> OK/ERR\n preview) 에서
    [oN] 태그를 파싱해 observation evidence item 을 만든다. 텍스트가 비었거나
    파싱 실패 시 None 반환 — generate 어댑터가 기존 critic 경로로 폴백.
    """
    import re

    pattern = re.compile(r"\[o(\d+)\|([^\]]+)\]\s*(.+?)\s*->\s*(OK|ERR)\s*\n(.*?)(?=\n\[o|\Z)", re.DOTALL)
    items: list[dict] = []
    for m in pattern.finditer(evidence or ""):
        seq = m.group(1)
        phase = m.group(2)
        tool_call = m.group(3)
        status = m.group(4)
        preview = m.group(5).strip()
        items.append({
            "id": f"o{seq}",
            "kind": "observation",
            "title": f"{tool_call.strip()[:80]}",
            "content": f"[{phase}] {status}\n{preview}",
            "observation_id": f"o{seq}",
            "metadata": {"phase": phase, "status": status},
        })

    if not items:
        return None
    theme = get_theme(theme_key)
    return build_evidence_pack(
        run_id, "", "manual", theme.id, items,
    )


def generate_with_critic(
    *, model, theme_key, evidence, scenarios_block, coverage_block,
    run_id, run_ref, stage, observer, emit_ctx,
    evidence_pack: dict | None = None,
):
    """write -> 형식검증 -> deterministic verifier + critic(관측 grounding) -> 재시도.

    (doc, verdict, warned) 반환.

    evidence_pack 이 주어지면:
    - deterministic_verifier 가 lint 단계에 추가된다 (frontmatter·근거·secret 검사).
    - critic 가 chunked_critic 로 대체돼 9k 단절 없이 전체 문서를 검증한다.
    - verdict 에 quality_gate 용 severity_counts·score 가 포함된다.
    """
    base_prompt = (
        f"'{theme_key}' 매뉴얼을 시스템 프롬프트의 관측 로그를 근거로 작성하라. "
        f"완성되면 frontmatter 포함 마크다운만 출력하라."
    )

    if evidence_pack is None:
        evidence_pack = _build_manual_evidence_pack(evidence, run_id, theme_key)
    ev_ids = evidence_ids(evidence_pack) if evidence_pack else []
    use_deterministic = evidence_pack is not None

    def write(feedback: list[str], no_tools: bool, prev_doc: str | None = None) -> str:
        prompt = compose_write_prompt(base_prompt, feedback=feedback,
                                      prev_doc=prev_doc, no_tools=no_tools)
        graph = build_manual_writer_graph(
            model=model, theme_key=theme_key, evidence_block=evidence,
            scenarios_block=scenarios_block, coverage_block=coverage_block,
            run_ref=run_ref, run_id=run_id,
        )
        return run_writer(graph, prompt, observer, recursion_limit=12)

    def lint(doc_md: str) -> list[str]:
        if not use_deterministic:
            return []
        v = deterministic_verify(
            doc_md, theme=get_theme(theme_key).id, evidence_ids=ev_ids,
            doc_type="manual",
        )
        return [f"[{e['code']}] {e['message']}" for e in v["errors"]]

    def critic(doc_md: str) -> dict:
        if evidence_pack is not None:
            evidence_block = evidence_block_text(evidence_pack)
            theme_contract = {
                "id": get_theme(theme_key).id,
                "perspective": get_theme(theme_key).perspective,
                "audience": get_theme(theme_key).audience,
                "must_cover": get_theme(theme_key).must_cover,
                "do_not_cover": get_theme(theme_key).do_not_cover,
            }
            critic_fn = _make_critic_fn(model, observer, stage=stage)
            verdict = chunked_critic(
                doc_md, evidence_block, theme_contract,
                chunk_size=6000, critic_fn=critic_fn,
            )
            feedback = []
            for f in verdict.get("blocking_findings") or []:
                feedback.append(
                    f"[{f.get('severity', 'minor')}] {f.get('claim', '')}: "
                    f"{f.get('reason', '')}. 고침: {f.get('required_fix', '')}"
                )
            return {
                "result": verdict["result"],
                "score": verdict.get("score", 0.0),
                "feedback": feedback,
                "blocking_findings": verdict.get("blocking_findings") or [],
                "nonblocking_notes": verdict.get("nonblocking_notes") or [],
            }

        def factory(no_tools: bool = False):
            return build_critic_graph(
                model=model, theme_key=theme_key, doc_markdown=doc_md,
                evidence_block=evidence, run_id=run_id, stage=f"critic:{stage}",
            )

        return run_json_verdict(factory, observer, recursion_limit=12)

    return verified_generate(
        write=write, critic=critic, lint=lint if use_deterministic else None,
        lint_name="quality", emit_ctx=emit_ctx, stage=stage, min_len=400,
        end_marker=DOC_END_MARKER,
    )
