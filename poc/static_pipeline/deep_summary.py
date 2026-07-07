"""deep init을 위한 map-reduce 요약.

큰 코드베이스 단위(수백~수천 파일)는 writer 1개가 read_file 몇 번으로 다 못 본다.
그래서 map-reduce:
  map   — 단위를 하위 그룹(서브폴더)으로 쪼개, 각 그룹을 요약 에이전트가 병렬로 요약.
  reduce — 하위 요약들을 합쳐 writer가 단위 문서를 합성 (요약이 근거).
원본 Docu-Automatic의 "순차 전용·병렬 금지" 약점(Explore §7-3)을 정면으로 개선한다.
토큰을 아끼지 않고 커버리지를 최대화하는 게 목적.
"""
from __future__ import annotations

import concurrent.futures
import uuid

from langchain_core.messages import HumanMessage

from ..common import events as ev
from ..common.agent_spec import AgentSpec
from ..common.graph import build_agent_graph
from ..common.run import run_graph
from .output import strip_reasoning
from .tools import make_tools

# 하위 그룹 하나에 담을 최대 파일 수. 너무 크면 요약이 얕아지고, 너무 작으면 에이전트가 폭증.
_GROUP_MAX_FILES = 25
# 병렬 요약 동시 실행 상한 (API rate·로컬 자원 고려).
_MAX_CONCURRENCY = 4


def _subgroup(files: list[str], unit_root: str) -> dict[str, list[str]]:
    """단위 파일을 바로 아래 하위 디렉터리(또는 파일 그 자체) 기준으로 그룹핑.

    unit_root 다음 세그먼트로 묶는다. 그룹이 여전히 크면 파일 수로 재분할.
    """
    root = unit_root.rstrip("/")
    depth = len(root.split("/")) if root and root != "(root)" else 0
    raw: dict[str, list[str]] = {}
    for f in files:
        parts = f.split("/")
        key = "/".join(parts[: depth + 1]) if len(parts) > depth + 1 else "/".join(parts[:-1]) or root
        raw.setdefault(key, []).append(f)

    # 큰 그룹은 파일 수로 재분할.
    out: dict[str, list[str]] = {}
    for key, fs in raw.items():
        if len(fs) <= _GROUP_MAX_FILES:
            out[key] = fs
        else:
            for i in range(0, len(fs), _GROUP_MAX_FILES):
                out[f"{key} [{i // _GROUP_MAX_FILES + 1}]"] = fs[i:i + _GROUP_MAX_FILES]
    return out


def _summary_prompt(unit: str, group: str, files: list[str]) -> str:
    flist = "\n".join(f"  - {f}" for f in files[:40])
    more = f"\n  ... 외 {len(files)-40}개" if len(files) > 40 else ""
    return f"""당신은 코드베이스의 한 부분을 읽고 **구조적 요약**을 만드는 분석가다.

## 대상
- 상위 단위: {unit}
- 이 그룹: {group} ({len(files)}개 파일)
- 파일:
{flist}{more}

## 방법
1. read_file / list_dir 도구로 **핵심 파일 위주로 최대 8회** 읽는다. 헤더(.h)·진입점·설정 파일 우선.
2. 코드에서 관측한 사실만 요약한다 — 추측 금지.

## 출력 (마크다운 요약, 300~600자)
- 이 그룹이 **무슨 역할**을 하는지
- **주요 클래스/함수/컴포넌트**와 책임
- **다른 그룹과의 의존/통신** 관계 (관측된 것만)
- 특이 사항(빌드·플랫폼·프로토콜 등)
<think> 같은 사고 과정은 넣지 말고 요약 본문만.
"""


def _summarize_group(model, client, ref, run_id, unit, group, files, observer):
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=_summary_prompt(unit, group, files),
        tools=make_tools(client, ref=ref),
        state_schema=_SummaryState, run_id=run_id,
        stage=f"summarize:{group}", max_steps=8,
    )
    graph = build_agent_graph(spec, model)
    final = run_graph(
        graph,
        {"messages": [HumanMessage(content=f"'{group}' 그룹을 요약하라.")]},
        observer, config={"recursion_limit": 30},
    )
    last = final["messages"][-1]
    text = last.content if isinstance(last.content, str) else str(last.content)
    return group, strip_reasoning(text)


from typing import Annotated, TypedDict  # noqa: E402
from langgraph.graph.message import add_messages  # noqa: E402


class _SummaryState(TypedDict):
    messages: Annotated[list, add_messages]


def map_summaries(
    *, model, client, ref, run_id, unit, unit_root, files, observer, emit_ctx,
) -> list[tuple[str, str]]:
    """단위를 하위 그룹으로 나눠 병렬 요약. [(group, summary), ...] 반환."""
    groups = _subgroup(files, unit_root)
    emit_ctx("engine_call", f"map:{unit}", "running",
             {"groups": len(groups), "files": len(files)})

    results: list[tuple[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_CONCURRENCY) as ex:
        futs = {
            ex.submit(_summarize_group, model, client, ref, run_id, unit, g, fs, observer): g
            for g, fs in groups.items()
        }
        for fut in concurrent.futures.as_completed(futs):
            g = futs[fut]
            try:
                results.append(fut.result())
            except Exception as e:  # noqa: BLE001
                emit_ctx("engine_call", f"map:{unit}", "running",
                         {"group": g, "error": f"{type(e).__name__}: {e}"})
    emit_ctx("engine_call", f"map:{unit}", "done", {"summaries": len(results)})
    return results


def summaries_block(summaries: list[tuple[str, str]]) -> str:
    """reduce 단계 프롬프트에 넣을 하위 요약 묶음."""
    parts = [f"### {g}\n{s}" for g, s in sorted(summaries)]
    return "\n\n".join(parts)
