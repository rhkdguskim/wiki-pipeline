"""Deterministic Verifier — LLM critic 전에 반드시 실행하는 기계 검증.

raw/2026-07-08-ai-agent-output-quality-plan.md §4 Deterministic Verifier 의 구현.
비싼 LLM critic 전에 기계적으로 잡을 수 있는 오류(frontmatter·펜스·근거 id·secret
누출·추측어)를 모두 제거한다 — LLM critic 은 문법/형식이 아니라 사실성·적합성에만
집중하게 한다.

verify() 는 common_pipeline.verify.invalid_doc_reason 와 정적 mermaid_lint.lint_mermaid
를 넘어 **문서 품질 계약 전체**를 한 번에 검사한다 — frontmatter schema, DOC-END,
펜스 짝, mermaid parse, evidence id 존재, secret redaction, forbidden words, 최소
섹션 coverage.

출력:
    {"result": "pass"|"fail", "errors": [{"code", "location", "message"}]}
"""
from __future__ import annotations

import re
from typing import Any

from .verify import DOC_END_MARKER

# credential-like 패턴 — observation.py._SECRET_VALUE_RE 와 동일 기준.
_SECRET_PATTERN = re.compile(
    r"(?:password|passwd|pwd|token|access_token|refresh_token|"
    r"api[_-]?key|apikey|secret|authorization)"
    r"\s*[=:]\s*(?:bearer\s+)?\S+",
    re.IGNORECASE,
)
# 더 넓은 패턴 — URL inline credential (postgres://user:pass@host).
_URL_CRED_RE = re.compile(r"://[^\s/:@]+:[^\s/:@]+@")
# high-entropy hex/base64 같은 값 (32자 이상) — token leak 휴리스틱.
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{40,}\b")

# 추측어 — writer prompt 의 FORBIDDEN 과 대응. 쓰면 안 되는 단어들.
FORBIDDEN_WORDS: dict[str, tuple[str, ...]] = {
    "korean": ("일반적으로", "보통", "아마", "대부분", "거의 항상"),
    "english": ("generally", "usually", "probably", "typically"),
}

# evidence id 인용 패턴 — [e1], [o12], [eN|...] 형식.
_CITATION_RE = re.compile(r"\[(?:e|o)(\d+)(?:\|[^\]]+)?\]")
# frontmatter 끝 — 첫 --- ... --- 블록.
_FM_BLOCK_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _frontmatter(doc: str) -> tuple[str, int]:
    """문서 앞의 frontmatter 블록과 그 끝 offset(본문 시작) 을 반환.

    frontmatter 가 없으면 ("", 0).
    """
    m = _FM_BLOCK_RE.match(doc)
    if not m:
        return "", 0
    return m.group(1), m.end()


def _cited_ids(doc: str) -> set[str]:
    """문서 본문에서 인용된 evidence/observation id 집합을 반환 ([e1] -> e1)."""
    out: set[str] = set()
    for m in _CITATION_RE.finditer(doc):
        digit = m.group(1)
        prefix = "e" if "[e" in doc[m.start():m.start() + 3] else "o"
        out.add(f"{prefix}{digit}")
    return out


def _section_count(doc: str) -> int:
    """## 헤딩 개수로 최소 섹션 coverage 를 잰다."""
    return len(re.findall(r"(?m)^##\s+\S", doc))


def _check_frontmatter(doc: str, theme: str, doc_type: str,
                       errors: list[dict]) -> None:
    """frontmatter schema 검증 — theme 필드 + doc_type 별 필수 필드."""
    fm, _ = _frontmatter(doc)
    if not fm:
        errors.append({
            "code": "frontmatter_missing",
            "location": "frontmatter",
            "message": "문서 시작에 --- frontmatter 블록이 없다",
        })
        return

    # theme 필드 존재 + 값 일치
    theme_match = re.search(r"(?m)^theme:\s*(\S+)", fm)
    if not theme_match:
        errors.append({
            "code": "frontmatter_theme_missing",
            "location": "frontmatter",
            "message": "frontmatter 에 theme: 필드가 없다",
        })
    elif theme and theme_match.group(1).strip() != theme:
        errors.append({
            "code": "frontmatter_theme_mismatch",
            "location": "frontmatter",
            "message": f"frontmatter theme={theme_match.group(1)!r} 가 예상 "
                       f"{theme!r} 과 다르다",
        })

    # doc_type 별 필수 필드 — manual 문서는 release/observation/coverage 가 필요.
    if doc_type == "manual":
        for key in ("source_observations:", "release:"):
            if key not in fm:
                errors.append({
                    "code": "frontmatter_missing_field",
                    "location": "frontmatter",
                    "message": f"manual 문서 frontmatter 에 {key} 필드가 없다",
                })
    elif doc_type == "static":
        if "source_files:" not in fm and "source_id:" not in fm:
            errors.append({
                "code": "frontmatter_missing_field",
                "location": "frontmatter",
                "message": "static 문서 frontmatter 에 source_files: 또는 "
                           "source_id: 필드가 없다",
            })


