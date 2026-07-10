"""init SearchAgent 단계 — 단위를 전수 스캔해 구조적 요약을 만드는 오케스트레이션.

설계(2026-07-10 재설계): init 은 **모든 소스 파일을 빠짐없이 읽는다**. 토큰이 많이
들더라도 init(최초 baseline)은 전수 스캔이 원칙이다 — 샘플링(예전 단위당 8회 read)은
큰 단위의 뒷부분을 놓쳐 문서 품질의 상한을 깎았다.

전수 스캔을 에이전트/컨텍스트 분리로 구현한다:

    단위(unit) — 파일 N개
      └ CHUNK_FILES(설정) 개씩 서브청크로 분할
          └ 각 청크: **SearchAgent 1개**(독립 그래프·독립 context)가 청크 내 모든
            파일을 read_file 로 빠짐없이 읽고 청크 요약을 낸다.
      └ 청크가 2개 이상이면 SummaryComposer 가 청크 요약들을 단위 요약으로 합성한다.

에이전트를 청크 단위로 분리하는 이유: 한 context 에 수십~수백 파일을 밀어넣으면
초반 파일이 밀려나 실질적으로 안 읽힌다. 청크마다 독립 context 를 주면 각 파일이
반드시 어느 SearchAgent 의 예산 안에서 읽힌다 — 이것이 전수 스캔의 실질 보장이다.

요약은 ref 기준으로 디스크에 캐시된다 (--reuse-summaries): 프롬프트를 다듬으며
반복 실행할 때 SearchAgent 재실행을 피한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import HumanMessage

from ..common.agent_spec import AgentSpec
from ..common.config import cached_settings
from ..common.graph import build_agent_graph
from ..common.llm_gate import effective_parallelism
from ..common.run import final_text, run_graph
from ..common.textproc import strip_reasoning
from ..common_pipeline.deterministic_verifier import FORBIDDEN_WORDS
from ..common_pipeline.parallel import parallel_map
from .tools import make_tools

# 요약이 반드시 담아야 하는 항목 (프롬프트의 출력 계약과 일치).
_REQUIRED_SUMMARY_FIELDS = ("역할", "주요 컴포넌트", "의존", "기술")
_SUMMARY_MIN_CHARS = 120   # 이보다 짧으면 스캔 실패로 본다 (프롬프트는 400~900자 요구)


def _max_concurrency() -> int:
    settings = cached_settings()
    return effective_parallelism(settings.static_map_concurrency)


def _chunk_files() -> int:
    return max(1, cached_settings().static_search_chunk_files)  # 청크당 파일 수 상한


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


def _split_chunks(files: list[str], size: int) -> list[list[str]]:
    """파일 목록을 size 개씩 서브청크로 나눈다 (전수 커버 — 버리는 파일 없음)."""
    return [files[i:i + size] for i in range(0, len(files), size)] or [[]]


def _search_prompt(unit_name: str, kind: str, root_path: str,
                   files: list[str], *, chunk_idx: int, chunk_total: int) -> str:
    flist = "\n".join(f"  - {f}" for f in files)
    part = f" (파트 {chunk_idx}/{chunk_total})" if chunk_total > 1 else ""
    return f"""당신은 코드베이스의 한 구획을 **전수 조사**하는 SearchAgent 다.
이 요약은 나중에 저장소 전체의 기술문서(개요·요구사항·아키텍처·컴포넌트)를 합성하는 근거가 된다.

## 대상 단위{part}
- 이름: **{unit_name}** ({kind})
- 경로: {root_path}
- 이 파트가 맡은 파일 ({len(files)}개) — **아래 파일을 하나도 빠짐없이 read_file 로 읽어라**:
{flist}

## 방법 (전수 스캔 — 샘플링 금지)
1. 위 목록의 **모든 파일**을 read_file 로 읽는다. 파일이 잘려 나오면(생략 표시) 앞부분으로 판단하되,
   목록의 다른 파일을 건너뛰지 마라 — 전부 읽는 것이 이 에이전트의 임무다.
