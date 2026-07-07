"""정적 파이프라인 init/backfill — 전체 레포 스캔 오케스트레이션.

신규 등록 소스의 최초 문서화 (decision-registration-baseline: last_processed_sha=null).
**저장소 전체에 대한 테마 문서**(intro·requirements·architecture-overview·
component-diagram)를 만든다 — 특정 레포 가정 없이 어떤 저장소든 동일하게 동작한다.

오케스트레이션 (구간별 에이전트 분배):
  1) 계획   — 에이전트가 레포 구조를 파악해 스캔 단위(구간)를 결정 (레포 구조 무관 적응)
  2) map    — 단위마다 요약 에이전트 1개, 병렬 실행 (deep_summary.py, 캐시 지원)
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
from ..common.llm import build_chat_model
from ..common.run import final_text, run_graph
from ..common.textproc import extract_json_obj
from ..common_pipeline.output import save_doc
from ..common_pipeline.parallel import parallel_map
from ..common_pipeline.run_context import RunContext
from ..connectors import connector_for_settings
from .deep_summary import map_unit_summaries, summaries_block
from .generate import generate_with_critic
from .graph import build_repo_writer_graph
from .pipeline_state import save_state
from .prompts import plan_system_prompt
from .theme_mapping import filter_source_files, is_vendored
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
        )
        path = save_doc(out_dir, theme, doc_md)
        mr = submit_mr_stub(theme, path, settings.docshub_mr_enabled)
        rev("engine_call", stage, "done",
            detail={"saved": str(path.relative_to(settings.out_path)),
                    "verdict": verdict.get("result"), "warned": warned, "mr": mr})
        return path, verdict, warned

    for theme, res, exc in parallel_map(themes, _gen_theme, max_workers=settings.static_reduce_concurrency):
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
        }
        if warned:
            summary["warned"].append(theme)

    # 래칫 사이드카 갱신 — 이번에 생성/유지된 테마의 판정을 기록 (pass는 다음 실행에서 유지됨).
    for theme, info in summary["docs"].items():
        if "error" not in info:
            prior[theme] = {"verdict": info.get("verdict"), "ref": ref,
                            "warned": info.get("warned", False)}
    try:
        verdicts_path.write_text(
            json.dumps(prior, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass

    # 상태 전진 — 전 테마가 (경고 포함) 저장됐을 때만 last_processed_sha를 기록한다.
    # 위키 계약(concept-idempotent-sha): 성공 후에만 전진, 실패 시 상태 불변 -> 재실행 안전.
    # state-advance 실패는 run 전체 실패로 취급한다 — 문서는 만들어졌어도 sha가
    # 전진하지 않으면 다음 실행이 같은 작업을 또 하게 되므로 "완료"로 보고하면 안 된다
    # (decision-state-advance-failure-propagates).
    ok_docs = [t for t, i in summary["docs"].items() if "error" not in i]
    if ok_docs and len(ok_docs) == len(themes):
        try:
            head_sha = client.resolve_ref(ref)
            sp = save_state(
                settings.out_path, project_id=settings.gitlab_project_id,
                last_processed_sha=head_sha, ref=ref, op="init",
                source_id=settings.source_id if settings.scm_sources_json else None,
                extra={"themes": ok_docs, "source_label": settings.source_label,
                       "source_kind": settings.source_kind},
            )
            summary["last_processed_sha"] = head_sha
            rev("stage", "state-advance", "done",
                detail={"last_processed_sha": head_sha[:12], "file": sp.name})
        except Exception as e:  # noqa: BLE001 — 이벤트로 남기고 run 실패로 전파(재발생)
            rev("stage", "state-advance", "failed",
                detail={"error": f"{type(e).__name__}: {e}"})
            raise
    else:
        rev("stage", "state-advance", "done",
            detail={"skipped": f"테마 {len(ok_docs)}/{len(themes)}만 성공 — sha 전진 안 함"})

    ctx.done(detail={"units": len(summary.get("units", [])),
                     "docs": list(summary["docs"].keys()), "warned": summary["warned"]})
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
        all_paths = [e["path"] for e in tree if e.get("type") == "blob"]
        rev("stage", "list-tree", "done", detail={"blobs": len(all_paths)})

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
        if not units:
            ctx.done(detail={"note": "매칭되는 계획 단위 없음"})
            return summary

        # 2) map — 단위별 요약 에이전트 병렬 분배 (캐시 지원)
        summaries = map_unit_summaries(
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
