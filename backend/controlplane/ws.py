"""WebSocket 실시간 채널 — 폴링을 대체하는 push 경로.

러너 webhook으로 적재되는 이벤트·run 상태 변화·등록 변경을 접속한 대시보드에
즉시 push한다. 폴링 API는 폴백으로 유지된다.

메시지 형태 (2026-07-08 envelope 통일):
- {"type": "events", "run_id": "...", "events": [...], "latest_seq": int, "snapshot_version": int}
- {"type": "run_status", "run_id": "...", "status": "...", "publishable": bool,
   "publish_state": str, "snapshot_version": int, ...}
- {"type": "quality_updated" | "evidence_updated" | "coverage_updated" |
   "artifact_updated" | "vnc_session_updated" | "mr_plan_updated" | "run_heartbeat"}
- {"type": "runs_changed" | "sources_changed" | "pipeline_status_changed" | "costs_changed"}
- {"type": "overflow", "run_id": "..."}  # 큐 overflow 시 클라이언트 fallback 유도

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


def build_envelope(*, message_type: str, run_id: str = "", latest_seq: int = 0,
                   snapshot_version: int = 0, payload: dict | None = None) -> dict:
    """모든 WS message envelope — latest_seq / snapshot_version 표준 첨부.

    frontend 가 이 필드를 보고 snapshot_version 증가 시 refetch, latest_seq 로
    dedupe/seq replay 를 수행한다.
    """
    env = {
        "type": message_type,
        "message_id": f"msg-{message_type}-{asyncio.get_event_loop().time():.0f}",
        "ts": "",
        "run_id": run_id,
        "latest_seq": int(latest_seq or 0),
        "snapshot_version": int(snapshot_version or 0),
    }
    if payload:
        env.update(payload)
    return env


class Broadcaster:
    """스레드(동기 라우트) -> asyncio(웹소켓) 브리지. publish는 스레드 안전.

    각 WS 클라이언트는 register(filter_fn) 로 자기 전용 큐 + 필터를 등록한다.
    fanout 은 메시지를 필터에 통과시켜 큐에 넣는다 — 필터가 None 을 반환하면 스킵.
    """

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._clients: set[_Client] = set()
        # (key, callback) 튜플 목록 — key 는 보통 클라이언트 큐(연결 종료 시 제거용).
        self._overflow_callbacks: list[tuple[object | None, Callable[[dict], None]]] = []

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

    def register_overflow_callback(self, fn: Callable[[dict], None],
                                   *, key: object | None = None) -> None:
        """WS 라우트에서 overflow 시 호출할 콜백 — ws_channel close 처리 위임.

        key(보통 그 클라이언트의 큐)를 함께 넘기면 unregister_overflow_callback 으로
        연결 종료 시 정확히 제거할 수 있다. 예전엔 append 만 하고 제거 경로가 없어,
        탭이 열렸다 닫힐 때마다 죽은 소켓을 가리키는 클로저가 무한 누적됐다
        (메모리 누수 + overflow 시 죽은 소켓 전부에 close 시도 → 예외 폭증).
        """
        self._overflow_callbacks.append((key, fn))

    def unregister_overflow_callback(self, key: object) -> None:
        """key(큐)로 등록된 overflow 콜백을 제거한다 — 연결 종료 시 호출."""
        self._overflow_callbacks = [
            (k, f) for (k, f) in self._overflow_callbacks if k is not key
        ]

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
                # overflow 신호도 큐에 못 들어간다 — ws_channel close 콜백으로
                # frontend 가 reconnect / snapshot refetch 하도록 유도.
                for _key, cb in self._overflow_callbacks:
                    try:
                        cb({"type": "overflow", "run_id": message.get("run_id", "")})
                    except Exception:  # noqa: BLE001
                        log.warning("overflow callback failed", exc_info=True)
        for client in dead:
            self._clients.discard(client)
            log.warning("ws client overflow — discarded (queue=%d, clients_left=%d)",
                        _QUEUE_MAX, len(self._clients))


class _Client:
    """등록된 WS 클라이언트 1개 — 큐 + per-client 필터."""
    __slots__ = ("queue", "filter_fn")

    def __init__(self, queue: asyncio.Queue, filter_fn: Callable[[dict], dict | None]):
        self.queue = queue
        self.filter_fn = filter_fn
