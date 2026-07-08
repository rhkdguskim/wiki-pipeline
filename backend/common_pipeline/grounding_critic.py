"""Grounding Critic — writer 산출물이 evidence 에 의해 지지되는지 판단하는 LLM critic.

raw/2026-07-08-ai-agent-output-quality-plan.md §5 Grounding Critic 의 구현.

기존 critic(prompts.critic_prompt/manual_critic_prompt)는 9,000자 단절(``doc_markdown[:9000]``)
로 인해 긴 문서의 뒷부분을 검증하지 못한다. chunked_critic 는 문서를 섹션 단위로 쪼개
각 chunk 마다 critic 를 돌린 뒤 verdict 를 합산한다 — 9k 한계를 구조적으로 해결한다.

출력 verdict schema (raw 설계서 §5):
    {"result": "pass"|"fail", "score": float,
     "blocking_findings": [{"severity", "claim", "reason", "required_fix", "evidence_refs"}],
     "nonblocking_notes": [...]}

이 모듈은 prompt 조립·파싱·chunk 분배까지만 담당한다 — 실제 LLM 호출은 critic_fn
callable 로 주입받는다 (테스트 가능성·의존 역전).
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

# 한 chunk 의 최대 문자 수 — 9k 한계보다 여유 있게 6k. evidence_block 과 합쳐져도
# LLM context 에 들어가도록. 원 설계서 §5 chunked_critic 의 기본값.
DEFAULT_CHUNK_SIZE = 6000

# critic system prompt — writer 프롬프트와 반대로 설계 (raw 설계서 §Prompt Contract).
_CRITIC_SYSTEM = """당신은 생성된 문서를 검증하는 적대적(adversarial) QA critic 이다.
writer 가 아니라 critic 이다 — 문서를 칭찬하지 말고, 사실·계약 위반을 찾아라.

## 작업
주어진 문서 chunk 가 아래 근거 블록에 의해 **지지되는지** 판단한다.
- 근거에 없는 UI label/API endpoint/설정값/수치/동작 서술 = hallucination (blocker).
- theme contract(perspective/audience/must_cover/do_not_cover) 위반 = major.
- 문체·구조·중복 = minor.

## 통과 기준
- blocker 0
- theme contract 위반 0 (major 0)
- score >= 0.82

## 출력 (반드시 JSON 오브젝트 하나만, 그 외 텍스트/도구 호출 금지)
{"result": "pass"|"fail", "score": 0.0~1.0,
 "blocking_findings": [{"severity": "blocker|major|minor",
                         "claim": "문서의 문제 되는 주장",
                         "reason": "왜 근거에 의해 지지되지 않는가",
                         "required_fix": "구체적 수정 지시",
                         "evidence_refs": ["e1", "o2"]}],
 "nonblocking_notes": ["경미한 제안"]}
"""

# chunk 마다 덧붙이는 user prompt 템플릿.
_CRITIC_USER_TMPL = """## 테마 계약 (검증 기준)
{theme_contract}

## 근거 블록 (사실의 유일한 원천)
{evidence_block}

## 검증 대상 문서 chunk ({chunk_label})
```markdown
{chunk}
```

