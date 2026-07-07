"""정적 파이프라인 CLI 엔트리 — 상태 기반 init/diff 자동 분기.

    python -m poc.static_pipeline.main                      # 상태 없으면 init, 있으면 상태->HEAD 증분
    python -m poc.static_pipeline.main --from <sha> --to <sha>   # 명시 구간 diff (상태 무시)
    python -m poc.static_pipeline.main --init                    # 강제 init
    python -m poc.static_pipeline.main --init --themes intro,architecture-overview

상태 계약 (decision-registration-baseline · concept-idempotent-sha):
- last_processed_sha 없음(=null) -> 전량 init. init 성공 시 sha 기록.
- 상태 있음 -> last_processed_sha..HEAD 증분 diff. 성공 시 sha 전진.
- 실패한 실행은 상태를 건드리지 않아 재실행이 안전(멱등).
"""
from __future__ import annotations

import argparse

from ..common.config import load_settings
from .init_runner import run_init
from .pipeline_state import load_state
from .runner import run_static


def _validate(settings) -> int:
    if not settings.llm_api_key:
        print("✗ LLM_API_KEY 가 .env 에 없습니다.")
        return 2
    if not settings.gitlab_token:
        print("✗ GITLAB_TOKEN 이 .env 에 없습니다.")
        return 2
    if not (settings.gitlab_url and settings.gitlab_project_id):
        print("✗ GITLAB_URL / GITLAB_PROJECT_ID 가 .env 에 없습니다.")
        return 2
    return 0


def _run_one(settings, args) -> int:
    source_note = f" source={settings.source_id}" if settings.source_id else ""
    from_sha = args.from_sha or settings.static_from_sha
    to_sha = args.to_sha or settings.static_to_sha

    invalid = _validate(settings)
    if invalid:
        return invalid

    # 상태 기반 분기: 명시 sha > 상태 파일 > init.
    # last_processed_sha=null(상태 없음) -> 전량 init (decision-registration-baseline).
    state_note = ""
    do_init = args.init
    if not do_init and not (from_sha and to_sha):
        state_source = settings.source_id if settings.scm_sources_json else None
        state = load_state(settings.out_path, state_source)
        if state and str(state.get("project_id")) == str(settings.gitlab_project_id):
            from_sha = state["last_processed_sha"]
            to_sha = "HEAD"   # 러너가 default branch HEAD로 해석
            state_note = f" (상태 기반: {from_sha[:10]}..HEAD, last_op={state.get('last_op')})"
        else:
            do_init = True

    if do_init:
        themes = [t.strip() for t in args.themes.split(",")] if args.themes else None
        print(f"[정적 파이프라인 · INIT]{source_note} project={settings.gitlab_project_id} "
              f"(전체 레포 스캔: 계획 -> 단위 병렬 요약 -> 테마별 합성)\n")
        summary = run_init(
            settings, ref=args.ref, themes=themes, max_units=args.max_units,
            reuse_summaries=args.reuse_summaries,
        )
        print("\n" + "=" * 60)
        print(f"INIT 완료. ref={summary['ref']} · 스캔 단위 {len(summary['units'])}개 · "
              f"테마 문서 {len(summary['docs'])}건:")
        for theme, info in summary["docs"].items():
            if "error" in info:
                print(f"  - {theme}: 실패 ({info['error']})")
            else:
                w = " [경고태그]" if info.get("warned") else ""
                print(f"  - {theme}: {info['file']} ({info['chars']}B, "
                      f"critic={info.get('verdict')}){w}")
        return 0

    print(f"[정적 파이프라인 · DIFF]{source_note} project={settings.gitlab_project_id} "
          f"compare {from_sha[:10]}..{(to_sha or 'HEAD')[:10]}{state_note}\n")
    diff_themes = [t.strip() for t in args.themes.split(",")] if args.themes else None
    summary = run_static(settings, from_sha, to_sha, themes=diff_themes)
    print("\n" + "=" * 60)
    print(f"완료. 변경 {summary['changed']}개(소스 {summary['sources']}개), "
          f"테마 {len(summary['themes'])}개 생성:")
    for theme, info in summary["themes"].items():
        print(f"  - {theme}: {info['file']} ({info['chars']} bytes)")
    if summary.get("last_processed_sha"):
        print(f"상태 전진: last_processed_sha={summary['last_processed_sha'][:12]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="정적 파이프라인 (docu-automation) PoC")
    parser.add_argument("--from", dest="from_sha", default=None, help="compare from sha")
    parser.add_argument("--to", dest="to_sha", default=None, help="compare to sha")
    parser.add_argument("--init", action="store_true", help="전량 init(backfill) 강제")
    parser.add_argument("--themes", default=None, help="init 테마 (쉼표구분). 기본=architecture-overview")
    parser.add_argument("--ref", default=None, help="init 기준 브랜치/태그 (기본=default_branch)")
    parser.add_argument("--max-units", type=int, default=None, help="init 시 계획 단위 상위 N개만(PoC)")
    parser.add_argument("--reuse-summaries", action="store_true",
                        help="이전 map 요약 캐시(out/init/_summaries.json) 재사용 — 프롬프트 반복 개선용")
    parser.add_argument("--source", default=None, help="SCM_SOURCES_JSON 안의 source id")
    parser.add_argument("--all-sources", action="store_true", help="등록된 모든 source를 순차 실행")
    args = parser.parse_args()

    settings = load_settings()
    sources = settings.source_list
    if args.all_sources:
        if not sources:
            print("✗ 등록된 source가 없습니다.")
            return 2
        rc = 0
        for source in sources:
            rc = max(rc, _run_one(settings.for_source(source), args))
        return rc

    source = settings.get_source(args.source)
    if source:
        settings = settings.for_source(source, isolate_output=len(sources) > 1)
    return _run_one(settings, args)


if __name__ == "__main__":
    raise SystemExit(main())
