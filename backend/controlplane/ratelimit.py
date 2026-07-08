"""Per-token rate limit (ENT-E).

slowapi 를 미들웨어로 감싸면 route 별 limit 을 쉽게 표현할 수 있다.
다만 controlplane 은 인증된 토큰 분당 한도를 두고 싶으므로 단순한
in-memory token bucket 으로 충분 — 멀티 인스턴스(스케일아웃) 환경에선
Redis 같은 외부 저장소가 필요하지만 v1 사내 VM 단일 인스턴스가 전제다.

기능:
  - 토큰/anon 별 분당 카운터 (RATE_LIMIT_PER_MIN, 기본 600)
  - 0 이면 비활성
  - 초과 시 429 + Retry-After 헤더
  - /health, /metrics, WS 는 rate limit 면제 (운영 가시성 깨지면 안 됨)
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Awaitable, Callable, Deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_log = logging.getLogger("controlplane.ratelimit")

_EXEMPT_PATHS = {"/health", "/health/live", "/health/ready", "/health/startup", "/metrics"}


class _Bucket:
    """단일 토큰(또는 anon) 의 분당 윈도우 카운터.

    메모리 한정: 토큰 ID 가 가산적으로 늘면 메모리 누수. v1 사내 환경은 토큰
    수가 작아(<100) 문제 없음. 멀티 인스턴스 환경에선 Redis 같은 외부 저장소로
    옮겨야 한다.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: Deque[float] = deque()

    def allow(self, *, limit: int, now: float, window_sec: float = 60.0) -> tuple[bool, float]:
        """True 면 허용. False 면 (False, retry_after_sec)."""
        with self._lock:
            cutoff = now - window_sec
            while self._hits and self._hits[0] < cutoff:
                self._hits.popleft()
            if len(self._hits) >= limit:
                retry = self._hits[0] + window_sec - now
                return False, max(retry, 0.5)
            self._hits.append(now)
            return True, 0.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, per_min: int) -> None:
        super().__init__(app)
        self.per_min = per_min
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def _bucket_for(self, key: str) -> _Bucket:
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket()
                self._buckets[key] = b
            return b

    async def dispatch(self, request: Request,
                       call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if self.per_min <= 0 or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        # 인증된 토큰이 있으면 토큰별, 없으면 IP별
        from .api import _extract_token
        from . import projection  # noqa: F401
        from .api import router as _r  # noqa: F401
        token = _extract_token(request)
        if token:
            # 토큰을 그대로 키로 쓰면 메모리에 비밀 평문이 남는다 — 해시 사용.
            import hashlib
            key = "tok:" + hashlib.sha256(token.encode()).hexdigest()[:16]
        else:
            key = "ip:" + (request.client.host if request.client else "anon")
        bucket = self._bucket_for(key)
        ok, retry = bucket.allow(limit=self.per_min, now=time.time())
        if not ok:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": "rate limit exceeded", "retry_after_sec": round(retry, 1)},
                headers={"Retry-After": str(int(retry) + 1)},
            )
        return await call_next(request)
