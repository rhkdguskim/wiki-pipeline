"""Audit log 서비스 — 관리 작업 감사 추적.

어디서 호출하나:
  - api.py: 소스/인스턴스/스케줄/doc_target 트리거 mutation
  - registration.py: 검증 실패(401/403)
  - scheduler.py: 자동 비활성화(decision-branch-loss-policy)
  - notifier.py: 인증 해지 알림(decision-engine-api-key-auth)

시크릿/토큰 값은 detail 에 절대 넣지 않는다 — 대상 ID·상태·이유만.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog
from ..timeutil import as_utc, isoformat_z

log = logging.getLogger("controlplane.audit")


class AuditService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def record(self, *, actor: str = "", action: str = "",
               target_kind: str = "", target_id: str = "",
               request_id: str = "", detail: dict[str, Any] | None = None,
               remote_addr: str = "") -> None:
        from common.logging_setup import current_request_id
        rid = request_id or current_request_id()
        payload = json.dumps(detail or {}, ensure_ascii=False)[:2000]
        from ..db import session_scope
        try:
            with session_scope(self.session_factory) as db:
                db.add(AuditLog(
                    actor=actor or "(anonymous)",
                    action=action or "unknown",
                    target_kind=target_kind or "",
                    target_id=target_id or "",
                    request_id=rid,
                    detail=payload,
                    remote_addr=remote_addr or "",
                ))
        except Exception as e:  # noqa: BLE001 — 감사 기록 실패가 본 요청을 막으면 안 된다
            log.warning("audit 기록 실패 action=%s target=%s: %s", action, target_id, e)

    def list_recent(self, db: Session, *, limit: int = 200,
                    actor: str = "", action: str = "") -> list[dict]:
        stmt = select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit)
        if actor:
            stmt = stmt.where(AuditLog.actor == actor)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        rows = db.scalars(stmt).all()
        return [{
            "id": r.id,
            "ts": isoformat_z(as_utc(r.ts)),
            "actor": r.actor,
            "action": r.action,
            "target_kind": r.target_kind,
            "target_id": r.target_id,
            "request_id": r.request_id,
            "detail": r.detail,
            "remote_addr": r.remote_addr,
        } for r in rows]

    def prune_older_than_days(self, db: Session, *, days: int) -> int:
        """retention 정책 — audit_log_retention_days 지난 행 정리. 0=비활성."""
        if days <= 0:
            return 0
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        from sqlalchemy import delete
        result = db.execute(delete(AuditLog).where(AuditLog.ts < cutoff))
        db.flush()
        return int(result.rowcount or 0)
