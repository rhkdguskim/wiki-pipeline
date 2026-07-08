"""매뉴얼 파이프라인 러너 — 7단계 흐름의 결정적 오케스트레이션.

entity-manual-pipeline의 실행 흐름을 PoC 범위로 구현한다:
  1) 아티팩트 수집  — 스텁 (릴리스 태그->아티팩트 소비는 PoC 밖, decision-artifact-consumption)
  2) 배포          — 스텁 (앱은 세션 호스트에서 이미 실행 중 가정, decision-app-host-connection)
  3) 실행/연결     — MCP SSE 연결 + 도구 로드 (L1)
  4) 전수 순회     — 하이브리드: 시나리오(결정적) + 자율 탐색(체크포인트) (L2·L4)
  5) 생성 + diff   — 관측 근거 매뉴얼 생성(critic grounding) + 라이프사이클 판정 (L3)
  6) 제출          — docs-hub MR 스텁 (common.docshub)
  7) 보고          — 버전 포인터 전진은 MR 머지 후 (PoC 스텁, concept-idempotent-sha)

판단(탐색·생성·검증)만 에이전트, 나머지는 일반 코드 — 정적 러너와 같은 계약.
러너 골격(run_id·observer·run 이벤트·자원 정리)은 common_pipeline.run_context 공용.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..common.config import Settings
from ..common.docshub import submit_mr_stub
from ..common.llm import build_chat_model
from ..common.mcp_bridge import McpBridge
from ..common_pipeline.output import save_doc
from ..common_pipeline.run_context import RunContext
from .generate import generate_with_critic
from .lifecycle import judge_action, mark_deprecated_candidates
from .observation import ObservationLog
from .scenarios import load_scenarios, scenarios_from_dict, scenarios_summary
from .themes import DEFAULT_THEMES
from .traversal import run_exploration, run_scenarios


def _bridge_for(settings: Settings, log: ObservationLog,
                out_dir: Path, run_id: str) -> McpBridge:
    """MCP 브리지 구성 — 모든 도구 호출을 관측 로그에 기록하도록 콜백을 물린다.

    브리지 자체는 common 런타임(파이프라인 무지)이고, '호출은 곧 관측'이라는
    grounding 감사 추적(concept-observation-grounding)은 여기서 주입한다.
    """
    return McpBridge(
        endpoint_url=settings.mcp_endpoint_url, transport=settings.mcp_transport,
        shots_dir=out_dir / "shots", run_id=run_id,
        tool_timeout=settings.manual_tool_timeout,
        on_record=lambda tool, args, ok, preview: log.record(
            tool=tool, args=args, ok=ok, preview=preview),
    )


def run_manual(
    settings: Settings,
    *,
    run_id: str | None = None,
    scenarios_file: str | None = None,
    scenarios_data: dict | None = None,
    themes: list[str] | None = None,
    explore_steps: int | None = None,
    resume: bool = False,
    no_explore: bool = False,
    strict_allowlist: bool = False,
) -> dict:
    """매뉴얼 파이프라인 실행.

    run_id:
      - None → RunContext 가 새 run_id 를 발급 (로컬 CLI 신규 실행).
      - 외부 주입(Control Plane) → 그 run_id 를 그대로 쓴다. 이때 resume=False 면
        신규 run 으로 취급 (체크포인트 무시). resume=True 면 같은 run_id 의
        체크포인트·관측 JSONL 을 이어간다 (CLI --resume 경로).

    scenarios_data: DB scenario_set JSON (dict). scenarios_file 보다 우선.
    strict_allowlist: True 면 MCP 도구 allowlist 가 비어 있을 때 에러 (production).
    """
    resume = bool(resume) and bool(run_id)
    if explore_steps:
        settings.manual_explore_steps = explore_steps
    themes = themes or settings.manual_theme_list or DEFAULT_THEMES

    with RunContext("manual", settings, run_stage="manual-run",
                    run_id=run_id) as ctx:
        rev = ctx.rev
        out_dir = settings.out_path / "manual"
        out_dir.mkdir(parents=True, exist_ok=True)
        # 관측 JSONL은 run_id 단위 영속 — resume 시 이어서 기록·재사용한다.
        log = ctx.track(ObservationLog.load(out_dir / f"observations-{ctx.run_id}.jsonl"))
        bridge = ctx.track(_bridge_for(settings, log, out_dir, ctx.run_id))
        summary: dict = {"run_id": ctx.run_id, "themes": {}, "observations": 0,
                         "coverage": {}, "lifecycle": {}, "warned": []}

        ctx.start(detail={"endpoint": settings.mcp_endpoint_url,
                          "transport": settings.mcp_transport, "resume": resume})

        # 1·2) 아티팩트·배포 — PoC 스텁 (흐름 자리 유지)
        rev("stage", "artifact", "done",
            detail={"note": "스텁 — 릴리스 태그->아티팩트 획득은 PoC 범위 밖"})
        rev("stage", "deploy", "done",
            detail={"note": "스텁 — 앱은 세션 호스트에서 이미 실행 중 가정"})

        # 3) 연결 — MCP SSE + 도구 로드 (L1)
        rev("stage", "connect", "running")
        names = bridge.connect()
        rev("stage", "connect", "done",
            detail={"tools": len(names), "sample": names[:8]})

        # 4) 전수 순회 — 하이브리드 (decision-hybrid-app-traversal)
        if scenarios_data:
            scenario_set = scenarios_from_dict(scenarios_data)
        else:
            sc_path = Path(scenarios_file) if scenarios_file else settings.manual_scenario_path
            scenario_set = load_scenarios(sc_path)
        rev("stage", "traverse-scenario", "running",
            detail={"scenarios": [s.id for s in scenario_set.scenarios]})
        sc_result = run_scenarios(bridge, scenario_set, log, rev)
        rev("stage", "traverse-scenario", "done", detail=sc_result)

        if sc_result.get("terminal_failure"):
            ctx.failed({"error": f"required scenario failed: "
                                  f"{sc_result['terminal_failure']}"})
            summary["error"] = f"required scenario failed: {sc_result['terminal_failure']}"
            return summary

        model = build_chat_model(settings)
        explore_cov: dict = {"visited": [], "unreached": [], "notes": "탐색 생략(--no-explore)"}
        if not no_explore:
            rev("stage", "traverse-explore", "running",
                detail={"max_steps": settings.manual_explore_steps, "resume": resume})
            explore_cov = run_exploration(
                model=model, bridge=bridge, settings=settings, run_id=ctx.run_id,
                observer=ctx.observer, log=log, scenario_set=scenario_set,
                resume=resume, out_dir=out_dir,
                strict_allowlist=strict_allowlist,
            )
            rev("stage", "traverse-explore", "done",
                detail={"visited": len(explore_cov.get("visited", [])),
                        "unreached": len(explore_cov.get("unreached", []))})

        # 커버리지 합산 + 누락 표시 (decision-coverage-metric-gap)
        coverage = {
            "scenarios": sc_result,
            "explore": explore_cov,
            "observations": len(log.items),
            "note": ("visited/unreached는 탐색 에이전트 자기보고 기반 추정 — "
                     "전체 기능 집합 산정은 열린 문제(위키 decision-coverage-metric-gap)"),
        }
        (out_dir / f"coverage-{ctx.run_id}.json").write_text(
            json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["coverage"] = coverage
        summary["observations"] = len(log.items)
        rev("stage", "coverage", "done",
            detail={"observations": len(log.items),
                    "unreached": explore_cov.get("unreached", [])[:5]})

        if not log.items:
            ctx.failed({"error": "관측 0건 — 시나리오·탐색 모두 근거를 만들지 못함"})
            return summary

        # 5) 매뉴얼 생성 + 라이프사이클 (concept-observation-grounding / manual-lifecycle-diff)
        evidence = log.evidence_block()
        scenarios_block = scenarios_summary(scenario_set, sc_result)
        coverage_block = json.dumps(explore_cov, ensure_ascii=False)
        for i, theme in enumerate(themes, 1):
            stage = f"manual:{theme}"
            action = judge_action(out_dir, theme)
            rev("engine_call", stage, "running",
                progress={"n": i, "m": len(themes), "unit": "manual"},
                detail={"lifecycle": action})
            doc_md, verdict, warned = generate_with_critic(
                model=model, theme_key=theme, evidence=evidence,
                scenarios_block=scenarios_block, coverage_block=coverage_block,
                run_id=ctx.run_id, run_ref=ctx.run_id, stage=stage,
                observer=ctx.observer, emit_ctx=rev,
            )
            path = save_doc(out_dir, theme, doc_md)
            mr = submit_mr_stub(theme, path, settings.docshub_mr_enabled)   # 6) 제출
            summary["themes"][theme] = {
                "file": str(path), "chars": path.stat().st_size,
                "verdict": verdict.get("result"), "warned": warned, "lifecycle": action,
            }
            if warned:
                summary["warned"].append(theme)
            rev("engine_call", stage, "done",
                progress={"n": i, "m": len(themes), "unit": "manual"},
                detail={"saved": path.name, "lifecycle": action,
                        "verdict": verdict.get("result"), "warned": warned, "mr": mr})

        # DELETE 후보 — 물리 삭제 없이 deprecated 표시만 (decision-manual-delete-grace)
        marked = mark_deprecated_candidates(out_dir, list(summary["themes"]))
        summary["lifecycle"] = {"deprecated_candidates": marked}
        rev("stage", "lifecycle", "done", detail={"deprecated_candidates": marked})

        # 7) 보고 — 버전 포인터 전진은 MR 머지 후에만 (PoC 스텁)
        ctx.done(detail={"themes": list(summary["themes"]), "observations": len(log.items),
                         "note": "버전 포인터 전진은 MR 머지 후 — PoC 스텁"})
        return summary


def run_smoke(settings: Settings) -> int:
    """L1/L2 스모크: MCP 연결 + 도구 로드 + 관측 도구 1회 호출. LLM 불필요."""
    with RunContext("manual", settings, prefix="manual-smoke",
                    run_stage="manual-smoke") as ctx:
        rev = ctx.rev
        out_dir = settings.out_path / "manual"
        log = ctx.track(ObservationLog(out_dir / f"observations-{ctx.run_id}.jsonl"))
        log.set_phase("smoke")
        bridge = ctx.track(_bridge_for(settings, log, out_dir, ctx.run_id))
        try:
            ctx.start(detail={"endpoint": settings.mcp_endpoint_url})
            names = bridge.connect()
            rev("stage", "connect", "done", detail={"tools": len(names)})
            print(f"\n✓ MCP 연결: 도구 {len(names)}개 로드 (L1)")
            print("  " + ", ".join(names[:12]) + (" ..." if len(names) > 12 else ""))

            # 관측 도구 후보를 우선순위로 찾아 1회 호출 (L2: 관측 실증)
            probe = None
            for key in ("screen_info", "screenshot", "snapshot", "capture"):
                probe = next((n for n in names if key in n.lower()), None)
                if probe:
                    break
            if probe:
                ok, text = bridge.call(probe, {})
                rev("stage", "observe", "done" if ok else "failed",
                    detail={"tool": probe, "preview": text[:200]})
                print(f"\n{'✓' if ok else '✗'} 관측 도구 {probe}: {text[:200]}")
            else:
                print("\n· 관측 도구(screen/capture 계열)를 찾지 못함 — 도구 이름 확인 필요")

            ctx.done(detail={"tools": len(names), "probe": probe})
            print(f"✓ 이벤트 로그: {ctx.observer.jsonl_path}")
            print(f"✓ 관측 로그: {log.path}")
            return 0
        except Exception as e:  # noqa: BLE001
            ctx.failed({"error": f"{type(e).__name__}: {e}"})
            print(f"\n✗ 스모크 실패: {type(e).__name__}: {e}")
            return 1
