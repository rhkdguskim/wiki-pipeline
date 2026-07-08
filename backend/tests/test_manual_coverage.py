"""Manual coverage denominator + measurement (2026-07-08 review P1).

decision-coverage-metric-gap 구현: 탐색 자기보고를 넘어 measured denominator.
시나리오 expected + MCP UIA 후보 + 방문 기록을 합산.
"""
from __future__ import annotations

import pytest

from backend.manual_pipeline.scenarios import Scenario, ScenarioSet


def _ss(*scenario_ids: str) -> ScenarioSet:
    """시나리오 ID 들로 ScenarioSet 빌드 (required 는 없음)."""
    return ScenarioSet(scenarios=[Scenario(id=i, title=f"scenario {i}", required=False,
                                       continue_on_failure=True) for i in scenario_ids])


def test_build_denominator_from_scenarios_only():
    from backend.manual_pipeline.coverage import build_denominator
    ss = _ss("login", "home", "settings")
    class FakeBridge:
        def call(self, name, args):
            return False, ""
    denom = build_denominator(FakeBridge(), ss)
    assert set(denom["expected"]) == {"login", "home", "settings"}
    assert denom["count"] == 3
    assert "uia" in denom["sources"]
    assert denom["sources"]["uia"] == []


def test_build_denominator_with_uia_candidates():
    from backend.manual_pipeline.coverage import build_denominator, _extract_candidates
    text = '''
    Window: Main View
    Name: Settings Panel
    Title: "Profile"
    '''
    assert "Main View" in _extract_candidates(text)
    assert "Settings Panel" in _extract_candidates(text)
    assert "Profile" in _extract_candidates(text)

    ss = _ss("login")
    class UiaBridge:
        def call(self, name, args):
            return True, text
    denom = build_denominator(UiaBridge(), ss)
    assert "login" in denom["expected"]
    assert "Main View" in denom["expected"]
    assert "Settings Panel" in denom["expected"]


def test_measure_coverage_full_match():
    from backend.manual_pipeline.coverage import measure_coverage
    denom = {"expected": ["a", "b", "c"]}
    r = measure_coverage(["a", "b", "c"], denom)
    assert r["percentage"] == 100.0
    assert r["missed_count"] == 0
    assert r["reached"] == ["a", "b", "c"]


def test_measure_coverage_partial_match():
    from backend.manual_pipeline.coverage import measure_coverage
    denom = {"expected": ["a", "b", "c", "d"]}
    r = measure_coverage(["a", "b"], denom)
    assert r["percentage"] == 50.0
    assert r["missed_count"] == 2
    assert r["unreached"] == ["c", "d"]


def test_measure_coverage_empty_denominator():
    from backend.manual_pipeline.coverage import measure_coverage
    r = measure_coverage(["a", "b"], {"expected": []})
    assert r["percentage"] == 0.0


def test_measure_coverage_extra_visited_counted():
    from backend.manual_pipeline.coverage import measure_coverage
    r = measure_coverage(["a", "b", "extra"], {"expected": ["a", "b"]})
    assert r["percentage"] == 100.0
    assert r["extra_visited"] == ["extra"]


def test_assess_coverage_pass():
    from backend.manual_pipeline.coverage import assess_coverage
    sc = {"completed": ["login", "home", "settings"], "failed": []}
    exp = {"visited": ["login", "home", "settings"], "unreached": []}
    denom = {"expected": ["login", "home", "settings"], "count": 3,
            "sources": {"scenario_meta": []}}
    r = assess_coverage(sc, exp, denom, threshold=70.0)
    assert r["status"] == "pass"
    assert r["percentage"] == 100.0


def test_assess_coverage_warning_below_threshold():
    from backend.manual_pipeline.coverage import assess_coverage
    sc = {"completed": ["login"], "failed": []}
    exp = {"visited": ["login"]}
    denom = {"expected": ["login", "home", "settings"], "count": 3,
            "sources": {"scenario_meta": []}}
    r = assess_coverage(sc, exp, denom, threshold=66.0)
    assert r["status"] == "warning"
    assert 30 < r["percentage"] < 66


def test_assess_coverage_fail_required_scenario_failed():
    from backend.manual_pipeline.coverage import assess_coverage
    sc = {"completed": ["home"], "failed": ["login"]}
    exp = {"visited": ["home"]}
    denom = {"expected": ["login", "home"], "count": 2,
            "sources": {"scenario_meta": [
                {"id": "login", "required": True},
                {"id": "home", "required": False},
            ]}}
    r = assess_coverage(sc, exp, denom, threshold=70.0)
    assert r["status"] == "fail"
    assert r["scenario_required_failed"] is True


def test_assess_coverage_fail_severely_below_threshold():
    from backend.manual_pipeline.coverage import assess_coverage
    sc = {"completed": ["login"], "failed": []}
    exp = {"visited": ["login"]}
    denom = {"expected": ["login", "home", "settings", "admin"], "count": 4,
            "sources": {"scenario_meta": []}}
    r = assess_coverage(sc, exp, denom, threshold=80.0)
    assert r["status"] == "fail"
    assert r["scenario_required_failed"] is False
