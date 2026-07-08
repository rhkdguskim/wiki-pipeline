"""AI agent output quality eval fixtures — golden verdicts for regression testing.

설계: raw/2026-07-08-ai-agent-output-quality-plan.md §Evaluation Plan.
목표: prompt 변경이 산출물 품질을 올렸는지/망쳤는지 기계적 회귀 판단.
LLM 없이 deterministic verifier + citation checker + quality gate 만으로 판정한다.
"""
from __future__ import annotations

import json
import re

import pytest

from backend.common_pipeline.verify import DOC_END_MARKER, invalid_doc_reason


# ── helpers ──────────────────────────────────────────────────

SECRET_PATTERN = re.compile(
    r"(?:password|passwd|pwd|token|api[_-]?key|apikey|secret)"
    r"\s*[=:]\s*\S+",
    re.IGNORECASE,
)
MERMAID_FENCE = re.compile(r"```mermaid\n.*?\n```", re.DOTALL)


def _has_frontmatter(doc: str, required_keys: tuple[str, ...] = ()) -> bool:
    if not doc.startswith("---\n"):
        return False
    end = doc.find("\n---", 4)
    if end < 0:
        return False
    fm = doc[4:end]
    return all(k in fm for k in required_keys)


def _has_doc_end(doc: str) -> bool:
    return DOC_END_MARKER in doc


def _fences_closed(doc: str) -> bool:
    return doc.count("```") % 2 == 0


def _no_secrets(doc: str) -> bool:
    return not SECRET_PATTERN.search(doc)


def _evidence_ids_cited(doc: str, available_ids: set[str]) -> list[str]:
    cited = set(re.findall(r"\[e(\d+)\]", doc))
    missing = [f"e{c}" for c in sorted(cited) if f"e{c}" not in available_ids]
    return missing


# ── Static Eval Fixtures ─────────────────────────────────────

STATIC_FIXTURES: list[dict] = [
    {
        "id": "static-config-change",
        "description": "config 환경변수 변경 — architecture-overview 생성",
        "doc": "---\ntheme: architecture-overview\nsource_id: demo\ngenerated_from:\n  from_sha: aaa\n  to_sha: bbb\n---\n\n# Architecture Overview\n\n시스템은 Control Plane과 Data Plane으로 구성된다 [e1].\n\n## Components\n\nControl Plane은 FastAPI 기반이다 [e2].\n\n" + DOC_END_MARKER,
        "evidence_ids": {"e1", "e2"},
        "required_fm_keys": ("theme:", "source_id:"),
        "expected": {"valid": True, "has_mermaid": False, "secrets": False},
    },
    {
        "id": "static-api-change",
        "description": "API endpoint 추가 — api-protocol 문서 생성",
        "doc": "---\ntheme: api-protocol\nsource_id: demo\n---\n\n# API Protocol\n\nPOST /api/runs/trigger [e1]\n\n" + DOC_END_MARKER,
        "evidence_ids": {"e1"},
        "required_fm_keys": ("theme:",),
        "expected": {"valid": True, "has_mermaid": False, "secrets": False},
    },
    {
        "id": "static-doc-only-change",
        "description": "docs-only 변경 — skip 가능",
        "doc": "",
        "evidence_ids": set(),
        "required_fm_keys": (),
        "expected": {"valid": True, "skip": True, "has_mermaid": False, "secrets": False},
    },
    {
        "id": "static-risky-migration",
        "description": "risky migration — critic 기준 높임",
        "doc": "---\ntheme: architecture-overview\nsource_id: demo\n---\n\n# Architecture Overview\n\n마이그레이션으로 DB 스키마가 변경된다 [e1].\n\n```mermaid\ngraph LR\n  A-->B\n```\n\n" + DOC_END_MARKER,
        "evidence_ids": {"e1"},
        "required_fm_keys": ("theme:",),
        "expected": {"valid": True, "has_mermaid": True, "secrets": False},
    },
    {
        "id": "static-no-source-change",
        "description": "변경 없음 — skip",
        "doc": "",
        "evidence_ids": set(),
        "required_fm_keys": (),
        "expected": {"valid": True, "skip": True, "has_mermaid": False, "secrets": False},
    },
    {
        "id": "static-secret-leak",
        "description": "secret 누출 — deterministic verifier fail",
        "doc": "---\ntheme: dev-guide\nsource_id: demo\n---\n\n# Dev Guide\n\nDATABASE_URL=postgres://user:password=secret123@host:5432/db [e1]\n\n" + DOC_END_MARKER,
        "evidence_ids": {"e1"},
        "required_fm_keys": ("theme:",),
        "expected": {"valid": False, "secrets": True},
    },
    {
        "id": "static-missing-doc-end",
        "description": "DOC-END 마커 누락 — 절단된 문서",
        "doc": "---\ntheme: architecture-overview\nsource_id: demo\n---\n\n# Architecture Overview\n\n시스템 구조 설명 [e1]",
        "evidence_ids": {"e1"},
        "required_fm_keys": ("theme:",),
        "expected": {"valid": False},
    },
    {
        "id": "static-unclosed-fence",
        "description": "코드 펜스 미닫힘",
        "doc": "---\ntheme: dev-guide\nsource_id: demo\n---\n\n# Dev Guide\n\n```python\nimport os\n\n",
        "evidence_ids": set(),
        "required_fm_keys": ("theme:",),
        "expected": {"valid": False},
    },
]


