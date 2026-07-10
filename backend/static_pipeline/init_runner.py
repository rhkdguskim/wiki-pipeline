"""정적 파이프라인 init/backfill — 전체 레포 스캔 오케스트레이션.

신규 등록 소스의 최초 문서화 (decision-registration-baseline: last_processed_sha=null).
**저장소 전체에 대한 테마 문서**(intro·requirements·architecture-overview·
component-diagram)를 만든다 — 특정 레포 가정 없이 어떤 저장소든 동일하게 동작한다.

오케스트레이션 (구간별 에이전트 분배):
  1) 계획   — 에이전트가 레포 구조를 파악해 스캔 단위(구간)를 결정 (레포 구조 무관 적응)
  2) search — 단위를 청크로 쪼개 청크마다 SearchAgent 1개(독립 context)가 **모든 파일을
              전수 read** 후 청크 요약, 여러 청크면 SummaryComposer 가 단위 요약으로 합성
              (deep_summary.py, 캐시 지원). init 은 샘플링이 아니라 전수 스캔이 원칙.
  3) reduce — 테마마다 writer가 전체 단위 요약을 종합해 레포 수준 문서 합성 (테마도 병렬)
              write -> mermaid-lint + critic(grounding) -> 재시도
init은 등록 시 1회만 도는 별도 작업(정기 야간 diff 배치와 분리).
"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage

from ..common.agent_spec import AgentSpec
from ..common.config import Settings
from ..common.docshub import submit_mr_stub
from ..common.graph import build_agent_graph
from ..common.llm_gate import effective_parallelism
from ..common.llm import build_chat_model
from ..common.run import final_text, run_graph
from ..common.textproc import extract_json_obj
from ..common_pipeline.evidence_builder import build_evidence_pack
from ..common_pipeline.output import save_doc
from ..common_pipeline.parallel import parallel_map
from ..common_pipeline.quality_gates import evaluate_generation_quality
from ..common_pipeline.run_context import RunContext
from ..common_pipeline.scope_planner import plan_static_init_docs
from ..connectors import connector_for_settings
from .deep_summary import search_unit_summaries, summaries_block
from .generate import generate_with_critic
from .graph import build_repo_writer_graph
from .pipeline_state import save_state
from .prompts import plan_system_prompt
from .theme_mapping import (
    filter_source_files, is_vendored, parse_submodule_paths, under_any,
)
from .tools import make_tools

# init 기본 4테마 (레포 무관 공통 축). --themes 로 dev-guide 등 확장 가능.
_DEFAULT_INIT_THEMES = ["intro", "requirements", "architecture-overview", "component-diagram"]


def _plan_units(client, model, ref, run_id, observer, max_steps=8) -> list[dict]:
    """계획 단계: 에이전트가 루트 구조를 파악해 스캔 단위 목록을 낸다."""
    top = [e["path"] for e in client.list_tree(path="", ref=ref)]
    spec = AgentSpec(
        pipeline_id="static", system_prompt=plan_system_prompt(ref, top),
        tools=make_tools(client, ref=ref), run_id=run_id,
        stage="plan", max_steps=max_steps,
    )
    graph = build_agent_graph(spec, model)
    final = run_graph(
        graph,
        {"messages": [HumanMessage(content="이 저장소의 문서화 단위를 계획해 JSON으로 출력하라.")]},
        observer, config={"recursion_limit": 25},
    )
    units = extract_json_obj(final_text(final), "units").get("units", [])
    return [u for u in units if u.get("root_path") and not is_vendored(u["root_path"])]


def _files_under(all_paths: list[str], root_path: str) -> list[str]:
    root = root_path.rstrip("/")
    under = [p for p in all_paths if p == root or p.startswith(root + "/")]
    return filter_source_files(under)


def _build_init_evidence_pack(ctx, client, ref, summaries) -> dict | None:
    """단위 요약(+best-effort 소스 파일)으로 init evidence pack 구축.

    init 의 1차 근거는 map 단계 단위 요약이다 (원본 소스가 아니라 요약). 각 요약을
    observation kind item 으로, 그리고 요약이 언급했을 소스 경로 일부를 source_file
    로 담아 writer/critic 이 같은 bounded 근거만 보게 한다 — diff 경로와 동일한 계약
    (generate.py: evidence_pack 이 있으면 chunked_critic + deterministic_verifier 활성).

    빌드 실패/근거 없음이면 None 을 반환해 기존 9k critic 경로로 폴백한다 (하위 호환).
    """
    settings = ctx.settings
    rev = ctx.rev
    items: list[dict] = []
    try:
        for i, (unit, text) in enumerate(summaries, 1):
            if not text or not str(text).strip():
                continue
            items.append({
                "id": f"e{i}",
                "kind": "observation",
                "path": "",
                "title": f"단위 요약: {unit}",
                "content": str(text),
                "metadata": {"unit": unit, "ref": ref},
            })
        if not items:
            return None
        pack = build_evidence_pack(
            ctx.run_id, settings.source_id, "static", ref, items,
        )
        rev("stage", "evidence-build", "done",
            detail={"pack_id": pack["pack_id"], "items": pack["item_count"],
                    "truncated": pack["truncated"], "source": "unit-summaries"})
        return pack
    except Exception as e:  # noqa: BLE001 — 폴백: None → 기존 critic 경로
        rev("stage", "evidence-build", "failed",
            detail={"error": f"{type(e).__name__}: {e}"})
        return None


def _init_coverage(themes, docs: dict, *, planned_units: int, summarized_units: int,
                   threshold: float = 70.0) -> dict:
    """init 문서 생성 커버리지 지표 (관측·게이트용).

    두 축을 잰다:
      - 문서 축: 만들기로 한 테마(전체 - skip) 중 실제 생성 성공 비율.
      - 단위 축: 계획된 스캔 단위 중 요약이 성공한 비율 (reduce 근거의 완전성).
    둘 중 낮은 쪽을 대표 pct 로 삼는다 (가장 약한 고리 기준).

    status:
      - fail:    대표 pct 가 threshold*0.5 미만 (근거·산출이 심각하게 빈다)
      - warning: threshold 미만
      - pass:    threshold 이상
    _summary_status 가 이 status 를 읽어 run terminal 을 조정한다 (fail→failed_quality_gate,
    warning→done_with_warnings). skip 은 분모에서 빠지므로 정상 skip 이 커버리지를 깎지 않는다.
    """
    expected_docs = [t for t in themes if not docs.get(t, {}).get("skipped")]
    produced = [t for t in expected_docs
                if "error" not in docs.get(t, {}) and docs.get(t)]
    unreached = [t for t in expected_docs if t not in produced]
    doc_pct = (100.0 * len(produced) / len(expected_docs)) if expected_docs else 100.0
    unit_pct = (100.0 * summarized_units / planned_units) if planned_units else 100.0
    pct = min(doc_pct, unit_pct)
    status = "pass" if pct >= threshold else (
        "warning" if pct >= threshold * 0.5 else "fail")
    return {
        "pct": round(pct, 1),
        "coverage_pct": round(pct, 1),   # emit_coverage/plan_manual 호환 키
        "status": status,
        "doc_pct": round(doc_pct, 1),
        "unit_pct": round(unit_pct, 1),
        # emit_coverage 가 읽는 키 (reached=리스트, expected_count=정수, unreached=리스트).
        "reached": produced,
        "expected_count": len(expected_docs),
        "unreached": unreached,
        "expected_docs": len(expected_docs),
        "produced_docs": len(produced),
        "skipped_docs": len(themes) - len(expected_docs),
        "planned_units": planned_units,
        "summarized_units": summarized_units,
    }


def _reduce_and_save(
    *, ctx: RunContext, client, model, ref, repo_name, themes, summaries, summary,
) -> dict:
    """reduce 단계: 테마별 레포 문서 합성(병렬) + critic + 저장. (계획/캐시 양쪽 공용)

    래칫(ratchet): 같은 ref에서 이미 critic pass한 테마는 재생성하지 않고 유지한다
    (_verdicts.json 사이드카). critic 판정은 비결정적이라 매 실행 전부 다시 뽑으면
    pass가 복권이 된다 — 실패 테마만 재생성해 반복을 단조 수렴시킨다.
    """
    settings = ctx.settings
    rev = ctx.rev
    out_dir = settings.out_path / "init"
    summ_block = summaries_block(summaries)

    # Evidence pack — 단위 요약을 bounded 근거로 만들어 writer/critic 이 같은 근거만
    # 보게 한다. 이게 주입되면 generate 어댑터가 chunked_critic(9k 단절 없음) +
    # deterministic_verifier 를 활성화한다 (diff 경로와 동일). 빌드 실패 시 None →
    # 기존 9k critic 경로로 폴백 (하위 호환).
    evidence_pack = _build_init_evidence_pack(ctx, client, ref, summaries)

    # Scope planning — 요약을 근거로 이 테마를 쓸 재료가 있는지 판정. 근거 없는
    # 테마(예: API 신호 없는 api-protocol, 단위 1개뿐인 component-diagram)는 skip 해
    # 과잉 생성·hallucination 을 줄인다. skip 테마는 문서를 안 만들고 요약에 기록만 한다.
    scope_plans = plan_static_init_docs(themes, summaries)
    skipped = {p["theme"]: p["reason"] for p in scope_plans if p["action"] == "skip"}
    active_themes = [p["theme"] for p in scope_plans if p["action"] != "skip"]
    for theme, reason in skipped.items():
        summary["docs"][theme] = {"skipped": True, "reason": reason}
        rev("engine_call", f"repo:{theme}", "done",
            detail={"skipped": reason})
    if skipped:
        rev("stage", "scope-plan", "done",
            detail={"active": active_themes, "skipped": list(skipped.keys())})

    verdicts_path = out_dir / "_verdicts.json"
    try:
        prior = json.loads(verdicts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        prior = {}

    def _gen_theme(theme: str):
        stage = f"repo:{theme}"
        # 래칫: 같은 ref에서 pass한 문서가 남아있으면 유지 (재생성 안 함).
        kept = prior.get(theme)
        doc_file = out_dir / f"{theme}.md"
        if (kept and kept.get("verdict") == "pass" and kept.get("ref") == ref
                and doc_file.exists()):
            rev("engine_call", stage, "done",
                detail={"kept": "이전 실행 critic pass 유지", "file": doc_file.name})
            return doc_file, {"result": "pass", "kept": True}, False

        rev("engine_call", stage, "running")

        def factory(_t=theme, no_tools=False):
            return build_repo_writer_graph(
                model=model, client=client, theme=_t, repo_name=repo_name,
                ref=ref, summaries_block=summ_block, run_id=ctx.run_id,
                no_tools=no_tools,
            )

        base_prompt = (
            f"저장소 '{repo_name}' 전체의 '{theme}' 문서를 단위 요약들을 근거로 "
            f"종합해 작성하라. 완성되면 frontmatter 포함 마크다운만 출력하라."
        )
        doc_md, verdict, warned = generate_with_critic(
            model=model, client=client, theme=theme, ref=ref, run_id=ctx.run_id,
            stage=stage, writer_graph_factory=factory, base_prompt=base_prompt,
            observer=ctx.observer, emit_ctx=rev,
            evidence_pack=evidence_pack,
        )
        path = save_doc(out_dir, theme, doc_md)
        mr = submit_mr_stub(theme, path, settings.docshub_mr_enabled)
        rev("engine_call", stage, "done",
            detail={"saved": str(path.relative_to(settings.out_path)),
                    "verdict": verdict.get("result"), "warned": warned, "mr": mr})
        return path, verdict, warned

    for theme, res, exc in parallel_map(
            active_themes, _gen_theme,
            max_workers=effective_parallelism(settings.static_reduce_concurrency)):
        if exc is not None:
            summary["docs"][theme] = {"error": f"{type(exc).__name__}: {exc}"}
            rev("engine_call", f"repo:{theme}", "failed",
                detail={"error": f"{type(exc).__name__}: {exc}"})
            continue
        path, verdict, warned = res
        summary["docs"][theme] = {
            "file": str(path), "chars": path.stat().st_size,
            "verdict": verdict.get("result"), "warned": warned,
            "kept": bool(verdict.get("kept")),
            "score": verdict.get("score"),
            "blocking_findings": verdict.get("blocking_findings") or [],
            "lint_errors": verdict.get("lint_errors") or [],
        }
        if warned:
            summary["warned"].append(theme)

    # 래칫 사이드카 갱신 — 이번에 생성/유지된 테마의 판정을 기록 (pass는 다음 실행에서 유지됨).
    # skip 테마는 문서를 안 만들었으므로 래칫 대상이 아니다.
    for theme, info in summary["docs"].items():
        if "error" not in info and not info.get("skipped"):
            prior[theme] = {"verdict": info.get("verdict"), "ref": ref,
                            "warned": info.get("warned", False)}
    try:
        verdicts_path.write_text(
            json.dumps(prior, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass

    quality_inputs = [
        {
            "theme": theme,
            "verdict_result": info.get("verdict"),
            "verdict_score": info.get("score"),
            "blocking_findings": info.get("blocking_findings") or [],
            "lint_errors": info.get("lint_errors") or [],
            "warned": info.get("warned"),
        }
        for theme, info in summary["docs"].items()
        if "error" not in info and not info.get("skipped")
    ]
    quality_gate, terminal = evaluate_generation_quality(quality_inputs)
    summary["quality_status"] = quality_gate["status"]
    summary["terminal_status"] = terminal
    summary["publishable"] = quality_gate["status"] != "fail"
    rev("stage", "quality-gate", "done",
        detail={"quality_status": quality_gate["status"],
                "terminal_status": terminal,
                "doc_count": len(quality_inputs)})

    # 문서 커버리지 지표 — 계획 단위/테마 대비 실제 요약·생성 완전성.
    # planned_unit_count 는 run_init 이 미리 심어둔다 (캐시 경로 포함). 없으면 요약 수로 폴백.
    planned_units = int(summary.get("planned_unit_count") or len(summaries))
    coverage = _init_coverage(
        themes, summary["docs"],
        planned_units=planned_units, summarized_units=len(summaries),
    )
    summary["coverage"] = {"assessment": coverage}
    summary["coverage_status"] = coverage["status"]
    rev("stage", "coverage", "done", detail=coverage)

    if terminal == "failed_quality_gate":
        ctx.failed({"quality_status": quality_gate["status"],
                    "terminal_status": terminal})
        return summary

    # 상태 전진 컨셉: **파이프라인 성공 -> SHA 전진, 파이프라인 실패 -> SHA 전진 X.**
    # 위키 계약(concept-idempotent-sha): 성공 후에만 전진, 실패 시 상태 불변 -> 재실행 안전.
    # state-advance 실패는 run 전체 실패로 취급한다 — 문서는 만들어졌어도 sha가
    # 전진하지 않으면 다음 실행이 같은 작업을 또 하게 되므로 "완료"로 보고하면 안 된다
    # (decision-state-advance-failure-propagates).
    #
    # 여기서 "성공"의 정의:
    #   - 에러난 테마가 0개 (경고 저장(warned)은 실패 아님 — 저장은 됐고 수동 검토만 필요)
    #   - 그리고 실제로 생성된 문서가 1개 이상 (전부 skip 이면 전진 근거 없음)
    # skip 테마는 "실패"가 아니라 "근거 없어 안 만듦"이므로 성공 판정을 막지 않는다.
    errored = [t for t, i in summary["docs"].items() if "error" in i]
    produced = [t for t, i in summary["docs"].items()
                if "error" not in i and not i.get("skipped")]
    if not errored and produced:
        try:
            head_sha = client.resolve_ref(ref)
            sp = save_state(
                settings.out_path, project_id=settings.gitlab_project_id,
                last_processed_sha=head_sha, ref=ref, op="init",
                source_id=settings.source_id if settings.scm_sources_json else None,
                extra={"themes": produced, "skipped": list(skipped.keys()),
                       "source_label": settings.source_label,
                       "source_kind": settings.source_kind},
            )
            summary["last_processed_sha"] = head_sha
            rev("stage", "state-advance", "done",
                detail={"last_processed_sha": head_sha[:12], "file": sp.name,
                        "produced": produced, "skipped": list(skipped.keys())})
        except Exception as e:  # noqa: BLE001 — 이벤트로 남기고 run 실패로 전파(재발생)
            rev("stage", "state-advance", "failed",
                detail={"error": f"{type(e).__name__}: {e}"})
            raise
    else:
        reason = (f"에러 테마 {len(errored)}건 존재" if errored
                  else "생성된 문서 없음 (전부 skip)")
        rev("stage", "state-advance", "done",
            detail={"skipped_advance": reason,
                    "errored": errored, "produced": produced})

    ctx.done(detail={"units": len(summary.get("units", [])),
                     "docs": list(summary["docs"].keys()), "warned": summary["warned"],
                     "quality_status": quality_gate["status"],
                     "terminal_status": terminal})
    return summary


def run_init(
    settings: Settings,
    *,
    ref: str | None = None,
    themes: list[str] | None = None,
    max_units: int | None = None,
    reuse_summaries: bool = False,
    run_id: str | None = None,
) -> dict:
    themes = themes or _DEFAULT_INIT_THEMES

    with RunContext("static", settings, prefix="init", run_stage="static-init",
                    run_id=run_id) as ctx:
        rev = ctx.rev
        client = ctx.track(connector_for_settings(settings))
        model = build_chat_model(settings)
        out_dir = settings.out_path / "init"
        out_dir.mkdir(parents=True, exist_ok=True)
        summary: dict = {"run_id": ctx.run_id, "ref": None,
                         "units": [], "docs": {}, "warned": []}

        ref = ref or client.default_branch()
        summary["ref"] = ref
        repo_name = f"project-{settings.gitlab_project_id}"
        try:
            repo_name = client.project_name() or repo_name
        except Exception:  # noqa: BLE001
            pass
        ctx.start(detail={
            "ref": ref, "themes": themes,
            "source_id": settings.source_id, "source_label": settings.source_label,
            "project_id": settings.gitlab_project_id,
        })

        # 캐시 재사용: 요약 캐시가 같은 ref면 계획·트리·map을 전부 건너뛴다 —
        # 프롬프트 반복 개선 시 비결정적 계획 재실행을 피해 반복을 결정적으로 만든다.
        cache_path = out_dir / "_summaries.json"
        if reuse_summaries and cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
            if data.get("ref") == ref and data.get("summaries"):
                summaries = [(s["unit"], s["summary"]) for s in data["summaries"]]
                summary["units"] = [u for u, _ in summaries]
                # 캐시는 성공한 요약만 담으므로 계획 단위 수 = 요약 수로 본다.
                summary["planned_unit_count"] = len(summaries)
                rev("stage", "map", "done",
                    detail={"cached": True, "units": len(summaries)})
                return _reduce_and_save(
                    ctx=ctx, client=client, model=model, ref=ref,
                    repo_name=repo_name, themes=themes,
                    summaries=summaries, summary=summary,
                )

        # 1) 계획 — 스캔 단위(구간) 결정
        rev("stage", "plan", "running")
        planned = _plan_units(client, model, ref, ctx.run_id, ctx.observer)
        rev("stage", "plan", "done",
            detail={"planned": [f"{u.get('name')}({u.get('root_path')})" for u in planned]})
        if not planned:
            ctx.done(detail={"note": "계획 단위 없음"})
            return summary

        # 전체 트리를 한 번 확보해 단위에 실제 파일을 붙이고, 매칭 0(경로 추정 오류)은 제외.
        rev("stage", "list-tree", "running")
        tree = client.list_tree_all(ref=ref, recursive=True)
        # 서브모듈은 참고하지 않는다 (사용자 요구). git 트리에서 서브모듈은
        # gitlink(type=commit)이라 blob 필터로 대부분 걸러지지만, .gitmodules 로
        # 경로를 명시 파악해 그 하위를 확실히 배제한다. 서브모듈 내부 파일은 애초에
        # 부모 트리에 안 나타나므로(다른 레포) 이 배제는 방어적 이중 안전장치다.
        submodule_paths: list[str] = []
        try:
            gm = client.raw_file(".gitmodules", ref)
            submodule_paths = parse_submodule_paths(gm)
        except Exception:  # noqa: BLE001 — .gitmodules 없으면 서브모듈 없음
            submodule_paths = []
        all_paths = [e["path"] for e in tree
                     if e.get("type") == "blob"
                     and not under_any(e["path"], submodule_paths)]
        rev("stage", "list-tree", "done",
            detail={"blobs": len(all_paths),
                    "submodules_excluded": submodule_paths})

        units, dropped = [], []
        for u in planned:
            fs = _files_under(all_paths, u.get("root_path", ""))
            if fs:
                units.append({**u, "_files": fs})
            else:
                dropped.append(f"{u.get('name')}({u.get('root_path')})")
        units.sort(key=lambda u: -len(u["_files"]))
        if dropped:
            rev("stage", "plan-filter", "done",
                detail={"dropped_no_match": dropped, "kept": len(units)})
        if max_units:
            units = units[:max_units]
        summary["units"] = [u.get("name", u.get("root_path")) for u in units]
        # 파일 매칭된 계획 단위 수 = 요약이 성공해야 할 분모 (커버리지 단위 축).
        summary["planned_unit_count"] = len(units)
        if not units:
            ctx.done(detail={"note": "매칭되는 계획 단위 없음"})
            return summary

        # 2) search — 단위별 SearchAgent 전수 스캔 병렬 분배 (캐시 지원).
        #    큰 단위는 청크로 쪼개 각 청크를 독립 SearchAgent 로 전수 읽는다.
        summaries = search_unit_summaries(
            model=model, client=client, ref=ref, run_id=ctx.run_id, units=units,
            observer=ctx.observer, emit_ctx=rev,
            cache_path=cache_path, reuse=reuse_summaries,
        )
        if not summaries:
            ctx.failed({"error": "단위 요약 전멸"})
            return summary

        # 3) reduce — 테마별 레포 문서 합성 (병렬) + critic + 저장
        return _reduce_and_save(
            ctx=ctx, client=client, model=model, ref=ref,
            repo_name=repo_name, themes=themes,
            summaries=summaries, summary=summary,
        )