def _check_doc_end(doc: str, errors: list[dict]) -> None:
    """DOC-END 마커 존재 검증 — 마커 없으면 잘린 문서로 판정."""
    if DOC_END_MARKER not in doc:
        errors.append({
            "code": "missing_doc_end",
            "location": "tail",
            "message": f"문서 끝에 완결 마커({DOC_END_MARKER})가 없다 — "
                       "출력이 잘렸거나 마커를 빠뜨렸다",
        })


def _check_fences(doc: str, errors: list[dict]) -> None:
    """코드 펜스(```)가 짝이 맞는지 검증."""
    count = doc.count("```")
    if count % 2 != 0:
        errors.append({
            "code": "unclosed_fence",
            "location": "body",
            "message": f"코드 펜스(```)가 닫히지 않았다 (count={count}) — "
                       "문서가 중간에 잘린 것",
        })


def _check_mermaid(doc: str, errors: list[dict]) -> None:
    """mermaid 블록 경량 parse 시도 — 정적 mermaid_lint 재사용.

    common_pipeline 은 static_pipeline 에 의존하지 않으므로 (역방향 금지),
    mermaid 검증은 선택적으로 import 한다 — import 실패 시 이 모듈 안에서
    최소 검증(펜스 + 다이어그램 타입 선언)만 수행한다.
    """
    mermaid_blocks = re.findall(
        r"```mermaid\s*\n(.*?)```", doc, re.DOTALL | re.IGNORECASE,
    )
    if not mermaid_blocks:
        return

    # 정적 mermaid_lint 가 있으면 정밀 검증 위임.
    try:
        from ..static_pipeline.mermaid_lint import lint_mermaid  # type: ignore
        lint_errs = lint_mermaid(doc, use_mmdc=False)
        for i, err in enumerate(lint_errs):
            errors.append({
                "code": "mermaid_parse",
                "location": f"mermaid#{i + 1}",
                "message": err,
            })
        return
    except Exception:  # noqa: BLE001 — 의존 없으면 자체 최소 검증
        pass

    diagram_types = (
        "graph", "flowchart", "sequencediagram", "classdiagram",
        "statediagram", "erdiagram", "gantt", "pie", "journey",
    )
    for i, block in enumerate(mermaid_blocks, 1):
        first = next((ln for ln in block.splitlines() if ln.strip()), "").strip().lower()
        if not first:
            errors.append({
                "code": "mermaid_empty",
                "location": f"mermaid#{i}",
                "message": f"mermaid #{i}: 빈 다이어그램",
            })
            continue
        if not any(first.startswith(t) for t in diagram_types):
            errors.append({
                "code": "mermaid_invalid_type",
                "location": f"mermaid#{i}",
                "message": f"mermaid #{i}: 첫 줄이 알려진 다이어그램 타입이 아님 "
                           f"(받은 값: {first[:40]!r})",
            })


def _check_evidence_ids(doc: str, evidence_ids: list[str],
                        errors: list[dict]) -> None:
    """인용된 evidence/observation id 가 제공된 목록에 존재하는지 검증."""
    if not evidence_ids:
        return  # 근거 id 자체를 안 쓰는 테스트/흐름은 스킵
    available = {str(e) for e in evidence_ids}
    cited = _cited_ids(doc)
    for cid in sorted(cited):
        if cid not in available:
            errors.append({
                "code": "missing_evidence_id",
                "location": "body",
                "message": f"인용된 근거 id {cid} 가 evidence pack 에 존재하지 않는다",
            })


def _check_secrets(doc: str, errors: list[dict]) -> None:
    """secret/token 패턴 redaction 검증 — leak 이 발견되면 fail."""
    # 1. password=..., token=... 같은 대입 패턴
    for m in _SECRET_PATTERN.finditer(doc):
        # 값이 ***REDACTED*** 면 통과 (이미 마스킹됨).
        if "REDACTED" in m.group(0):
            continue
        snippet = m.group(0)[:60]
        errors.append({
            "code": "secret_leak",
            "location": f"body@{m.start()}",
            "message": f"secret/token 패턴이 평문으로 노출됐다: {snippet!r}",
        })
    # 2. URL inline credential (postgres://user:pass@host)
    for m in _URL_CRED_RE.finditer(doc):
        # 마스킹된 값이면 통과.
        if "REDACTED" in m.group(0):
            continue
        snippet = m.group(0)[:60]
        errors.append({
            "code": "secret_leak_url",
            "location": f"body@{m.start()}",
            "message": f"URL inline credential 노출: {snippet!r}",
        })


