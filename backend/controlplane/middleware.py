"""FastAPI 미들웨어 — request_id, HTTP 메트릭, access log.

순서:
1. X-Request-ID 헤더(없으면 생성) -> contextvar 주입
2. 요청 시작 시각 기록
3. 응답 직전 메트릭 갱신 + access log 출력
4. contextvar 리셋

메트릭 라벨 path 는 route template 으로 정규화 — /api/runs/abc-123 같은
고유 path 가 cardinality 폭증을 일으키지 않도록.
"""
from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .observability import http_request_duration_seconds, http_requests_in_flight, http_requests_total
from ..common.logging_setup import reset_request_id, set_request_id

_log = logging.getLogger("controlplane.http")


def _route_template(request: Request) -> str:
    """Starlette 의 route pattern (예: /api/runs/{run_id}). 없으면 path 그대로."""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


class RequestIdAndMetricsMiddleware(BaseHTTPMiddleware):
    """단일 미들웨어로 request_id + access log + 메트릭 처리."""

    async def dispatch(self, request: Request,
                       call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = request.headers.get("x-request-id") or None
        rid = set_request_id(rid)
        start = time.perf_counter()
        http_requests_in_flight.inc()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            elapsed = time.perf_counter() - start
            http_requests_in_flight.dec()
            path = _route_template(request)
            method = request.method
            try:
                http_requests_total.labels(method=method, path=path,
                                           status=str(status)).inc()
                http_request_duration_seconds.labels(method=method, path=path).observe(elapsed)
            except Exception:  # noqa: BLE001 — 메트릭 실패가 응답을 막으면 안 된다
                pass
            # access log — JSON 모드에서는 logger adapter 가 request_id 를 자동 부여.
            _log.info("%s %s %s %.3fs", method, path, status, elapsed)
            reset_request_id()
