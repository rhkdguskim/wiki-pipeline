"""WebSocket 실시간 채널 — 폴링을 대체하는 push 경로.

러너 webhook으로 적재되는 이벤트·run 상태 변화·등록 변경을 접속한 대시보드에
즉시 push한다. 폴링 API는 폴백으로 유지된다.

메시지 형태:
- {"type": "events", "run_id": "...", "events": [...]}      # 러너 이벤트 배치
- {"type": "run_status", "run_id": "...", "status": "..."}  # 완료 보고 반영
- {"type": "runs_changed" | "sources_changed" | "instances_changed" | "targets_changed"}

Per-client 필터 (Track E):
  각 WS 클라이언트는 ?verbose=0|1 쿼리 파라미터로 필터 모드를 지정한다.
  - verbose=1: 모든 이벤트 수신 (과거 동작 — 디버그용)
  - verbose=0 (기본): agent_step.thinking 이벤트는 드랍 (고용량·모니터링용 노이즈)
  제어 메시지(run_status·runs_changed·sources_changed)는 항상 송신된다.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

log = logging.getLogger("controlplane.ws")

_QUEUE_MAX = 1000   # 느린 클라이언트 보호 — 넘치면 그 클라이언트만 끊는다


def default_filter(message: dict[str, Any]) -> dict[str, Any] | None:
    """verbose=0 기본 필터 — agent_step.thinking 이벤트를 드랍.

    제어 메시지(run_status·runs_changed·...)는 무조건 통과. events 메시지는
    events 배열에서 detail.kind == "thinking" 인 항목만 제거한다. 빈 배열이
    되면 메시지 자체를 송신하지 않는다 (None 반환).
    """
    if message.get("type") != "events":
        return message
    events = message.get("events") or []
    filtered = [e for e in events
                if not ((e.get("detail") or {}).get("kind") == "thinking"
                        and e.get("layer") == "agent_step")]
    if not filtered:
        return None
    if len(filtered) == len(events):
        return message
    return {**message, "events": filtered}


def passthrough_filter(message: dict[str, Any]) -> dict[str, Any] | None:
    """verbose=1 필터 — 모든 메시지를 그대로 통과."""
    return message


class Broadcaster:
    """스레드(동기 라우트) -> asyncio(웹소켓) 브리지. publish는 스레드 안전.

    각 WS 클라이언트는 register(filter_fn) 로 자기 전용 큐 + 필터를 등록한다.
    fanout 은 메시지를 필터에 통과시켜 큐에 넣는다 — 필터가 None 을 반환하면 스킵.
    """

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._clients: set[_Client] = set()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def register(self, filter_fn: Callable[[dict], dict | None] = passthrough_filter) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
        client = _Client(queue=q, filter_fn=filter_fn)
        self._clients.add(client)
        return q

    def unregister(self, q: asyncio.Queue) -> None:
        for c in list(self._clients):
            if c.queue is q:
                self._clients.discard(c)
                break

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
        for client in self._clients:
            try:
                filtered = client.filter_fn(message)
            except Exception:  # noqa: BLE001 — 필터 예외가 다른 클라이언트를 막으면 안 된다
                filtered = message
            if filtered is None:
                continue
            try:
                client.queue.put_nowait(filtered)
            except asyncio.QueueFull:
                dead.append(client)   # 소비를 멈춘 클라이언트 — 큐 정리 유도
        for client in dead:
            self._clients.discard(client)
            # 큐가 가득 찬 상태에서는 overflow 신호도 큐에 못 들어간다 — 클라이언트는
            # 다음 메시지 부재로 자연 타임아웃되거나, WS ping 실패로 끊긴다.
            # 운영 가시성을 위해 warning 로그만 남긴다.
            log.warning("ws client overflow — discarded (queue=%d, clients_left=%d)",
                        _QUEUE_MAX, len(self._clients))


class _Client:
    """등록된 WS 클라이언트 1개 — 큐 + per-client 필터."""
    __slots__ = ("queue", "filter_fn")

    def __init__(self, queue: asyncio.Queue, filter_fn: Callable[[dict], dict | None]):
        self.queue = queue
        self.filter_fn = filter_fn
