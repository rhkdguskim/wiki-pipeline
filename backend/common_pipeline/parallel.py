"""에이전트 병렬 분배 — ThreadPoolExecutor 골격 공용화.

map(단위 요약)·reduce(테마 합성)처럼 '항목마다 에이전트 1개'를 병렬로 돌리는 자리가
파이프라인마다 반복된다. 완료 순서대로 (item, result, exc)를 스트리밍해 호출부가
진행 이벤트·실패 기록을 자기 정책대로 처리하게 한다.

LangGraph Send API(그래프 내 fan-out) 대신 러너 계층 병렬을 쓰는 이유: 항목마다
**독립 그래프 실행**이어야 항목 단위 캐시(_summaries.json)·래칫(_verdicts.json)·
실패 격리(한 항목 예외가 전체를 죽이지 않음)·완료 즉시 저장이 성립한다.
Send는 한 그래프 안 병렬이라 이 격리가 없다.
"""
from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Callable, Iterator


def parallel_map(
    items: list, worker: Callable[[Any], Any], *, max_workers: int,
    stagger: float = 0.0,
) -> Iterator[tuple[Any, Any, Exception | None]]:
    """items 각각에 worker를 병렬 적용, 완료 순서대로 (item, result|None, exc|None)를 낸다.

    제너레이터라 항목이 끝나는 즉시 진행 이벤트를 낼 수 있다 — 끝까지 소비해야
    풀이 정리된다 (호출부는 전 항목을 순회하는 것이 계약).

    stagger>0 이면 작업 제출을 그 간격(초)만큼 어긋나게 한다. 모든 worker가
    같은 순간 LLM 호출을 열면(특히 concurrency 게이트 슬롯이 동시에 나면) 공급자
    rate limit 창에 한꺼번에 부딪힌다 — 소폭 지연이 시작 시점을 흩뿌려 이를 완화한다.
    게이트가 없거나(무제한) 항목 수가 워커 수 이하면 실질 효과는 미미하지만 무해하다.
    """
    if not items:
        return
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(max_workers, len(items)))) as ex:
        futs = {}
        for i, it in enumerate(items):
            if stagger > 0 and i > 0:
                time.sleep(stagger)
            futs[ex.submit(worker, it)] = it
        for fut in concurrent.futures.as_completed(futs):
            item = futs[fut]
            try:
                yield item, fut.result(), None
            except Exception as e:  # noqa: BLE001
                yield item, None, e
