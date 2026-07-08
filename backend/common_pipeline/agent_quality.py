"""AI agent output quality pipeline — 7-stage quality contract.

raw/2026-07-08-ai-agent-output-quality-plan.md §Common Agent Pipeline:
  Evidence Builder → Scope Planner → Draft Writer → Deterministic Verifier →
  Grounding Critic → Repair Writer → Final Packager

공통: 결정적 검증으로 hallucinated evidence/format 위반을 LLM critic 비용 전에
걸러내고, critic verdict 는 structured JSON 으로 고정하고, 최종 status 는
backend policy 가 결정한다 (agent 는 done_with_warnings 를 직접 결정하지 않음).
"""
from __future__ import annotations

import json
import re
from typing import Any

# ── Evidence Builder ─────────────────────────────────────────


_EV_TRUNCATE_BYTES = 16000


def build_evidence_pack(
    *,
    run_id: str,
    pipeline_id: str,
    version_ref: str,
    items: list[dict],
    source_id: str = "",
) -> dict:
    """raw 근거를 LLM 입력용 evidence pack 으로 정규화.

    items: [{"id": "e1", "kind": "source_file|diff_hunk|config|observation|screenshot|scenario|coverage",
             "path": "...", "title": "...", "content": "...", "metadata": {...}}, ...]
    반출 schema 는 /api/webhook/evidence 입력과 호환.
    """
    norm_items: list[dict] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        iid = str(it.get("id") or "")
        kind = str(it.get("kind") or "source_file")
        title = str(it.get("title") or "")[:300]
        path = str(it.get("path") or "")[:500]
        content = str(it.get("content") or "")
        truncated = len(content.encode("utf-8")) > _EV_TRUNCATE_BYTES
        if truncated:
            content = content[:_V_TRUNCATE_CHAR]
        norm_items.append({
            "id": iid, "kind": kind, "title": title, "path": path,
            "content_preview": content, "truncated": truncated,
            "metadata": it.get("metadata") if isinstance(it.get("metadata"), dict) else {},
        })
    return {
        "pack_id": f"evpack-{run_id}",
        "run_id": run_id,
        "pipeline_id": pipeline_id,
        "source_id": source_id,
        "version_ref": version_ref,
        "item_count": len(norm_items),
        "items": norm_items,
        "truncated": any(i["truncated"] for i in norm_items),
        "omitted_count": sum(1 for i in items or [] if i not in norm_items),
    }


_V_TRUNCATE_CHAR = 16000 // 2


# ── Scope Planner ────────────────────────────────────────────


def plan_static_docs(change_units: list[dict], evidence_pack: dict) -> list[dict]:
    """변경 유닛과 근거로 어떤 theme 별 문서를 만들지 결정.

    change_units: [{"id": "cu1", "files": [...], "change_type": "api|config|architecture|ui|test|docs|build",
                    "significance": "trivial|minor|material|risky",
                    "summary": "...", "doc_impact": [...]}, ...]
    반출: [{"theme": "...", "action": "create|update|skip",
            "reason": "...", "required_evidence": [ids], "risk": "..."}, ...]
    """
    plans: list[dict] = []
    evidence_ids = {it["id"] for it in (evidence_pack.get("items") or [])}
    for cu in change_units or []:
        if not isinstance(cu, dict):
            continue
        sig = str(cu.get("significance") or "minor")
        ct = str(cu.get("change_type") or "")
        impact = cu.get("doc_impact") or []
        if sig in ("trivial", "minor") and ct in ("test", "docs", "build"):
            plans.append({
                "theme": ct, "action": "skip",
                "reason": f"trivial {ct} change — 문서 생성 불필요",
                "required_evidence": [], "risk": "low",
                "change_unit_id": cu.get("id"),
            })
            continue
        for theme in impact:
            if not isinstance(theme, str):
                continue
            plans.append({
                "theme": theme, "action": "update" if sig in ("minor", "material") else "create",
                "reason": cu.get("summary") or "",
                "required_evidence": sorted(i for i in cu.get("required_evidence", []) or []
                                            if i in evidence_ids),
                "risk": "high" if sig == "risky" else ("medium" if sig == "material" else "low"),
                "change_unit_id": cu.get("id"),
            })
    return plans


