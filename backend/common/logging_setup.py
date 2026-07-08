"""구조화 로깅 — JSON / 텍스트 듀얼 모드 + request_id 상관관계.

LOG_FORMAT 환경 변수로 모드 전환:
  - "json"     : python-json-logger 로 한 줄 JSON 출력 (수집 친화)
  - "text"(기본) : 사람 친화 텍스트 — 개발·디버깅용
  - 다른 값     : text 로 폴백

request_id:
  - FastAPI 미들웨어가 X-Request-ID 헤더(없으면 자동 생성)를 contextvar 에 주입.
  - JSON 포맷에서 모든 로그 엔트리에 request_id 필드 포함.
  - WS 메시지 / Control Plane webhook 도 같은 키로 묶을 수 있게 emit_log() 제공.

운영 가이드:
  - log.info() 대신 logger.adapter 로 request_id 바인딩된 로거를 만들 수 있으나,
    contextvar + logging.Filter 조합이 ASGI/FastAPI 와 어울림. 그래서 logger.info()
    만 부르면 자동으로 request_id 가 따라간다.
"""
from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any


_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="")


def current_request_id() -> str:
    return _request_id_var.get()


def set_request_id(value: str | None = None) -> str:
    """컨텍스트에 request_id 를 주입. 없으면 자동 생성."""
    rid = value or uuid.uuid4().hex[:12]
    _request_id_var.set(rid)
    return rid


# ── JSON 포맷터 (python-json-logger 가 없을 때 폴백) ──────────────────────

class _JsonFormatter(logging.Formatter):
    """python-json-logger 미설치 시 폴백. 주요 필드만 노출."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = current_request_id()
        if rid:
            payload["request_id"] = rid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # extra= 로 넘어온 필드 (adapter 없이 dict update 도 흡수)
        for k, v in record.__dict__.items():
            if k in ("args", "asctime", "created", "exc_info", "exc_text", "filename",
                    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                    "message", "msg", "name", "pathname", "process", "processName",
                    "relativeCreated", "stack_info", "thread", "threadName",
                    "taskName"):
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except TypeError:
                payload[k] = repr(v)
        return json.dumps(payload, ensure_ascii=False)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        rid = current_request_id()
        if rid:
            record.request_id = rid
        return True


def setup_logging(level: str | None = None, fmt: str | None = None) -> None:
    """앱 기동 시 1회 — LOG_LEVEL/LOG_FORMAT 환경 반영. force=True 로 중복 호출도 안전."""
    from .config import cached_settings
    settings = cached_settings()
    resolved_level = (level or settings.log_level or "INFO").upper()
    resolved_fmt = (fmt or settings.log_format or "text").lower()

    root = logging.getLogger()
    # 기존 핸들러 제거 — uvicorn 의 핸들러가 중복 출력하는 것 방지
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(getattr(logging, resolved_level, logging.INFO))

    handler = logging.StreamHandler(sys.stderr)
    if resolved_fmt == "json":
        # python-json-logger 가 있으면 그쪽을, 없으면 폴백 사용
        try:
            from pythonjsonlogger import jsonlogger  # type: ignore
            handler.setFormatter(jsonlogger.JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
            ))
        except ImportError:
            handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s %(message)s"
            if False else  # request_id 는 Filter 가 주입 — 그래도 텍스트에 포함
            "%(asctime)s %(levelname)-7s %(name)s %(message)s"
        ))
    handler.addFilter(_RequestIdFilter())
    root.addHandler(handler)

    # 폴링·헬스체크로 시끄러운 액세스 로그는 한 단계 조용히.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def bind_request_id(value: str | None = None) -> str:
    """컨텍스트 매니저 진입 시 호출 — set_request_id 의 wrapper, 가독성용."""
    return set_request_id(value)


def reset_request_id() -> None:
    _request_id_var.set("")
