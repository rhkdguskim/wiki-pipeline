"""LLM 호출·도구 실행 재시도 (tenacity 래핑).

일시적 오류(네트워크·타임아웃·rate limit·5xx)에만 재시도하고, 재시도를 콜백으로 관측한다.
공급자에 따라 긴 컨텍스트에서 APITimeoutError가 잦으므로 이를 재시도 대상에 포함한다.
"""
from __future__ import annotations

from typing import Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

T = TypeVar("T")

# 기본 일시 오류 (표준 예외).
_TRANSIENT_BASE = (ConnectionError, TimeoutError)

# openai/httpx 계열 일시 오류 — 클래스명을 문자열로 매칭(임포트 실패해도 동작).
_TRANSIENT_NAMES = {
    "APITimeoutError", "APIConnectionError", "InternalServerError",
    "RateLimitError", "APIError", "Timeout", "ConnectTimeout",
    "ReadTimeout", "ConnectError", "RemoteProtocolError",
}


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, _TRANSIENT_BASE):
        return True
    name = type(exc).__name__
    if name in _TRANSIENT_NAMES:
        return True
    # 상태 코드 5xx / 429 도 일시로 취급.
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status, int) and (status == 429 or 500 <= status < 600):
        return True
    return False


def with_retry(fn: Callable[[], T], *, attempts: int = 4, on_retry=None) -> T:
    """동기 콜러블을 지수 백오프로 재시도. on_retry(attempt, exc)로 관측 가능."""

    def _before_sleep(state):
        if on_retry:
            exc = state.outcome.exception() if state.outcome else None
            on_retry(state.attempt_number, exc)

    @retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=2, min=2, max=40),
        retry=retry_if_exception(is_transient),
        before_sleep=_before_sleep,
        reraise=True,
    )
    def _run() -> T:
        return fn()

    return _run()
