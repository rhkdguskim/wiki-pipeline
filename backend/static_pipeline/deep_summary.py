"""init map 단계 — 단위별 요약 에이전트를 병렬로 분배하는 오케스트레이션 레이어.

계획 단위(구간)마다 요약 에이전트 1개를 배정하고 병렬 실행한다
(골격은 common_pipeline.parallel.parallel_map).
이전 설계(단위를 25파일 그룹으로 재분할 -> 에이전트 폭증)가 너무 느려서, 단위당 1에이전트
+ 높은 병렬도로 단순화했다. 요약은 reduce 단계(레포 수준 테마 문서 합성)의 근거가 된다.

요약은 ref 기준으로 디스크에 캐시된다 — 프롬프트를 다듬으며 반복 실행할 때
map을 다시 돌리지 않는다 (--reuse-summaries).
"""
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import HumanMessage

from ..common.agent_spec import AgentSpec
from ..common.config import cached_settings
from ..common.graph import build_agent_graph
from ..common.run import final_text, run_graph
from ..common.textproc import strip_reasoning
from ..common_pipeline.deterministic_verifier import FORBIDDEN_WORDS
from ..common_pipeline.parallel import parallel_map
from .tools import make_tools

# 요약이 반드시 담아야 하는 항목 (프롬프트의 출력 계약과 일치).
_REQUIRED_SUMMARY_FIELDS = ("역할", "주요 컴포넌트", "의존", "기술")
_SUMMARY_MIN_CHARS = 120   # 이보다 짧으면 스캔 실패로 본다 (프롬프트는 400~900자 요구)
_SUMMARY_MAX_CHARS = 4000  # 이보다 길면 요약이 아니라 원문 나열일 가능성


def _max_concurrency() -> int:
    return cached_settings().static_map_concurrency  # 단위 요약 동시 실행 상한


def summary_quality_issue(summary: str) -> str | None:
    """단위 요약의 결정적 품질 검증. 문제가 있으면 사유, 정상이면 None.

    요약은 reduce(레포 문서 합성)의 유일한 근거라 여기서 걸러야 나쁜 요약이
    문서로 증폭되지 않는다. 검증은 LLM 없이 기계적으로: 필수 항목 존재·최소 길이·
    도구 호출 텍스트 유출·추측어. (사실성은 여기서 못 잡지만 형식·완결성은 잡는다.)
    """
    if not summary or not summary.strip():
        return "요약이 비었다 — 스캔 실패"
    text = summary.strip()
    if len(text) < _SUMMARY_MIN_CHARS:
        return f"요약이 너무 짧다 ({len(text)}자) — 스캔이 제대로 안 됨"
    if any(m in text for m in ("<tool_call>", "<invoke name=", "</invoke>")):
        return "요약에 도구 호출 텍스트가 섞였다 — 도구를 흉내내지 말 것"
    missing = [f for f in _REQUIRED_SUMMARY_FIELDS if f not in text]
    if missing:
        return f"필수 항목 누락: {', '.join(missing)} — 출력 계약의 항목을 모두 채울 것"
    for _lang, words in FORBIDDEN_WORDS.items():
        for w in words:
            if w in text:
                return f"추측어 '{w}' 사용 — 코드에서 관측한 사실만 쓸 것"
    return None


def _summary_prompt(unit_name: str, kind: str, root_path: str, files: list[str]) -> str:
    flist = "\n".join(f"  - {f}" for f in files[:80])
    more = f"\n  ... 외 {len(files)-80}개" if len(files) > 80 else ""
    return f"""당신은 코드베이스의 한 단위를 스캔해 **구조적 요약**을 만드는 분석가다.
이 요약은 나중에 저장소 전체의 기술문서(개요·요구사항·아키텍처·컴포넌트)를 합성하는 근거가 된다.

## 대상 단위
- 이름: **{unit_name}** ({kind})
- 경로: {root_path}
- 파일 ({len(files)}개):
{flist}{more}

## 방법
1. read_file / list_dir 도구로 **최대 8회** 읽는다. 우선순위: 저장소 문서(README·CONTRIBUTING 등)
   > 빌드/매니페스트 파일(언어 불문 — CMakeLists.txt, .sln/.csproj, package.json, pyproject.toml,
   go.mod, pom.xml, Dockerfile 등) > 공개 인터페이스/진입점(헤더, main, Program, index 등) > 설정 파일.
2. 같은 파일을 두 번 읽지 마라. 잘려도 앞부분으로 판단하라.
3. 코드에서 관측한 사실만 쓴다 — 추측 금지. 8회 도달 시 즉시 요약을 출력하라.

## 출력 (마크다운, 400~900자 — 반드시 이 항목 순서대로)
**역할**: 이 단위가 무엇을 하는가 (1~2문장)
**주요 컴포넌트**: 핵심 클래스/모듈/실행파일과 책임 (목록)
**의존·통신**: 다른 단위·라이브러리와의 관계, 사용하는 프로토콜 (관측된 것만)
**기술·플랫폼**: 언어/프레임워크/지원 OS/빌드 도구
**실행·설정**: 포트, 환경변수, 설정파일, 런타임/메모리/권한 요구 (관측된 것만 — 없으면 "관측 안 됨")
<think> 같은 사고 과정은 넣지 말고 요약 본문만 출력하라.
"""


