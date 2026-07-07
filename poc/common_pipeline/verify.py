"""생성물 검증·재시도 공용 루프 — write -> 형식검증 -> lint -> critic -> 재시도.

정책(원본 Docu-Automatic 이식): 검증 fail 시 최대 2회 재작성, 초과 시 경고 태그 삽입 후
저장. 형식 검증(결정적)이 먼저 걸러 쓰레기 출력은 critic 비용 없이 재시도하고,
도구 호출 텍스트 유출은 다음 시도에서 도구를 떼어(no_tools) 구조적으로 차단한다.

파이프라인별 차이(writer 구성·결정적 lint·critic 프롬프트·근거 소스)는 콜러블로
주입받는다 — 이 계층은 파이프라인을 모른다 (agent_spec과 같은 계약).
"""
from __future__ import annotations

import re
from typing import Callable

from langchain_core.messages import HumanMessage

from ..common.run import final_text, run_graph
from ..common.textproc import extract_json_obj

MAX_RETRY = 2   # 원본 Hard Cap

# critic류 판정 요청의 표준 지시문 (두 파이프라인 공통).
CRITIC_ASK = ("이 문서를 3단계로 검증하라. 최종 출력은 반드시 JSON 오브젝트 하나만 — "
              "그 외 텍스트·설명·도구 호출 흉내 금지.")

# 모델이 도구 호출을 텍스트로 유출할 때 나타나는 마커 (공급자 무관).
_GARBAGE_MARKERS = ("<tool_call>", "<invoke name=", "</invoke>")
# 공급자별 내부 태그 형식(]<]provider[>[ 등)을 공급자 이름과 무관하게 매칭.
_PROVIDER_TAG_RE = re.compile(r"\]<\]\w+\[>\[")


def invalid_doc_reason(doc_md: str, *, fm_key: str = "theme:", min_len: int = 500) -> str | None:
    """문서 형식 검증 (결정적). 문제 있으면 사유 반환, 정상이면 None."""
    if any(g in doc_md for g in _GARBAGE_MARKERS) or _PROVIDER_TAG_RE.search(doc_md):
        return "출력에 도구 호출 텍스트가 섞였다 — 도구를 흉내내지 말고 문서만 출력할 것"
    if fm_key not in doc_md[:800]:
        return f"frontmatter({fm_key} 필드)가 문서 맨 앞에 없다"
    if len(doc_md) < min_len:
        return f"문서가 너무 짧다 ({len(doc_md)}자) — 완전한 문서를 출력할 것"
    if doc_md.count("```") % 2 != 0:
        return "코드 펜스(```)가 닫히지 않았다 — 문서가 중간에 잘린 것. 전체 문서를 완결해 출력할 것"
    tail = [ln.strip() for ln in doc_md.rstrip().splitlines()[-2:]]
    if tail and tail[-1].startswith("#"):
        return f"문서가 빈 섹션 헤딩({tail[-1][:40]!r})으로 끝난다 — 내용이 잘린 것. 완결해 출력할 것"
    return None


def apply_warn_tag(doc_md: str) -> str:
    """Hard Cap 초과 문서에 경고 태그 삽입 (원본 정책 — 버리지 않고 수동 검토로)."""
    warn_tag = "auto_generated_warning: 검증 미통과 - 수동 검토 필요"
    if doc_md.startswith("---"):
        return doc_md.replace("---", f"---\n{warn_tag}", 1)
    return f"---\n{warn_tag}\n---\n\n{doc_md}"


def run_json_verdict(
    graph_factory: Callable[..., object], observer, *,
    ask: str = CRITIC_ASK, key: str = "result", allowed: tuple = ("pass", "fail"),
    rounds: int = 3, recursion_limit: int = 20,
) -> dict:
    """critic류 판정 1건 실행 — JSON 파싱 실패 시 그래프 재생성·재시도 후 fail 처리.

    마지막 라운드는 도구 없이(no_tools) 실행 — 판정자가 탐색하다 JSON을 못 내는 것을
    구조적으로 차단한다 (writer의 no_tools 안전판과 같은 패턴). factory가 no_tools
    인자를 안 받으면 기본 그래프로 폴백.
    """
    for round_no in range(rounds):
        last_round = round_no == rounds - 1
        try:
            graph = graph_factory(no_tools=True) if last_round else graph_factory()
        except TypeError:
            graph = graph_factory()
        prompt = ask if not last_round else (
            ask + "\n\n[시스템] 도구 없이 지금까지의 근거만으로 즉시 JSON 판정만 출력하라.")
        final = run_graph(
            graph, {"messages": [HumanMessage(content=prompt)]},
            observer, config={"recursion_limit": recursion_limit},
        )
        verdict = extract_json_obj(final_text(final), key)
        if verdict.get(key) in allowed:
            return verdict
    return {"result": "fail",
            "feedback": [f"판정 JSON 파싱 실패 ({rounds}회) — 문서 형식 재점검 필요"]}