def plan_manual_docs(scenario_results: dict, coverage: dict) -> list[dict]:
    """매뉴얼 문서 계획 — failed scenario 가 있으면 user-manual 보류."""
    plans: list[dict] = []
    critical_failed = bool(scenario_results.get("critical_failed"))
    plans.append({
        "theme": "user-manual", "action": "deprecate-candidate" if critical_failed else "create",
        "reason": "관측된 시나리오 절차 기반" if not critical_failed else "critical scenario 실패",
        "coverage_gate": coverage.get("status", "warning"),
        "focus": ["main workflow", "unreached import dialog"] if coverage.get("status") != "warning" else ["recover critical path"],
    })
    plans.append({
        "theme": "operator-manual", "action": "create",
        "reason": "설치/기동/연결 — artifact/install/readiness 근거 필요",
        "coverage_gate": "pass",
        "focus": ["install procedure", "readiness check"],
    })
    return plans


# ── Deterministic Verifier ──────────────────────────────────


_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_SECRET_PATTERN = re.compile(
    r"(?:password|passwd|pwd|token|api[_-]?key|apikey|secret)\s*[=:]\s*\S+", re.IGNORECASE
)
_MERMAID_FENCE = re.compile(r"```mermaid\n.*?\n```", re.DOTALL)
_DOC_END_MARKER = "<!-- DOC-END -->"
_FORBIDDEN_WORDS = ("보통", "아마", "일반적으로", "probably", "maybe")


def deterministic_verifier(doc_md: str, *, evidence_ids: list[str] | None = None,
                          doc_type: str = "static") -> dict:
    """기계적 검증 — LLM critic 전에 형식/근거 위반을 잡는다.

    반출: {"result": "pass"|"fail",
            "errors": [{"code": "...", "location": "...", "message": "..."}], ...}
    - frontmatter_schema: 시작이 --- ... --- 인지
    - doc_end_marker: 마지막에 DOC-END 마커가 있는지
    - fence_closed: ``` 짝수 개수
    - mermaid_parse: mermaid 블록이 있으면 balanced 인지
    - evidence_id: [eN] 참조 중 available id 목록에 없는 것
    - secret_redaction: 금지 패턴이 텍스트에 그대로 노출
    - forbidden_words: 추측성 단어 검출
    - min_section_coverage: 헤딩이 0개 거나 1개뿐이면 fail
    """
    errors: list[dict] = []
    m = _FRONT_MATTER_RE.match(doc_md.strip())
    if not m:
        errors.append({"code": "frontmatter_missing", "message": "frontmatter(---...---) 없음"})

    secret_hits = list(_SECRET_PATTERN.finditer(doc_md))
    if secret_hits:
        for h in secret_hits[:3]:
            errors.append({"code": "secret_pattern",
                           "location": h.group(0)[:40],
                           "message": "secret-like pattern 노출"})

    if not doc_md.rstrip().endswith(_DOC_END_MARKER):
        errors.append({"code": "doc_end_missing", "message": f"end marker({_DOC_END_MARKER}) 없음"})

    fence_count = doc_md.count("```")
    if fence_count % 2 != 0:
        errors.append({"code": "fence_unclosed",
                       "message": f"코드 펜스 {fence_count}개 (홀수)"})

    if fence_count >= 2:
        mblocks = _MERMAID_FINDALL.findall(doc_md)
        umblocks = _MERMAID_FENCE.findall(doc_md)
        if len(mblocks) != len(umblocks):
            errors.append({"code": "mermaid_unbalanced",
                           "message": "mermaid 블록 페어 불일치"})

    if evidence_ids is not None:
        avail = set(evidence_ids)
        for ref in re.findall(r"\[(e\d+)\]", doc_md):
            if ref not in avail:
                errors.append({"code": "missing_evidence_id", "location": ref,
                               "message": f"근거 {ref} 가 available id 목록에 없음"})

    headings = re.findall(r"^\#{1,6} .+$", doc_md, re.MULTILINE)
    if 0 < len(headings) < 2:
        errors.append({"code": "min_section_coverage",
                       "message": f"헤딩 {len(headings)}개 — 최소 2개 권장"})

    for kw in _FORBIDDEN_WORDS:
        if re.search(rf"\b{kw}\b", doc_md, re.IGNORECASE):
            errors.append({"code": "forbidden_word", "location": kw,
                           "message": f"추측 단어 '{kw}' 검출"})

    return {
        "result": "pass" if not errors else "fail",
        "errors": errors,
        "error_count": len(errors),
        "checked_at": "deterministic",
    }


