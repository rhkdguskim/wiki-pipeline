"""Quality Gates — deterministic verifier + grounding critic 결과를 종합해
normalized quality status 와 terminal run status 를 결정한다.

raw/2026-07-08-ai-agent-output-quality-plan.md §5 통과 기준·§Final Review Corrections.

통과 기준 (raw 설계서 §5, 2026-07-09 완화):
- blocker 0 (hallucination/secret 0관용)
- major <= warning_major (3) — 이하면 warning, 초과면 fail
- score >= 0.75
- deterministic verifier pass

status 정규화 (raw 설계서 'Quality Status Normalization'):
- deterministic verifier result: pass | fail
- grounding critic result: pass | fail
- quality status: pass | warning | fail | not_evaluated
- run status: done | done_with_warnings | failed_quality_gate | failed | partial

`failed`는 실행 실패, `fail`은 quality/gate 판정값으로만 사용한다 — 이 모듈은
quality_status(pass|warning|fail) 와 terminal_status(done|done_with_warnings|
failed_quality_gate|failed) 을 구분해 반환한다.
"""
from __future__ import annotations

from .grounding_critic import severity_counts

# raw 설계서 §5 통과 기준의 기본 임계치.
# warning_major 를 실제로 적용 — major 가 warning_major 이하면 fail 아닌 warning 허용.
# (이전 max_major=0 은 major 1개만 있어도 fail 이었는데, 이는 warning 상태가
# 사실상 발생하지 않는 구조였다. 검증 통과율을 높이기 위해 warning_major 를
# 실제 임계치로 사용하고 값을 3 으로 상향했다.)
DEFAULT_THRESHOLDS: dict[str, float] = {
    "min_score": 0.75,        # critic score 하한 (0.82 → 0.75 완화)
    "max_blocker": 0,         # blocker 허용 수 (0 — hallucination/secret 0관용)
    "warning_major": 3,       # major 가 이 수 이하면 warning, 초과면 fail
}


def _verifier_passed(verifier_result: dict | None) -> bool:
    """deterministic verifier 결과가 pass 인지."""
    if not verifier_result:
        return True  # 검증을 안 돌렸으면 통과로 간주 (legacy 호환)
    return verifier_result.get("result") == "pass"


def _critic_passed(critic_result: dict | None) -> tuple[bool, dict[str, int], float]:
    """critic 결과를 (passed, severity_counts, score) 로 풀어 반환.

    critic 결과가 없으면 (True, zero_counts, 1.0) — legacy 호환.
    """
    if not critic_result:
        return True, {"blocker": 0, "major": 0, "minor": 0}, 1.0
    counts = severity_counts(critic_result)
    score = float(critic_result.get("score", 0.0))
    passed = str(critic_result.get("result", "")).lower() == "pass"
    return passed, counts, score


def evaluate_quality_gate(
    verifier_result: dict | None,
    critic_result: dict | None,
    *,
    thresholds: dict | None = None,
) -> dict:
    """deterministic verifier + grounding critic 결과로 quality gate 를 평가.

    Returns
    -------
    dict
        {"status": "pass"|"warning"|"fail",
         "score": float,
         "verifier_status": "pass"|"fail",
         "critic_status": "pass"|"fail",
         "severity_counts": {"blocker", "major", "minor"},
         "failed_gate": str,  # fail 사유 (status != pass 일 때)
         "failed_reason": str}

    판정 우선순위:
    1. verifier fail -> status=fail (기계 검증 실패는 LLM critic 전에 끊어야)
    2. blocker > 0 -> status=fail (hallucination/secret/contract 위반)
    3. major > warning_major -> status=fail (theme contract 위반 다수)
    4. score < min_score -> status=fail
    5. major > 0 (하지만 warning_major 이하) 또는 minor 만 있으면 -> status=warning
    6. 그 외 -> status=pass
    """
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    min_score = float(th["min_score"])
    max_blocker = int(th["max_blocker"])
    warning_major = int(th["warning_major"])

    verifier_ok = _verifier_passed(verifier_result)
    critic_ok, counts, score = _critic_passed(critic_result)

    failed_gate = ""
    failed_reason = ""

    # 1) verifier fail
    if not verifier_ok:
        status = "fail"
        failed_gate = "deterministic_verifier"
        n_errs = len((verifier_result or {}).get("errors") or [])
        failed_reason = f"deterministic verifier fail ({n_errs} errors)"
    # 2) blocker 존재
    elif counts["blocker"] > max_blocker:
        status = "fail"
        failed_gate = "grounding"
        failed_reason = f"blocker {counts['blocker']}건 — hallucination 또는 contract 위반"
    # 3) major 초과 — warning_major 를 초과하면 fail (이전 max_major=0 버그 수정)
    elif counts["major"] > warning_major:
        status = "fail"
        failed_gate = "grounding"
        failed_reason = (f"major {counts['major']}건 — theme contract 위반 "
                         f"(허용 {warning_major}건 초과)")
    # 4) score 미달
    elif score < min_score:
        status = "fail"
        failed_gate = "grounding"
        failed_reason = f"score {score:.2f} < {min_score:.2f}"
    # 5) major 있지만 허용 범위 (warning). 또는 minor 만.
    elif counts["major"] > 0 or counts["minor"] > 0:
        status = "warning"
        failed_gate = ""
        # warning 은 failed_reason 이 아니라 note. failed_gate 도 비움.
    # 6) 전부 통과
    else:
        status = "pass"

    # critic 결과가 fail 이면 status 도 fail 이어야 한다 (critic 자체 fail 판정).
    # 단, severity count 만으로 pass 처럼 보여도 critic result="fail" 이면 따른다.
    if critic_result and str(critic_result.get("result", "")).lower() == "fail":
        if status == "pass":
            status = "fail"
            failed_gate = failed_gate or "grounding"
            failed_reason = failed_reason or "grounding critic result=fail"

    return {
        "status": status,
        "score": round(score, 4),
        "verifier_status": "pass" if verifier_ok else "fail",
        "critic_status": "pass" if critic_ok else "fail",
        "severity_counts": counts,
        "failed_gate": failed_gate,
        "failed_reason": failed_reason,
        "thresholds": th,
    }