def _summarize_unit(model, client, ref, run_id, unit: dict, observer, *,
                    emit_ctx=None):
    """단위 1개를 스캔해 요약을 만든다. 결정적 품질 검증 실패 시 1회 재시도.

    요약은 reduce 의 유일 근거라 형식/완결성을 여기서 거른다. 재시도해도 실패하면
    가장 나은(검증 통과했거나 마지막) 요약을 반환한다 — 요약 전멸을 막고 evidence
    pack + critic 이 2차로 방어한다. 반환은 (name, summary) 로 기존 계약 유지.
    """
    name = unit.get("name") or unit["root_path"]
    sys_prompt = _summary_prompt(name, unit.get("kind", ""), unit["root_path"], unit["_files"])
    ask = f"단위 '{name}'을 스캔해 구조적 요약을 출력하라."

    def _run(extra: str = "") -> str:
        spec = AgentSpec(
            pipeline_id="static",
            system_prompt=sys_prompt + extra,
            tools=make_tools(client, ref=ref),
            run_id=run_id, stage=f"map:{name}", max_steps=8,
        )
        graph = build_agent_graph(spec, model)
        final = run_graph(
            graph, {"messages": [HumanMessage(content=ask)]},
            observer, config={"recursion_limit": 30},
        )
        return strip_reasoning(final_text(final))

    summary = _run()
    issue = summary_quality_issue(summary)
    if issue is None:
        return name, summary

    # 검증 실패 — 지적 사항을 붙여 1회 재시도.
    if emit_ctx:
        emit_ctx("stage", "map", "running",
                 detail={"unit_retry": name, "reason": issue})
    retry_hint = (
        f"\n\n## 재작성 지시\n직전 요약이 검증에 실패했다: {issue}\n"
        "출력 계약(역할·주요 컴포넌트·의존·통신·기술·플랫폼·실행·설정)의 모든 항목을 "
        "채우고, 코드에서 관측한 사실만 400~900자로 요약하라."
    )
    retry_summary = _run(retry_hint)
    # 재시도본이 검증을 통과하면 그것, 아니면 더 긴 쪽(정보량이 많은 쪽)을 택한다.
    if summary_quality_issue(retry_summary) is None:
        return name, retry_summary
    best = retry_summary if len(retry_summary or "") > len(summary or "") else summary
    return name, best


def map_unit_summaries(
    *, model, client, ref, run_id, units: list[dict], observer, emit_ctx,
    cache_path: Path | None = None, reuse: bool = False,
) -> list[tuple[str, str]]:
    """단위별 요약 에이전트를 병렬 분배. [(unit_name, summary), ...] 반환.

    reuse=True고 캐시가 같은 ref면 map을 건너뛴다 (프롬프트 반복 개선용).
    """
    if reuse and cache_path and cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if data.get("ref") == ref and data.get("summaries"):
                emit_ctx("stage", "map", "done",
                         detail={"cached": True, "units": len(data["summaries"])})
                return [(s["unit"], s["summary"]) for s in data["summaries"]]
        except (json.JSONDecodeError, KeyError):
            pass  # 캐시 손상 -> 새로 스캔

    emit_ctx("stage", "map", "running", detail={"units": len(units), "concurrency": _max_concurrency()})
    results: list[tuple[str, str]] = []
    done = 0
    for u, res, exc in parallel_map(
            units,
            lambda u: _summarize_unit(model, client, ref, run_id, u, observer,
                                      emit_ctx=emit_ctx),
            max_workers=_max_concurrency()):
        uname = u.get("name") or u["root_path"]
        done += 1
        if exc is None:
            results.append(res)
            emit_ctx("stage", "map", "running",
                     progress={"n": done, "m": len(units), "unit": "unit"},
                     detail={"unit_done": uname})
        else:
            emit_ctx("stage", "map", "running",
                     progress={"n": done, "m": len(units), "unit": "unit"},
                     detail={"unit_failed": uname, "error": f"{type(exc).__name__}: {exc}"})

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(
            {"ref": ref, "summaries": [{"unit": u, "summary": s} for u, s in results]},
            ensure_ascii=False, indent=1), encoding="utf-8")
    emit_ctx("stage", "map", "done", detail={"summaries": len(results)})
    return results


def summaries_block(summaries: list[tuple[str, str]]) -> str:
    """reduce 단계 프롬프트에 넣을 단위 요약 묶음."""
    parts = [f"### 단위: {u}\n{s}" for u, s in sorted(summaries)]
    return "\n\n".join(parts)
