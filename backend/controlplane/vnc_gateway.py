"""VNC WebSocket Gateway — browser react-vnc 와 mcp-vnc remote session 사이 proxy.

v1 (현재):
  - session 검증 (run_vnc_sessions 테이블)
  - view-only 강제 (input frame 드랍)
  - session expiry 검사
  - short-lived signed token 발급/검증
  - audit log (open/close/reconnect)
  - 연결 유지 + 주기적 status frame 송신
  - 실제 TCP VNC proxy 는 v2 (구조만 존재)

설계 근거: raw/2026-07-08-backend-api-ai-pipeline-improvement-plan.md §6.8, §12.2
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Run, RunVncSession
from .timeutil import as_utc, isoformat_z

log = logging.getLogger("controlplane.vnc_gateway")

# view-only 모드에서 드랍하는 input frame type 집합.
# react-vnc / noVNC 프로토콜에서 사용하는 입력 관련 type 키워드.
_INPUT_FRAME_TYPES: frozenset[str] = frozenset({
    # keyboard
    "key", "key_event", "key_down", "key_up", "keydown", "keyup",
    "keypress",
    # mouse / pointer
    "mouse", "mouse_event", "mouse_down", "mouse_up", "mouse_move",
    "mouse_wheel", "mousedown", "mouseup", "mousemove", "wheel",
    "pointer", "pointer_event", "click", "double_click", "drag",
    # clipboard
    "clipboard", "clipboard_event", "cut", "paste", "copy",
    # touch
    "touch", "touch_event", "touch_start", "touch_end", "touch_move",
})

# token 기본 TTL (초) — 짧게 유지, 재발급은 vnc-session GET 에서.
_TOKEN_TTL_SEC = 300

# WebSocket close codes (custom range 4000-4999)
WS_CLOSE_VIEW_ONLY_VIOLATION = 4403
WS_CLOSE_SESSION_EXPIRED = 4402
WS_CLOSE_INVALID_TOKEN = 4401
WS_CLOSE_SESSION_NOT_FOUND = 4404
WS_CLOSE_VIEW_ONLY_FALSE = 4403


class VncGateway:
    """browser WebSocket 연결을 관리 — view-only 강제, session 검증, audit.

    RunService 와 마찬가지로 app.state 에 싱글톤으로 존재한다.
    각 WebSocket 연결은 route handler 에서 개별적으로 처리된다.
    """

    def __init__(self, *, secret_key: str = "", audit_service=None):
        self._secret = (secret_key or "vnc-gateway-default").encode("utf-8")
        self._audit_service = audit_service

    # ── token 발급 / 검증 ──────────────────────────────────────

    def issue_token(self, run_id: str, session_id: str,
                    expires_at: datetime | None = None,
                    *, ttl_sec: int = _TOKEN_TTL_SEC) -> str:
        """short-lived signed token 생성 — WebSocket connect 시 검증.

        token = base64url(payload).hmac_sha256_hex
        payload: {run_id, session_id, exp (unix ts)}
        """
        if expires_at is not None:
            exp_ts = int(as_utc(expires_at).timestamp()) if expires_at else 0
        else:
            exp_ts = int(time.time()) + ttl_sec
        payload = {"run_id": run_id, "session_id": session_id, "exp": exp_ts}
        payload_b = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        sig = hmac.new(self._secret, payload_b.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{payload_b}.{sig}"

    def validate_token(self, token: str, run_id: str, session_id: str,
                       *, now: float | None = None) -> bool:
        """token 검증 — 서명 일치 + 만료 확인 + run_id/session_id 일치."""
        if not token or "." not in token:
            return False
        parts = token.split(".", 1)
        if len(parts) != 2:
            return False
        payload_b, sig = parts
        expected_sig = hmac.new(
            self._secret, payload_b.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False
        try:
            payload = json.loads(base64.urlsafe_b64decode(payload_b))
        except Exception:  # noqa: BLE001
            return False
        if payload.get("run_id") != run_id:
            return False
        if payload.get("session_id") != session_id:
            return False
        exp = int(payload.get("exp") or 0)
        current = now if now is not None else time.time()
        if exp and current > exp:
            return False
        return True

    # ── session 검증 ───────────────────────────────────────────

    def get_session(self, db: Session, run_id: str, session_id: str) -> RunVncSession | None:
        """run_id + session_id 로 VNC session row 조회."""
        return db.scalars(
            select(RunVncSession).where(
                RunVncSession.run_id == run_id,
                RunVncSession.session_id == session_id,
            )
        ).first()

    def is_view_only(self, session_row: RunVncSession) -> bool:
        return bool(session_row.view_only)

    def is_expired(self, session_row: RunVncSession,
                   now: datetime | None = None) -> bool:
        """session 의 expires_at 이 지났는지 확인. expires_at 없으면 미만료."""
        if session_row.expires_at is None:
            return False
        current = now or datetime.now(timezone.utc)
        exp = as_utc(session_row.expires_at)
        return exp is not None and current > exp

    # ── view-only enforcement ──────────────────────────────────

    def is_input_frame(self, message: dict) -> bool:
        """frame 이 입력(키보드/마우스/클립보드)인지 판별 — view-only 에서 드랍."""
        if not isinstance(message, dict):
            return False
        msg_type = str(message.get("type") or "").lower()
        if msg_type in _INPUT_FRAME_TYPES:
            return True
        # type 이 없으면 kind 필드로 폴백
        kind = str(message.get("kind") or "").lower()
        if kind in _INPUT_FRAME_TYPES:
            return True
        return False

    # ── audit ──────────────────────────────────────────────────

    def audit(self, *, run_id: str, session_id: str, event: str,
              actor: str = "", detail: dict | None = None,
              remote_addr: str = "") -> None:
        """VNC 연결 이벤트 audit log — open/close/reconnect."""
        if self._audit_service is None:
            log.info("vnc audit (no audit service): run=%s session=%s event=%s",
                     run_id, session_id, event)
            return
        try:
            full_detail = {"session_id": session_id, "event": event}
            if detail:
                full_detail.update(detail)
            self._audit_service.record(
                actor=actor or "(vnc-gateway)",
                action=f"vnc_session.{event}",
                target_kind="run_vnc_session",
                target_id=f"{run_id}/{session_id}",
                detail=full_detail,
                remote_addr=remote_addr,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("vnc audit failed run=%s session=%s event=%s: %s",
                        run_id, session_id, event, e)

    # ── status frame ───────────────────────────────────────────

    def build_status_frame(self, session_row: RunVncSession) -> dict[str, Any]:
        """주기적 status frame — v1 에서 연결을 유지하며 frontend 에 상태 전달."""
        return {
            "type": "vnc_status",
            "run_id": session_row.run_id,
            "session_id": session_row.session_id,
            "status": session_row.status,
            "view_only": bool(session_row.view_only),
            "current_scenario_step": session_row.current_scenario_step,
            "current_action": session_row.current_action,
            "latency_ms": session_row.latency_ms,
            "resolution": session_row.resolution,
            "ts": isoformat_z(datetime.now(timezone.utc)),
        }