# ── Manual Eval Fixtures ─────────────────────────────────────

MANUAL_FIXTURES: list[dict] = [
    {
        "id": "manual-happy-path",
        "description": "정상 시나리오 — user-manual 생성",
        "doc": "---\ntheme: manual/user-guide\nsource_id: demo\nrelease:\n  tag: v1.0.0\n  artifact: app.msi\nmanual_profile: profile-demo\nsource_observations: [o1, o2]\ncoverage:\n  pct: 85.0\n  unreached_count: 2\n---\n\n# User Manual\n\n앱을 실행한다 [o1].\n\n로그인 버튼을 클릭한다 [o2].\n\n" + DOC_END_MARKER,
        "evidence_ids": {"o1", "o2"},
        "observation_ids": {"o1", "o2"},
        "required_fm_keys": ("theme:", "release:", "source_observations:"),
        "expected": {"valid": True, "coverage_pass": True},
    },
    {
        "id": "manual-err-observation",
        "description": "ERR observation을 성공으로 서술",
        "doc": "---\ntheme: manual/user-guide\nsource_id: demo\nrelease:\n  tag: v1.0.0\n  artifact: app.msi\nsource_observations: [o1]\n---\n\n# User Manual\n\n로그인이 성공적으로 완료된다 [o1].\n\n" + DOC_END_MARKER,
        "evidence_ids": {"o1"},
        "observation_ids": {"o1"},
        "observation_errors": {"o1": "ERR: login button not found"},
        "required_fm_keys": ("theme:", "release:"),
        "expected": {"valid": True, "has_err_observation": True},
    },
    {
        "id": "manual-unreached-hidden",
        "description": "unreached 기능을 숨김",
        "doc": "---\ntheme: manual/user-guide\nsource_id: demo\nrelease:\n  tag: v1.0.0\n  artifact: app.msi\nsource_observations: [o1]\ncoverage:\n  pct: 45.0\n  unreached_count: 8\n---\n\n# User Manual\n\n모든 기능이 정상 동작한다 [o1].\n\n" + DOC_END_MARKER,
        "evidence_ids": {"o1"},
        "observation_ids": {"o1"},
        "required_fm_keys": ("theme:", "release:"),
        "expected": {"valid": True, "coverage_pass": False, "hides_unreached": True},
    },
    {
        "id": "manual-uncited-claim",
        "description": "관측 근거 없는 UI claim",
        "doc": "---\ntheme: manual/user-guide\nsource_id: demo\nrelease:\n  tag: v1.0.0\n  artifact: app.msi\nsource_observations: [o1]\n---\n\n# User Manual\n\n설정 메뉴에서 언어를 변경할 수 있다.\n\n" + DOC_END_MARKER,
        "evidence_ids": {"o1"},
        "observation_ids": {"o1"},
        "required_fm_keys": ("theme:", "release:"),
        "expected": {"valid": True, "uncited_claim": True},
    },
    {
        "id": "manual-low-coverage",
        "description": "coverage threshold 미달",
        "doc": "---\ntheme: manual/user-guide\nsource_id: demo\nrelease:\n  tag: v1.0.0\n  artifact: app.msi\nsource_observations: [o1]\ncoverage:\n  pct: 35.0\n  unreached_count: 12\n---\n\n# User Manual\n\n기본 화면을 설명한다 [o1].\n\n## 관측 범위와 한계\n\nCoverage 35% — 미도달 기능이 많다.\n\n" + DOC_END_MARKER,
        "evidence_ids": {"o1"},
        "observation_ids": {"o1"},
        "required_fm_keys": ("theme:", "release:"),
        "expected": {"valid": True, "coverage_pass": False},
    },
    {
        "id": "manual-deprecated-candidate",
        "description": "deprecated 후보",
        "doc": "---\ntheme: manual/user-guide\nsource_id: demo\nrelease:\n  tag: v0.9.0\n  artifact: app-old.msi\nsource_observations: []\nstatus: deprecated\n---\n\n# User Manual (Legacy)\n\n" + DOC_END_MARKER,
        "evidence_ids": set(),
        "observation_ids": set(),
        "required_fm_keys": ("theme:",),
        "expected": {"valid": True, "deprecated": True},
    },
]


