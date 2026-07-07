"""정적 파이프라인 CLI 엔트리.

    python -m poc.static_pipeline.main [--from <sha>] [--to <sha>]

sha 미지정 시 .env의 STATIC_FROM_SHA / STATIC_TO_SHA 사용.
"""
from __future__ import annotations

import argparse

from ..common.config import load_settings
from .runner import run_static


def main() -> int:
    parser = argparse.ArgumentParser(description="정적 파이프라인 (docu-automation) PoC")
    parser.add_argument("--from", dest="from_sha", default=None, help="compare from sha")
    parser.add_argument("--to", dest="to_sha", default=None, help="compare to sha")
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
    if not (from_sha and to_sha):
        print("✗ compare 대상 sha 가 없습니다 (--from/--to 또는 .env STATIC_FROM_SHA/TO_SHA).")
        return 2

    print(f"[정적 파이프라인] project={settings.gitlab_project_id} "
          f"compare {from_sha[:10]}..{to_sha[:10]}\n")
    summary = run_static(settings, from_sha, to_sha)

    print("\n" + "=" * 60)
    print(f"완료. 변경 {summary['changed']}개(소스 {summary['sources']}개), "
          f"테마 {len(summary['themes'])}개 생성:")
    for theme, info in summary["themes"].items():
        print(f"  - {theme}: {info['file']} ({info['chars']} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