2. 같은 파일을 두 번 읽지 마라. 읽은 파일 수만큼 도구를 호출하면 된다.
3. 코드에서 **관측한 사실만** 쓴다 — 추측 금지. "일반적으로/보통/아마" 같은 추측어 금지.
4. 목록의 모든 파일을 읽은 뒤 즉시 요약을 출력하라.

## 출력 (마크다운, 400~900자 — 반드시 이 항목 순서대로)
**역할**: 이 구획이 무엇을 하는가 (1~2문장)
**주요 컴포넌트**: 핵심 클래스/모듈/실행파일과 책임 (목록)
**의존·통신**: 다른 단위·라이브러리와의 관계, 사용하는 프로토콜 (관측된 것만)
**기술·플랫폼**: 언어/프레임워크/지원 OS/빌드 도구
**실행·설정**: 포트, 환경변수, 설정파일, 런타임/메모리/권한 요구 (관측된 것만 — 없으면 "관측 안 됨")
<think> 같은 사고 과정은 넣지 말고 요약 본문만 출력하라.
"""


def _compose_prompt(unit_name: str, chunk_summaries: list[str]) -> str:
    joined = "\n\n".join(f"### 파트 {i+1} 요약\n{s}"
                         for i, s in enumerate(chunk_summaries))
    return f"""당신은 SummaryComposer 다. 한 단위를 여러 SearchAgent 가 파트별로 전수 조사한
요약들을 받아, **단위 전체의 구조적 요약 하나**로 종합한다.

## 대상 단위: {unit_name}
아래는 이 단위를 파트별로 나눠 조사한 요약들이다. 이들을 통합하되, 어느 파트에도
없는 내용을 지어내지 마라 (파트 요약이 유일한 근거다).

{joined}

