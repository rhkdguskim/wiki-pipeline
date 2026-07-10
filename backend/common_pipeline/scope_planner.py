"""Scope Planner — evidence 기반으로 어떤 문서를 생성/수정/스킵할지 결정한다.

raw/2026-07-08-ai-agent-output-quality-plan.md §2 Scope Planner 의 구현.
writer 가 모든 것을 다 쓰려 하지 않고 좁은 목적에 집중하게 한다 — skip 이 가능한
구조가 hallucination 과 비용을 줄인다.

입력:
    - static: change_units (변경 분류 결과) + evidence_pack
    - manual: scenario_results (시나리오 실행 결과) + coverage (커버리지)

출력 (raw 설계서 §2 schema):
    [{"theme", "action": "create|update|skip|deprecate-candidate",
      "reason", "required_evidence": [...], "risk", "focus": [...]}]
"""
from __future__ import annotations

# significance -> risk 매핑 (raw 설계서 §Static Agent Roles Change Classifier).
_SIG_TO_RISK = {
    "trivial": "low",
    "minor": "low",
    "material": "medium",
    "risky": "high",
}

# change_type 별 기본 영향 테마 (static_pipeline.theme_mapping 과 정합).
_CHANGE_TYPE_THEMES: dict[str, list[str]] = {
    "api": ["api-protocol", "architecture-overview"],
    "config": ["requirements", "dev-guide"],
    "architecture": ["architecture-overview", "component-diagram"],
    "ui": ["intro"],
    "build": ["requirements", "dev-guide"],
    "test": [],
    "docs": [],
}

# doc_impact 이 비어있을 때 기본 테마.
_DEFAULT_STATIC_THEMES = ("intro", "architecture-overview", "component-diagram")

# manual: 항상 2축(user/operator)을 기본으로. 단, terminal failure 면 user 만 스킵.
_DEFAULT_MANUAL_THEMES = ("user-manual", "operator-manual")


def _evidence_for_theme(pack: dict, theme: str, files: list[str] | None = None) -> list[str]:
    """테마에 해당하는 evidence item id 목록을 pack 에서 추출.

    files 가 주어지면 path 매칭되는 item 만, 아니면 전체 source_file item.
    """
    items = pack.get("items") or []
    if files:
        wanted = {f for f in files}
        matched = [it for it in items
                   if it.get("path") in wanted
                   or any(w in (it.get("path") or "") for w in wanted)]
    else:
        matched = [it for it in items if it.get("kind") == "source_file"]
    return [str(it.get("id")) for it in matched if it.get("id")]


def _evidence_for_kind(pack: dict, kind: str) -> list[str]:
    """특정 kind 의 evidence id 목록."""
    return [str(it.get("id")) for it in (pack.get("items") or [])
            if it.get("kind") == kind and it.get("id")]


