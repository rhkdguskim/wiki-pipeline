"""하이브리드 순회 — 시나리오(결정적 뼈대) + 자율 탐색(커버리지 보완).

decision-hybrid-app-traversal 구현:
- 시나리오는 LLM 없이 MCP 도구를 순서대로 실행한다 — 결정적·재현 가능. 매뉴얼의 뼈대.
- 탐색 에이전트가 시나리오가 못 덮은 화면·기능을 훑는다 — 커버리지 보완.

탐색 그래프에는 SqliteSaver 체크포인터를 물려, 중단돼도 같은 run_id(--resume)로
탐색 루프를 이어간다 (README L4: 체크포인트 중단 재개). 관측은 ObservationLog JSONL로
이미 영속이라 시나리오는 재실행하지 않고 기록을 재사용한다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from ..common import events as ev
from ..common.mcp_bridge import McpBridge
from ..common.run import final_text, run_graph
from ..common.textproc import extract_json_obj
from .graph import build_explorer_graph
from .observation import ObservationLog
from .scenarios import ScenarioSet


def run_scenarios(bridge: McpBridge, scenario_set: ScenarioSet,
                  log: ObservationLog, rev) -> dict:
    """시나리오를 결정적으로 실행. resume 시 이미 관측된 시나리오는 건너뛴다."""
    result: dict = {"completed": [], "failed": [], "skipped": [], "steps": 0}
    for sc in scenario_set.scenarios:
        stage = f"scenario:{sc.id}"
        if log.scenario_ran(sc.id):
            result["skipped"].append(sc.id)
            rev("engine_call", stage, "done",
                detail={"note": "관측 기록 있음(재개) — 재실행 안 함"})
            continue
        rev("engine_call", stage, "running",
            detail={"title": sc.title, "audience": sc.audience, "steps": len(sc.steps)})
        log.set_phase(f"scenario:{sc.id}")
        ok_all = True
        for st in sc.steps:
            rev("agent_step", stage, "running", detail=ev.tool_use(st.tool, st.args))
            ok, text = bridge.call(st.tool, st.args)
            rev("agent_step", stage, "running", detail=ev.tool_result(ok, text))
            result["steps"] += 1
            if not ok:
                ok_all = False   # 스텝 실패는 기록하고 계속 — 관측 로그에 ERR로 남는다
        (result["completed"] if ok_all else result["failed"]).append(sc.id)
        rev("engine_call", stage, "done" if ok_all else "failed",
            detail={"ok": ok_all})
    return result


def run_exploration(
    *, model, bridge: McpBridge, settings, run_id: str, observer,
    log: ObservationLog, scenario_set: ScenarioSet, resume: bool, out_dir: Path,
) -> dict:
    """자율 탐색 1회 실행(체크포인트 지원) -> 탐색 에이전트의 커버리지 자기보고 반환."""
    log.set_phase("explore")
    max_steps = settings.manual_explore_steps
    conn = sqlite3.connect(str(out_dir / "checkpoints.sqlite"), check_same_thread=False)
    try:
        graph = build_explorer_graph(
            model=model, tools=bridge.sync_tools(settings.manual_allowlist),
            run_id=run_id, app=scenario_set.app, max_steps=max_steps,
            scenario_titles=[s.title for s in scenario_set.scenarios],
            checkpointer=SqliteSaver(conn),
        )
        config = {"configurable": {"thread_id": f"{run_id}:explore"},
                  "recursion_limit": max_steps * 2 + 8}
        # resume이면 입력 None — 체크포인트의 마지막 상태에서 루프를 이어간다.
        initial = None if resume else {
            "messages": [HumanMessage(content=(
                "앱 탐색을 시작하라. 화면 정보 확인부터 시작해 안전하게 순회하고, "
                "끝나면 커버리지 JSON만 출력하라."))],
        }
        final = run_graph(graph, initial, observer, config=config)
        coverage = extract_json_obj(final_text(final), "visited")
        if not coverage:
            coverage = {"visited": [], "unreached": [],
                        "notes": "탐색 에이전트가 커버리지 JSON을 출력하지 않음"}
        return coverage
    finally:
        conn.close()