## 출력 (마크다운, 400~900자 — 반드시 이 항목 순서대로, 파트들을 통합)
**역할**: 이 단위가 무엇을 하는가 (1~2문장)
**주요 컴포넌트**: 핵심 클래스/모듈/실행파일과 책임 (목록 — 파트별 컴포넌트 통합)
**의존·통신**: 다른 단위·라이브러리와의 관계, 프로토콜 (관측된 것만)
**기술·플랫폼**: 언어/프레임워크/지원 OS/빌드 도구
**실행·설정**: 포트, 환경변수, 설정파일, 런타임/권한 요구 (관측된 것만 — 없으면 "관측 안 됨")
<think> 같은 사고 과정은 넣지 말고 요약 본문만 출력하라.
"""


# 청크의 파일을 몇 %까지 읽으면 전수 스캔으로 인정할지 (나머지는 재시도로 보강).
_COVERAGE_OK = 0.95


def _run_search_agent(model, client, ref, run_id, unit_name, kind, root_path,
                      files, observer, *, chunk_idx, chunk_total, emit_ctx=None):
    """청크 1개를 독립 SearchAgent(독립 context)로 전수 읽어 청크 요약 반환.

    전수 스캔을 프롬프트에만 맡기지 않고 **결정적으로 보장**한다:
    read_file 이 실제로 읽은 경로를 read_log 로 추적해, 청크 목록 대비 커버리지가
    _COVERAGE_OK 미만이면 **안 읽은 파일 목록을 명시해 한 번 더** 에이전트를 돌린다
    (누적 read_log). max_steps 도 파일 수 + 여유로 잡아 목록 전체를 읽을 예산을 준다.
    이전의 고정 8회 샘플링과 근본적으로 다른 지점 — init 은 모든 파일을 읽는다.
    """
    label = unit_name if chunk_total == 1 else f"{unit_name}#{chunk_idx}"
    read_log: set[str] = set()

    def _once(target_files: list[str], *, missing: list[str] | None = None) -> str:
        budget = len(target_files) + 3   # 파일 수만큼 read + 마무리 여유
        prompt = _search_prompt(unit_name, kind, root_path, files,
                                chunk_idx=chunk_idx, chunk_total=chunk_total)
        if missing:
            mlist = "\n".join(f"  - {m}" for m in missing)
            prompt += (f"\n\n## 아직 안 읽은 파일 (반드시 먼저 read_file 하라)\n{mlist}\n")
        spec = AgentSpec(
            pipeline_id="static",
            system_prompt=prompt,
            tools=make_tools(client, ref=ref, read_log=read_log),
            run_id=run_id, stage=f"search:{label}", max_steps=budget,
        )
        graph = build_agent_graph(spec, model)
        final = run_graph(
            graph,
            {"messages": [HumanMessage(
                content=f"구획 '{label}'의 모든 파일을 읽고 구조적 요약을 출력하라.")]},
            observer, config={"recursion_limit": 2 * budget + 10},
        )
        return strip_reasoning(final_text(final))

    summary = _once(files)
    read_target = {f for f in files}
    covered = len(read_log & read_target)
    if files and covered / len(files) < _COVERAGE_OK:
        missing = [f for f in files if f not in read_log]
        if emit_ctx:
            emit_ctx("stage", "search", "running",
                     detail={"chunk_undercovered": label,
                             "read": covered, "total": len(files),
                             "missing_sample": missing[:5]})
        # 안 읽은 파일을 명시해 보강 스캔 — read_log 는 누적되므로 커버리지가 올라간다.
        summary = _once(missing, missing=missing)
    return summary


def _summarize_unit(model, client, ref, run_id, unit: dict, observer, *,
                    emit_ctx=None):
    """단위 1개를 전수 스캔해 요약을 만든다.

    단위 파일을 CHUNK_FILES 개씩 청크로 쪼개 각 청크에 SearchAgent 1개(독립 context)를
    배정한다. 청크가 여러 개면 SummaryComposer 가 청크 요약을 단위 요약으로 합성한다.
    최종 요약이 결정적 검증을 통과 못하면 1회 재시도(합성 단계에서). 반환은 (name, summary).
    """
    name = unit.get("name") or unit["root_path"]
    kind = unit.get("kind", "")
    root_path = unit["root_path"]
    files = unit["_files"]
    chunks = _split_chunks(files, _chunk_files())
    total = len(chunks)

    # 각 청크를 독립 SearchAgent 로 전수 스캔 (단위 내부에서도 병렬).
    chunk_summaries: list[str] = []
    if total == 1:
        chunk_summaries.append(_run_search_agent(
            model, client, ref, run_id, name, kind, root_path, chunks[0],
            observer, chunk_idx=1, chunk_total=1, emit_ctx=emit_ctx))
    else:
        if emit_ctx:
            emit_ctx("stage", "search", "running",
                     detail={"unit": name, "files": len(files), "chunks": total})
        for cs, res, exc in parallel_map(
                list(enumerate(chunks, 1)),
                lambda ic: _run_search_agent(
                    model, client, ref, run_id, name, kind, root_path, ic[1],
                    observer, chunk_idx=ic[0], chunk_total=total, emit_ctx=emit_ctx),
                max_workers=min(total, _max_concurrency())):
            if exc is None and res:
                chunk_summaries.append(res)
            elif emit_ctx:
                emit_ctx("stage", "search", "running",
                         detail={"unit": name, "chunk_failed": cs[0],
                                 "error": f"{type(exc).__name__}: {exc}" if exc else "빈 결과"})

    if not chunk_summaries:
        return name, ""

    # 청크 1개면 그 요약이 곧 단위 요약. 여러 개면 SummaryComposer 로 합성.
    if len(chunk_summaries) == 1:
        summary = chunk_summaries[0]
    else:
        summary = _compose_unit_summary(model, run_id, name, chunk_summaries, observer)

    issue = summary_quality_issue(summary)
    if issue is None:
        return name, summary

    # 검증 실패 — 합성을 1회 재시도(청크 요약은 유효하므로 재스캔은 안 함).
    if emit_ctx:
        emit_ctx("stage", "search", "running",
                 detail={"unit_retry": name, "reason": issue})
    retry = _compose_unit_summary(model, run_id, name, chunk_summaries, observer,
                                  hint=issue)
    if summary_quality_issue(retry) is None:
        return name, retry
    best = retry if len(retry or "") > len(summary or "") else summary
    return name, best


def _compose_unit_summary(model, run_id, unit_name, chunk_summaries, observer,
                          *, hint: str = "") -> str:
    """청크 요약들을 단위 요약 하나로 합성 (SummaryComposer, 도구 없음)."""
    prompt = _compose_prompt(unit_name, chunk_summaries)
    if hint:
        prompt += (f"\n\n## 재작성 지시\n직전 합성이 검증에 실패했다: {hint}\n"
                   "출력 계약의 모든 항목을 채워 400~900자로 다시 작성하라.")
    spec = AgentSpec(
        pipeline_id="static",
        system_prompt=prompt, tools=[],
        run_id=run_id, stage=f"compose:{unit_name}", max_steps=1,
    )
    graph = build_agent_graph(spec, model)
    final = run_graph(
        graph, {"messages": [HumanMessage(content=f"단위 '{unit_name}' 요약을 합성해 출력하라.")]},
        observer, config={"recursion_limit": 6},
    )
    return strip_reasoning(final_text(final))


def search_unit_summaries(
    *, model, client, ref, run_id, units: list[dict], observer, emit_ctx,
    cache_path: Path | None = None, reuse: bool = False,
) -> list[tuple[str, str]]:
    """단위별 SearchAgent 전수 스캔을 병렬 분배. [(unit_name, summary), ...] 반환.

    reuse=True고 캐시가 같은 ref면 전수 스캔을 건너뛴다 (프롬프트 반복 개선용).
    """
    if reuse and cache_path and cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if data.get("ref") == ref and data.get("summaries"):
                emit_ctx("stage", "search", "done",
                         detail={"cached": True, "units": len(data["summaries"])})
                return [(s["unit"], s["summary"]) for s in data["summaries"]]
        except (json.JSONDecodeError, KeyError):
            pass  # 캐시 손상 -> 새로 스캔

    total_files = sum(len(u.get("_files") or []) for u in units)
    emit_ctx("stage", "search", "running",
             detail={"units": len(units), "files": total_files,
                     "concurrency": _max_concurrency(),
                     "chunk_files": _chunk_files()})
    results: list[tuple[str, str]] = []
    done = 0
    for u, res, exc in parallel_map(
            units,
            lambda u: _summarize_unit(model, client, ref, run_id, u, observer,
                                      emit_ctx=emit_ctx),
            max_workers=_max_concurrency()):
        uname = u.get("name") or u["root_path"]
        done += 1
        if exc is None and res and res[1]:
            results.append(res)
            emit_ctx("stage", "search", "running",
                     progress={"n": done, "m": len(units), "unit": "unit"},
                     detail={"unit_done": uname, "files": len(u.get("_files") or [])})
        else:
            emit_ctx("stage", "search", "running",
                     progress={"n": done, "m": len(units), "unit": "unit"},
                     detail={"unit_failed": uname,
                             "error": f"{type(exc).__name__}: {exc}" if exc else "빈 요약"})

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(
            {"ref": ref, "summaries": [{"unit": u, "summary": s} for u, s in results]},
            ensure_ascii=False, indent=1), encoding="utf-8")
    emit_ctx("stage", "search", "done", detail={"summaries": len(results)})
    return results


def summaries_block(summaries: list[tuple[str, str]]) -> str:
    """reduce 단계 프롬프트에 넣을 단위 요약 묶음."""
    parts = [f"### 단위: {u}\n{s}" for u, s in sorted(summaries)]
    return "\n\n".join(parts)
