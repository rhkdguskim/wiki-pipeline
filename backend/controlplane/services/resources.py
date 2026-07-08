"""Quality/Evidence/Manual/Coverage/VNC webhook ingest.

webhook /api/webhook/{quality,evidence,coverage,artifact,vnc-session}의 idempotent
저장 로직을 모은다. RunService 는 core event/complete 만 갖고, 이 모듈은 first-class
resource (quality report, evidence pack, artifact, coverage, VNC session) 의
ingest 와 view 변환을 담당한다.

설계:
- idempotent upsert (run_id UNIQUE 기반)
- secret value/token 은 저장하지 않음 (host_ip_encrypted 는 운영 시 Fernet 으로
  보호, v1 에서는 빈 값 허용)
- frontend 응답은 masked / redacted view 만 반환
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ManualScenarioSet, Run, RunArtifact, RunCoverageReport, RunDocOutput,
    RunEvidenceItem, RunEvidencePack, RunQualityFinding, RunQualityReport,
    RunVncSession, Source, SourceManualProfile,
)
from ..timeutil import as_utc, isoformat_z

log = logging.getLogger("controlplane.resources")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── run_quality_reports ─────────────────────────────────────────


def upsert_quality_report(db: Session, run_id: str, payload: dict) -> dict:
    """runner 가 보내는 최종 quality report 를 upsert.

    payload 필수 키 (없으면 0/empty fallback):
      status (pass|warning|fail|not_evaluated), score, publishable, failed_gate,
      warning_count, error_count, repair_attempts,
      deterministic_verifier_status, grounding_critic_status, schema_status,
      mermaid_status, redaction_status, gates (list)

    payload findings (optional): list of finding dicts — 같은 run 의 findings 를
    replace 한다 (run당 누적은 보수적으로, 변경/추가만 반영 — update_or_create).
    """
    run = db.get(Run, run_id)
    if run is None:
        raise ValueError(f"unknown run: {run_id}")

    status = str(payload.get("status") or "not_evaluated")
    score = payload.get("score")
    score_i = int(score) if score is not None else None
    publishable = bool(payload.get("publishable", False))
    failed_gate = str(payload.get("failed_gate") or "")[:80]
    warning_count = int(payload.get("warning_count") or 0)
    error_count = int(payload.get("error_count") or 0)
    repair_attempts = int(payload.get("repair_attempts") or 0)
    det_status = str(payload.get("deterministic_verifier_status") or "")[:16]
    ground_status = str(payload.get("grounding_critic_status") or "")[:16]
    schema_status = str(payload.get("schema_status") or "")[:16]
    mermaid_status = str(payload.get("mermaid_status") or "")[:16]
    redaction_status = str(payload.get("redaction_status") or "")[:16]
    gates_json = payload.get("gates") if isinstance(payload.get("gates"), (dict, list)) else None

    row = db.scalars(
        select(RunQualityReport).where(RunQualityReport.run_id == run_id)
    ).first()
    if row is None:
        row = RunQualityReport(run_id=run_id)
        db.add(row)
    row.status = status
    row.score = score_i
    row.publishable = publishable
    row.failed_gate = failed_gate
    row.warning_count = warning_count
    row.error_count = error_count
    row.repair_attempts = repair_attempts
    row.deterministic_verifier_status = det_status
    row.grounding_critic_status = ground_status
    row.schema_status = schema_status
    row.mermaid_status = mermaid_status
    row.redaction_status = redaction_status
    row.gates_json = gates_json
    row.updated_at = _utcnow()

    # findings: 기존 row 를 replace 하지 않고 add-only (audit trail 보존)
    findings_payload = payload.get("findings") or []
    if isinstance(findings_payload, list):
        for f in findings_payload:
            if not isinstance(f, dict):
                continue
            db.add(RunQualityFinding(
                run_id=run_id,
                doc_id=str(f.get("doc_id") or "")[:200],
                gate=str(f.get("gate") or "")[:80],
                code=str(f.get("code") or "")[:120],
                severity=str(f.get("severity") or "warning")[:16],
                blocking=bool(f.get("blocking", False)),
                message=str(f.get("message") or "")[:5000],
                location=str(f.get("location") or "")[:200],
                evidence_ref=str(f.get("evidence_ref") or "")[:200],
                repair_status=str(f.get("repair_status") or "")[:40],
                metadata_json=f.get("metadata") if isinstance(f.get("metadata"), dict) else None,
            ))

    # run row 도 같이 update — publishable / quality_status 의 진실은 quality 가
    # 결정하므로 run_summary 가 매번 재계산하지 않도록 캐시한다.
    run.quality_status = status
    run.quality_score = score_i
    run.publishable = publishable
    if failed_gate and not publishable:
        run.blocked_reason = failed_gate
    if status == "pass" and publishable:
        run.publish_state = "publishable"
    elif status == "fail" or not publishable:
        run.publish_state = "blocked"
    elif status == "warning":
        policy = str(run.warning_publish_policy or "review_required")
        run.publish_state = "review_required" if policy != "block" else "blocked"
    run.snapshot_version = int(run.snapshot_version or 0) + 1
    db.flush()
    return {"ok": True, "status": status, "publishable": publishable,
            "findings_added": len(findings_payload) if isinstance(findings_payload, list) else 0}


def get_quality_view(db: Session, run_id: str) -> dict | None:
    row = db.scalars(
        select(RunQualityReport).where(RunQualityReport.run_id == run_id)
    ).first()
    if row is None:
        return None
    return {
        "run_id": run_id,
        "status": row.status,
        "score": row.score,
        "publishable": row.publishable,
        "publish_state": "",  # run 의 publish_state 가 진실 (이 필드는 자리만)
        "failed_gate": row.failed_gate,
        "warning_count": row.warning_count,
        "error_count": row.error_count,
        "repair_attempts": row.repair_attempts,
        "gates": row.gates_json or [],
        "deterministic_verifier_status": row.deterministic_verifier_status,
        "grounding_critic_status": row.grounding_critic_status,
        "schema_status": row.schema_status,
        "mermaid_status": row.mermaid_status,
        "redaction_status": row.redaction_status,
        "updated_at": isoformat_z(row.updated_at),
    }


def get_quality_findings(db: Session, run_id: str, *, severity: str = "",
                         blocking: bool | None = None,
                         doc_id: str = "", limit: int = 200) -> list[dict]:
    stmt = select(RunQualityFinding).where(RunQualityFinding.run_id == run_id)
    if severity:
        stmt = stmt.where(RunQualityFinding.severity == severity)
    if blocking is not None:
        stmt = stmt.where(RunQualityFinding.blocking == blocking)
    if doc_id:
        stmt = stmt.where(RunQualityFinding.doc_id == doc_id)
    stmt = stmt.order_by(RunQualityFinding.id).limit(limit)
    rows = db.scalars(stmt).all()
    return [{
        "id": r.id, "doc_id": r.doc_id, "gate": r.gate, "code": r.code,
        "severity": r.severity, "blocking": r.blocking, "message": r.message,
        "location": r.location, "evidence_ref": r.evidence_ref,
        "repair_status": r.repair_status,
        "metadata": r.metadata_json or {},
        "created_at": isoformat_z(r.created_at),
    } for r in rows]


# ── run_evidence_packs / run_evidence_items ─────────────────────


def upsert_evidence_pack(db: Session, run_id: str, payload: dict) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise ValueError(f"unknown run: {run_id}")

    pack_id = str(payload.get("pack_id") or f"evpack-{uuid.uuid4().hex[:12]}")
    pack = db.get(RunEvidencePack, pack_id)
    if pack is None:
        pack = RunEvidencePack(id=pack_id, run_id=run_id)
        db.add(pack)
    pack.source_id = run.source_id or ""
    pack.pipeline_id = run.pipeline_id or ""
    pack.version_ref = str(payload.get("version_ref") or run.to_sha or run.from_sha or "")[:120]
    pack.item_count = int(payload.get("item_count") or 0)
    pack.source_file_count = int(payload.get("source_file_count") or 0)
    pack.observation_count = int(payload.get("observation_count") or 0)
    pack.unsupported_claim_count = int(payload.get("unsupported_claim_count") or 0)
    pack.truncated = bool(payload.get("truncated", False))
    pack.omitted_count = int(payload.get("omitted_count") or 0)
    manifest = payload.get("manifest")
    pack.manifest_json = manifest if isinstance(manifest, (dict, list)) else None
    pack.created_at = _utcnow()

    items = payload.get("items") or []
    added = 0
    if isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            iid = str(it.get("id") or f"evi-{uuid.uuid4().hex[:10]}")
            row = db.get(RunEvidenceItem, iid)
            if row is None:
                row = RunEvidenceItem(id=iid, pack_id=pack_id, run_id=run_id)
                db.add(row)
            row.kind = str(it.get("kind") or "source_file")[:40]
            row.title = str(it.get("title") or "")[:300]
            row.path = str(it.get("path") or "")[:500]
            ls = it.get("line_start")
            le = it.get("line_end")
            row.line_start = int(ls) if ls is not None else None
            row.line_end = int(le) if le is not None else None
            row.observation_id = str(it.get("observation_id") or "")[:64]
            row.scenario_id = str(it.get("scenario_id") or "")[:64]
            row.artifact_ref = str(it.get("artifact_ref") or "")[:500]
            # content_preview 는 길이 제한 — 16KB 초과면 잘라서 표시
            preview = str(it.get("content_preview") or "")
            row.content_preview = preview[:16000]
            row.content_uri = str(it.get("content_uri") or "")[:500]
            row.metadata_json = it.get("metadata") if isinstance(it.get("metadata"), dict) else None
            added += 1

    # run row 의 evidence_count 는 summary 가 빠르게 읽을 수 있도록 캐시
    db.flush()
    return {"ok": True, "pack_id": pack_id, "items_upserted": added,
            "item_count": pack.item_count}


def get_evidence_pack(db: Session, run_id: str, *, kind: str = "",
                      doc_id: str = "", limit: int = 200,
                      cursor: str = "") -> dict | None:
    pack = db.scalars(
        select(RunEvidencePack).where(RunEvidencePack.run_id == run_id)
        .order_by(RunEvidencePack.created_at.desc()).limit(1)
    ).first()
    if pack is None:
        return None
    stmt = select(RunEvidenceItem).where(RunEvidenceItem.pack_id == pack.id)
    if kind:
        stmt = stmt.where(RunEvidenceItem.kind == kind)
    stmt = stmt.order_by(RunEvidenceItem.id).limit(limit)
    rows = db.scalars(stmt).all()
    items = [{
        "id": r.id, "kind": r.kind, "title": r.title, "path": r.path,
        "line_start": r.line_start, "line_end": r.line_end,
        "observation_id": r.observation_id, "scenario_id": r.scenario_id,
        "artifact_ref": r.artifact_ref, "content_preview": r.content_preview,
        "content_uri": r.content_uri, "metadata": r.metadata_json or {},
        "created_at": isoformat_z(r.created_at),
    } for r in rows]
    return {
        "pack_id": pack.id,
        "run_id": run_id,
        "source_id": pack.source_id,
        "pipeline_id": pack.pipeline_id,
        "version_ref": pack.version_ref,
        "item_count": pack.item_count,
        "source_file_count": pack.source_file_count,
        "observation_count": pack.observation_count,
        "unsupported_claim_count": pack.unsupported_claim_count,
        "truncated": pack.truncated,
        "omitted_count": pack.omitted_count,
        "missing": False,
        "items": items,
    }


def get_evidence_item(db: Session, run_id: str, item_id: str) -> dict | None:
    row = db.scalars(
        select(RunEvidenceItem).where(
            RunEvidenceItem.id == item_id,
            RunEvidenceItem.run_id == run_id,
        )
    ).first()
    if row is None:
        return None
    return {
        "id": row.id, "pack_id": row.pack_id, "run_id": row.run_id,
        "kind": row.kind, "title": row.title, "path": row.path,
        "line_start": row.line_start, "line_end": row.line_end,
        "observation_id": row.observation_id, "scenario_id": row.scenario_id,
        "artifact_ref": row.artifact_ref, "content_preview": row.content_preview,
        "content_uri": row.content_uri, "metadata": row.metadata_json or {},
        "created_at": isoformat_z(row.created_at),
    }


# ── run_coverage_reports ────────────────────────────────────────


def upsert_coverage(db: Session, run_id: str, payload: dict) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise ValueError(f"unknown run: {run_id}")

    row = db.scalars(
        select(RunCoverageReport).where(RunCoverageReport.run_id == run_id)
    ).first()
    if row is None:
        row = RunCoverageReport(run_id=run_id)
        db.add(row)
    row.status = str(payload.get("status") or "not_applicable")[:24]
    pct = payload.get("percentage")
    row.percentage = float(pct) if pct is not None else None
    th = payload.get("threshold")
    row.threshold = float(th) if th is not None else None
    row.reached = int(payload.get("reached") or 0)
    row.expected = int(payload.get("expected") or 0)
    row.missed_count = int(payload.get("missed_count") or 0)
    misses = payload.get("misses")
    row.misses_json = misses if isinstance(misses, (dict, list)) else None
    scenarios = payload.get("scenario_results")
    row.scenario_results_json = scenarios if isinstance(scenarios, (dict, list)) else None
    row.created_at = _utcnow()

    db.flush()
    return {"ok": True, "status": row.status, "percentage": row.percentage,
            "threshold": row.threshold, "reached": row.reached,
            "expected": row.expected, "missed": row.missed_count}


def get_coverage_view(db: Session, run_id: str) -> dict:
    row = db.scalars(
        select(RunCoverageReport).where(RunCoverageReport.run_id == run_id)
    ).first()
    if row is None:
        return {
            "status": "not_applicable", "percentage": None, "threshold": None,
            "reached": 0, "expected": 0, "missed_count": 0,
            "misses": [], "scenario_results": [],
        }
    return {
        "status": row.status, "percentage": row.percentage,
        "threshold": row.threshold, "reached": row.reached,
        "expected": row.expected, "missed_count": row.missed_count,
        "misses": row.misses_json or [],
        "scenario_results": row.scenario_results_json or [],
    }


# ── run_artifacts ───────────────────────────────────────────────


def upsert_artifact(db: Session, run_id: str, payload: dict) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise ValueError(f"unknown run: {run_id}")

    # run 당 1 row — release_tag 가 다르면 새 row 를 만들지 않고 가장 최근 것을
    # update. 운영에서는 release 가 같으면 idempotent.
    row = db.scalars(
        select(RunArtifact).where(RunArtifact.run_id == run_id)
        .order_by(RunArtifact.id.desc()).limit(1)
    ).first()
    if row is None:
        row = RunArtifact(run_id=run_id)
        db.add(row)
    row.source_id = run.source_id or ""
    row.release_tag = str(payload.get("release_tag") or "")[:120]
    row.artifact_name = str(payload.get("artifact_name") or "")[:200]
    row.artifact_url = str(payload.get("artifact_url") or "")[:500]
    row.artifact_sha256 = str(payload.get("artifact_sha256") or "")[:64]
    row.artifact_type = str(payload.get("artifact_type") or "unknown")[:16]
    row.selected_by = str(payload.get("selected_by") or "policy")[:32]
    for fld in ("build_status", "download_status", "deploy_status",
                "install_status", "readiness_status", "smoke_status"):
        if fld in payload:
            setattr(row, fld, str(payload.get(fld) or "unknown")[:16])
    row.installed_version = str(payload.get("installed_version") or "")[:120]
    if payload.get("error"):
        row.error = str(payload["error"])[:5000]
    meta = payload.get("metadata")
    row.metadata_json = meta if isinstance(meta, dict) else None
    row.updated_at = _utcnow()

    if row.release_tag:
        run.release_tag = row.release_tag
    if row.installed_version:
        run.artifact_version = row.installed_version

    db.flush()
    return {"ok": True, "release_tag": row.release_tag, "artifact_name": row.artifact_name,
            "artifact_sha256": (row.artifact_sha256 or "")[:16] + "..." if row.artifact_sha256 else "",
            "build_status": row.build_status, "deploy_status": row.deploy_status,
            "install_status": row.install_status, "smoke_status": row.smoke_status}


def get_artifact_view(db: Session, run_id: str) -> dict:
    row = db.scalars(
        select(RunArtifact).where(RunArtifact.run_id == run_id)
        .order_by(RunArtifact.id.desc()).limit(1)
    ).first()
    if row is None:
        return {
            "available": False, "release_tag": "", "artifact_name": "",
            "artifact_sha256": "", "build_status": "unknown",
            "deploy_status": "unknown", "install_status": "unknown",
            "readiness_status": "unknown", "smoke_status": "unknown",
            "installed_version": "", "error": "",
        }
    return {
        "available": True,
        "release_tag": row.release_tag, "artifact_name": row.artifact_name,
        "artifact_sha256": row.artifact_sha256,
        "artifact_type": row.artifact_type,
        "build_status": row.build_status, "download_status": row.download_status,
        "deploy_status": row.deploy_status, "install_status": row.install_status,
        "readiness_status": row.readiness_status, "smoke_status": row.smoke_status,
        "installed_version": row.installed_version,
        "error": row.error,
    }


# ── run_vnc_sessions ────────────────────────────────────────────


def upsert_vnc_session(db: Session, run_id: str, payload: dict) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise ValueError(f"unknown run: {run_id}")

    row = db.scalars(
        select(RunVncSession).where(RunVncSession.run_id == run_id)
    ).first()
    if row is None:
        row = RunVncSession(run_id=run_id)
        db.add(row)
    row.session_id = str(payload.get("session_id") or row.session_id or f"vnc-{uuid.uuid4().hex[:10]}")[:64]
    row.status = str(payload.get("status") or "unavailable")[:24]
    row.host_label = str(payload.get("host_label") or "")[:200]
    raw_ip = str(payload.get("host_ip") or "")
    if raw_ip and not row.host_ip_encrypted:
        # v1: 평문 저장. 운영에서는 SecretBox/fernet 적용이 정석.
        # mask 는 응답 변환 시점에만.
        row.host_ip_encrypted = raw_ip
    row.host_port = int(payload["host_port"]) if payload.get("host_port") is not None else row.host_port
    row.gateway_url = str(payload.get("gateway_url") or "")[:500]
    if "view_only" in payload:
        row.view_only = bool(payload.get("view_only", True))
    row.current_scenario_step = str(payload.get("current_scenario_step") or "")[:200]
    row.current_action = str(payload.get("current_action") or "")[:200]
    if payload.get("latency_ms") is not None:
        row.latency_ms = int(payload["latency_ms"])
    row.resolution = str(payload.get("resolution") or "")[:40]
    if payload.get("expires_at"):
        row.expires_at = as_utc(payload["expires_at"])
    row.error = str(payload.get("error") or "")[:5000]
    row.updated_at = _utcnow()

    db.flush()
    return {"ok": True, "session_id": row.session_id, "status": row.status,
            "view_only": row.view_only}


def get_vnc_view(db: Session, run_id: str) -> dict:
    row = db.scalars(
        select(RunVncSession).where(RunVncSession.run_id == run_id)
    ).first()
    if row is None:
        return {
            "available": False, "status": "unavailable",
            "session_id": "", "websocket_url": "",
            "host_label": "", "port_label": "",
            "view_only": True, "current_scenario_step": "",
            "current_action": "", "latency_ms": None,
            "resolution": "", "expires_at": "", "error": "",
        }
    # v1 host_ip 는 저장된 값을 그대로 노출 — 응답에서 policy mask 가 적용된다.
    # 운영에서는 host_ip_encrypted 를 Fernet 으로 복호화 후 반환. 여기서는
    # host_label/port_label 만 우선.
    return {
        "available": row.status not in ("unavailable", "expired", "error"),
        "status": row.status,
        "session_id": row.session_id,
        "websocket_url": _build_vnc_ws_url(run_id, row.session_id),
        "host_label": row.host_label,
        "port_label": str(row.host_port) if row.host_port else "",
        "view_only": row.view_only,
        "current_scenario_step": row.current_scenario_step,
        "current_action": row.current_action,
        "latency_ms": row.latency_ms,
        "resolution": row.resolution,
        "expires_at": isoformat_z(row.expires_at),
        "error": row.error,
    }


def _build_vnc_ws_url(run_id: str, session_id: str) -> str:
    if not session_id:
        return ""
    return f"/api/runs/{run_id}/vnc/ws?session={session_id}"


# ── source_manual_profiles (CRUD view) ──────────────────────────


def get_manual_profile(db: Session, source_id: str) -> dict | None:
    row = db.get(SourceManualProfile, source_id)
    if row is None:
        return None
    return _manual_profile_view(row, with_secret=False)


def save_manual_profile(db: Session, source_id: str, payload: dict) -> dict:
    source = db.get(Source, source_id)
    if source is None:
        raise ValueError(f"unknown source: {source_id}")
    row = db.get(SourceManualProfile, source_id)
    if row is None:
        row = SourceManualProfile(source_id=source_id)
        db.add(row)
    _apply_manual_profile_payload(row, payload)
    row.updated_at = _utcnow()
    db.flush()
    return _manual_profile_view(row, with_secret=False)


def _apply_manual_profile_payload(row: SourceManualProfile, payload: dict) -> None:
    for fld in ("enabled", "mcp_endpoint_url", "mcp_transport",
                "host_label", "host_ip", "vnc_enabled", "vnc_host",
                "vnc_gateway_policy", "coverage_threshold", "failure_policy"):
        if fld in payload and payload[fld] is not None:
            val = payload[fld]
            if fld in ("enabled", "vnc_enabled"):
                setattr(row, fld, bool(val))
            elif fld in ("host_port", "vnc_port", "coverage_threshold"):
                try:
                    setattr(row, fld, int(val))
                except (TypeError, ValueError):
                    pass
            else:
                setattr(row, fld, str(val))
    for port_fld in ("host_port", "vnc_port"):
        if port_fld in payload and payload[port_fld] is not None:
            try:
                setattr(row, port_fld, int(payload[port_fld]))
            except (TypeError, ValueError):
                pass
    # JSON field aliases: frontend 는 ..._json 접미사 없이 보낸다 (tool_allowlist
    # vs DB 컬럼 tool_allowlist_json). 둘 다 받아서 정규화.
    json_aliases = {
        "tool_allowlist": "tool_allowlist_json",
        "secret_refs": "secret_refs_json",
        "artifact_selector": "artifact_selector_json",
        "install_profile": "install_profile_json",
        "readiness_check": "readiness_check_json",
        "smoke_check": "smoke_check_json",
    }
    for src_key, db_col in json_aliases.items():
        if src_key in payload and payload[src_key] is not None:
            val = payload[src_key]
            setattr(row, db_col, val if isinstance(val, (dict, list)) else None)
        elif db_col in payload and payload[db_col] is not None:
            val = payload[db_col]
            setattr(row, db_col, val if isinstance(val, (dict, list)) else None)


def _manual_profile_view(row: SourceManualProfile, *, with_secret: bool) -> dict:
    return {
        "source_id": row.source_id,
        "enabled": row.enabled,
        "mcp_endpoint_url": row.mcp_endpoint_url,
        "mcp_transport": row.mcp_transport,
        "host_label": row.host_label,
        "host_ip": row.host_ip if with_secret else _mask_host_ip(row.host_ip),
        "host_port": row.host_port,
        "vnc_enabled": row.vnc_enabled,
        "vnc_host": row.vnc_host,
        "vnc_port": row.vnc_port,
        "vnc_gateway_policy": row.vnc_gateway_policy,
        "tool_allowlist": row.tool_allowlist_json or [],
        "secret_refs": row.secret_refs_json or {},
        "artifact_selector": row.artifact_selector_json or {},
        "install_profile": row.install_profile_json or {},
        "readiness_check": row.readiness_check_json or {},
        "smoke_check": row.smoke_check_json or {},
        "coverage_threshold": row.coverage_threshold,
        "failure_policy": row.failure_policy,
        "updated_at": isoformat_z(row.updated_at),
    }


def _mask_host_ip(ip: str) -> str:
    if not ip:
        return ""
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.x.x"
    if ":" in ip:
        return ":".join(ip.split(":")[:2]) + ":xxxx:xxxx"
    return "***"


# ── manual_scenario_sets (CRUD) ─────────────────────────────────


def list_scenarios(db: Session, source_id: str) -> list[dict]:
    rows = db.scalars(
        select(ManualScenarioSet).where(ManualScenarioSet.source_id == source_id)
        .order_by(ManualScenarioSet.version.desc())
    ).all()
    return [{
        "id": r.id, "name": r.name, "version": r.version,
        "status": r.status, "lint_status": r.lint_status,
        "updated_at": isoformat_z(r.updated_at),
    } for r in rows]


def get_scenario(db: Session, source_id: str, set_id: str) -> dict | None:
    row = db.scalars(
        select(ManualScenarioSet).where(
            ManualScenarioSet.id == set_id,
            ManualScenarioSet.source_id == source_id,
        )
    ).first()
    if row is None:
        return None
    return {
        "id": row.id, "name": row.name, "version": row.version,
        "status": row.status, "scenarios": row.scenario_json or {},
        "lint_status": row.lint_status, "lint_errors": row.lint_errors_json or [],
        "updated_at": isoformat_z(row.updated_at),
    }


def save_scenario(db: Session, source_id: str, payload: dict,
                  *, set_id: str | None = None) -> dict:
    source = db.get(Source, source_id)
    if source is None:
        raise ValueError(f"unknown source: {source_id}")
    if set_id:
        row = db.get(ManualScenarioSet, set_id)
        if row is None or row.source_id != source_id:
            raise ValueError(f"unknown scenario set: {set_id}")
    else:
        row = ManualScenarioSet(
            id=f"scset-{uuid.uuid4().hex[:10]}",
            source_id=source_id,
        )
        db.add(row)
    row.name = str(payload.get("name") or row.name or "default")[:120]
    row.version = int(payload.get("version") or row.version or 1)
    row.status = str(payload.get("status") or "draft")[:16]
    scenarios = payload.get("scenarios")
    row.scenario_json = scenarios if isinstance(scenarios, (dict, list)) else None
    if payload.get("lint_status"):
        row.lint_status = str(payload.get("lint_status"))[:16]
    if payload.get("lint_errors") is not None:
        le = payload.get("lint_errors")
        row.lint_errors_json = le if isinstance(le, (dict, list)) else None
    row.updated_at = _utcnow()
    db.flush()
    return get_scenario(db, source_id, row.id) or {}


def delete_scenario(db: Session, source_id: str, set_id: str) -> bool:
    row = db.get(ManualScenarioSet, set_id)
    if row is None or row.source_id != source_id:
        return False
    db.delete(row)
    db.flush()
    return True


def activate_scenario(db: Session, source_id: str, set_id: str) -> dict:
    target = db.get(ManualScenarioSet, set_id)
    if target is None or target.source_id != source_id:
        raise ValueError(f"unknown scenario set: {set_id}")
    others = db.scalars(
        select(ManualScenarioSet).where(
            ManualScenarioSet.source_id == source_id,
            ManualScenarioSet.id != set_id,
        )
    ).all()
    for o in others:
        if o.status == "active":
            o.status = "archived"
    target.status = "active"
    target.updated_at = _utcnow()
    db.flush()
    return get_scenario(db, source_id, set_id) or {}


def lint_scenarios(payload: dict) -> dict:
    """scenario JSON 을 lint — schema/step/required tool/timeout 검증.

    runner 가 보내는 scenario 의 기본 정합성 검증. secret value 가 들어왔는지
    도 같이 검사 (raw secret 가 저장되지 않도록).
    """
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, (dict, list)):
        return {"ok": False, "errors": [{"code": "missing_scenarios",
                                          "message": "scenarios 가 dict/list 가 아닙니다"}]}
    items = scenarios.get("scenarios") if isinstance(scenarios, dict) else scenarios
    if not isinstance(items, list):
        items = []
    errors: list[dict] = []
    seen_step_ids: set[str] = set()
    for i, sc in enumerate(items):
        if not isinstance(sc, dict):
            errors.append({"index": i, "code": "scenario_not_object",
                           "message": "step 가 object 가 아닙니다"})
            continue
        sid = str(sc.get("id") or f"step-{i}")
        if sid in seen_step_ids:
            errors.append({"id": sid, "code": "duplicate_step_id",
                           "message": "step id 중복"})
        seen_step_ids.add(sid)
        if not sc.get("action") and not sc.get("tool"):
            errors.append({"id": sid, "code": "missing_action",
                           "message": "action 또는 tool 중 하나는 필요합니다"})
        if sc.get("timeout_sec") is not None:
            try:
                t = int(sc["timeout_sec"])
                if t < 1 or t > 600:
                    errors.append({"id": sid, "code": "bad_timeout",
                                   "message": "timeout 은 1~600 초"})
            except (TypeError, ValueError):
                errors.append({"id": sid, "code": "bad_timeout",
                               "message": "timeout 이 정수가 아님"})
        for raw_field in ("password", "token", "secret", "api_key"):
            if raw_field in sc:
                errors.append({"id": sid, "code": "raw_secret_not_allowed",
                               "message": f"{raw_field} 은 secret_ref 만 허용됩니다"})
    return {
        "ok": not errors,
        "error_count": len(errors),
        "errors": errors,
        "scenario_count": len(items),
    }


# ── manual profile preflight ───────────────────────────────────


def preflight_manual_profile(db: Session, source_id: str) -> dict:
    profile = db.get(SourceManualProfile, source_id)
    if profile is None:
        return {"ok": False, "errors": ["manual profile 이 등록되지 않았습니다"],
                "warnings": [], "resolved_tools": [],
                "selected_artifact_preview": "", "vnc_available": False}
    errors: list[str] = []
    warnings: list[str] = []
    if not profile.enabled:
        errors.append("manual profile 이 비활성화 상태입니다")
    if not profile.mcp_endpoint_url:
        errors.append("mcp_endpoint_url 이 비어 있습니다")
    allow = profile.tool_allowlist_json or []
    if not allow:
        errors.append("tool_allowlist 가 비어 있습니다 (production manual run 은 allowlist 필수)")
    # active scenario set 확인
    active = db.scalars(
        select(ManualScenarioSet).where(
            ManualScenarioSet.source_id == source_id,
            ManualScenarioSet.status == "active",
        )
    ).first()
    if active is None:
        errors.append("active scenario set 이 없습니다")
    elif (active.lint_status or "") not in ("pass", ""):
        warnings.append(f"active scenario set lint_status={active.lint_status or 'unknown'}")
    # artifact selector
    sel = profile.artifact_selector_json or {}
    if not sel:
        warnings.append("artifact_selector 가 비어 있어 release tag 기반 자동 선택이 됩니다")
    # vnc
    vnc_ok = bool(profile.vnc_enabled and profile.vnc_host and profile.vnc_port)
    if profile.vnc_enabled and not vnc_ok:
        warnings.append("vnc_enabled 이지만 host/port 가 비어 있습니다")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "resolved_tools": allow if isinstance(allow, list) else [],
        "selected_artifact_preview": sel.get("preview") if isinstance(sel, dict) else "",
        "vnc_available": vnc_ok,
    }


def preflight_artifact(db: Session, source_id: str, payload: dict) -> dict:
    """release tag / override 기반 artifact preflight.

    v1: 단순 — manifest 에서 release_tag/branch/build 를 받아 checksum/asset match
    시뮬레이션. 실제 다운로드/installer 호출은 v2.
    """
    profile = db.get(SourceManualProfile, source_id)
    if profile is None:
        return {"ok": False, "errors": ["manual profile 미등록"],
                "warnings": [], "selected_artifact": None}
    selector = profile.artifact_selector_json or {}
    install = profile.install_profile_json or {}
    release_tag = str(payload.get("release_tag") or selector.get("default_release_tag") or "")
    asset_pattern = selector.get("asset_pattern", "*")
    installer_type = selector.get("installer_type", "unknown")
    cmd_template = install.get("command", "")
    preview = {
        "release_tag": release_tag,
        "asset_pattern": asset_pattern,
        "installer_type": installer_type,
        "checksum_available": bool(selector.get("checksum_path")),
        "install_command_preview": cmd_template.format(release_tag=release_tag) if cmd_template else "",
    }
    warnings: list[str] = []
    if not release_tag:
        warnings.append("release_tag 가 비어 있습니다 — 수동 지정이 필요합니다")
    return {
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "selected_artifact": preview,
    }


# ── run_doc_outputs helper ─────────────────────────────────────


def upsert_doc_outputs(db: Session, run_id: str, docs: list[dict]) -> int:
    """doc_outputs webhook batch. 기존 row 는 update 없으면 add-only."""
    added = 0
    for d in docs:
        if not isinstance(d, dict):
            continue
        path = str(d.get("path") or "")
        if not path:
            continue
        row = db.scalars(
            select(RunDocOutput).where(
                RunDocOutput.run_id == run_id,
                RunDocOutput.path == path,
            ).limit(1)
        ).first()
        if row is None:
            row = RunDocOutput(run_id=run_id, path=path)
            db.add(row)
            added += 1
        row.theme = str(d.get("theme") or row.theme or "")[:200]
        row.title = str(d.get("title") or row.title or "")[:300]
        row.action = str(d.get("action") or row.action or "create")[:40]
        if d.get("quality_status"):
            row.quality_status = str(d["quality_status"])[:24]
        if "publishable" in d:
            row.publishable = bool(d.get("publishable", False))
        row.warning_count = int(d.get("warning_count") or row.warning_count or 0)
        row.error_count = int(d.get("error_count") or row.error_count or 0)
        row.unsupported_claim_count = int(d.get("unsupported_claim_count") or 0)
        row.evidence_count = int(d.get("evidence_count") or 0)
        if d.get("schema_status"):
            row.schema_status = str(d["schema_status"])[:16]
        if d.get("mermaid_status"):
            row.mermaid_status = str(d["mermaid_status"])[:16]
        if d.get("mr_inclusion_status"):
            row.mr_inclusion_status = str(d["mr_inclusion_status"])[:24]
        if d.get("content_sha256"):
            row.content_sha256 = str(d["content_sha256"])[:64]
        meta = d.get("metadata")
        if meta is not None:
            row.metadata_json = meta if isinstance(meta, dict) else None
    db.flush()
    return added


def get_doc_outputs(db: Session, run_id: str) -> list[dict]:
    rows = db.scalars(
        select(RunDocOutput).where(RunDocOutput.run_id == run_id)
        .order_by(RunDocOutput.id)
    ).all()
    return [{
        "id": r.id, "theme": r.theme, "path": r.path, "title": r.title,
        "action": r.action, "quality_status": r.quality_status,
        "publishable": r.publishable, "warning_count": r.warning_count,
        "error_count": r.error_count,
        "unsupported_claim_count": r.unsupported_claim_count,
        "evidence_count": r.evidence_count,
        "schema_status": r.schema_status, "mermaid_status": r.mermaid_status,
        "mr_inclusion_status": r.mr_inclusion_status,
        "content_sha256": r.content_sha256,
    } for r in rows]


# ── final-pack per-item validation ──────────────────────────────


def validate_quality_report(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "not_object"
    status = str(payload.get("status") or "")
    if status and status not in ("pass", "warning", "fail", "not_evaluated"):
        return False, f"invalid_status:{status}"
    return True, ""


def validate_evidence_pack(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "not_object"
    items = payload.get("items")
    if items is not None and not isinstance(items, list):
        return False, "items_not_list"
    return True, ""


def validate_coverage(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "not_object"
    status = str(payload.get("status") or "")
    if status and status not in ("pass", "fail", "not_applicable"):
        return False, f"invalid_status:{status}"
    pct = payload.get("percentage")
    if pct is not None:
        try:
            float(pct)
        except (TypeError, ValueError):
            return False, "percentage_not_numeric"
    return True, ""


def validate_artifact(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "not_object"
    return True, ""


def validate_doc_outputs(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, list):
        return False, "not_list"
    return True, ""


_FINAL_PACK_VALIDATORS = {
    "quality": validate_quality_report,
    "evidence": validate_evidence_pack,
    "coverage": validate_coverage,
    "artifact": validate_artifact,
    "doc_outputs": validate_doc_outputs,
}

_FINAL_PACK_UPSERTERS = {
    "quality": lambda db, rid, p: upsert_quality_report(db, rid, p),
    "evidence": lambda db, rid, p: upsert_evidence_pack(db, rid, p),
    "coverage": lambda db, rid, p: upsert_coverage(db, rid, p),
    "artifact": lambda db, rid, p: upsert_artifact(db, rid, p),
    "vnc": lambda db, rid, p: upsert_vnc_session(db, rid, p),
}


def final_pack_required_items(pipeline_id: str) -> list[str]:
    """pipeline_id 에 따라 final-pack 번들에 필수인 item key 목록.

    static: evidence + quality
    manual: evidence + quality + coverage + artifact
    """
    base = ["evidence", "quality"]
    if (pipeline_id or "static") == "manual":
        base += ["coverage", "artifact"]
    return base


def ingest_final_pack(db: Session, run_id: str, payload: dict,
                      pipeline_id: str = "") -> dict:
    """final-pack bundle 을 부분 ingest — per-item validate 후 upsert.

    반환:
      - ok: True (항상 — 부분 실패도 응답은 정상)
      - partial: True 면 하나 이상 item 실패
      - items: {key: {ok, ...} or {ok:False, error}}
      - required_missing: 필수 item 중 누락/실패한 key 목록
      - blocks_done: required_missing 이 비어있지 않으면 True
    """
    result: dict[str, Any] = {
        "ok": True, "partial": False, "items": {},
        "required_missing": [], "blocks_done": False,
    }
    required = final_pack_required_items(pipeline_id)

    for key in ("evidence", "quality", "coverage", "artifact", "vnc"):
        sub = payload.get(key)
        if sub is None:
            continue
        validator = _FINAL_PACK_VALIDATORS.get(key)
        if validator:
            ok, err = validator(sub)
            if not ok:
                result["partial"] = True
                result["items"][key] = {"ok": False, "error": err}
                continue
        try:
            upserted = _FINAL_PACK_UPSERTERS[key](db, run_id, sub)
            if isinstance(upserted, dict) and upserted.get("ok") is False:
                result["partial"] = True
                result["items"][key] = upserted
            else:
                result["items"][key] = upserted
        except ValueError as e:
            result["partial"] = True
            result["items"][key] = {"ok": False, "error": str(e)}

    docs = payload.get("doc_outputs")
    if docs is not None:
        ok, err = validate_doc_outputs(docs)
        if not ok:
            result["partial"] = True
            result["items"]["doc_outputs"] = {"ok": False, "error": err}
        else:
            try:
                n = upsert_doc_outputs(db, run_id, docs)
                result["items"]["doc_outputs"] = {"ok": True, "upserted": n}
            except Exception as e:  # noqa: BLE001
                result["partial"] = True
                result["items"]["doc_outputs"] = {"ok": False, "error": str(e)}

    mr_summary = payload.get("mr_summary")
    if mr_summary is not None:
        result["items"]["mr_summary"] = {"ok": True, "received": True}

    for req in required:
        item_result = result["items"].get(req)
        if item_result is None:
            result["required_missing"].append(req)
        elif isinstance(item_result, dict) and item_result.get("ok") is False:
            result["required_missing"].append(req)

    if result["required_missing"]:
        result["blocks_done"] = True
        run = db.get(Run, run_id)
        if run is not None:
            run.publishable = False
            run.publish_state = "blocked"
            missing_str = ", ".join(result["required_missing"])
            existing = str(run.blocked_reason or "")
            reason = f"final-pack missing required items: {missing_str}"
            if reason not in existing:
                run.blocked_reason = (existing + " / " + reason).strip(" /") \
                    if existing else reason
    return result
