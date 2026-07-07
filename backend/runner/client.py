"""Control Plane HTTP 클라이언트 + webhook 이벤트 배치 싱크."""
from __future__ import annotations

import queue
import threading

import httpx

from ..common.retry import with_retry

_BATCH_MAX = 50          # 배치 1회 최대 이벤트 수
_FLUSH_INTERVAL = 2.0    # 초 — 이벤트가 적어도 이 주기로 밀어낸다


class ControlPlaneClient:
    def __init__(self, base_url: str, runner_token: str, *,
                 timeout: float = 30.0, transport: httpx.BaseTransport | None = None):
        self.base = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {runner_token}"} if runner_token else {}
        self._client = httpx.Client(headers=headers, timeout=timeout, transport=transport)

    def runner_context(self, run_id: str) -> dict:
        resp = with_retry(lambda: self._client.get(
            f"{self.base}/api/runner/context", params={"run": run_id}), attempts=3)
        resp.raise_for_status()
        return resp.json()

    def push_events(self, run_id: str, events: list[dict]) -> None:
        resp = self._client.post(f"{self.base}/api/webhook/events",
                                 json={"run_id": run_id, "events": events})
        resp.raise_for_status()

    def complete(self, run_id: str, report: dict) -> dict:
        resp = with_retry(lambda: self._client.post(
            f"{self.base}/api/webhook/complete",
            json={"run_id": run_id, **report}), attempts=3)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()


class WebhookEventSink:
    """Observer 전역 싱크 — 이벤트를 큐에 넣고 배경 스레드가 배치로 push.

    파이프라인 스레드를 절대 블로킹하지 않는다. push 실패는 로컬 JSONL이
    감사 사본으로 남으므로 조용히 버린다 (다음 배치가 이어서 감).
    """

    def __init__(self, client: ControlPlaneClient, run_id: str):
        self.client = client
        self.run_id = run_id
        self._q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def __call__(self, event: dict) -> None:
        self._q.put(event)

    def _drain(self) -> list[dict]:
        batch: list[dict] = []
        while len(batch) < _BATCH_MAX:
            try:
                batch.append(self._q.get_nowait())
            except queue.Empty:
                break
        return batch

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._stop.wait(_FLUSH_INTERVAL)
            self._flush()

    def _flush(self) -> None:
        while True:
            batch = self._drain()
            if not batch:
                return
            try:
                self.client.push_events(self.run_id, batch)
            except Exception:  # noqa: BLE001 — 로컬 JSONL이 감사 사본
                return

    def close(self) -> None:
        """종료 시 잔여 이벤트를 마지막으로 밀어낸다."""
        self._stop.set()
        self._thread.join(timeout=5)
        self._flush()
