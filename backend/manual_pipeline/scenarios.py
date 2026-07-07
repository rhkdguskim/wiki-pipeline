"""시나리오 세트 로드 — 하이브리드 순회의 결정적 뼈대.

decision-scenario-owner-dashboard: 실제 시스템에선 과제 담당자가 대시보드에서 정의·유지하고
서버 DB(SoT)에 app 등록의 일부로 저장된다. PoC는 그 자리를 로컬 JSON 파일로 대신한다
(소유·형식 사상은 동일 — 코드 배포 없이 편집 가능한 데이터).

decision-hybrid-app-traversal: 시나리오 = 결정적·재현 가능한 매뉴얼의 뼈대. LLM 없이
도구를 순서대로 실행한다. 세션 부트스트랩(Manager 서버 AddSession/Connect 등)도
"첫 시나리오"로 표현한다 — 서버마다 도구 이름·인자가 달라 코드 추측 대신 데이터로 둔다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScenarioStep:
    tool: str                                 # MCP 도구 이름 (연결된 서버 기준)
    args: dict = field(default_factory=dict)
    note: str = ""                            # 이 스텝의 의도 (매뉴얼 서술 힌트)


@dataclass
class Scenario:
    id: str
    title: str
    goal: str = ""
    audience: str = "user"                    # user | operator | both (독자 2축 매핑)
    steps: list[ScenarioStep] = field(default_factory=list)


@dataclass
class ScenarioSet:
    app: str = "대상 앱"
    scenarios: list[Scenario] = field(default_factory=list)


def load_scenarios(path: Path) -> ScenarioSet:
    """시나리오 파일 로드. 없으면 빈 세트 — 러너는 자율 탐색만으로 진행한다."""
    if not path.exists():
        return ScenarioSet()
    data = json.loads(path.read_text(encoding="utf-8"))
    scenarios: list[Scenario] = []
    for s in data.get("scenarios", []):
        steps = [ScenarioStep(tool=st["tool"], args=st.get("args", {}),
                              note=st.get("note", ""))
                 for st in s.get("steps", []) if st.get("tool")]
        scenarios.append(Scenario(
            id=s.get("id") or f"scenario-{len(scenarios) + 1}",
            title=s.get("title", s.get("id", "")),
            goal=s.get("goal", ""),
            audience=s.get("audience", "user"),
            steps=steps,
        ))
    return ScenarioSet(app=data.get("app", "대상 앱"), scenarios=scenarios)


def scenarios_summary(scenario_set: ScenarioSet, result: dict | None = None) -> str:
    """writer 프롬프트용 시나리오 요약 (뼈대·의도·수행 결과)."""
    if not scenario_set.scenarios:
        return "  (시나리오 없음 — 자율 탐색 관측만이 근거다)"
    lines = []
    for s in scenario_set.scenarios:
        status = ""
        if result:
            if s.id in result.get("completed", []):
                status = " [완료]"
            elif s.id in result.get("failed", []):
                status = " [일부 실패 — 해당 관측은 ERR 표시 참조]"
        lines.append(f"  - {s.id} (독자: {s.audience}): {s.title} — {s.goal}{status}")
    return "\n".join(lines)