def plan_static_docs(
    change_units: list[dict],
    evidence_pack: dict,
    *,
    existing_docs: list[str] | None = None,
) -> list[dict]:
    """static 파이프라인의 문서 생성/수정/스킵 계획을 세운다.

    Parameters
    ----------
    change_units:
        Change Classifier 출력 (raw 설계서 §Static Agent Roles):
        [{"id", "files", "change_type", "significance", "summary", "doc_impact"}]
        doc_impact 이 비어있으면 change_type 기본 매핑을 쓴다.
    evidence_pack:
        evidence_builder.build_evidence_pack 출력.
    existing_docs:
        이미 생성된 적 있는 테마 목록 (없으면 create, 있으면 update 판정용).
        None 이면 모두 create 로 간주.

    Returns
    -------
    list[dict]
        [{"theme", "action", "reason", "required_evidence", "risk", "focus"}]

    skip 조건:
    - change_units 가 빈 리스트 -> 모든 기본 테마 skip (변경 없음).
    - change_type 이 test/docs 만 있는 change_unit -> 그 unit 의 doc_impact 무시.
    - significance=trivial 이고 change_type 이 docs -> 스킵.
    """
    existing = set(existing_docs or [])

    # 변경 자체가 없으면 모든 기본 테마를 skip 으로 채운다.
    if not change_units:
        return [
            {
                "theme": t,
                "action": "skip",
                "reason": "변경 분류 결과 없음 — 문서화 대상 아님",
                "required_evidence": [],
                "risk": "low",
                "focus": [],
            }
            for t in _DEFAULT_STATIC_THEMES
        ]

    # change_unit 들에서 영향받는 테마를 모은다.
    theme_to_files: dict[str, list[str]] = {}
    theme_to_reasons: dict[str, list[str]] = {}
    theme_to_focus: dict[str, list[str]] = {}
    max_risk_per_theme: dict[str, str] = {}

    for cu in change_units:
        if not isinstance(cu, dict):
            continue
        cu_id = cu.get("id") or "(unknown)"
        files = cu.get("files") or []
        change_type = str(cu.get("change_type") or "").lower()
        significance = str(cu.get("significance") or "minor").lower()
        summary = str(cu.get("summary") or "")
        doc_impact = cu.get("doc_impact") or []

        # test/docs only 변경은 문서 생성에 기여하지 않는다 (skip 후보).
        if change_type in ("test", "docs") and not doc_impact:
            continue

        # 테마 결정 — doc_impact 우선, 없으면 change_type 기본 매핑.
        themes = [str(t) for t in doc_impact] if doc_impact else _CHANGE_TYPE_THEMES.get(
            change_type, list(_DEFAULT_STATIC_THEMES))

        risk = _SIG_TO_RISK.get(significance, "medium")
        for theme in themes:
            theme_to_files.setdefault(theme, []).extend(files)
            if summary:
                theme_to_reasons.setdefault(theme, []).append(
                    f"{cu_id}: {summary[:120]}")
            theme_to_focus.setdefault(theme, []).extend(
                [str(f) for f in files[:5]])
            # 위험도는 더 높은 쪽으로 승격.
            cur = theme_to_max_risk_per_theme(theme, max_risk_per_theme)
            max_risk_per_theme[theme] = _escalate_risk(cur, risk)

    # 변경된 파일이 하나도 없는 기본 테마는 skip.
    plans: list[dict] = []
    seen_themes = set(theme_to_files.keys())
    for theme in _DEFAULT_STATIC_THEMES:
        if theme in seen_themes:
            continue
        plans.append({
            "theme": theme,
            "action": "skip",
            "reason": "이번 변경에서 이 테마에 해당하는 파일이 없음",
            "required_evidence": [],
            "risk": "low",
            "focus": [],
        })

    # 영향받은 테마는 create 또는 update.
    for theme, files in theme_to_files.items():
        unique_files = sorted(set(files))
        required_evidence = _evidence_for_theme(evidence_pack, theme, unique_files)
        action = "update" if theme in existing else "create"
        plans.append({
            "theme": theme,
            "action": action,
            "reason": "; ".join(theme_to_reasons.get(theme, [f"{len(unique_files)}개 파일 변경"]))[:500],
            "required_evidence": required_evidence,
            "risk": theme_to_max_risk_per_theme(theme, max_risk_per_theme),
            "focus": sorted(set(theme_to_focus.get(theme, [])))[:8],
        })

    return plans


# init 에서 특정 테마가 근거를 요구할 때 요약 텍스트에서 찾는 신호어.
# init 은 change_units 가 없고 "전체 스캔"이라 diff 용 plan_static_docs 와 판정이 다르다.
_API_SIGNALS = (
    "api", "endpoint", "route", "rest", "grpc", "graphql", "websocket",
    "protocol", "rpc", "http", "swagger", "openapi",
    "엔드포인트", "프로토콜", "라우트",
)


