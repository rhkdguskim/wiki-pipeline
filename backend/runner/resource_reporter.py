"""파이프라인 산출물을 Control Plane webhook 으로 보고한다.

quality / evidence / coverage / artifact webhook 을 best-effort 로 전송한다.
엔드포인트가 없거나 에러를 반환해도 러너 실행에는 영향을 주지 않는다
(post_webhook 가 None 을 반환하고 조용히 넘어간다).
"""
from __future__ import annotations

import logging
from pathlib import Path

from .client import ControlPlaneClient

log = logging.getLogger("runner.resource_reporter")


def _doc_quality_from_summary(summary: dict) -> list[dict]:
    docs = summary.get("themes") or summary.get("docs") or {}
    out: list[dict] = []
    for theme, info in docs.items():
        if not isinstance(info, dict):
            continue
        file_path = str(info.get("file") or "")
        # file 경로가 없으면 theme 기반 경로 생성 (최소한 path 는 채워야 upsert 됨)
        if not file_path:
            file_path = f"init/{theme}.md"
        has_error = "error" in info
        warned = bool(info.get("warned"))
        out.append({
            "theme": theme,
            "title": str(info.get("title") or theme),
            "path": file_path,
            "action": str(info.get("action") or "create"),
            "quality_status": "fail" if has_error else ("warning" if warned else "pass"),
            "publishable": not has_error,
            "warning_count": 1 if warned else 0,
            "error_count": 1 if has_error else 0,
        })
    return out


def emit_quality(cp: ControlPlaneClient, run_id: str, summary: dict,
                 *, pipeline_id: str = "static") -> None:
    themes = summary.get("themes") or summary.get("docs") or {}
    error_count = sum(1 for v in themes.values()
                      if isinstance(v, dict) and "error" in v)
    warning_count = sum(1 for v in themes.values()
                        if isinstance(v, dict) and v.get("warned"))
    warned_themes = summary.get("warned") or []

    if error_count > 0:
        status = "fail"
    elif warning_count > 0 or warned_themes:
        status = "warning"
    else:
        status = "pass"

    publishable = error_count == 0
    payload: dict = {
        "run_id": run_id,
        "status": status,
        "score": None,
        "publishable": publishable,
        "warning_count": warning_count,
        "error_count": error_count,
        "repair_attempts": 0,
        "findings": [],
    }
    for theme, info in themes.items():
        if not isinstance(info, dict):
            continue
        if "error" in info:
            payload["findings"].append({
                "doc_id": theme,
                "gate": "generation",
                "severity": "error",
                "blocking": True,
                "message": str(info.get("error", ""))[:500],
            })
        elif info.get("warned"):
            payload["findings"].append({
                "doc_id": theme,
                "gate": "critic",
                "severity": "warning",
                "blocking": False,
                "message": f"문서 '{theme}' 검토 결과 경고 — review 필요",
            })
    cp.post_webhook("/api/webhook/quality", payload)


def emit_evidence(cp: ControlPlaneClient, run_id: str, summary: dict,
                  *, pipeline_id: str = "static") -> None:
    themes = summary.get("themes") or summary.get("docs") or {}
    items: list[dict] = []
    for theme, info in themes.items():
        if not isinstance(info, dict):
            continue
        f = info.get("file")
        if not f:
            continue
        p = Path(f)
        try:
            content = p.read_text(encoding="utf-8", errors="replace")[:8000]
        except OSError:
            content = ""
        items.append({
            "kind": "generated_doc",
            "title": theme,
            "path": str(p.name),
            "content_preview": content,
        })
    observations = summary.get("observations", 0)
    payload: dict = {
        "run_id": run_id,
        "items": items,
        "item_count": len(items),
        "observation_count": int(observations),
        "manifest": {"themes": list(themes.keys())},
    }
    cp.post_webhook("/api/webhook/evidence", payload)


def emit_coverage(cp: ControlPlaneClient, run_id: str, summary: dict) -> None:
    coverage = summary.get("coverage") or {}
    scenarios = coverage.get("scenarios") or {}
    explore = coverage.get("explore") or {}
    reached = len(scenarios.get("completed", [])) + len(explore.get("visited", []))
    expected = (len(scenarios.get("completed", [])) +
                len(scenarios.get("failed", [])) +
                len(scenarios.get("skipped", [])))
    unreached = explore.get("unreached", [])
    missed_count = len(unreached) if isinstance(unreached, list) else 0
    payload: dict = {
        "run_id": run_id,
        "status": "pass" if missed_count == 0 and not scenarios.get("failed") else "warning",
        "reached": reached,
        "expected": expected,
        "missed_count": missed_count,
        "misses": unreached if isinstance(unreached, list) else [],
        "scenario_results": scenarios,
    }
    cp.post_webhook("/api/webhook/coverage", payload)


def emit_artifact(cp: ControlPlaneClient, run_id: str, summary: dict) -> None:
    artifact = summary.get("artifact") or {}
    deploy = summary.get("deploy") or {}
    readiness = summary.get("readiness") or {}
    smoke = summary.get("smoke") or {}
    payload: dict = {
        "run_id": run_id,
        "build_status": artifact.get("status") or "unknown",
        "deploy_status": deploy.get("status") or "unknown",
        "install_status": deploy.get("status") or "unknown",
        "readiness_status": readiness.get("status") or "unknown",
        "smoke_status": smoke.get("status") or "unknown",
        "artifact_path": artifact.get("path", ""),
        "artifact_sha256": artifact.get("sha256", ""),
        "deploy_error": deploy.get("error", ""),
        "readiness_detail": readiness.get("detail", ""),
        "smoke_detail": smoke.get("detail", ""),
    }
    cp.post_webhook("/api/webhook/artifact", payload)


def emit_doc_outputs(cp: ControlPlaneClient, run_id: str, summary: dict,
                     *, pipeline_id: str = "static") -> None:
    """생성된 문서 목록을 doc-outputs webhook 으로 전송.

    RunDocOutput 테이블을 채워 MR plan 의 included_files/excluded_files 가
    프런트엔드에 표시되도록 한다. _doc_quality_from_summary 로 doc 품질 정보를
    함께 보낸다.
    """
    docs = _doc_quality_from_summary(summary)
    if not docs:
        return
    payload: dict = {
        "run_id": run_id,
        "docs": docs,
    }
    cp.post_webhook("/api/webhook/doc-outputs", payload)


def report_all(cp: ControlPlaneClient, run_id: str, summary: dict,
               *, pipeline_id: str = "static") -> None:
    emit_quality(cp, run_id, summary, pipeline_id=pipeline_id)
    emit_evidence(cp, run_id, summary, pipeline_id=pipeline_id)
    emit_doc_outputs(cp, run_id, summary, pipeline_id=pipeline_id)
    if pipeline_id == "manual":
        emit_coverage(cp, run_id, summary)
        emit_artifact(cp, run_id, summary)