# ── Eval runner ──────────────────────────────────────────────

def run_static_eval(fixture: dict) -> dict:
    if fixture["expected"].get("skip"):
        return {"fixture": fixture["id"], "verdict": "skip", "reason": "no source change"}
    doc = fixture["doc"]
    issues: list[str] = []
    if not _has_frontmatter(doc, fixture["required_fm_keys"]):
        issues.append("frontmatter_missing")
    if not _has_doc_end(doc):
        issues.append("doc_end_missing")
    if not _fences_closed(doc):
        issues.append("fence_unclosed")
    if not _no_secrets(doc):
        issues.append("secret_leak")
    missing_evidence = _evidence_ids_cited(doc, fixture["evidence_ids"])
    if missing_evidence:
        issues.append(f"missing_evidence:{missing_evidence}")
    has_mermaid = bool(MERMAID_FENCE.search(doc))
    if fixture["expected"].get("has_mermaid") and not has_mermaid:
        issues.append("mermaid_expected_missing")
    valid = len(issues) == 0
    expected_valid = fixture["expected"]["valid"]
    passed = valid == expected_valid
    return {
        "fixture": fixture["id"],
        "verdict": "pass" if passed else "fail",
        "valid": valid,
        "issues": issues,
        "has_mermaid": has_mermaid,
    }


