"""정적 파이프라인 init/backfill — 에이전트 주도 2단계 구조.

신규 등록 소스의 최초 문서화 (decision-registration-baseline: last_processed_sha=null).
디렉터리 깊이 하드코딩을 쓰지 않는다. 대신:
  1) 계획 단계 — 에이전트가 루트 트리를 탐색해 이 저장소에 맞는 '문서화 단위'를 스스로 결정
     (C++/C#/혼합 등 레포마다 다른 구조에 적응).
  2) 생성 단계 — 각 단위마다 기존 에이전트 루프로 문서 생성.
init은 등록 시 1회만 도는 별도 작업(정기 야간 diff 배치와 분리).
"""
from __future__ import annotations

import json
import re
import uuid

from langchain_core.messages import HumanMessage

from ..common import events as ev
from ..common.agent_spec import AgentSpec
from ..common.config import Settings
from ..common.graph import build_agent_graph
from ..common.llm import build_chat_model
from ..common.observer import Observer
from ..common.run import run_graph
from .deep_summary import map_summaries, summaries_block
from .generate import generate_with_critic
from .gitlab_client import GitLabClient
from .graph import build_deep_writer_graph, build_init_writer_graph
from .output import save_init_doc, submit_mr_stub
from .prompts import plan_system_prompt
from .state import StaticState
from .theme_mapping import filter_source_files, is_vendored