위 chunk 가 근거에 의해 지지되는지 JSON 판정만 출력하라."""


def format_critic_prompt(
    doc_content: str,
    evidence_block: str,
    theme_contract: dict | str,
) -> list[dict]:
    """LLM 에 보낼 messages 목록을 반환 (OpenAI 호환 role/content).

    theme_contract 는 ThemeSpec.brief() 문자열이거나 dict(perspective/audience/
    must_cover/do_not_cover 키). 문자열이면 그대로, dict 이면 직렬화해 user prompt 에
    포함한다.
    """
    if isinstance(theme_contract, dict):
        contract_lines = []
        for key in ("id", "name", "perspective", "audience", "writing_style",
                    "must_cover", "do_not_cover"):
            val = theme_contract.get(key)
            if not val:
                continue
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            contract_lines.append(f"- {key}: {val}")
        contract_str = "\n".join(contract_lines) or "(theme contract 없음)"
    else:
        contract_str = str(theme_contract or "(theme contract 없음)")

    user = _CRITIC_USER_TMPL.format(
        theme_contract=contract_str,
        evidence_block=evidence_block or "(근거 없음)",
        chunk_label="전체",
        chunk=doc_content[:9000],  # 단일 호출 fallback — chunked_critic 쓰면 분할됨
    )
    return [
        {"role": "system", "content": _CRITIC_SYSTEM},
        {"role": "user", "content": user},
    ]


def parse_critic_verdict(raw_response: str) -> dict:
    """LLM 응답에서 verdict schema 를 파싱. 실패 시 fail+빈 findings 로 폴백.

    LLM 이 서술·펜스·think 블록에 JSON 을 싸서 내는 경우를 모두 처리한다.
    """
    if not raw_response:
        return _empty_verdict("빈 응답")

    # 1차: 전체에서 JSON 오브젝트 추출 (common.textproc.extract_json_obj 패턴 이식).
    obj = _extract_first_json(raw_response)
    if obj is None:
        return _empty_verdict("JSON 파싱 실패")

    result = str(obj.get("result") or "").lower()
    if result not in ("pass", "fail"):
        result = "fail"

    score = obj.get("score")
    try:
        score_f = float(score) if score is not None else (1.0 if result == "pass" else 0.0)
    except (TypeError, ValueError):
        score_f = 1.0 if result == "pass" else 0.0

    blocking = _coerce_findings(obj.get("blocking_findings"))
    nonblocking = obj.get("nonblocking_notes") or []
    if not isinstance(nonblocking, list):
        nonblocking = [str(nonblocking)]

    # severity 정규화 — blocker/major/minor 외 값은 minor 로.
    for f in blocking:
        sev = str(f.get("severity") or "minor").lower()
        if sev not in ("blocker", "major", "minor"):
            sev = "minor"
        f["severity"] = sev

    return {
        "result": result,
        "score": score_f,
        "blocking_findings": blocking,
        "nonblocking_notes": [str(n) for n in nonblocking],
    }


def _extract_first_json(text: str) -> dict | None:
    """text 에서 첫 번째 {"result": ...} JSON 오브젝트를 회수."""
    # 1. ```json ... ``` 펜스
    for m in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    # 2. key 주변 중괄호 매칭 (extract_json_obj 와 같은 패턴).
    for needle in ('"result"', "'result'", "result"):
        idx = text.find(needle)
        if idx < 0:
            continue
        start = text.rfind("{", 0, idx)
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict):
                        return obj
                    break
    return None


def _coerce_findings(raw: Any) -> list[dict]:
    """blocking_findings 를 list[dict] 로 정규화."""
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for f in raw:
        if isinstance(f, str):
            f = {"severity": "minor", "reason": f}
        if not isinstance(f, dict):
            continue
        out.append({
            "severity": str(f.get("severity") or "minor"),
            "claim": str(f.get("claim") or ""),
            "reason": str(f.get("reason") or ""),
            "required_fix": str(f.get("required_fix") or ""),
            "evidence_refs": list(f.get("evidence_refs") or []),
        })
    return out


def _empty_verdict(reason: str) -> dict:
    """파싱 실패 폴백 — fail + 이유를 nonblocking_notes 에 남긴다."""
    return {
        "result": "fail",
        "score": 0.0,
        "blocking_findings": [{
            "severity": "major",
            "claim": "(critic 응답 파싱 불가)",
            "reason": reason,
            "required_fix": "critic 응답이 JSON schema 를 따르는지 확인",
            "evidence_refs": [],
        }],
        "nonblocking_notes": [],
    }


def _split_into_chunks(doc: str, chunk_size: int) -> list[tuple[str, str]]:
    """문서를 ## 섹션 단위로 chunk_size 에 맞춰 분할.

    반환: [(chunk_label, chunk_text), ...]
    한 섹션이 chunk_size 를 넘으면 그 섹션 안에서 줄 단위로 추가 분할한다.
    """
    if len(doc) <= chunk_size:
        return [("전체", doc)]

    # ## 헤딩으로 섹션 분할 — 헤딩 라인을 섹션 시작으로 취급.
    sections: list[tuple[str, str]] = []
    current_title = "(서문)"
    current_lines: list[str] = []
    sections_data: list[tuple[str, list[str]]] = []

    for ln in doc.splitlines(keepends=True):
        m = re.match(r"(?m)^##\s+(.+?)$", ln.rstrip("\n"))
        if m:
            if current_lines:
                sections_data.append((current_title, current_lines))
            current_title = m.group(1).strip()
            current_lines = [ln]
        else:
            current_lines.append(ln)
    if current_lines:
        sections_data.append((current_title, current_lines))

    # 섹션들을 chunk_size 이하로 병합.
    chunks: list[tuple[str, str]] = []
    buf_lines: list[str] = []
    buf_label_parts: list[str] = []
    buf_len = 0

    def _flush() -> None:
        nonlocal buf_lines, buf_label_parts, buf_len
        if buf_lines:
            label = "+".join(buf_label_parts[:3]) if buf_label_parts else "(chunk)"
            if len(buf_label_parts) > 3:
                label += f" 외 {len(buf_label_parts) - 3}"
            chunks.append((label, "".join(buf_lines)))
        buf_lines, buf_label_parts, buf_len = [], [], 0

    for title, lines in sections_data:
        section_text = "".join(lines)
        # 단일 섹션이 chunk_size 초과면 줄 단위로 잘라 별도 chunk.
        if len(section_text) > chunk_size:
            _flush()
            sub_lines: list[str] = []
            sub_len = 0
            for ln in lines:
                if sub_len + len(ln) > chunk_size and sub_lines:
                    chunks.append((f"{title} (부분)", "".join(sub_lines)))
                    sub_lines, sub_len = [], 0
                sub_lines.append(ln)
                sub_len += len(ln)
            if sub_lines:
                chunks.append((f"{title} (부분)", "".join(sub_lines)))
            continue

        if buf_len + len(section_text) > chunk_size and buf_lines:
            _flush()

        buf_lines.extend(lines)
        buf_label_parts.append(title)
        buf_len += len(section_text)

    _flush()
    return chunks or [("전체", doc)]


def _aggregate_verdicts(verdicts: list[dict]) -> dict:
    """chunk 별 verdict 를 하나로 합친다.

    - result: 모든 chunk pass 면 pass, 하나라도 fail 이면 fail.
    - score: chunk score 의 최소값 (가장 약한 chunk 기준).
    - blocking_findings: 모든 chunk 의 blocking_findings 병합.
    - nonblocking_notes: 모든 chunk 의 notes 병합.
    """
    if not verdicts:
        return _empty_verdict("chunk verdict 없음")

    overall = "pass" if all(v.get("result") == "pass" for v in verdicts) else "fail"
    scores = [v.get("score", 0.0) for v in verdicts]
    min_score = min(scores) if scores else 0.0

    all_blocking: list[dict] = []
    all_notes: list[str] = []
    for v in verdicts:
        all_blocking.extend(v.get("blocking_findings") or [])
        all_notes.extend(v.get("nonblocking_notes") or [])

    return {
        "result": overall,
        "score": min_score,
        "blocking_findings": all_blocking,
        "nonblocking_notes": all_notes,
        "chunk_count": len(verdicts),
    }


def chunked_critic(
    doc_content: str,
    evidence_block: str,
    theme_contract: dict | str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    critic_fn: Callable[[list[dict]], str] | None = None,
) -> dict:
    """문서를 chunk 단위로 분할해 critic 를 돌리고 verdict 를 합산한다.

    9k 단절 한계를 구조적으로 해결한다 — 긴 문서도 전체가 검증된다.

    Parameters
    ----------
    doc_content:
        검증 대상 문서 전체.
    evidence_block:
        critic prompt 에 들어갈 근거 블록 텍스트 (evidence_builder.evidence_block_text
        또는 observation log.evidence_block 출력).
    theme_contract:
        ThemeSpec.brief() 문자열 또는 dict.
    chunk_size:
        한 chunk 의 최대 문자 수. 기본 6000.
    critic_fn:
        messages list 를 받아 LLM raw 응답(str) 을 반환하는 callable.
        None 이면 critic 를 호출하지 않고 parse 불가능한 sentinel verdict 를 반환한다
        (테스트나 LLM 미연결 시 사용 — 실 운영에서는 반드시 주입해야 한다).

    Returns
    -------
    dict
        {"result", "score", "blocking_findings", "nonblocking_notes", "chunk_count"}
    """
    chunks = _split_into_chunks(doc_content, chunk_size)

    if critic_fn is None:
        # LLM 호출이 불가능하면 chunk 분할은 됐다는 정보만 남기고 fail 폴백.
        return {
            **_empty_verdict("critic_fn 미주입 — LLM 호출 없이 chunked 분할만 수행"),
            "chunk_count": len(chunks),
        }

    verdicts: list[dict] = []
    for label, chunk_text in chunks:
        messages = _build_chunk_messages(
            chunk_text, evidence_block, theme_contract, label,
        )
        try:
            raw = critic_fn(messages)
        except Exception as e:  # noqa: BLE001 — critic 한 chunk 실패해도 계속
            raw = json.dumps({"result": "fail", "score": 0.0,
                              "blocking_findings": [{
                                  "severity": "major",
                                  "claim": f"chunk {label} critic 호출 실패",
                                  "reason": f"{type(e).__name__}: {e}",
                                  "required_fix": "LLM 호출 안정성 점검",
                                  "evidence_refs": [],
                              }], "nonblocking_notes": []})
        verdicts.append(parse_critic_verdict(raw))

    return _aggregate_verdicts(verdicts)


def _build_chunk_messages(
    chunk_text: str, evidence_block: str,
    theme_contract: dict | str, label: str,
) -> list[dict]:
    """단일 chunk 용 messages 조립 — format_critic_prompt 와 같은 schema."""
    if isinstance(theme_contract, dict):
        contract_lines = []
        for key in ("id", "name", "perspective", "audience", "writing_style",
                    "must_cover", "do_not_cover"):
            val = theme_contract.get(key)
            if not val:
                continue
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            contract_lines.append(f"- {key}: {val}")
        contract_str = "\n".join(contract_lines) or "(theme contract 없음)"
    else:
        contract_str = str(theme_contract or "(theme contract 없음)")

    user = _CRITIC_USER_TMPL.format(
        theme_contract=contract_str,
        evidence_block=evidence_block or "(근거 없음)",
        chunk_label=label,
        chunk=chunk_text,
    )
    return [
        {"role": "system", "content": _CRITIC_SYSTEM},
        {"role": "user", "content": user},
    ]


def severity_counts(verdict: dict) -> dict[str, int]:
    """verdict 의 blocking_findings 를 severity 별로 count. quality gate 용."""
    counts = {"blocker": 0, "major": 0, "minor": 0}
    for f in verdict.get("blocking_findings") or []:
        sev = str(f.get("severity") or "minor").lower()
        if sev in counts:
            counts[sev] += 1
    return counts
