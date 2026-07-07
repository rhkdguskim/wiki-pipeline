"""매뉴얼 파이프라인 CLI 엔트리.

    python -m backend.manual_pipeline.main                      # 전체 실행 (시나리오+탐색 -> 매뉴얼)
    python -m backend.manual_pipeline.main --smoke              # L1/L2: MCP 연결 + 도구 로드 + 관측 1회
    python -m backend.manual_pipeline.main --scenarios path.json
    python -m backend.manual_pipeline.main --themes user-manual
    python -m backend.manual_pipeline.main --no-explore         # 시나리오만 (결정적)
    python -m backend.manual_pipeline.main --explore-steps 16
    python -m backend.manual_pipeline.main --resume manual-xxxxxxxx   # 체크포인트 중단 재개 (L4)
"""
from __future__ import annotations

import argparse

from ..common.config import load_settings
from .runner import run_manual, run_smoke


def main() -> int:
    parser = argparse.ArgumentParser(description="매뉴얼 파이프라인 (manual-automation) PoC")
    parser.add_argument("--smoke", action="store_true",
                        help="MCP 연결 + 도구 로드 + 관측 도구 1회 (LLM 불필요)")
    parser.add_argument("--scenarios", default=None, help="시나리오 JSON 경로 (기본=.env)")
    parser.add_argument("--themes", default=None,
                        help="매뉴얼 테마 (쉼표구분). 기본=user-manual,operator-manual")
    parser.add_argument("--explore-steps", type=int, default=None, help="자율 탐색 도구 호출 예산")
    parser.add_argument("--no-explore", action="store_true", help="자율 탐색 생략 (시나리오만)")
    parser.add_argument("--resume", default=None, metavar="RUN_ID",
                        help="중단된 run_id 재개 (관측 JSONL + 탐색 체크포인트 이어감)")
    args = parser.parse_args()

    settings = load_settings()
    if not settings.mcp_endpoint_url:
        print("✗ MCP_ENDPOINT_URL 이 .env 에 없습니다.")
        return 2

    if args.smoke:
        return run_smoke(settings)

    if not settings.llm_api_key:
        print("✗ LLM_API_KEY 가 .env 에 없습니다.")
        return 2

    themes = [t.strip() for t in args.themes.split(",")] if args.themes else None
    mode = "RESUME" if args.resume else "RUN"
    print(f"[매뉴얼 파이프라인 · {mode}] endpoint={settings.mcp_endpoint_url} "
          f"(하이브리드 순회: 시나리오 + 자율 탐색 -> 관측 근거 매뉴얼)\n")
    summary = run_manual(
        settings, scenarios_file=args.scenarios, themes=themes,
        explore_steps=args.explore_steps, resume_run_id=args.resume,
        no_explore=args.no_explore,
    )
    print("\n" + "=" * 60)
    print(f"완료. run_id={summary['run_id']} · 관측 {summary['observations']}건 · "
          f"매뉴얼 {len(summary['themes'])}건:")
    for theme, info in summary["themes"].items():
        w = " [경고태그]" if info.get("warned") else ""
        print(f"  - {theme} [{info['lifecycle']}]: {info['file']} "
              f"({info['chars']}B, critic={info.get('verdict')}){w}")
    dep = summary.get("lifecycle", {}).get("deprecated_candidates", [])
    if dep:
        print(f"  ! deprecated 후보(유예 표시): {', '.join(dep)}")
    if not summary["themes"]:
        print("  (생성된 매뉴얼 없음 — 관측이 0건이었는지 확인)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