# init 기본 테마: 개요 중심 (단위 x 테마 폭발 방지). --themes 로 확장 가능.
_DEFAULT_INIT_THEMES = ["intro", "architecture-overview"]
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> dict:
    """에이전트 최종 응답에서 units JSON 추출.

    <think> 블록 제거 -> ```json 펜스 우선 -> 없으면 'units' 키를 포함하는
    가장 바깥 중괄호 블록을 균형 매칭으로 찾는다.
    """
    body = _THINK_RE.sub("", text)

    # 1) ```json ... ``` 펜스 우선
    for m in _FENCE_RE.finditer(body):
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict) and "units" in obj:
                return obj
        except json.JSONDecodeError:
            continue

    # 2) 'units'가 등장하는 위치에서 바깥 중괄호를 균형 매칭
    idx = body.find('"units"')
    if idx == -1:
        return {"units": []}
    start = body.rfind("{", 0, idx)
    if start == -1:
        return {"units": []}
    depth = 0
    for i in range(start, len(body)):
        if body[i] == "{":
            depth += 1
        elif body[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(body[start:i + 1])
                except json.JSONDecodeError:
                    return {"units": []}
    return {"units": []}


def _plan_units(settings, client, model, ref, run_id, observer, max_steps=8) -> list[dict]:
    """계획 단계: 에이전트가 루트 구조를 파악해 문서화 단위 목록을 낸다."""
    top = [e["path"] for e in client.list_tree(path="", ref=ref)]
    tools = _plan_tools(client, ref)
    spec = AgentSpec(
        pipeline_id="static", system_prompt=plan_system_prompt(ref, top),
        tools=tools, state_schema=StaticState, run_id=run_id,
        stage="plan", max_steps=max_steps,
    )
    graph = build_agent_graph(spec, model)
    final = run_graph(
        graph,
        {"messages": [HumanMessage(content="이 저장소의 문서화 단위를 계획해 JSON으로 출력하라.")],
         "theme": "plan", "changed_files": [], "from_sha": "", "to_sha": ref},
        observer, config={"recursion_limit": 25},
    )
    last = final["messages"][-1]
    text = last.content if isinstance(last.content, str) else str(last.content)
    units = _extract_json(text).get("units", [])
    # 서드파티로 판단되는 단위는 방어적으로 제외.
    return [u for u in units if u.get("root_path") and not is_vendored(u["root_path"])]


def _plan_tools(client, ref):
    from .tools import make_tools
    return make_tools(client, ref=ref)


def _files_under(all_paths: list[str], root_path: str) -> list[str]:
    """단위 root_path 아래의 소스 파일만 (서드파티·산출물 제외)."""
    root = root_path.rstrip("/")
    under = [p for p in all_paths if p == root or p.startswith(root + "/")]
    return filter_source_files(under)


def run_init(
    settings: Settings,
    *,
    ref: str | None = None,
    themes: list[str] | None = None,
    max_units: int | None = None,
    deep: bool = False,
) -> dict:
    run_id = "init-" + uuid.uuid4().hex[:8]
    observer = Observer(run_id, settings.out_path)
    client = GitLabClient(settings)
    model = build_chat_model(settings)
    themes = themes or _DEFAULT_INIT_THEMES
    summary: dict = {"run_id": run_id, "ref": None, "units": [], "docs": {}}

    def rev(layer, stage, status="running", progress=None, detail=None):
        observer.sink(ev.make_event(
            pipeline_id="static", run_id=run_id, layer=layer,
            stage=stage, status=status, progress=progress, detail=detail,
        ))

    try:
        ref = ref or client.default_branch()
        summary["ref"] = ref
        rev("run", "static-init", "running", detail={"ref": ref, "themes": themes})

        # 1) 계획 단계 (stage) — 에이전트가 단위 결정
        rev("stage", "plan", "running")
        planned = _plan_units(settings, client, model, ref, run_id, observer)
        rev("stage", "plan", "done",
            detail={"planned": [f"{u.get('name')}({u.get('root_path')})" for u in planned]})

        if not planned:
            rev("run", "static-init", "done", detail={"note": "계획 단위 없음"})
            return summary

        # 전체 트리(파일 목록)를 한 번만 확보해 단위별로 파일을 매칭.
        rev("stage", "list-tree", "running")
        tree = client.list_tree_all(ref=ref, recursive=True)
        all_paths = [e["path"] for e in tree if e.get("type") == "blob"]
        rev("stage", "list-tree", "done", detail={"blobs": len(all_paths)})

        # 계획 단위에 실제 파일을 붙이고, 매칭 0개(에이전트 경로 추정 오류)는 제외.
        # 파일 수 많은 순으로 정렬 (--max-units가 의미있는 큰 단위부터 고르도록).
        units = []
        dropped = []
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
            rev("run", "static-init", "done", detail={"note": "매칭되는 계획 단위 없음"})
            return summary

        # 2) 생성 단계 (engine_call) — 단위 x 테마
        #    deep: 단위마다 map(전체 병렬 요약) 1회 -> 요약을 테마별 reduce writer가 공유.
        #    normal: writer가 직접 read_file (작은 단위용).
        summary["warned"] = []
        total = len(units) * len(themes)
        done = 0
        for unit in units:
            name = unit.get("name") or unit["root_path"]
            root = unit["root_path"]
            files = unit["_files"]

            # deep: 이 단위 전체를 하위 그룹으로 병렬 스캔·요약 (테마 무관, 1회).
            unit_summaries = []
            summ_block = ""
            if deep and files:
                unit_summaries = map_summaries(
                    model=model, client=client, ref=ref, run_id=run_id,
                    unit=name, unit_root=root, files=files,
                    observer=observer, emit_ctx=rev,
                )
                summ_block = summaries_block(unit_summaries)

            for theme in themes:
                done += 1
                label = f"{name}:{theme}"
                rev("engine_call", label, "running",
                    progress={"n": done, "m": total, "unit": "unit-theme"})
                if not files:
                    rev("engine_call", label, "done",
                        progress={"n": done, "m": total, "unit": "unit-theme"},
                        detail={"skip": "소스 파일 없음"})
                    continue

                if deep:
                    def factory(_t=theme, _n=name, _sb=summ_block, _f=files):
                        return build_deep_writer_graph(
                            model=model, client=client, theme=_t, unit=_n, ref=ref,
                            summaries_block=_sb, source_files=_f, run_id=run_id,
                        )
                    base_prompt = (
                        f"단위 '{name}'의 '{theme}' 문서를 하위 그룹 요약을 근거로 종합해 작성하라. "
                        f"완성되면 frontmatter 포함 마크다운만 출력하라."
                    )
                else:
                    def factory(_t=theme, _n=name, _f=files):
                        return build_init_writer_graph(
                            model=model, client=client, theme=_t, unit=_n,
                            unit_files=_f, ref=ref, run_id=run_id,
                        )
                    base_prompt = (
                        f"단위 '{name}'({unit.get('kind','')}, {len(files)}개 파일)의 "
                        f"'{theme}' 문서를 처음부터 작성하라. 필요하면 도구로 코드를 읽고, "
                        f"완성되면 frontmatter 포함 마크다운만 출력하라."
                    )

                doc_md, verdict, warned = generate_with_critic(
                    model=model, client=client, theme=theme, ref=ref, run_id=run_id,
                    stage=label, writer_graph_factory=factory, base_prompt=base_prompt,
                    observer=observer, emit_ctx=rev,
                )
                path = save_init_doc(settings.out_path, name, theme, doc_md)
                mr = submit_mr_stub(label, path, settings.docshub_mr_enabled)
                summary["docs"][f"{name}/{theme}"] = {
                    "file": str(path), "chars": path.stat().st_size, "files": len(files),
                    "verdict": verdict.get("result"), "warned": warned,
                    "summaries": len(unit_summaries),
                }
                if warned:
                    summary["warned"].append(label)
                rev("engine_call", label, "done",
                    progress={"n": done, "m": total, "unit": "unit-theme"},
                    detail={"saved": str(path.relative_to(settings.out_path)),
                            "verdict": verdict.get("result"), "warned": warned, "mr": mr})

        rev("run", "static-init", "done",
            detail={"units": len(units), "docs": len(summary["docs"])})
        return summary
    except Exception as e:  # noqa: BLE001
        rev("run", "static-init", "failed",
            detail={"error": f"{type(e).__name__}: {e}"})
        raise
    finally:
        client.close()
        observer.close()
