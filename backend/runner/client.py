"""Control Plane HTTP 클라이언트 + webhook 이벤트 배치 싱크 + heartbeat."""
from __future__ import annotations

import logging
import os
import queue
import threading
from datetime import datetime, timezone

import httpx

from ..common.retry import with_retry

log = logging.getLogger("runner.client")

_BATCH_MAX = 50          # 배치 1회 최대 이벤트 수
_FLUSH_INTERVAL = 2.0    # 초 — 이벤트가 적어도 이 주기로 밀어낸다
_HEARTBEAT_INTERVAL = 30.0   # 초 — 러너 heartbeat 주기


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

    def heartbeat(self, run_id: str, *, attempt: int = 1, stage: str = "",
                 pid: str = "") -> None:
        """POST /api/webhook/heartbeat — best-effort, 실패해도 러너를 중단하지 않는다."""
        try:
            resp = self._client.post(
                f"{self.base}/api/webhook/heartbeat",
                json={"run_id": run_id, "attempt": attempt, "stage": stage,
                      "pid": pid,
                      "timestamp": datetime.now(timezone.utc).isoformat()},
            )
            resp.raise_for_status()
        except Exception as e:  # noqa: BLE001 — heartbeat 실패는 조용히 무시
            log.debug("heartbeat 전송 실패 run=%s: %s: %s", run_id, type(e).__name__, e)

    def post_webhook(self, path: str, payload: dict) -> dict | None:
        """best-effort webhook POST — 실패 시 None 반환, 예외 전파 안 함.

        quality/evidence/coverage/artifact/vnc webhook 용. 엔드포인트가 아직
        없거나 에러를 반환해도 러너 실행에는 영향을 주지 않는다.
        """
        try:
            resp = self._client.post(f"{self.base}{path}", json=payload,
                                     timeout=15.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001
            log.warning("webhook %s 전송 실패: %s: %s", path, type(e).__name__, e)
            return None

    def complete(self, run_id: str, report: dict) -> dict:
        """완료 보고 — run 결과(status/sha/mr) 를 Control Plane 에 확정 전달.

        이것이 실패하면 성공한 run 이 유실되므로(다음 배치가 같은 구간 재처리),
        전송 실패 시 로컬에 리포트를 남긴다(감사·수동 재전송용). 재시도 횟수를
        heartbeat 보다 넉넉히(6회) 줘서 Control Plane 의 짧은 재기동을 흡수한다.
        """
        try:
            resp = with_retry(lambda: self._client.post(
                f"{self.base}/api/webhook/complete",
                json={"run_id": run_id, **report}), attempts=6)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001 — 유실 방지: 로컬에 남기고 재발생
            self._dump_pending_complete(run_id, report, e)
            raise

    def _dump_pending_complete(self, run_id: str, report: dict,
                               exc: BaseException) -> None:
        """complete 전송 실패 시 리포트를 out/pending_completes/ 에 JSON 으로 남긴다.

        운영자가 이 파일로 유실된 run 결과를 확인하고 수동 재전송할 수 있다.
        디렉터리 생성/쓰기 자체가 실패해도 조용히 넘어간다(로그만).
        """
        try:
            import json
            from pathlib import Path
            out_root = Path(os.environ.get("OUT_DIR", "out"))
            pending_dir = out_root / "pending_completes"
            pending_dir.mkdir(parents=True, exist_ok=True)
            payload = {"run_id": run_id, "report": report,
                       "error": f"{type(exc).__name__}: {exc}",
                       "ts": datetime.now(timezone.utc).isoformat()}
            (pending_dir / f"{run_id}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8")
            log.error("complete 전송 실패 — 리포트를 %s 에 보존. run=%s: %s: %s",
                      pending_dir, run_id, type(exc).__name__, exc)
        except Exception as dump_exc:  # noqa: BLE001
            log.error("complete 실패 + 로컬 보존도 실패 run=%s: %s / %s",
                      run_id, exc, dump_exc)

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


class HeartbeatSender:
    """백그라운드 스레드에서 주기적으로 heartbeat 를 전송한다.

    execute() 시작 시 start(), 종료 시 stop() — 파이프라인 실행 중
    Control Plane 이 run 이 살아있음을 알 수 있게 한다 (stuck run reaper 회피).
    전송 실패는 무시한다 (best-effort).
    """

    def __init__(self, client: ControlPlaneClient, run_id: str, *,
                 interval: float = _HEARTBEAT_INTERVAL, attempt: int = 1):
        self._client = client
        self._run_id = run_id
        self._interval = interval
        self._attempt = attempt
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="runner-heartbeat")
        self._stage = ""

    def start(self) -> None:
        self._send()
        self._thread.start()

    def set_stage(self, stage: str) -> None:
        self._stage = stage

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            self._send()

    def _send(self) -> None:
        self._client.heartbeat(
            self._run_id, attempt=self._attempt, stage=self._stage,
            pid=str(os.getpid()),
        )

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
