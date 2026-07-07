"""러너 잡 엔트리 — Control Plane이 발급한 run 1건을 실행한다.

    python -m backend.runner.job --run-id <id> --source <sid> --mode auto --branch-role dev

흐름: 컨텍스트 조회 -> webhook 싱크 등록 -> (init|diff) 실행 -> MR/PR 제출 ->
완료 보고(성공 시에만 last_processed_sha 전진 — concept-idempotent-sha).
run별 격리 작업 디렉터리(out/<source>/runs/<run_id>)로 동시 실행 레이스를 없앤다.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from ..common.config import Settings, load_settings
from ..common.docshub import build_mr_plan, submit_change_request
from ..common.observer import Observer
from ..connectors.base import ScmAuthError, ScmNotFoundError, ScmRateLimitError
from .client import ControlPlaneClient, WebhookEventSink


def build_run_settings(base: Settings, ctx: dict) -> Settings:
    """컨텍스트(소스·토큰) + 러너 .env(LLM 설정)로 실행 스코프 Settings 구성."""
    source = ctx["source"]
    run = ctx["run"]
    out_root = base.out_path / source["id"] / "runs" / run["run_id"]
    return base.model_copy(update={
        "gitlab_url": source["url"],
        "gitlab_token": source["token"],
        "gitlab_token_header": source["token_header"],
        "gitlab_project_id": source["repo"],
        "source_id": source["id"],
        "source_label": source["label"],
        "source_kind": source["kind"],
        "static_themes": source["themes"] or base.static_themes,
        "out_dir": str(out_root),
    })


def decide_mode(mode: str, branch: dict) -> str:
    """auto: last_processed_sha 없음 -> init (decision-registration-baseline), 있음 -> diff."""
    if mode in ("init", "diff"):
        return mode
    return "diff" if branch.get("last_processed_sha") else "init"


def projection_summary(summary: dict, settings: Settings, *, run_id: str,
                       source_id: str, pipeline_id: str = "static") -> dict:
    """파이프라인 반환 summary -> build_mr_plan 입력(생성 산출물 목록)으로 변환."""
    docs = summary.get("themes") or summary.get("docs") or {}
    generated = []
    for theme, info in docs.items():
        f = info.get("file")
        if not f or "error" in info:
            continue
        p = Path(f)
        try:
            rel = p.relative_to(settings.out_path) if p.is_absolute() else p
        except ValueError:
            rel = Path(p.name)
        generated.append({"path": str(rel), "stage": theme,
                          "warned": bool(info.get("warned"))})
    return {"run_id": run_id, "source_id": source_id,
            "pipeline_id": pipeline_id, "generated": generated}


def submit_to_targets(summary: dict, settings: Settings, ctx: dict) -> dict:
    """활성 doc target에 MR/PR 제출. 반환: {submitted, mr_url, doc_count, error}.

    제출 대상이 있는데 제출이 실패하면 예외 전파 -> run 실패 (sha 미전진).
    활성 대상이 없으면 제출 없이 통과 (개발 모드 — sha는 생성 성공 기준으로 전진).
    """
    run = ctx["run"]
    source = ctx["source"]
    branch = ctx["branch"]
    proj = projection_summary(summary, settings, run_id=run["run_id"],
                              source_id=source["id"], pipeline_id=run["pipeline_id"] or "static")
    doc_count = len(proj["generated"])
    targets = [t for t in ctx.get("doc_targets", []) if t.get("enabled")]
    if not targets or doc_count == 0:
        return {"submitted": False, "mr_url": "", "doc_count": doc_count}

    role = run.get("branch_role") or "dev"
    source_dict = {
        "id": source["id"], "label": source["label"], "doc_dir": source["doc_dir"],
        "dev_branch": branch["branch"] if role == "dev" else "",
        "release_branch": branch["branch"] if role == "release" else "",
    }
    mr_urls = []
    for target in targets:
        plan = build_mr_plan(proj, target=target, source=source_dict,
                             out_dir=settings.out_path)
        if not plan["can_submit"]:
            continue
        result = submit_change_request(plan, target=target, out_dir=settings.out_path)
        mr_urls.append(result["merge_request"].get("web_url") or "")
    return {"submitted": bool(mr_urls), "mr_url": ", ".join(u for u in mr_urls if u),
            "doc_count": doc_count}


def classify_error(exc: BaseException) -> str:
    if isinstance(exc, ScmNotFoundError):
        return "not_found"
    if isinstance(exc, ScmRateLimitError):  # ScmAuthError보다 먼저 검사 (rate limit도 403)
        return "rate_limited"
    if isinstance(exc, ScmAuthError):
        return "auth"
    return ""


def execute(run_id: str, mode: str, cp: ControlPlaneClient) -> dict:
    """run 1건 실행 + 완료 보고. 반환값은 보고 결과 (테스트 관측용)."""
    ctx = cp.runner_context(run_id)
    base = load_settings()
    settings = build_run_settings(base, ctx)
    branch = ctx["branch"]
    effective = decide_mode(mode or ctx["run"].get("mode") or "auto", branch)

    sink = WebhookEventSink(cp, run_id)
    Observer.register_global_sink(sink)
    report: dict = {"status": "failed", "error": "", "error_kind": ""}
    try:
        from ..static_pipeline.init_runner import run_init
        from ..static_pipeline.runner import run_static

        if effective == "init":
            summary = run_init(settings, ref=branch.get("branch") or None,
                               themes=settings.theme_list or None, run_id=run_id)
        else:
            summary = run_static(settings, branch["last_processed_sha"],
                                 branch.get("branch") or None,
                                 themes=settings.theme_list or None, run_id=run_id)

        submission = submit_to_targets(summary, settings, ctx)
        report = {
            "status": "done",
            "from_sha": branch.get("last_processed_sha", ""),
            "to_sha": summary.get("last_processed_sha", ""),
            "last_processed_sha": summary.get("last_processed_sha", ""),
            "doc_count": submission["doc_count"],
            "mr_url": submission["mr_url"],
        }
    except Exception as e:  # noqa: BLE001 — 모든 실패는 보고로 변환
        report = {"status": "failed", "error": f"{type(e).__name__}: {e}",
                  "error_kind": classify_error(e)}
    finally:
        Observer.clear_global_sinks()
        sink.close()
    return cp.complete(run_id, report)


def main() -> int:
    from ..common.logging_setup import setup_logging

    setup_logging()
    parser = argparse.ArgumentParser(description="wiki-pipeline Data Plane 러너")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source", default="")     # 참조용 (컨텍스트가 진실)
    parser.add_argument("--mode", default="auto")   # auto | init | diff
    parser.add_argument("--branch-role", default="dev")
    args = parser.parse_args()

    api_url = os.environ.get("CONTROL_API_URL", "http://127.0.0.1:8420")
    token = os.environ.get("CONTROL_RUNNER_TOKEN", "")
    cp = ControlPlaneClient(api_url, token)
    try:
        result = execute(args.run_id, args.mode, cp)
        print(f"완료 보고: {result}")
        return 0 if result.get("status") != "failed" else 1
    finally:
        cp.close()


if __name__ == "__main__":
    raise SystemExit(main())
