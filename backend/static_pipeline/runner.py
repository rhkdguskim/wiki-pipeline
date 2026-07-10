"""정적 파이프라인 diff 러너 (증분).

결정적 오케스트레이션: compare -> evidence pack -> 테마 매핑 -> 테마당
[write -> deterministic verifier + chunked critic -> 재시도] -> 저장.
판단(문서 생성·검증)만 에이전트, 나머지는 일반 코드. 러너 골격(run_id·observer·
run 이벤트·자원 정리)은 common_pipeline.run_context.RunContext 공용.

7단계 품질 파이프라인 (raw/2026-07-08-ai-agent-output-quality-plan.md):
evidence_builder 가 변경 파일을 bounded evidence pack 으로 만들고, generate 어댑터가
deterministic verifier + chunked critic 로 품질 gate 를 평가한다.
"""
from __future__ import annotations

from ..common.config import Settings
from ..common.docshub import submit_mr_stub
from ..common.llm import build_chat_model
from ..common_pipeline.evidence_builder import build_evidence_pack
from ..common_pipeline.output import save_doc
from ..common_pipeline.quality_gates import evaluate_generation_quality
from ..common_pipeline.run_context import RunContext
from ..connectors import connector_for_settings
from .generate import generate_with_critic
from .graph import build_diff_writer_graph
from .pipeline_state import save_state
from .theme_mapping import (
    filter_source_files, parse_submodule_paths, themes_for_changes, under_any,
)
from .themes import DEFAULT_THEMES


def run_static(settings: Settings, from_sha: str, to_sha: str | None,
               themes: list[str] | None = None, run_id: str | None = None) -> dict:
    themes = themes or DEFAULT_THEMES

    with RunContext("static", settings, run_stage="static-diff", run_id=run_id) as ctx:
        rev = ctx.rev
        client = ctx.track(connector_for_settings(settings))
        model = build_chat_model(settings)
        summary: dict = {"run_id": ctx.run_id, "themes": {},
                         "changed": 0, "sources": 0, "warned": []}

        # to_sha 미지정(상태 기반 증분)이면 default branch HEAD로 해석.
        if not to_sha or to_sha.upper() == "HEAD":
            to_sha = client.resolve_ref(client.default_branch())
        ctx.start(detail={
            "from": from_sha[:10], "to": to_sha[:10],
            "source_id": settings.source_id, "source_label": settings.source_label,
            "project_id": settings.gitlab_project_id,
        })

        rev("stage", "compare", "running")
        diffs = client.compare(from_sha, to_sha)
        changed = [d.get("new_path") for d in diffs if d.get("new_path")]
        # 서브모듈은 참고하지 않는다 (사용자 요구) — .gitmodules 경로 하위 변경 배제.
        submodule_paths: list[str] = []
        try:
            submodule_paths = parse_submodule_paths(client.raw_file(".gitmodules", to_sha))
        except Exception:  # noqa: BLE001 — 서브모듈 없음
            submodule_paths = []
        if submodule_paths:
            changed = [c for c in changed if not under_any(c, submodule_paths)]
            diffs = [d for d in diffs
                     if not under_any(d.get("new_path") or d.get("old_path") or "",
                                      submodule_paths)]
        sources = filter_source_files(changed)
        summary["changed"] = len(changed)
        summary["sources"] = len(sources)
        rev("stage", "compare", "done",
            detail={"changed": len(changed), "sources": len(sources),
                    "submodules_excluded": submodule_paths})

        if not sources:
            # 변경 없음도 성공 — "여기까지 봤다"로 sha 전진 (재실행 시 같은 구간 재검사 방지).
            _advance(settings, client, to_sha, summary, rev)
            ctx.done(detail={"note": "문서화할 소스 변경 없음"})
            return summary

        # Evidence pack — writer/critic 은 이 pack 만 보고 raw repo 를 직접 보지 않는다
        # (raw 설계서 §1). 빌드 실패 시 pack=None 폴백 — 기존 critic 경로 유지.
        evidence_pack = _build_static_evidence_pack(
            client, rev, ctx.run_id, settings.source_id, to_sha, sources, diffs,
        )

        theme_map = themes_for_changes(changed, themes)
        rev("stage", "theme-mapping", "done", detail={"themes": list(theme_map.keys())})

        theme_ids = list(theme_map.keys())
        quality_summaries: list[dict] = []
        for i, theme in enumerate(theme_ids, 1):
            files = theme_map[theme]
            stage = f"theme:{theme}"
            rev("engine_call", stage, "running",
                progress={"n": i, "m": len(theme_ids), "unit": "theme"})

            def factory(_t=theme, _f=files, no_tools=False):
                return build_diff_writer_graph(
                    model=model, client=client, theme=_t, changed_files=_f,
                    from_sha=from_sha, to_sha=to_sha, run_id=ctx.run_id,
                    no_tools=no_tools,
                )

            base_prompt = (
                f"'{theme}' 테마의 기술문서를 작성하라. 변경 파일과 테마 정의는 시스템 "
                f"프롬프트에 있다. 완성되면 frontmatter 포함 마크다운만 출력하라."
            )
            doc_md, verdict, warned = generate_with_critic(
                model=model, client=client, theme=theme, ref=to_sha, run_id=ctx.run_id,
                stage=stage, writer_graph_factory=factory, base_prompt=base_prompt,
                observer=ctx.observer, emit_ctx=rev,
                evidence_pack=evidence_pack,
            )
            path = save_doc(settings.out_path, theme, doc_md)
            mr = submit_mr_stub(theme, path, settings.docshub_mr_enabled)

            quality_summaries.append({
                "theme": theme,
                "verdict_result": verdict.get("result"),
                "verdict_score": verdict.get("score"),
                "blocking_findings": verdict.get("blocking_findings") or [],
                "lint_errors": verdict.get("lint_errors") or [],
                "warned": warned,
            })

            summary["themes"][theme] = {
                "file": str(path), "chars": path.stat().st_size,
                "verdict": verdict.get("result"), "warned": warned,
                "score": verdict.get("score"),
                "lint_errors": verdict.get("lint_errors") or [],
            }
            if warned:
                summary["warned"].append(theme)
            rev("engine_call", stage, "done",
                progress={"n": i, "m": len(theme_ids), "unit": "theme"},
                detail={"saved": path.name, "verdict": verdict.get("result"),
                        "warned": warned, "mr": mr})

        quality_status, terminal = _evaluate_run_quality(quality_summaries, summary)
        summary["quality_status"] = quality_status
        summary["terminal_status"] = terminal
        summary["publishable"] = quality_status != "fail"
        rev("stage", "quality-gate", "done",
            detail={"quality_status": quality_status, "terminal_status": terminal,
                    "theme_count": len(quality_summaries)})

        if terminal == "failed_quality_gate":
            ctx.failed(detail={"quality_status": quality_status,
                               "terminal_status": terminal})
            return summary

        # 상태 전진 — 성공 후에만 (concept-idempotent-sha). 실패 시 상태 불변.
        _advance(settings, client, to_sha, summary, rev)
        ctx.done(detail={"generated": list(summary["themes"].keys()),
                         "warned": summary["warned"],
                         "quality_status": quality_status,
                         "terminal_status": terminal})
        return summary


