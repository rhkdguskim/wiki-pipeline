"""write -> 검증(mermaid lint + deterministic verifier + critic) -> 재시도.

재시도 루프·형식검증·수정모드 프롬프트 합성·JSON 판정 회수는 common_pipeline 공용
(verify·writer). 여기는 정적 고유 부분만 — mermaid lint, frontmatter source_files
추출, 소스 대조 critic 그래프 구성.

7단계 품질 파이프라인 통합 (raw/2026-07-08-ai-agent-output-quality-plan.md):
evidence_pack 이 주어지면 deterministic_verifier 를 lint 단계에 추가하고,
chunked_critic 로 9k 단절 한계를 넘어선다. evidence_pack 이 없으면 기존 동작 유지
(하위 호환 — LLM 없는 테스트 경로).
"""
from __future__ import annotations

import re

from langchain_core.messages import HumanMessage

from ..common_pipeline.deterministic_verifier import verify as deterministic_verify
from ..common_pipeline.evidence_builder import evidence_ids
from ..common_pipeline.grounding_critic import chunked_critic
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


def _make_critic_fn(model, observer, *, stage: str, recursion_limit: int = 12):
    """chunked_critic 용 critic_fn — messages list 를 받아 LLM raw 텍스트를 반환.

    기존 critic 그래프의 tool 탐색 없이, chunked_critic 가 조립한 messages 를
    그대로 model 에 보낸다. 근거는 evidence_block 으로 이미 prompt 에 들어있다.
    """

    def critic_fn(messages: list[dict]) -> str:
        # role/content dict 를 단일 HumanMessage 로 병합 — system+user 를 하나의
        # 프롬프트로 합쳐 model 이 system 지시를 무시하지 않게 한다.
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"[{role}]\n{content}")
        prompt = "\n\n".join(parts)
        try:
            from ..common.run import run_graph
            from ..common.agent_spec import AgentSpec
            from ..common.graph import build_agent_graph
            spec = AgentSpec(
                pipeline_id="static",
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
            from ..common.run import final_text
            return final_text(final)
        except Exception:  # noqa: BLE001 — 폴백: 직접 model.invoke
            try:
                resp = model.invoke([HumanMessage(content=prompt)])
                return resp.content if isinstance(resp.content, str) else str(resp.content)
            except Exception as e:  # noqa: BLE001
                return f'{{"result": "fail", "score": 0.0, "blocking_findings": [], "nonblocking_notes": ["critic 호출 실패: {type(e).__name__}"]}}'

    return critic_fn


def _combined_lint(doc_md: str, *, theme: str, ev_ids: list[str],
                   use_deterministic: bool) -> list[str]:
    """mermaid lint + deterministic verifier 를 합친 lint.

    deterministic_verifier 가 활성화되면 mermaid 뿐 아니라 frontmatter·근거 id·
    secret·추측어 까지 한 번에 검사한다. 두 검사의 에러를 lint feedback 문자열로
    합쳐 verified_generate 의 재시도 루프로 보낸다.
    """
    errs: list[str] = list(lint_mermaid(doc_md))
    if not use_deterministic:
        return errs
    v = deterministic_verify(
        doc_md, theme=theme, evidence_ids=ev_ids, doc_type="static",
    )
    for e in v["errors"]:
        errs.append(f"[{e['code']}] {e['message']}")
    return errs


def generate_with_critic(
    *, model, client, theme, ref, run_id, stage, writer_graph_factory,
    base_prompt, observer, emit_ctx,
    evidence_pack: dict | None = None,
):
    """write -> 형식검증 -> mermaid lint + deterministic verifier -> critic(grounding) -> 재시도.

    (doc, verdict, warned) 반환 — 루프는 common_pipeline.verify.verified_generate.

    evidence_pack 이 주어지면:
    - deterministic_verifier 가 lint 단계에 추가된다 (frontmatter·근거·secret 검사).
    - critic 가 chunked_critic 로 대체돼 9k 단절 없이 전체 문서를 검증한다.
    - verdict 에 quality_gate 용 severity_counts·score 가 포함된다.
    """
    ev_ids = evidence_ids(evidence_pack) if evidence_pack else []
    use_deterministic = evidence_pack is not None

    def write(feedback: list[str], no_tools: bool, prev_doc: str | None = None) -> str:
        prompt = compose_write_prompt(base_prompt, feedback=feedback,
                                      prev_doc=prev_doc, no_tools=no_tools)
        doc = run_writer(writer_graph_factory(no_tools=no_tools), prompt, observer)
        # 엣지 라벨 문법(<br/>·괄호)은 재시도 대신 결정적으로 정규화 — lint 전에 고친다.
        return sanitize_mermaid(doc)

    def critic(doc_md: str) -> dict:
        if evidence_pack is not None:
            # chunked_critic 경로 — 9k 단절 없이 전체 문서를 chunk 별로 검증.
            from ..common_pipeline.evidence_builder import evidence_block_text
            evidence_block = evidence_block_text(evidence_pack)
            critic_fn = _make_critic_fn(model, observer, stage=stage)
            verdict = chunked_critic(
                doc_md, evidence_block, theme,
                chunk_size=6000, critic_fn=critic_fn,
            )
            # verified_generate 호환 — result + feedback (blocking_findings 에서).
            feedback = []
            for f in verdict.get("blocking_findings") or []:
                claim = f.get("claim", "")
                reason = f.get("reason", "")
                fix = f.get("required_fix", "")
                feedback.append(f"[{f.get('severity', 'minor')}] {claim}: {reason}. 고침: {fix}")
            return {
                "result": verdict["result"],
                "score": verdict.get("score", 0.0),
                "feedback": feedback,
                "blocking_findings": verdict.get("blocking_findings") or [],
                "nonblocking_notes": verdict.get("nonblocking_notes") or [],
            }

        # 기존 경로 — LLM critic 그래프 (read_file 도구로 grounding).
        src = _extract_source_files(doc_md)

        def factory(no_tools: bool = False):
            return build_critic_graph(
                model=model, client=client, theme=theme, doc_markdown=doc_md,
                source_files_read=src, ref=ref, run_id=run_id, stage=f"critic:{stage}",
                no_tools=no_tools,
            )

        return run_json_verdict(factory, observer)

    lint_fn = (lambda md: _combined_lint(
        md, theme=theme, ev_ids=ev_ids, use_deterministic=use_deterministic,
    )) if use_deterministic else lint_mermaid

    return verified_generate(
        write=write, critic=critic, lint=lint_fn, lint_name="quality",
        emit_ctx=emit_ctx, stage=stage, end_marker=DOC_END_MARKER,
    )