_MERMAID_FINDALL = re.compile(r"```mermaid\b")


# ── Grounding Critic (structured verdict + chunked) ──────────


def critic_prompt(doc_md: str, evidence_block: str, theme_contract: dict) -> list[dict]:
    """critic LLM 호출을 위한 메시지 list — 실제 LLM 호출은 외부."""
    must = theme_contract.get("must_cover", [])
    dont = theme_contract.get("do_not_cover", [])
    ask = (
        "You are an adversarial documentation QA critic. "
        "Find unsupported claims and contract violations. Output JSON only.\n\n"
        f"MUST COVER: {', '.join(must)}\n"
        f"DO NOT COVER: {', '.join(dont)}\n\n"
        f"DOCUMENT:\n```\n{doc_md}\n```\n\n"
        f"EVIDENCE BLOCK:\n{evidence_block}\n\n"
        "JSON schema: {result: pass|fail, score: 0..1, "
        "stage1_schema: pass|fail, stage2_theme_fit: pass|fail, "
        "stage3_grounding: pass|fail, stage4_usefulness: pass|fail, "
        "blocking_findings: [{severity: blocker|major|minor, "
        "claim, reason, required_fix, evidence_refs: []}], "
        "nonblocking_notes: []}"
    )
    return [{"role": "user", "content": ask}]


def parse_critic_verdict(raw_response: str) -> dict:
    """critic LLM 응답을 JSON 으로 파싱. 파싱 실패 시 fail verdict."""
    if not raw_response:
        return _empty_verdict(reason="empty response")
    try:
        m = re.search(r"\{.*\}", raw_response, re.DOTALL)
        body = m.group(0) if m else raw_response
        v = json.loads(body)
    except Exception:  # noqa: BLE001
        return _empty_verdict(reason=f"json parse fail: {raw_response[:80]}")
    if not isinstance(v, dict):
        return _empty_verdict(reason="verdict not object")
    v.setdefault("blocking_findings", [])
    v.setdefault("nonblocking_notes", [])
    v.setdefault("score", 0.0)
    if v.get("result") not in ("pass", "fail"):
        # 자동 판정: blocker 0 + score >= 0.82 → pass
        blockers = sum(1 for f in v["blocking_findings"]
                       if isinstance(f, dict) and f.get("severity") == "blocker")
        if blockers == 0 and float(v["score"]) >= 0.82:
            v["result"] = "pass"
        else:
            v["result"] = "fail"
    return v


def _empty_verdict(*, reason: str = "") -> dict:
    return {
        "result": "fail", "score": 0.0,
        "blocking_findings": [{
            "severity": "blocker", "claim": "verdict parse",
            "reason": reason, "required_fix": "JSON 만 출력하라", "evidence_refs": [],
        }],
        "nonblocking_notes": [],
        "stage1_schema": "fail", "stage2_theme_fit": "fail",
        "stage3_grounding": "fail", "stage4_usefulness": "fail",
    }


