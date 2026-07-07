"""과제별 스케줄러 (decision-schedule-per-source · decision-nightly-batch).

APScheduler cron — 소스별 schedule_cron(비우면 서버 기본값: 평일 20:00)으로
정적 파이프라인 배치를 건다. 수동 트리거는 API가 같은 launch 경로를 쓴다.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from ..db import session_scope
from ..models import Run, Source, SourceSchedule
from ..schedule import describe_cron, next_fire, parse_cron, validate_cron
from ..settings import ControlPlaneSettings
from .runs import RunService

log = logging.getLogger("controlplane.scheduler")


class SourceScheduler:
    def __init__(self, settings: ControlPlaneSettings,
                 session_factory: sessionmaker, run_service: RunService):
        self.settings = settings
        self.session_factory = session_factory
        self.run_service = run_service
        self._scheduler = BackgroundScheduler(timezone="Asia/Seoul")

    def start(self) -> None:
        if not self.settings.scheduler_enabled:
            log.info("스케줄러 비활성화 (SCHEDULER_ENABLED=false)")
            return
        self.reload_jobs()
        self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def reload_jobs(self) -> None:
        """소스 등록/수정 후 재호출 — 활성 소스의 cron 잡을 재구성한다."""
        for job in self._scheduler.get_jobs():
            job.remove()
        # 유지보수: 이벤트 보존 정책 (매일 03:30, 배치와 겹치지 않는 시각)
        if self.settings.event_retention_days > 0:
            self._scheduler.add_job(
                self._prune_events, CronTrigger.from_crontab("30 3 * * *", timezone="Asia/Seoul"),
                id="maintenance-prune-events", replace_existing=True,
                misfire_grace_time=3600, coalesce=True,
            )
        with session_scope(self.session_factory) as db:
            sources = db.scalars(select(Source).where(Source.enabled.is_(True))).all()
            for source in sources:
                schedules = [s for s in source.schedules if s.enabled]
                if schedules:
                    for sched in schedules:
                        self._add_source_job(source, sched)
                else:
                    self._add_legacy_source_job(source)
        log.info("스케줄 잡 %d개 등록", len(self._scheduler.get_jobs()))

    def _add_source_job(self, source: Source, sched: SourceSchedule) -> None:
        cron = sched.cron.strip() or self.settings.default_schedule_cron
        try:
            trigger = CronTrigger.from_crontab(validate_cron(cron), timezone="Asia/Seoul")
        except ValueError as e:
            log.error("source %s schedule %s cron 파싱 실패(%r): %s — 잡 미등록",
                      source.id, sched.id, cron, e)
            return
        self._scheduler.add_job(
            self._run_batch, trigger,
            args=[source.id, sched.pipeline_id, sched.mode, sched.branch_role],
            id=f"batch-{source.id}-{sched.id}", replace_existing=True,
            misfire_grace_time=3600, coalesce=True,
        )

    def _add_legacy_source_job(self, source: Source) -> None:
        cron = source.schedule_cron.strip() or self.settings.default_schedule_cron
        try:
            trigger = CronTrigger.from_crontab(validate_cron(cron), timezone="Asia/Seoul")
        except ValueError as e:
            log.error("source %s cron 파싱 실패(%r): %s — 잡 미등록", source.id, cron, e)
            return
        self._scheduler.add_job(
            self._run_batch, trigger, args=[source.id, "static", "auto", "dev"],
            id=f"batch-{source.id}", replace_existing=True,
            misfire_grace_time=3600, coalesce=True,
        )

    def list_schedules(self, db) -> list[dict]:
        sources = db.scalars(select(Source).order_by(Source.id)).all()
        jobs = {j.id: j for j in self._scheduler.get_jobs()}
        rows: list[dict] = []
        for source in sources:
            if source.schedules:
                for sched in source.schedules:
                    rows.append(self._schedule_row(source, sched, jobs))
            else:
                rows.append(self._legacy_schedule_row(source, jobs))
        return rows

    def _schedule_row(self, source: Source, sched: SourceSchedule, jobs: dict) -> dict:
        effective_cron = sched.cron.strip() or self.settings.default_schedule_cron
        job = jobs.get(f"batch-{source.id}-{sched.id}")
        return {
            "id": sched.id,
            "source_id": source.id,
            "source_label": source.label,
            "label": sched.label,
            "enabled": source.enabled and sched.enabled,
            "pipeline_id": sched.pipeline_id,
            "mode": sched.mode,
            "branch_role": sched.branch_role,
            "schedule_cron": sched.cron,
            "effective_cron": effective_cron,
            "schedule": parse_cron(effective_cron),
            "description": describe_cron(effective_cron),
            "next_run_at": self._next_run(job, effective_cron, source.enabled and sched.enabled),
            "job_registered": bool(job),
        }

    def _legacy_schedule_row(self, source: Source, jobs: dict) -> dict:
        effective_cron = source.schedule_cron.strip() or self.settings.default_schedule_cron
        job = jobs.get(f"batch-{source.id}")
        return {
            "id": None,
            "source_id": source.id,
            "source_label": source.label,
            "label": "정적 문서 자동화",
            "enabled": source.enabled,
            "pipeline_id": "static",
            "mode": "auto",
            "branch_role": "dev",
            "schedule_cron": source.schedule_cron,
            "effective_cron": effective_cron,
            "schedule": parse_cron(effective_cron),
            "description": describe_cron(effective_cron),
            "next_run_at": self._next_run(job, effective_cron, source.enabled),
            "job_registered": bool(job),
        }

    def _next_run(self, job, cron: str, enabled: bool) -> str:
        job_next_run = getattr(job, "next_run_time", None) if job else None
        if job_next_run:
            return job_next_run.isoformat()
        if enabled:
            try:
                return next_fire(cron)
            except ValueError:
                return ""
        return ""

    def _prune_events(self) -> None:
        try:
            with session_scope(self.session_factory) as db:
                self.run_service.prune_events(
                    db, older_than_days=self.settings.event_retention_days)
        except Exception as e:  # noqa: BLE001
            log.error("이벤트 정리 실패: %s: %s", type(e).__name__, e)

    def _run_batch(self, source_id: str, pipeline_id: str = "static",
                   mode: str = "auto", branch_role: str = "dev") -> None:
        """야간 배치 1건 — run 생성 + 러너 기동. (mode=auto: 상태 기반 init/diff 분기)"""
        try:
            with session_scope(self.session_factory) as db:
                run = self.run_service.create_run(
                    db, source_id=source_id, mode=mode,
                    branch_role=branch_role, trigger="schedule",
                    pipeline_id=pipeline_id)
                run_id = run.id
            with session_scope(self.session_factory) as db:
                run = db.get(Run, run_id)
                if run is not None:
                    self.run_service.launch_runner(run)
        except Exception as e:  # noqa: BLE001 — 한 소스의 실패가 스케줄러를 죽이면 안 된다
            log.error("배치 트리거 실패 source=%s: %s: %s", source_id, type(e).__name__, e)