def _check_forbidden_words(doc: str, errors: list[dict]) -> None:
    """추측어(일반적으로, 보통, 아마 등) 사용 금지 — writer prompt FORBIDDEN."""
    body = doc
    for lang, words in FORBIDDEN_WORDS.items():
        for w in words:
            idx = body.find(w)
            if idx >= 0:
                ctx = body[max(0, idx - 20):idx + len(w) + 20]
                errors.append({
                    "code": "forbidden_word",
                    "location": f"body@{idx}",
                    "message": f"추측어 '{w}' 사용 — 근거 없는 서술이다. "
                               f"문맥: ...{ctx}...",
                })


def _check_section_coverage(doc: str, doc_type: str,
                            errors: list[dict]) -> None:
    """최소 섹션 coverage — ## 헤딩이 최소 개수 있어야 완결된 문서로 본다."""
    n = _section_count(doc)
    # manual 은 독자 2축 + 한계 섹션 등 최소 3개. static 은 overview/components 최소 2개.
    minimum = 3 if doc_type == "manual" else 2
    if n < minimum:
        errors.append({
            "code": "insufficient_sections",
            "location": "body",
            "message": f"섹션(##) 이 {n}개뿐 — 최소 {minimum}개 필요 "
                       f"(doc_type={doc_type})",
        })


def verify(
    doc_content: str,
    *,
    theme: str = "",
    evidence_ids: list[str] | None = None,
    doc_type: str = "static",
    checks: tuple[str, ...] | None = None,
) -> dict:
    """생성된 문서를 기계적으로 검증. fail 시 errors 목록과 함께 반환.

    Parameters
    ----------
    doc_content:
        검증 대상 마크다운 문서 (frontmatter + 본문 + DOC-END 마커).
    theme:
        기대 frontmatter theme 값 (예: "architecture-overview"). 빈 값이면
        theme 일치 검사는 스킵.
    evidence_ids:
        문서가 인용 가능한 근거 id 목록 (evidence pack 의 item id 들).
        [e1]·[o12] 형식 인용이 이 목록에 없으면 missing_evidence_id 에러.
    doc_type:
        "static" | "manual" — doc_type 별 필수 frontmatter 필드/최소 섹션 수가 다름.
    checks:
        실행할 검사 이름 튜플. None 이면 전체. 부분 집합 지정으로 일부 검사만
        실행할 수 있다 (테스트나 흐름 제어용).

    Returns
    -------
    dict
        {"result": "pass"|"fail", "errors": [{"code", "location", "message"}, ...]}
    """
    all_checks = (
        "frontmatter", "doc_end", "fences", "mermaid",
        "evidence_ids", "secrets", "forbidden_words", "section_coverage",
    )
    active = set(checks) if checks else set(all_checks)

    errors: list[dict] = []
    if "frontmatter" in active:
        _check_frontmatter(doc_content, theme, doc_type, errors)
    if "doc_end" in active:
        _check_doc_end(doc_content, errors)
    if "fences" in active:
        _check_fences(doc_content, errors)
    if "mermaid" in active:
        _check_mermaid(doc_content, errors)
    if "evidence_ids" in active:
        _check_evidence_ids(doc_content, evidence_ids or [], errors)
    if "secrets" in active:
        _check_secrets(doc_content, errors)
    if "forbidden_words" in active:
        _check_forbidden_words(doc_content, errors)
    if "section_coverage" in active:
        _check_section_coverage(doc_content, doc_type, errors)

    return {
        "result": "pass" if not errors else "fail",
        "errors": errors,
    }


def summarize(verifier_result: dict) -> dict:
    """verifier 결과를 webhook quality report 용 status 문자열로 요약.

    {"schema_status", "mermaid_status", "redaction_status"} 각각 pass|fail.
    """
    errs = verifier_result.get("errors") or []
    codes = {e.get("code") for e in errs}
    return {
        "schema_status": "fail" if codes & {
            "frontmatter_missing", "frontmatter_theme_missing",
            "frontmatter_theme_mismatch", "frontmatter_missing_field",
            "missing_doc_end", "unclosed_fence",
        } else "pass",
        "mermaid_status": "fail" if codes & {
            "mermaid_parse", "mermaid_empty", "mermaid_invalid_type",
        } else "pass",
        "redaction_status": "fail" if codes & {
            "secret_leak", "secret_leak_url",
        } else "pass",
    }