def plan_static_init_docs(
    themes: list[str],
    summaries: list[tuple[str, str]],
) -> list[dict]:
    """init(전체 스캔) 경로의 테마 skip 계획.

    init 은 diff 와 달리 change_units 가 없다 — 근거는 map 단계 단위 요약이다.
    요약을 근거로 "이 테마를 쓸 재료가 있는가"만 보수적으로 판정한다. 기본은 생성
    (init 의 목적이 레포 전체 문서화이므로), 아래 경우만 skip:

    - 요약이 하나도 없으면 모든 테마 skip (근거 전무 — 상위에서 이미 걸러지나 방어).
    - component-diagram: 단위 요약이 2개 미만이면 skip (그릴 컴포넌트 관계가 없다).
    - api-protocol: 요약 전체에 API/프로토콜 신호어가 없으면 skip (근거 없는
      API 문서는 hallucination 위험이 크다).

    반환은 plan_static_docs 와 같은 schema — [{"theme","action","reason",
    "required_evidence","risk","focus"}]. action 은 create|skip.
    """
    n_units = len(summaries)
    blob = "\n".join(s for _u, s in summaries).lower()
    has_api = any(sig in blob for sig in _API_SIGNALS)

    plans: list[dict] = []
    for theme in themes:
        action, reason, risk = "create", "", "low"
        if n_units == 0:
            action, reason = "skip", "단위 요약 없음 — 문서화 근거 전무"
        elif theme == "component-diagram" and n_units < 2:
            action, reason = ("skip",
                              f"단위 요약이 {n_units}개뿐 — 컴포넌트 간 관계를 그릴 근거 부족")
        elif theme == "api-protocol" and not has_api:
            action, reason = ("skip",
                              "요약에서 API·프로토콜 신호를 찾지 못함 — 근거 없는 API 문서 회피")
        else:
            reason = f"단위 요약 {n_units}건을 근거로 생성"
        plans.append({
            "theme": theme,
            "action": action,
            "reason": reason,
            "required_evidence": [],
            "risk": risk,
            "focus": [],
        })
    return plans


def theme_to_max_risk_per_theme(theme: str, mapping: dict[str, str]) -> str:
    """theme 의 현재 risk 등급을 반환 (기본 'low')."""
    return mapping.get(theme, "low")


def _escalate_risk(current: str, new: str) -> str:
    """두 risk 등급 중 더 높은 쪽을 반환. low < medium < high."""
    order = {"low": 0, "medium": 1, "high": 2}
    return new if order.get(new, 1) > order.get(current, 0) else current