def verified_generate(
    *,
    write: Callable[[list[str], bool, str | None], str],  # (feedback, no_tools, prev_doc) -> doc_md
    critic: Callable[[str], dict],                     # (doc_md) -> verdict JSON
    lint: Callable[[str], list[str]] | None = None,    # 결정적 검증 (없으면 생략)
    lint_name: str = "lint",
    emit_ctx,                                          # (layer, stage, status=, progress=, detail=)
    stage: str,
    max_retry: int = MAX_RETRY,
    min_len: int = 500,
) -> tuple[str, dict, bool]:
    """write -> 형식검증 -> lint -> critic -> 재시도. (doc, verdict, warned) 반환.

    재시도는 재작성이 아니라 **수정**이다 — 직전의 형식 유효한 문서(prev_doc)를 피드백과
    함께 넘겨 지적 부분만 고치게 한다 (compose_write_prompt가 표준 조립을 제공).
    매번 처음부터 다시 쓰면 다른 곳에 새 오류가 생기는 두더지잡기가 된다.
    """
    feedback: list[str] = []
    doc_md = ""
    last_valid_doc: str | None = None   # 형식 검증을 통과한 마지막 draft
    verdict: dict = {"result": "unknown"}
    force_no_tools = False   # 도구 호출 텍스트 유출 후엔 도구를 떼고 재시도 (구조적 차단)

    for attempt in range(max_retry + 1):
        emit_ctx("engine_call", stage, "running",
                 detail={"phase": "write", "attempt": attempt + 1,
                         "no_tools": force_no_tools,
                         "mode": "edit" if last_valid_doc else "write"})
        doc_md = write(feedback, force_no_tools, last_valid_doc)

        # 0) 형식 검증 (결정적) — 쓰레기 출력이면 critic 없이 즉시 재시도.
        invalid = invalid_doc_reason(doc_md, min_len=min_len)
        if invalid:
            if "도구 호출 텍스트" in invalid:
                force_no_tools = True
            feedback = [f"[format] {invalid}"]
            emit_ctx("engine_call", stage, "running",
                     detail={"phase": "format", "verdict": "fail",
                             "reason": invalid, "attempt": attempt + 1})
            continue
        last_valid_doc = doc_md   # 형식 통과본만 수정 기반으로 삼는다

        # 1) 결정적 lint (mermaid 등 — 주입된 경우만).
        lint_errs = lint(doc_md) if lint else []
        if lint:
            emit_ctx("engine_call", stage, "running",
                     detail={"phase": lint_name,
                             "verdict": "pass" if not lint_errs else "fail",
                             "errors": lint_errs[:3], "attempt": attempt + 1})

        # 2) LLM critic (frontmatter + 적합성 + grounding — 프롬프트는 파이프라인 소유).
        emit_ctx("engine_call", stage, "running",
                 detail={"phase": "critic", "attempt": attempt + 1})
        verdict = critic(doc_md)

        if verdict.get("result") == "pass" and not lint_errs:
            emit_ctx("engine_call", stage, "running",
                     detail={"phase": "verify", "verdict": "pass", "attempt": attempt + 1})
            return doc_md, verdict, False

        # 실패 사유 합치기: lint 오류 + critic 피드백 -> writer 핀포인트 수정
        feedback = list(verdict.get("feedback", []) or [])
        if lint_errs:
            feedback = [f"[{lint_name}] {e}" for e in lint_errs] + feedback
        if not feedback:
            feedback = ["검증 실패 (사유 미상)"]
        verdict["lint_errors"] = lint_errs
        emit_ctx("engine_call", stage, "running",
                 detail={"phase": "verify", "verdict": "fail",
                         "feedback": feedback[:3], "attempt": attempt + 1})

    return apply_warn_tag(doc_md), verdict, True
