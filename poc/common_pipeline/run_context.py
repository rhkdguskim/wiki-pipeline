"""러너 스캐폴드 — run_id 발급·Observer 수명·run 계층 이벤트·자원 정리를 한 곳에.

네 러너(정적 diff/init, 매뉴얼 run/smoke)가 같은 모양으로 반복하던 골격
(uuid run_id + Observer + emitter + try/except/finally + run 이벤트)을 컨텍스트
매니저로 공용화한다. 예외는 run failed 이벤트를 남기고 그대로 전파된다 —
정책(상태 전진·요약 구성·부분 실패 처리)은 여전히 러너 소유다.
"""
from __future__ import annotations

import uuid

from ..common.config import Settings
from ..common.observer import Observer


class RunContext:
    def __init__(self, pipeline_id: str, settings: Settings, *, run_stage: str,
                 prefix: str | None = None, run_id: str | None = None):
        source_id = getattr(settings, "source_id", "")
        stem = "-".join(x for x in [prefix or pipeline_id, source_id] if x)
        self.run_id = run_id or f"{stem}-{uuid.uuid4().hex[:8]}"
        self.settings = settings
        self.run_stage = run_stage
        self.observer = Observer(self.run_id, settings.out_path)
        self.rev = self.observer.emitter(pipeline_id, self.run_id)
        self._resources: list = []

    def track(self, resource):
        """close()를 가진 자원을 등록 — 종료 시 등록 역순으로 정리한다."""
        self._resources.append(resource)
        return resource

    # ── run 계층 이벤트 (stage/engine_call/agent_step은 self.rev로 직접) ──

    def start(self, detail: dict | None = None) -> None:
        self.rev("run", self.run_stage, "running", detail=detail)

    def done(self, detail: dict | None = None) -> None:
        self.rev("run", self.run_stage, "done", detail=detail)

    def failed(self, detail: dict | None = None) -> None:
        """예외 없이 실패로 끝내는 경로용 (예: 관측 0건) — 이벤트만 남기고 반환은 러너가."""
        self.rev("run", self.run_stage, "failed", detail=detail)

    def __enter__(self) -> "RunContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is not None:
            self.failed({"error": f"{type(exc).__name__}: {exc}"})
        for r in reversed(self._resources):
            try:
                r.close()
            except Exception:  # noqa: BLE001
                pass
        self.observer.close()
        return False
