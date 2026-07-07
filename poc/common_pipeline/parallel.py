"""에이전트 병렬 분배 — ThreadPoolExecutor 골격 공용화.

map(단위 요약)·reduce(테마 합성)처럼 '항목마다 에이전트 1개'를 병렬로 돌리는 자리가
파이프라인마다 반복된다. 완료 순서대로 (item, result, exc)를 스트리밍해 호출부가
진행 이벤트·실패 기록을 자기 정책대로 처리하게 한다.
"""
from __future__ import annotations

import concurrent.futures
from typing import Any, Callable, Iterator


def parallel_map(
    items: list, worker: Callable[[Any], Any], *, max_workers: int,
) -> Iterator[tuple[Any, Any, Exception | None]]:
    """items 각각에 worker를 병렬 적용, 완료 순서대로 (item, result|None, exc|None)를 낸다.

    제너레이터라 항목이 끝나는 즉시 진행 이벤트를 낼 수 있다 — 끝까지 소비해야
    풀이 정리된다 (호출부는 전 항목을 순회하는 것이 계약).
    """
    if not items:
        return
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(max_workers, len(items)))) as ex:
        futs = {ex.submit(worker, it): it for it in items}
        for fut in concurrent.futures.as_completed(futs):
            item = futs[fut]
            try:
                yield item, fut.result(), None
            except Exception as e:  # noqa: BLE001
                yield item, None, e
