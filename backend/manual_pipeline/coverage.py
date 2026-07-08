"""커버리지 분모 산정 + 측정 — 탐색 자기보고를 넘어 측정 기반 denominator 구축.

P1 review (decision-coverage-metric-gap) 구현:
기존 coverage 는 explorer 의 visited/unreached 자기보고 JSON 만 썼다. 이 모듈은
측정 가능한 분모(denominator)를 세 source 에서 합산한다:
  1) scenario registry 가 기대하는 화면/기능 (시나리오 id + expected_screens)
  2) MCP UIA tree / window_list probe 로 발견한 후보
  3) run summary 산출 시점의 관측 로그 방문 기록

측정은 ID 문자열 교집합으로 한다. UIA tree 의 원시 텍스트에서 이름 토큰을 추출해
scenario id 및 explorer visited 와 같은 namespace 로 정규화한다. 완벽한 매칭이
아니더라도, "빈 denominator → 0% 가 아닌 측정값" 을 제공하는 것이 목표다.

설계 계약:
- bridge.call(name, args) -> (ok, text) 인터페이스 사용.
- 모든 함수는 dict 를 반환하고 예외를 raise 하지 않는다.
- assess_coverage 의 status 는 "pass"|"warning"|"fail" — runner 가 summary["coverage"]
  와 terminal status 판정에 쓴다.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..common.mcp_bridge import McpBridge
    from .scenarios import ScenarioSet

# UIA tree 응답에서 이름 후보를 추출하기 위한 단순 휴리스틱.
# 일반적인 형태: 'Name: Main Window', 'Window: Settings', '"Menu" [Button]' 등.
_NAME_LINE_RE = re.compile(
    r"(?:Name|Window|Title|Control)\s*[:：]\s*(.{1,80})", re.IGNORECASE)
# 따옴표로 감싸진 텍스트도 후보로 삼는다.
_QUOTED_RE = re.compile(r"[\"'“”]([^\"'“”]{1,80})[\"'“”]")

# coverage 가 비어 있을 때 대신 쓸 기본 denominator (최소 1로 나눗셈 방지).
_MIN_DENOMINATOR = 1


def _extract_candidates(text: str) -> list[str]:
    """MCP probe 응답 텍스트에서 화면/컨트롤 이름 후보를 추출한다.

    라벨:값 형식과 따옴표 텍스트를 잡고, 빈 줄/제어 문자를 정리한다.
    중복은 순서를 보존하며 제거한다.
    """
    seen: dict[str, None] = {}
    for m in _NAME_LINE_RE.finditer(text):
        _add_candidate(m.group(1).strip(), seen)
    for m in _QUOTED_RE.finditer(text):
        _add_candidate(m.group(1).strip(), seen)
    return list(seen)


def _add_candidate(raw: str, seen: dict[str, None]) -> None:
    name = raw.strip(" \t·-|[]()<>")
    if not name or len(name) < 2:
        return
    # 너무 토막난 토큰(단일 단어로 UI 식별자가 되기 어려운 경우)은 휴리스틱으로 거른다.
    if name.lower() in {"ok", "true", "false", "none", "null", "button", "menu",
                        "window", "panel", "dialog", "close", "open"}:
        return
    if name not in seen:
        seen[name] = None


def build_denominator(bridge: "McpBridge", scenario_set: "ScenarioSet") -> dict:
    """시나리오 registry + MCP UIA probe 를 합쳐 coverage denominator 를 만든다.

    반환: {"expected": [...], "count": int,
           "sources": {"scenarios": [...], "uia": [...], "scenario_meta": [...]}}
    - scenario id 를 expected 에 넣고, 추가로 scenario 의 expected_screens list 를
      합친다 (있다면). UIA probe 는 window_list → uia_tree 순으로 시도.
    """
    from_scenarios: list[str] = []
    scenario_meta: list[dict] = []
    for sc in scenario_set.scenarios:
        from_scenarios.append(sc.id)
        # scenario 가 expected_screens/expected_features 를 달고 있으면 합산.
        meta = getattr(sc, "expected_screens", None) or _scenario_extra(sc, "expected_screens")
        if isinstance(meta, list):
            for s in meta:
                if isinstance(s, str) and s not in from_scenarios:
                    from_scenarios.append(s)
        feat = getattr(sc, "expected_features", None) or _scenario_extra(sc, "expected_features")
        if isinstance(feat, list):
            for s in feat:
                if isinstance(s, str) and s not in from_scenarios:
                    from_scenarios.append(s)
        scenario_meta.append({"id": sc.id, "title": sc.title, "required": sc.required})

    from_uia: list[str] = []
    for probe in ("uia_tree", "window_list"):
        if not from_uia:
            ok, text = bridge.call(probe, {})
            if ok and text:
                from_uia = _extract_candidates(text)
                if from_uia:
                    break

    expected = _union_preserve_order(from_scenarios + from_uia)
    return {"expected": expected, "count": len(expected),
            "sources": {"scenarios": from_scenarios, "uia": from_uia,
                        "scenario_meta": scenario_meta}}


def _scenario_extra(scenario, key: str):
    """Scenario dataclass 에 없을 수 있는 확장 필드를 dict 에서 안전하게 꺼낸다."""
    raw = getattr(scenario, key, None)
    if raw is not None:
        return raw
    # dataclass 가 __dict__ 를 가지면 거기서도 찾아본다.
    return getattr(scenario, "__dict__", {}).get(key)


def _union_preserve_order(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for it in items:
        if it and it not in seen:
            seen[it] = None
    return list(seen)


def measure_coverage(visited: list[str], denominator: dict) -> dict:
    """visited(탐색/시나리오가 도달한 ID)를 denominator 에 대해 측정한다.

    반환: {"percentage": float, "reached": [...], "unreached": [...],
           "missed_count": int, "expected_count": int, "extra_count": int}
    - reached    : denominator ∩ visited
    - unreached  : denominator − visited
    - extra      : visited − denominator (denominator 밖이라 무시)
    - percentage : reached / max(count, 1) * 100
    """
    expected: list[str] = list(denominator.get("expected") or [])
    visited_set = set(visited or [])
    reached = [e for e in expected if e in visited_set]
    unreached = [e for e in expected if e not in visited_set]
    extra = [v for v in (visited or []) if v not in set(expected)]
    count = max(len(expected), _MIN_DENOMINATOR)
    percentage = round((len(reached) / count) * 100, 2) if count else 0.0
    return {"percentage": percentage, "reached": reached,
            "unreached": unreached, "missed_count": len(unreached),
            "expected_count": len(expected), "extra_count": len(extra),
            "extra_visited": extra}


def assess_coverage(scenario_results: dict, exploration_coverage: dict,
                    denominator: dict, threshold: float) -> dict:
    """시나리오 결과 + 탐색 자기보고 + denominator 를 합쳐 coverage 평가를 낸다.

    반환: {"status": "pass"|"warning"|"fail", "percentage": float,
           "reached": [...], "unreached": [...], "missed_count": int,
           "expected_count": int, "scenario_required_failed": bool,
           "threshold": float, "note": str}
    - status:
        fail    required scenario 실패 가 있거나 percentage < threshold * 0.5
        warning percentage < threshold (하지만 fail 기준은 넘음)
        pass    그 외
    - reached/unreached 는 scenario completed id + explorer visited 를 합쳐
      denominator 에 대해 measure 한 결과를 따른다.
    """
    scenario_completed: list[str] = list(scenario_results.get("completed") or [])
    scenario_failed: list[str] = list(scenario_results.get("failed") or [])
    explore_visited: list[str] = list(exploration_coverage.get("visited") or [])

    visited_all = _union_preserve_order(scenario_completed + explore_visited)
    measured = measure_coverage(visited_all, denominator)
    percentage = measured["percentage"]

    required_meta = [
        m for m in (denominator.get("sources", {}).get("scenario_meta") or [])
        if isinstance(m, dict) and m.get("required")
    ]
    required_ids = {m.get("id") for m in required_meta if m.get("id")}
    required_failed = any(fid in scenario_failed for fid in required_ids)

    fail_floor = threshold * 0.5
    if required_failed or percentage < fail_floor:
        status = "fail"
    elif percentage < threshold:
        status = "warning"
    else:
        status = "pass"

    note = (f"threshold={threshold}% measured={percentage}% "
            f"required_failed={required_failed}")

    return {"status": status, "percentage": percentage,
            "reached": measured["reached"], "unreached": measured["unreached"],
            "missed_count": measured["missed_count"],
            "expected_count": measured["expected_count"],
            "scenario_required_failed": required_failed,
            "threshold": threshold, "note": note,
            "scenario_completed": scenario_completed,
            "scenario_failed": scenario_failed,
            "explore_visited": explore_visited,
            "extra_visited": measured.get("extra_visited", [])}
