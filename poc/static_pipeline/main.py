"""정적 파이프라인 CLI 엔트리.

    python -m poc.static_pipeline.main                      # sha 없으면 자동 init(전량 backfill)
    python -m poc.static_pipeline.main --from <sha> --to <sha>   # 증분 diff
    python -m poc.static_pipeline.main --init                    # 강제 init
    python -m poc.static_pipeline.main --init --themes intro,architecture-overview
    python -m poc.static_pipeline.main --init --max-modules 3    # PoC: 상위 N개 모듈만

decision-registration-baseline: last_processed_sha=null -> 전체 init.
init은 등록 시 1회만 도는 별도 작업, 정기 야간 배치(diff)와 분리.
"""
from __future__ import annotations

import argparse

from ..common.config import load_settings
from .init_runner import run_init
from .runner import run_static


def main() -> int:
    parser = argparse.ArgumentParser(description="정적 파이프라인 (docu-automation) PoC")
    parser.add_argument("--from", dest="from_sha", default=None, help="compare from sha")
    parser.add_argument("--to", dest="to_sha", default=None, help="compare to sha")
    parser.add_argument("--init", action="store_true", help="전량 init(backfill) 강제")
    parser.add_argument("--themes", default=None, help="init 테마 (쉼표구분). 기본=architecture-overview")
    parser.add_argument("--ref", default=None, help="init 기준 브랜치/태그 (기본=default_branch)")
    parser.add_argument("--max-units", type=int, default=None, help="init 시 계획 단위 상위 N개만(PoC)")
    parser.add_argument("--deep", action="store_true",
                        help="deep init — 단위마다 하위 그룹을 병렬 스캔·요약 후 합성 (전체 레포 스캔)")
    args = parser.parse_args()

    settings = load_settings()
    from_sha = args.from_sha or settings.static_from_sha
    to_sha = args.to_sha or settings.static_to_sha

    if not settings.llm_api_key:
        print("✗ LLM_API_KEY 가 .env 에 없습니다.")
        return 2
    if not settings.gitlab_token:
        print("✗ GITLAB_TOKEN 이 .env 에 없습니다.")
        return 2

    # last_processed_sha=null(=compare sha 없음) 또는 --init -> 전량 init.
    do_init = args.init or not (from_sha and to_sha)

    if do_init:
        themes = [t.strip() for t in args.themes.split(",")] if args.themes else None
        print(f"[정적 파이프라인 · INIT] project={settings.gitlab_project_id} "
              f"(전량 backfill, 에이전트 계획 단위)\n")
        summary = run_init(
            settings, ref=args.ref, themes=themes, max_units=args.max_units,
            deep=args.deep,
        )
        print("\n" + "=" * 60)
        print(f"INIT 완료. ref={summary['ref']} · 단위 {len(summary['units'])}개 · "
              f"문서 {len(summary['docs'])}건 생성:")
        for key, info in list(summary["docs"].items())[:20]:
            print(f"  - {key}: {info['chars']}B (소스 {info['files']}개)")
        if len(summary["docs"]) > 20:
            print(f"  ... 외 {len(summary['docs'])-20}건")
        return 0

    print(f"[정적 파이프라인 · DIFF] project={settings.gitlab_project_id} "
          f"compare {from_sha[:10]}..{to_sha[:10]}\n")
    diff_themes = [t.strip() for t in args.themes.split(",")] if args.themes else None
    summary = run_static(settings, from_sha, to_sha, themes=diff_themes)
    print("\n" + "=" * 60)
    print(f"완료. 변경 {summary['changed']}개(소스 {summary['sources']}개), "
          f"테마 {len(summary['themes'])}개 생성:")
    for theme, info in summary["themes"].items():
        print(f"  - {theme}: {info['file']} ({info['chars']} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
