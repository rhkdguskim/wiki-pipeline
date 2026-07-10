"""LLM 호출·도구 실행 재시도 (tenacity 래핑).

일시적 오류(네트워크·타임아웃·rate limit·5xx)에만 재시도하고, 재시도를 콜백으로 관측한다.
공급자에 따라 긴 컨텍스트에서 APITimeoutError가 잦으므로 이를 재시도 대상에 포함한다.

429(rate limit) 처리 정책:
- 공급자가 준 **Retry-After** 헤더를 존중한다 — 그 시간만큼 기다리면 다음 시도가
  거의 확실히 통과하므로, 임의 백오프로 짧게 재시도해 또 429를 맞는 낭비를 없앤다.
- 대기에 **랜덤 jitter**를 더한다. 여러 워커가 같은 429를 동시에 맞으면 백오프도
  똑같이 끝나 한꺼번에 재돌진(thundering herd)해 또 한도를 넘긴다 — jitter가 재시도
  시점을 흩뿌려 이를 깬다. (concurrency 게이트가 1차 방어, 이건 2차 방어다.)
"""
from __future__ import annotations

import random
from email.utils import parsedate_to_datetime
from typing import Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from tenacity.wait import wait_base

T = TypeVar("T")

# 기본 일시 오류 (표준 예외).
_TRANSIENT_BASE = (ConnectionError, TimeoutError)

# openai/httpx 계열 일시 오류 — 클래스명을 문자열로 매칭(임포트 실패해도 동작).
_TRANSIENT_NAMES = {
    "APITimeoutError", "APIConnectionError", "InternalServerError",
    "RateLimitError", "APIError", "Timeout", "ConnectTimeout",
    "ReadTimeout", "ConnectError", "RemoteProtocolError",
    "TimeoutException", "WriteTimeout", "PoolTimeout",
}

# Retry-After가 초가 아닌 절대 시각으로 올 때 대비한 상한 (과도한 대기 방지).
_RETRY_AFTER_MAX = 60.0

# wait 클래스가 파라미터명 max 로 내장 max 를 가리므로 별칭으로 보존.
builtin_max = max


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, _TRANSIENT_BASE):
        return True
    name = type(exc).__name__
    if name in _TRANSIENT_NAMES:
        return True
    # 상태 코드 5xx / 429 도 일시로 취급. httpx.HTTPStatusError는 코드가
    # exc.response.status_code에 있으므로 response 쪽도 본다.
    status = _status_code(exc)
    if isinstance(status, int) and (status == 429 or 500 <= status < 600):
        return True
    return False


def _status_code(exc: BaseException | None) -> int | None:
    if exc is None:
        return None
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def _retry_after_seconds(exc: BaseException | None) -> float | None:
    """예외에 실린 응답에서 Retry-After 헤더를 초 단위로 뽑는다 (없으면 None).

    헤더는 "초"(정수) 또는 HTTP-date 두 형식이 가능하다. openai SDK는 예외의
    response.headers 또는 exc.headers 에 원본 헤더를 남긴다. 파싱 실패는 조용히
    None (표준 백오프로 폴백) — 재시도 경로에서 예외를 또 던지면 안 된다.
    """
    if exc is None:
        return None
    headers = (getattr(getattr(exc, "response", None), "headers", None)
               or getattr(exc, "headers", None))
    if not headers:
        return None
    try:
        # 대소문자 무시 조회 (httpx.Headers는 지원, dict는 수동).
        value = None
        if hasattr(headers, "get"):
            value = headers.get("retry-after") or headers.get("Retry-After")
        if not value:
            return None
        value = str(value).strip()
        # 형식 1: 초 (정수/실수).
        try:
            secs = float(value)
            return max(0.0, min(secs, _RETRY_AFTER_MAX))
        except ValueError:
            pass
        # 형식 2: HTTP-date — 지금과의 차이를 초로.
        try:
            import datetime as _dt

            when = parsedate_to_datetime(value)
            if when is None:
                return None
            now = _dt.datetime.now(when.tzinfo) if when.tzinfo else _dt.datetime.now()
            delta = (when - now).total_seconds()
            return max(0.0, min(delta, _RETRY_AFTER_MAX))
        except (TypeError, ValueError):
            return None
    except Exception:  # noqa: BLE001 — 헤더 파싱은 절대 재시도를 깨선 안 된다
        return None


class _WaitRateLimitAware(wait_base):
    """Retry-After 존중 + jitter를 더한 wait 전략.

    - 예외에 Retry-After가 있으면 그 값을 기준으로 (헤더 우선).
    - 없으면 지수 백오프(multiplier·min·max) 기준.
    - 두 경우 모두 [0, jitter] 범위의 랜덤 값을 더해 재시도 시점을 흩뿌린다.
    """

    def __init__(self, *, multiplier: float = 2, min: float = 2,  # noqa: A002
                 max: float = 40, jitter: float = 3.0) -> None:  # noqa: A002
        self._exp = wait_exponential(multiplier=multiplier, min=min, max=max)
        self._jitter = builtin_max(0.0, jitter)

    def __call__(self, retry_state) -> float:  # type: ignore[override]
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        base = self._exp(retry_state)
        after = _retry_after_seconds(exc)
        if after is not None:
            # 헤더가 명시적이므로 지수 백오프보다 우선하되, 둘 중 큰 값을 택해
            # 헤더가 비현실적으로 짧을 때(0초 등) 재돌진하지 않게 한다.
            base = builtin_max(base, after)
        return base + (random.random() * self._jitter if self._jitter else 0.0)


def with_retry(fn: Callable[[], T], *, attempts: int = 4, on_retry=None) -> T:
    """동기 콜러블을 지수 백오프(+Retry-After·jitter)로 재시도. on_retry(attempt, exc)로 관측 가능."""

    def _before_sleep(state):
        if on_retry:
            exc = state.outcome.exception() if state.outcome else None
            on_retry(state.attempt_number, exc)

    @retry(
        stop=stop_after_attempt(attempts),
        wait=_WaitRateLimitAware(multiplier=2, min=2, max=40, jitter=3.0),
        retry=retry_if_exception(is_transient),
        before_sleep=_before_sleep,
        reraise=True,
    )
    def _run() -> T:
        return fn()

    return _run()
