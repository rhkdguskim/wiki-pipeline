"""프로세스 전역 LLM 동시 호출 게이트 (공급자 concurrency 한도 강제).

문제: map(단위 요약 6병렬) × reduce(테마 4병렬) + 각 테마 내부의 writer→critic
호출이 겹치면 in-flight LLM 요청이 순간적으로 십수 개가 된다. Z.AI(GLM)는 계정
rate limit 때문에 병렬 호출을 안정적으로 허용하지 않을 수 있다. 재시도만으로는
동시성 자체를 줄이지 않으므로 같은 429를 반복한다.

해결: 실제 `model.invoke` 지점을 이 게이트로 감싸 **동시에 열려 있는 LLM 호출
수를 N개 이하로 강제**한다. 병렬도(스레드 풀 크기)는 보통 그대로 두되, 게이트가
초과 스레드를 대기시켜 공급자에 나가는 in-flight 요청만 N으로 눌러 담는다.
재시도(common.retry)는 그래도 새는 일시 오류를 위한 2차 안전망으로 남는다.

한도 원천: 러너 subprocess는 Control Plane이 DB effective 값을
`LLM_MAX_CONCURRENCY` env로 주입한다(services/runs.py). 그래서 env를 1차
원천으로 읽고, 없으면 cached_settings()(=.env)로 폴백한다. 0/음수/미설정이면
게이트를 열어둔 채(무제한) 통과시켜 하위 호환을 지킨다. 단, provider가 Z.AI이거나
base URL이 z.ai이면 설정값과 관계없이 1개 슬롯만 열고 병렬 작업도 직렬화한다.

스레드 기반인 이유: 병렬 실행은 ThreadPoolExecutor(common_pipeline.parallel)이고
model.invoke는 동기 호출이라 threading.Semaphore로 충분하다. asyncio 경로가
생기면 별도 async 게이트를 추가하면 된다.
"""
from __future__ import annotations

import contextlib
import os
import threading
from typing import Iterator

_lock = threading.Lock()
_sem: threading.BoundedSemaphore | None = None
_limit: int = 0


def is_zai_runtime() -> bool:
    """현재 런타임이 Z.AI 계열인지 판별한다.

    Control Plane은 provider를 ``openai-compatible``으로 두고 base URL만 z.ai로
    설정할 수 있으므로 두 값을 모두 본다. 환경변수가 없는 로컬 실행에서는 Settings
    값을 폴백으로 사용한다.
    """
    provider = os.getenv("LLM_PROVIDER", "")
    base_url = os.getenv("LLM_BASE_URL", "")
    if not provider and not base_url:
        try:
            from .config import cached_settings

            settings = cached_settings()
            provider = settings.llm_provider
            base_url = settings.llm_base_url
        except Exception:  # noqa: BLE001 - gate detection must not block a run
            return False

    provider_key = provider.lower().replace("-", "").replace("_", "").replace(".", "")
    return provider_key in {"zai", "zhipu", "zhipuai"} or "z.ai" in base_url.lower()


def _resolve_limit() -> int:
    """동시 호출 한도. env(LLM_MAX_CONCURRENCY) 우선, 없으면 .env Settings, 실패 시 0."""
    # Z.AI에는 병렬 in-flight 요청을 보내지 않는다. DB 설정이 더 커도 이
    # 공급자 정책을 우선해 rate-limit 재시도 폭주를 막는다.
    if is_zai_runtime():
        return 1
    raw = os.getenv("LLM_MAX_CONCURRENCY")
    if raw is not None and raw.strip() != "":
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    try:
        from .config import cached_settings

        return max(0, int(cached_settings().llm_max_concurrency))
    except Exception:  # noqa: BLE001 — 설정 로드 실패해도 게이트가 파이프라인을 막으면 안 된다
        return 0


def _get_semaphore() -> threading.BoundedSemaphore | None:
    """한도가 양수면 그 크기의 세마포어를, 아니면 None(무제한)을 반환 (프로세스당 1회 초기화)."""
    global _sem, _limit
    if _sem is not None:
        return _sem
    with _lock:
        if _sem is None:
            limit = _resolve_limit()
            _limit = limit
            _sem = threading.BoundedSemaphore(limit) if limit > 0 else None
    return _sem


@contextlib.contextmanager
def llm_slot() -> Iterator[None]:
    """LLM 호출 1건이 점유하는 동시성 슬롯. `with llm_slot(): model.invoke(...)`.

    한도가 0(무제한)이면 즉시 통과한다. 양수면 슬롯이 빌 때까지 블록해
    in-flight 호출 수를 한도 이하로 유지한다. 예외가 나도 슬롯은 반드시 반납된다.
    """
    sem = _get_semaphore()
    if sem is None:
        yield
        return
    sem.acquire()
    try:
        yield
    finally:
        sem.release()


def current_limit() -> int:
    """현재 적용 중인 동시성 한도 (0=무제한). 관측·로그용 — 세마포어 초기화도 유발."""
    _get_semaphore()
    return _limit


def effective_parallelism(requested: int) -> int:
    """LLM 작업을 시작할 워커 수를 공급자 정책에 맞춰 계산한다.

    세마포어만으로도 실제 invoke는 직렬화되지만, Z.AI에서 여러 스레드를 만드는
    것은 대기열·컨텍스트·재시도만 늘린다. 따라서 map/reduce 오케스트레이션도 1개
    워커로 줄인다. 다른 공급자는 기존 요청 값을 보존한다.
    """
    if is_zai_runtime():
        return 1
    return max(1, int(requested))


def reset_for_test() -> None:
    """테스트 전용 — 게이트 상태를 초기화해 다음 호출이 env를 다시 읽게 한다."""
    global _sem, _limit
    with _lock:
        _sem = None
        _limit = 0