def determine_terminal_status(
    quality_status: str,
    summary_errors: int = 0,
    summary_warnings: int = 0,
) -> str:
    """quality_status + run summary 신호로 terminal run status 를 결정.

    Parameters
    ----------
    quality_status:
        evaluate_quality_gate 의 status (pass|warning|fail|not_evaluated).
    summary_errors:
        run 전체 error count (예외·stage 실패).
    summary_warnings:
        run 전체 warning count (warned themes).

    Returns
    -------
    str
        done | done_with_warnings | failed_quality_gate | failed

    매핑 규칙:
    - summary_errors > 0 (예외적 실행 실패) -> failed
    - quality_status == fail -> failed_quality_gate
    - quality_status == warning 또는 summary_warnings > 0 -> done_with_warnings
    - 그 외 -> done
    """
    qs = (quality_status or "not_evaluated").lower()

    # 실행 자체가 실패한 경우가 우선 — quality 가 pass 여도 run failed.
    if summary_errors > 0:
        return "failed"

    if qs == "fail":
        return "failed_quality_gate"

    if qs == "warning" or summary_warnings > 0:
        return "done_with_warnings"

    if qs == "pass":
        return "done"

    # not_evaluated 또는 알 수 없는 값 — warning 으로 보수적으로.
    return "done_with_warnings"


def evaluate_generation_quality(results: list[dict]) -> tuple[dict, str]:
    """Aggregate writer verification results without losing deterministic failures.

    ``verified_generate`` returns the final critic verdict plus any deterministic
    lint errors that survived its repair attempts.  Those lint errors are gate
    failures, not merely display warnings, and must remain visible to the run
    status and submission policy.
    """
    if not results:
        gate = {
            "status": "not_evaluated",
            "score": 0.0,
            "verifier_status": "pass",
            "critic_status": "pass",
            "severity_counts": {"blocker": 0, "major": 0, "minor": 0},
            "failed_gate": "",
            "failed_reason": "",
            "thresholds": DEFAULT_THRESHOLDS,
        }
        return gate, "done_with_warnings"

    worst_score = 1.0
    all_blocking: list[dict] = []
    lint_errors: list[object] = []
    critic_failed = False
    warned_count = 0
    for result in results:
        critic_failed = critic_failed or result.get("verdict_result") == "fail"
        score = result.get("verdict_score")
        if score is not None:
            try:
                worst_score = min(worst_score, float(score))
            except (TypeError, ValueError):
                pass
        all_blocking.extend(result.get("blocking_findings") or [])
        lint_errors.extend(result.get("lint_errors") or [])
        warned_count += int(bool(result.get("warned")))

    gate = evaluate_quality_gate(
        {"result": "fail" if lint_errors else "pass", "errors": lint_errors},
        {
            "result": "fail" if critic_failed else "pass",
            "score": worst_score,
            "blocking_findings": all_blocking,
        },
    )
    return gate, determine_terminal_status(
        gate["status"], summary_warnings=warned_count,
    )


def to_webhook_payload(
    gate_result: dict,
    *,
    repair_attempts: int = 0,
    findings: list[dict] | None = None,
) -> dict:
    """gate_result 를 /api/webhook/quality payload schema 로 변환.

    resources.upsert_quality_report 가 받는 필드를 채운다. findings 는
    blocking_findings + nonblocking_notes 를 webhook finding schema 로 변환한 것.
    """
    counts = gate_result.get("severity_counts", {})
    status = gate_result.get("status", "not_evaluated")
    publishable = status == "pass"
    failed_gate = gate_result.get("failed_gate", "")

    return {
        "status": status,
        "score": int(round(gate_result.get("score", 0.0) * 100)),
        "publishable": publishable,
        "failed_gate": failed_gate,
        "warning_count": int(counts.get("minor", 0)),
        "error_count": int(counts.get("blocker", 0) + counts.get("major", 0)),
        "repair_attempts": int(repair_attempts),
        "deterministic_verifier_status": gate_result.get("verifier_status", ""),
        "grounding_critic_status": gate_result.get("critic_status", ""),
        "schema_status": gate_result.get("schema_status", ""),
        "mermaid_status": gate_result.get("mermaid_status", ""),
        "redaction_status": gate_result.get("redaction_status", ""),
        "gates": [
            {"name": "deterministic_verifier",
             "status": gate_result.get("verifier_status", "")},
            {"name": "grounding_critic",
             "status": gate_result.get("critic_status", "")},
        ],
        "findings": findings or [],
    }