def plan_manual_docs(
    scenario_results: dict,
    coverage: dict,
    *,
    existing_docs: list[str] | None = None,
    coverage_threshold: float = 70.0,
) -> list[dict]:
    """manual 파이프라인의 문서 생성/수정/스킵 계획을 세운다.

    Parameters
    ----------
    scenario_results:
        run_scenarios 결과: {"completed": [...], "failed": [...],
                             "terminal_failure": str|None, ...}
    coverage:
        coverage assessor 출력: {"visited", "unreached",
                                 "coverage_pct", "confidence"}
    existing_docs:
        이미 생성된 매뉴얼 테마 목록 (create/update 판정용).
    coverage_threshold:
        coverage_pct 가 이 값 미만이면 user-manual 은 warning 또는 skip.

    Returns
    -------
    list[dict]
        [{"theme", "action", "reason", "required_evidence", "risk",
          "coverage_gate", "focus"}]

    skip/deprecate 조건:
    - terminal_failure 있고 critical scenario -> user-manual action=skip
    - coverage_pct < threshold -> user-manual action=update (경고), risk=high
    - 기존 문서가 있고 이번 관측이 없으면 -> deprecate-candidate
    """
    existing = set(existing_docs or [])
    completed = scenario_results.get("completed") or []
    failed = scenario_results.get("failed") or []
    terminal = scenario_results.get("terminal_failure")
    observations_count = (scenario_results.get("observation_count")
                          or scenario_results.get("observations") or 0)

    coverage_pct = float(coverage.get("coverage_pct") or coverage.get("pct") or 0.0)
    unreached = coverage.get("unreached") or []
    coverage_gate = "pass" if coverage_pct >= coverage_threshold else (
        "warning" if coverage_pct >= coverage_threshold * 0.5 else "fail")

    plans: list[dict] = []

    # user-manual — 절차 중심. coverage/terminal failure 에 민감.
    if terminal:
        plans.append({
            "theme": "user-manual",
            "action": "skip",
            "reason": f"required scenario 실패({terminal}) — 사용자 매뉴얼 생성 불가",
            "required_evidence": [],
            "risk": "high",
            "coverage_gate": coverage_gate,
            "focus": [],
        })
    elif observations_count == 0:
        plans.append({
            "theme": "user-manual",
            "action": "skip",
            "reason": "관측 0건 — 근거 없이 매뉴얼을 쓸 수 없다",
            "required_evidence": [],
            "risk": "high",
            "coverage_gate": "fail",
            "focus": [],
        })
    else:
        action = "update" if "user-manual" in existing else "create"
        risk = "high" if coverage_gate != "pass" else "medium"
        reason = (f"시나리오 {len(completed)}건 완료, {len(failed)}건 실패. "
                  f"coverage {coverage_pct:.1f}% (gate={coverage_gate})")
        focus: list[str] = []
        if unreached:
            # unreached 가 있으면 '관측 범위와 한계' 섹션에 명시하라고 focus 에 넣는다.
            focus.append("관측 범위와 한계 (미도달 기능 명시)")
            for u in unreached[:5]:
                if isinstance(u, dict):
                    focus.append(f"unreached: {u.get('id') or u.get('name') or u}")
                else:
                    focus.append(f"unreached: {u}")
        plans.append({
            "theme": "user-manual",
            "action": action,
            "reason": reason[:500],
            "required_evidence": [],  # critic 단계에서 observation id 로 채움
            "risk": risk,
            "coverage_gate": coverage_gate,
            "focus": focus[:12],
        })

    # operator-manual — 설치/설정/트러블슈팅. terminal failure 와 무관하게 생성 가능.
    if observations_count == 0:
        plans.append({
            "theme": "operator-manual",
            "action": "skip",
            "reason": "관측 0건 — 운영 매뉴얼도 근거 필요",
            "required_evidence": [],
            "risk": "high",
            "coverage_gate": "fail",
            "focus": [],
        })
    elif terminal:
        # operator-manual 은 critical scenario 실패와 무관하게 생성 가능 —
        # 오히려 트러블슈팅 섹션의 근거가 된다.
        action = "update" if "operator-manual" in existing else "create"
        plans.append({
            "theme": "operator-manual",
            "action": action,
            "reason": f"required scenario 실패({terminal}) — 트러블슈팅 섹션 근거로 활용",
            "required_evidence": [],
            "risk": "high",
            "coverage_gate": coverage_gate,
            "focus": ["오류·경고·대화상자와 대응", "실패한 시나리오 원인"],
        })
    else:
        action = "update" if "operator-manual" in existing else "create"
        plans.append({
            "theme": "operator-manual",
            "action": action,
            "reason": f"관측 {observations_count}건 — 운영 매뉴얼 근거 확보",
            "required_evidence": [],
            "risk": "medium",
            "coverage_gate": coverage_gate,
            "focus": ["실행 환경·설정·연결 항목", "관측된 오류·경고"],
        })

    # deprecate-candidate: 기존 문서 중 이번에 생성 안 한 것.
    generated = {p["theme"] for p in plans}
    for theme in existing:
        if theme in generated:
            continue
        plans.append({
            "theme": theme,
            "action": "deprecate-candidate",
            "reason": "이번 실행에서 생성하지 않은 기존 문서 — 관측 신호 없음",
            "required_evidence": [],
            "risk": "low",
            "coverage_gate": coverage_gate,
            "focus": [],
        })

    return plans


def actionable_plans(plans: list[dict]) -> list[dict]:
    """action != skip|deprecate-candidate 인 plan 만 필터 (writer 에 보낼 대상)."""
    skip_actions = {"skip", "deprecate-candidate"}
    return [p for p in plans if p.get("action") not in skip_actions]