def chunked_critic(doc_md: str, evidence_block: str, theme_contract: dict,
                    *, chunk_size: int = 6000, critic_fn=None) -> dict:
    """긴 문서를 섹션별로 잘라 critic 호출 후 verdict 합산.

    critic_fn(doc_chunk, evidence_block) -> raw_response. None 이면 critic 단계를
    skip 하고 deterministic verifier 만으로 pass/fail 결정 (테스트/개발용).
    """
    sections = _split_into_sections(doc_md)
    if len(sections) <= 1 or len(doc_md) <= chunk_size:
        if critic_fn is None:
            return parse_critic_verdict("")  # fail safe
        raw = critic_fn(doc_md, evidence_block)
        return parse_critic_verdict(raw)

    all_blockers: list[dict] = []
    all_notes: list[str] = []
    scores: list[float] = []
    for idx, sec in enumerate(sections, 1):
        if critic_fn is None:
            v = parse_critic_verdict("")
        else:
            v = parse_critic_verdict(critic_fn(sec, evidence_block))
        for f in v.get("blocking_findings", []):
            if isinstance(f, dict):
                f = dict(f)
                f["section_index"] = idx
                all_blockers.append(f)
        all_notes.extend(f"[section {idx}] {n}" for n in v.get("nonblocking_notes", []))
        scores.append(float(v.get("score") or 0))

    score = round(sum(scores) / max(len(scores), 1), 3)
    result = "pass" if not all_blockers and score >= 0.82 else "fail"
    return {
        "result": result, "score": score,
        "blocking_findings": all_blockers,
        "nonblocking_notes": all_notes,
        "stages": {"section_count": len(sections)},
    }


def _split_into_sections(doc_md: str) -> list[str]:
    """## / ### 헤딩 기준 섹션 분리 (최소 1개 보장)."""
    parts = re.split(r"(?m)^(?=##\s)", doc_md)
    return [p.strip() for p in parts if p.strip()] or [doc_md]


# ── Quality Gate Evaluator ───────────────────────────────────


def evaluate_quality_gate(verifier: dict, critic: dict, *,
                          thresholds: dict | None = None) -> dict:
    """deterministic + grounding 결과를 합쳐 quality.status 결정.

    thresholds 기본: min_score 0.82, blocker_count 0, major_count 0.
    """
    th = thresholds or {"min_score": 0.82, "max_blockers": 0, "max_majors": 0}
    score = float((critic or {}).get("score") or 0)
    blockers = sum(1 for f in (critic or {}).get("blocking_findings", []) or []
                   if isinstance(f, dict) and f.get("severity") == "blocker")
    majors = sum(1 for f in (critic or {}).get("blocking_findings", []) or []
                 if isinstance(f, dict) and f.get("severity") == "major")
    verifier_pass = (verifier or {}).get("result") == "pass"
    if not verifier_pass:
        status = "fail"
        failed_gate = "deterministic_verifier"
    elif blockers > th["max_blockers"]:
        status, failed_gate = "fail", "grounding_critic.blocker"
    elif majors > th["max_majors"]:
        status, failed_gate = "warning", "grounding_critic.major"
    elif score < th["min_score"]:
        status, failed_gate = "warning", "grounding_critic.score"
    else:
        status, failed_gate = "pass", ""

    return {
        "status": status,
        "score": round(score, 3),
        "failed_gate": failed_gate,
        "warning_count": (critic or {}).get("nonblocking_notes", []) and len((critic or {}).get("nonblocking_notes", [])) or 0,
        "blocker_count": blockers,
        "major_count": majors,
        "verifier_pass": verifier_pass,
        "verifier_errors": (verifier or {}).get("errors", []),
    }


def determine_terminal_status(quality_status: str, summary_errors: int = 0,
                              summary_warnings: int = 0) -> str:
    """quality + summary → run status. backend policy 가 결정 (agent 가 임의로 결정 금지)."""
    if quality_status == "fail":
        return "failed_quality_gate" if summary_errors == 0 else "failed"
    if quality_status == "warning":
        return "done_with_warnings"
    if summary_errors > 0:
        return "partial"
    return "done"
