"""static docu-automation 품질 개선 P1/P2 회귀 테스트.

원본 설계서(raw/2026-07-08-ai-agent-output-quality-plan.md) 대비 갭 보강:
- P1: map 단위 요약 결정적 품질 검증 (deep_summary.summary_quality_issue)
- P1: init scope planning (scope_planner.plan_static_init_docs) — 근거 없는 테마 skip
- P2: init 문서 커버리지 지표 (init_runner._init_coverage)
- P2: unsupported_claim_count 되채움 (resource_reporter._doc_quality_from_summary)
전부 LLM 없이 deterministic 하게 검증한다.
"""
from __future__ import annotations

from backend.static_pipeline.deep_summary import summary_quality_issue
from backend.common_pipeline.scope_planner import plan_static_init_docs
from backend.static_pipeline.init_runner import _init_coverage
from backend.runner.resource_reporter import _doc_quality_from_summary


_THEMES = ["intro", "architecture-overview", "component-diagram", "api-protocol"]

# 필수 항목을 모두 갖춘 유효 요약 (길이 통과용으로 충분히 길게).
_GOOD_SUMMARY = (
    "역할: 소스를 파싱해 구문 트리를 만드는 단위다. "
    "주요 컴포넌트: Lexer, Parser, AstBuilder 로 구성된다. "
    "의존·통신: engine 단위를 호출하고 표준 라이브러리만 쓴다. "
    "기술·플랫폼: C++17, CMake 로 빌드하며 Linux/Windows 를 지원한다. "
    "실행·설정: 포트 없음, 환경변수 없음 — 라이브러리로 링크된다."
)


# ── P1: 요약 품질 검증 ──────────────────────────────────────────────────


def test_summary_quality_accepts_good():
    assert summary_quality_issue(_GOOD_SUMMARY) is None


def test_summary_quality_rejects_empty_and_short():
    assert summary_quality_issue("") is not None
    assert summary_quality_issue("역할: 파서") is not None


def test_summary_quality_rejects_missing_fields():
    # 길이는 충분하지만 필수 항목(주요 컴포넌트/의존/기술) 누락.
    text = "역할: 파서라는 단위입니다. " + ("설명 " * 40)
    issue = summary_quality_issue(text)
    assert issue is not None and "필수 항목 누락" in issue


def test_summary_quality_rejects_guess_words():
    text = _GOOD_SUMMARY + " 이 단위는 보통 빠르게 동작한다."
    issue = summary_quality_issue(text)
    assert issue is not None and "추측어" in issue


def test_summary_quality_rejects_tool_leak():
    text = _GOOD_SUMMARY + " <invoke name=read_file>"
    issue = summary_quality_issue(text)
    assert issue is not None and "도구 호출" in issue


# ── P1: init scope planning ─────────────────────────────────────────────


def test_scope_plan_all_create_with_evidence():
    plans = plan_static_init_docs(
        _THEMES, [("a", "역할: REST API 서버"), ("b", "역할: 엔진")])
    actions = {p["theme"]: p["action"] for p in plans}
    # API 신호 있음 + 단위 2개 → 전부 create.
    assert all(a == "create" for a in actions.values()), actions


def test_scope_plan_skips_component_diagram_when_single_unit():
    plans = plan_static_init_docs(_THEMES, [("only", "역할: REST API 하나뿐")])
    actions = {p["theme"]: p["action"] for p in plans}
    assert actions["component-diagram"] == "skip"
    assert actions["intro"] == "create"


def test_scope_plan_skips_api_protocol_without_signal():
    plans = plan_static_init_docs(
        _THEMES, [("a", "역할: CLI 유틸"), ("b", "역할: 파일 변환기")])
    actions = {p["theme"]: p["action"] for p in plans}
    assert actions["api-protocol"] == "skip"
    assert actions["architecture-overview"] == "create"


def test_scope_plan_all_skip_when_no_summaries():
    plans = plan_static_init_docs(_THEMES, [])
    assert all(p["action"] == "skip" for p in plans)


# ── P2: init 문서 커버리지 지표 ─────────────────────────────────────────


def test_coverage_pass_when_all_produced():
    docs = {t: {"file": "x"} for t in _THEMES[:3]}
    docs["api-protocol"] = {"skipped": True}
    cov = _init_coverage(_THEMES, docs, planned_units=5, summarized_units=5)
    assert cov["status"] == "pass"
    assert cov["skipped_docs"] == 1
    assert cov["produced_docs"] == 3
    # skip 은 분모에서 빠진다 — expected_docs = 3.
    assert cov["expected_docs"] == 3


def test_coverage_warning_on_partial_units():
    docs = {t: {"file": "x"} for t in _THEMES}
    # 계획 5단위 중 2개만 요약 성공 → unit_pct 40 → warning (>= 35).
    cov = _init_coverage(_THEMES, docs, planned_units=5, summarized_units=2)
    assert cov["status"] == "warning"
    assert cov["unit_pct"] == 40.0


def test_coverage_fail_on_severe_unit_gap():
    docs = {t: {"file": "x"} for t in _THEMES}
    # 10단위 중 1개만 요약 → 10% → fail (< 35).
    cov = _init_coverage(_THEMES, docs, planned_units=10, summarized_units=1)
    assert cov["status"] == "fail"


def test_coverage_emit_keys_present():
    # emit_coverage 가 읽는 키가 모두 있는지 (webhook 호환).
    docs = {t: {"file": "x"} for t in _THEMES}
    cov = _init_coverage(_THEMES, docs, planned_units=4, summarized_units=4)
    for key in ("reached", "expected_count", "unreached", "coverage_pct", "status"):
        assert key in cov, f"emit_coverage 호환 키 {key} 누락"


# ── P2: unsupported_claim_count 되채움 ──────────────────────────────────


def test_doc_output_backfills_unsupported_claim_count():
    summary = {
        "docs": {
            "intro": {
                "file": "", "verdict": "warning", "warned": True,
                "blocking_findings": [
                    {"severity": "major", "claim": "근거 없는 주장 A"},
                    {"severity": "minor", "claim": "근거 없는 주장 B"},
                ],
            },
            "requirements": {
                "file": "", "verdict": "pass", "warned": False,
                "blocking_findings": [],
            },
        }
    }
    docs = _doc_quality_from_summary(summary)
    by_theme = {d["theme"]: d for d in docs}
    assert by_theme["intro"]["unsupported_claim_count"] == 2
    assert by_theme["requirements"]["unsupported_claim_count"] == 0


def test_doc_output_skipped_theme_zero_unsupported():
    summary = {"docs": {"api-protocol": {"skipped": True,
                                         "reason": "API 신호 없음"}}}
    docs = _doc_quality_from_summary(summary)
    # skip 문서도 doc output 에 나오되 unsupported=0.
    assert docs[0]["unsupported_claim_count"] == 0