def run_manual_eval(fixture: dict) -> dict:
    doc = fixture["doc"]
    issues: list[str] = []
    if not _has_frontmatter(doc, fixture["required_fm_keys"]):
        issues.append("frontmatter_missing")
    if not _has_doc_end(doc):
        issues.append("doc_end_missing")
    if not _fences_closed(doc):
        issues.append("fence_unclosed")
    cited_obs = set(re.findall(r"\[o(\d+)\]", doc))
    available_obs = fixture.get("observation_ids", set())
    missing_obs = [f"o{c}" for c in sorted(cited_obs) if f"o{c}" not in available_obs]
    if missing_obs:
        issues.append(f"missing_observation:{missing_obs}")
    obs_errors = fixture.get("observation_errors", {})
    for o in cited_obs:
        oid = f"o{o}"
        if oid in obs_errors:
            if not any(kw in doc.lower() for kw in ("실패", "err", "오류", "불가", "실행할 수 없")):
                issues.append(f"err_observation_as_success:{oid}")
    if fixture["expected"].get("uncited_claim"):
        sentences = re.findall(r"[^.]+\.", doc)
        for s in sentences:
            if "[o" not in s and len(s.strip()) > 20 and "관측 범위" not in s:
                issues.append("uncited_claim")
                break
    if fixture["expected"].get("hides_unreached"):
        if "관측 범위" not in doc and "한계" not in doc and "미도달" not in doc:
            issues.append("hides_unreached")
    valid = len(issues) == 0
    expected_valid = fixture["expected"]["valid"]
    coverage_pct = 0.0
    fm_match = re.search(r"pct:\s*([\d.]+)", doc)
    if fm_match:
        coverage_pct = float(fm_match.group(1))
    coverage_pass = coverage_pct >= 70.0
    if fixture["expected"].get("coverage_pass") is False and coverage_pass:
        issues.append("coverage_should_fail")
    passed = (valid == expected_valid) and not any("err_observation" in i for i in issues)
    return {
        "fixture": fixture["id"],
        "verdict": "pass" if passed else "fail",
        "valid": valid,
        "issues": issues,
        "coverage_pct": coverage_pct,
        "coverage_pass": coverage_pass,
    }


# ── Tests ────────────────────────────────────────────────────

@pytest.mark.parametrize("fixture", STATIC_FIXTURES, ids=[f["id"] for f in STATIC_FIXTURES])
def test_static_eval_fixture(fixture):
    result = run_static_eval(fixture)
    if result["verdict"] == "skip":
        assert fixture["expected"].get("skip"), f"{fixture['id']}: unexpected skip"
        return
    assert result["verdict"] == "pass", f"{fixture['id']}: {result['issues']}"


@pytest.mark.parametrize("fixture", MANUAL_FIXTURES, ids=[f["id"] for f in MANUAL_FIXTURES])
def test_manual_eval_fixture(fixture):
    result = run_manual_eval(fixture)
    if fixture["expected"].get("has_err_observation"):
        assert any("err_observation_as_success" in i for i in result["issues"]), \
            f"{fixture['id']}: ERR observation should be detected"
    elif fixture["expected"].get("uncited_claim"):
        assert "uncited_claim" in result["issues"], \
            f"{fixture['id']}: uncited claim should be detected"
    elif fixture["expected"].get("hides_unreached"):
        assert "hides_unreached" in result["issues"], \
            f"{fixture['id']}: hidden unreached should be detected"
    else:
        assert result["verdict"] == "pass", f"{fixture['id']}: {result['issues']}"


def test_eval_suite_metrics():
    static_results = [run_static_eval(f) for f in STATIC_FIXTURES]
    manual_results = [run_manual_eval(f) for f in MANUAL_FIXTURES]
    all_results = [r for r in static_results if r["verdict"] != "skip"] + manual_results
    total = len(all_results)
    positive = [r for r in all_results if "err_observation" not in str(r["issues"])
                and "uncited_claim" not in str(r["issues"])
                and "hides_unreached" not in str(r["issues"])
                and "coverage_should_fail" not in str(r["issues"])]
    pos_total = len(positive)
    pos_passed = sum(1 for r in positive if r["verdict"] == "pass")
    pass_rate = pos_passed / pos_total if pos_total else 1.0
    assert pass_rate >= 0.8, f"pass rate {pass_rate:.1%} < 80% — regression detected"
    skip_count = sum(1 for r in static_results if r["verdict"] == "skip")
    assert skip_count == 2, "skip fixtures should be exactly 2"
    detection_fixtures = total - pos_total
    assert detection_fixtures >= 3, "at least 3 detection-test fixtures expected"
