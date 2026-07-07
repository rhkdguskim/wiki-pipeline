"""LLM 호출·도구 실행 재시도 (tenacity 래핑).

일시적 오류(네트워크·rate limit·5xx)에만 재시도하고, 스텝 이벤트로 재시도를 관측한다.
"""
from __future__ import annotations

from typing import Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

T = TypeVar("T")

# 재시도 대상 예외: 네트워크·타임아웃·rate limit 계열. 도구 로직 오류는 재시도 안 함.
_TRANSIENT = (ConnectionError, TimeoutError)


def with_retry(fn: Callable[[], T], *, attempts: int = 3) -> T:
    """동기 콜러블을 지수 백오프로 재시도해 실행한다."""

    @retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception_type(_TRANSIENT),
        reraise=True,
    )
    def _run() -> T:
        return fn()

    return _run()