def _advance(settings, client, to_sha: str, summary: dict, rev) -> None:
    """last_processed_sha 전진 (성공 경로에서만 호출).

    실패하면 이벤트만 남기고 끝내지 않는다 — 문서는 만들어졌어도 sha가 전진하지
    않으면 run을 "완료"로 보고할 수 없다 (decision-state-advance-failure-propagates).
    재발생시켜 호출부(run_static)의 RunContext가 run failed로 마무리하게 한다.
    """
    try:
        full = to_sha if len(to_sha) == 40 else client.resolve_ref(to_sha)
        sp = save_state(
            settings.out_path, project_id=settings.gitlab_project_id,
            last_processed_sha=full, ref=to_sha, op="diff",
            source_id=settings.source_id if settings.scm_sources_json else None,
            extra={"themes": list(summary["themes"].keys()),
                   "source_label": settings.source_label,
                   "source_kind": settings.source_kind},
        )
        summary["last_processed_sha"] = full
        rev("stage", "state-advance", "done",
            detail={"last_processed_sha": full[:12], "file": sp.name})
    except Exception as e:  # noqa: BLE001 — 이벤트로 남기고 run 실패로 전파(재발생)
        rev("stage", "state-advance", "failed",
            detail={"error": f"{type(e).__name__}: {e}"})
        raise


def _build_static_evidence_pack(client, rev, run_id, source_id, ref,
                                sources, diffs) -> dict | None:
    """변경 파일 diff hunk + (best-effort) 파일 원문 으로 evidence pack 구축.

    client.read_file 실패(권한·경로·바이너리) 시 해당 파일은 스킵하고 나머지로 pack
    을 만든다 — 빈 pack 이라도 반환하는 게 기존 critic 경로보다 낫다. 예외 자체가
    발생하면 None 을 반환해 generate 어댑터가 기존 critic 경로로 폴백하게 한다.
    """
    items: list[dict] = []
    try:
        for i, d in enumerate(diffs[:50], 1):
            path = d.get("new_path") or d.get("old_path") or ""
            if not path:
                continue
            diff_text = d.get("diff") or ""
            items.append({
                "id": f"e{i}",
                "kind": "diff_hunk",
                "path": path,
                "title": f"diff: {path}",
                "content": diff_text[:8000],
                "metadata": {"from_sha": d.get("old_sha", ""),
                             "to_sha": d.get("new_sha", "")},
            })
        for j, path in enumerate(sources[:30], 1):
            try:
                content = client.read_file(path, ref=ref)
                items.append({
                    "id": f"f{j}",
                    "kind": "source_file",
                    "path": path,
                    "title": path,
                    "content": content,
                })
            except Exception:  # noqa: BLE001 — 바이너리·권한·404 스킵
                continue
        if not items:
            return None
        pack = build_evidence_pack(
            run_id, source_id, "static", ref, items,
        )
        rev("stage", "evidence-build", "done",
            detail={"pack_id": pack["pack_id"], "items": pack["item_count"],
                    "truncated": pack["truncated"]})
        return pack
    except Exception as e:  # noqa: BLE001 — 폴백: None 반환 → 기존 critic 경로
        rev("stage", "evidence-build", "failed",
            detail={"error": f"{type(e).__name__}: {e}"})
        return None


def _evaluate_run_quality(quality_summaries: list[dict], summary: dict) -> tuple[str, str]:
    """테마별 critic verdict 를 합쳐 run 단위 quality_status·terminal_status 산출.

    가장 약한 테마의 verdict 가 run 전체 품질을 대표한다 — 한 테마라도 fail 이면
    run 도 fail 에 가깝게 본다 (raw 설계서 §5 통과 기준).
    """
    gate, terminal = evaluate_generation_quality(quality_summaries)
    return gate["status"], terminal
