"""WebSocket 실시간 채널 — 폴링을 대체하는 push 경로.

러너 webhook으로 적재되는 이벤트·run 상태 변화·등록 변경을 접속한 대시보드에
즉시 push한다. 서버는 전체를 브로드캐스트하고 클라이언트가 run_id로 필터링한다
(로컬 규모에서 단순함 우선). 폴링 API는 폴백으로 유지된다.

메시지 형태:
- {"type": "events", "run_id": "...", "events": [...]}      # 러너 이벤트 배치
- {"type": "run_status", "run_id": "...", "status": "..."}  # 완료 보고 반영
- {"type": "runs_changed" | "sources_changed" | "instances_changed" | "targets_changed"}
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger("controlplane.ws")

_QUEUE_MAX = 1000   # 느린 클라이언트 보호 — 넘치면 그 클라이언트만 끊는다


class Broadcaster:
    """스레드(동기 라우트) -> asyncio(웹소켓) 브리지. publish는 스레드 안전."""

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queues: set[asyncio.Queue] = set()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def client_count(self) -> int:
        return len(self._queues)

    def register(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._queues.add(q)
        return q

    def unregister(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    def publish(self, message: dict[str, Any]) -> None:
        """어느 스레드에서든 호출 가능 — 이벤트 루프로 넘겨 브로드캐스트."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._fanout, message)
        except RuntimeError:
            pass   # 루프 종료 중 — 관측 push 실패는 치명 아님

    def _fanout(self, message: dict[str, Any]) -> None:
        dead = []
        for q in self._queues:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(q)   # 소비를 멈춘 클라이언트 — 연결 정리 유도
        for q in dead:
            self._queues.discard(q)
            try:
                q.put_nowait({"type": "overflow"})
            except asyncio.QueueFull:
                pass
