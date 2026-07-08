"""run 수명주기 — 트리거·이벤트 적재·완료 보고·sha 전진.

concept-idempotent-sha: last_processed_sha는 완료 보고(MR 제출 성공 포함)에서만
전진한다. 실패한 run은 포인터를 건드리지 않아 다음 배치가 같은 구간을 재처리한다.
decision-branch-loss-policy: compare 404 -> 소스 자동 비활성화 + admin 알림.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Run, RunEvent, RunModelUsage, Source, SourceBranch
from ..settings import ControlPlaneSettings
from ..timeutil import as_utc, isoformat_z
from .notifier import Notifier

log = logging.getLogger("controlplane.runs")

log = logging.getLogger("controlplane.runs")


class RunService:
    def __init__(self, settings: ControlPlaneSettings, notifier: Notifier,
                 broadcaster=None):
        self.settings = settings
        self.notifier = notifier
        self.broadcaster = broadcaster

    def _publish(self, message: dict) -> None:
        if self.broadcaster is not None:
            self.broadcaster.publish(message)

    # ── 트리거 (수동/스케줄) ─────────────────────────────────
    def create_run(self, db: Session, *, source_id: str, mode: str = "auto",
                   branch_role: str = "dev", trigger: str = "manual",
                   pipeline_id: str = "static") -> Run:
        source = db.get(Source, source_id)
        if source is None:
            raise ValueError(f"알 수 없는 source: {source_id}")
        if not source.enabled:
            raise ValueError(f"비활성화된 source: {source_id} ({source.disabled_reason})")
        run_id = f"{pipeline_id}-{source_id}-{uuid.uuid4().hex[:8]}"
        run = Run(id=run_id, source_id=source_id, pipeline_id=pipeline_id,
                  mode=mode, branch_role=branch_role, trigger=trigger, status="pending")
        db.add(run)
        db.flush()
        self._publish({"type": "runs_changed", "run_id": run_id})
        return run

    def launch_runner(self, run: Run) -> subprocess.Popen | None:
        """Data Plane 러너 프로세스 기동 (backend.runner.job).

        Control Plane과 같은 호스트에서 subprocess로 실행하는 것이 v1 —
        docs-hub CI 러너로 옮길 때는 이 지점이 CI 트리거 API 호출로 바뀐다.
        """
        api_url = f"http://{self.settings.control_host}:{self.settings.control_port}"
        env = {
            **os.environ,
            "CONTROL_API_URL": api_url,
            "CONTROL_RUNNER_TOKEN": self.settings.control_runner_token,
        }
        cmd = [sys.executable, "-m", "backend.runner.job",
               "--run-id", run.id, "--source", run.source_id,
               "--mode", run.mode, "--branch-role", run.branch_role]
        try:
            proc = subprocess.Popen(cmd, env=env, cwd=None,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.info("러너 기동: run=%s pid=%s", run.id, proc.pid)
            return proc
        except Exception as e:  # noqa: BLE001
            log.error("러너 기동 실패: run=%s %s: %s", run.id, type(e).__name__, e)
            return None

    # ── webhook 이벤트 적재 ─────────────────────────────────
    def _record_model_usage(self, db: Session, run: Run, detail: dict) -> None:
        provider = str(detail.get("provider") or detail.get("vendor") or "unknown")
        model = str(detail.get("model") or detail.get("model_name") or "unknown")
        input_tokens = int(detail.get("input_tokens") or 0)
        output_tokens = int(detail.get("output_tokens") or 0)
        if not (input_tokens or output_tokens):
            return
        row = db.scalars(select(RunModelUsage).where(
            RunModelUsage.run_id == run.id,
            RunModelUsage.provider == provider,
            RunModelUsage.model == model,
        )).first()
        if row is None:
            row = RunModelUsage(
                run_id=run.id,
                source_id=run.source_id,
                pipeline_id=run.pipeline_id,
                provider=provider,
                model=model,
            )
            db.add(row)
        row.input_tokens = int(row.input_tokens or 0) + input_tokens
        row.output_tokens = int(row.output_tokens or 0) + output_tokens
        row.calls = int(row.calls or 0) + 1

    def ingest_events(self, db: Session, run_id: str, events: list[dict]) -> int:
        run = db.get(Run, run_id)
        count = 0
        for e in events:
            if not isinstance(e, dict):
                continue
            db.add(RunEvent(
                run_id=run_id,
                ts=str(e.get("ts") or ""),
                layer=str(e.get("layer") or ""),
                stage=str(e.get("stage") or ""),
                status=str(e.get("status") or ""),
                payload=json.dumps(e, ensure_ascii=False),
            ))
            count += 1
            if run is not None and e.get("layer") == "run":
                status = str(e.get("status") or "")
                if status == "running" and run.status == "pending":
                    run.status = "running"
                elif status in ("done", "failed"):
                    run.status = status
                detail = e.get("detail") or {}
                if status == "failed" and detail.get("error"):
                    run.error = str(detail["error"])[:2000]
            if run is not None and (e.get("detail") or {}).get("kind") == "usage":
                detail = e["detail"]
                run.input_tokens += int(detail.get("input_tokens") or 0)
                run.output_tokens += int(detail.get("output_tokens") or 0)
                self._record_model_usage(db, run, detail)
        db.flush()
        if count:
            self._publish({"type": "events", "run_id": run_id,
                           "events": [e for e in events if isinstance(e, dict)]})
        return count

    def read_db_events(self, db: Session, run_id: str, after_id: int = 0,
                       limit: int = 2000) -> dict:
        rows = db.scalars(
            select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.id > after_id)
            .order_by(RunEvent.id).limit(limit)
        ).all()
        events = [json.loads(r.payload) for r in rows]
        return {"events": events,
                "offset": rows[-1].id if rows else after_id,
                "size": after_id + len(rows), "age_sec": 0.0}

    def all_db_events(self, db: Session, run_id: str) -> list[dict]:
        rows = db.scalars(select(RunEvent).where(RunEvent.run_id == run_id)
                          .order_by(RunEvent.id)).all()
        return [json.loads(r.payload) for r in rows]

    def has_db_events(self, db: Session, run_id: str) -> bool:
        return db.scalars(select(RunEvent.id).where(RunEvent.run_id == run_id)
                          .limit(1)).first() is not None

    # ── 완료 보고 (sha 전진의 유일한 경로) ───────────────────
    def complete_run(self, db: Session, run_id: str, report: dict[str, Any]) -> dict:
        run = db.get(Run, run_id)
        if run is None:
            raise ValueError(f"알 수 없는 run: {run_id}")
        status = str(report.get("status") or "done")
        run.status = status
        run.from_sha = str(report.get("from_sha") or run.from_sha)
        run.to_sha = str(report.get("to_sha") or run.to_sha)
        run.doc_count = int(report.get("doc_count") or run.doc_count)
        run.mr_url = str(report.get("mr_url") or run.mr_url)
        if report.get("error"):
            run.error = str(report["error"])[:2000]

        source = db.get(Source, run.source_id) if run.source_id else None
        advanced = False
        disabled = False

        if status == "done" and report.get("last_processed_sha") and source is not None:
            row = db.scalars(select(SourceBranch).where(
                SourceBranch.source_id == source.id,
                SourceBranch.role == (run.branch_role or "dev"))).first()
            if row is not None:
                row.last_processed_sha = str(report["last_processed_sha"])
                advanced = True

        if status == "failed" and source is not None:
            error_kind = str(report.get("error_kind") or "")
            if error_kind == "not_found":
                # 좀비 소스: 레포/브랜치 소실 — 자동 비활성화 (decision-branch-loss-policy)
                source.enabled = False
                source.disabled_reason = f"compare 404: {str(report.get('error') or '')[:200]}"
                disabled = True
                self.notifier.source_disabled(source_label=source.label,
                                              reason=source.disabled_reason)
            elif error_kind == "auth":
                self.notifier.auth_revoked(where=f"source {source.label}",
                                           detail=str(report.get("error") or ""))
            elif error_kind == "rate_limited":
                # SCM API rate limit — 토큰은 정상이다. 담당자 알림만 보내고 auth 알림/
                # 자동 비활성화는 하지 않는다 (decision-scm-rate-limit-not-auth).
                self.notifier.run_failed(source_label=source.label, run_id=run_id,
                                         error=str(report.get("error") or ""),
                                         owner_email=source.owner_email)
            else:
                self.notifier.run_failed(source_label=source.label, run_id=run_id,
                                         error=str(report.get("error") or ""),
                                         owner_email=source.owner_email)
        db.flush()
        self._publish({"type": "run_status", "run_id": run_id, "status": status,
                       "sha_advanced": advanced, "source_disabled": disabled,
                       "mr_url": run.mr_url})
        self._publish({"type": "runs_changed", "run_id": run_id})
        if disabled:
            self._publish({"type": "sources_changed"})
        return {"ok": True, "status": status, "sha_advanced": advanced,
                "source_disabled": disabled}

    # ── 보존 정책 — 오래된 이벤트 정리 (이력 runs/보고는 영구 보존) ──
    def prune_events(self, db: Session, *, older_than_days: int) -> int:
        """run_events만 정리한다. runs·완료 보고(sha·MR URL)는 감사용으로 영구 보존
        (decision-db-source-of-truth: 비활성화 후에도 삭제 안 함)."""
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        # SQLite 가 naive datetime 을 돌려주는 경우 대비 — Run.updated_at 을 UTC 로
        # 정규화한 컬럼을 비교에 사용. SQLAlchemy 의 func.timezone() 으로 비교가
        # 가능하지만 portable 하지 않으므로 Python 측 필터.
        all_done_failed = db.scalars(
            select(Run).where(Run.status.in_(["done", "failed"]))).all()
        old_run_ids = [r.id for r in all_done_failed
                       if as_utc(r.updated_at) and as_utc(r.updated_at) < cutoff]
        if not old_run_ids:
            return 0
        from sqlalchemy import delete
        result = db.execute(delete(RunEvent).where(RunEvent.run_id.in_(old_run_ids)))
        db.flush()
        deleted = int(result.rowcount or 0)
        if deleted:
            log.info("이벤트 보존 정책: %d일 경과 run %d건의 이벤트 %d행 정리",
                     older_than_days, len(old_run_ids), deleted)
        return deleted

    # ── 조회 ────────────────────────────────────────────────
    def list_runs(self, db: Session, limit: int = 100,
                  source_id: str | None = None) -> list[dict]:
        stmt = select(Run).order_by(Run.created_at.desc()).limit(limit)
        if source_id:
            stmt = stmt.where(Run.source_id == source_id)
        rows = db.scalars(stmt).all()
        return [{
            "run_id": r.id, "source_id": r.source_id, "pipeline_id": r.pipeline_id,
            "mode": r.mode, "branch_role": r.branch_role, "trigger": r.trigger,
            "status": r.status, "from_sha": r.from_sha, "to_sha": r.to_sha,
            "doc_count": r.doc_count, "mr_url": r.mr_url, "error": r.error,
            "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
            "created_at": isoformat_z(r.created_at),
            "updated_at": isoformat_z(r.updated_at),
        } for r in rows]

    def list_model_usage(self, db: Session, limit: int = 1000) -> list[dict]:
        rows = db.scalars(
            select(RunModelUsage).order_by(RunModelUsage.updated_at.desc()).limit(limit)
        ).all()
        return [{
            "run_id": r.run_id,
            "source_id": r.source_id,
            "pipeline_id": r.pipeline_id,
            "provider": r.provider,
            "model": r.model,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "calls": r.calls,
            "updated_at": isoformat_z(r.updated_at),
        } for r in rows]

    # ── 파이프라인 상태 집계 (Track F) ──────────────────────────
    def pipeline_status(self, db: Session, window_hours: int = 24) -> list[dict]:
        """각 (source × pipeline_id) 쌍의 최근 상태 + window 집계를 반환한다.

        프런트 파이프라인 페이지가 useDbRunsQuery + 수동 집계하던 것을 서버가
        단일 호출로 제공한다. 각 항목:
        - last_run_id, last_status, last_run_at, last_error, last_mr_url, last_doc_count
        - success_{w}h, failed_{w}h, running, total_tokens_{w}h, mean_duration_sec
        - enabled_schedule, schedule_cron, next_scheduled_at (scheduler 가 채움)
        """
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=window_hours)
        rows = db.scalars(select(Run).order_by(Run.created_at.desc())).all()

        # 활성 스케줄 (per source × pipeline) — 있으면 enabled=true, cron 기록
        from ..models import SourceSchedule
        schedules = {}
        for sched in db.scalars(select(SourceSchedule).where(SourceSchedule.enabled.is_(True))).all():
            key = (sched.source_id, sched.pipeline_id)
            schedules[key] = {
                "schedule_id": sched.id,
                "schedule_label": sched.label,
                "schedule_cron": sched.cron,
                "schedule_branch_role": sched.branch_role,
            }

        # group by (source_id, pipeline_id)
        grouped: dict[tuple, dict] = {}
        for r in rows:
            key = (r.source_id or "", r.pipeline_id or "static")
            bucket = grouped.setdefault(key, {
                "source_id": key[0], "pipeline_id": key[1],
                "last_run_id": "", "last_status": "", "last_run_at": "",
                "last_error": "", "last_error_kind": "",
                "last_mr_url": "", "last_doc_count": 0,
                "last_branch_role": "", "last_trigger": "",
                "success_window": 0, "failed_window": 0, "running": 0,
                "total_tokens_window": 0, "mean_duration_sec": None,
                "_done_durations": [],
            })
            # 첫 번째(가장 최근) row 로 last_* 채운다 — rows 가 desc 정렬이라 그대로.
            if not bucket["last_run_id"]:
                bucket["last_run_id"] = r.id
                bucket["last_status"] = r.status
                bucket["last_run_at"] = isoformat_z(r.created_at)
                bucket["last_error"] = r.error
                bucket["last_mr_url"] = r.mr_url
                bucket["last_doc_count"] = int(r.doc_count or 0)
                bucket["last_branch_role"] = r.branch_role
                bucket["last_trigger"] = r.trigger
                # error_kind 는 complete_run 시점에 분류되지 row 에 저장 안 됨 —
                # error 문자열에서 heuristically 복원 (ScmNotFoundError/ScmAuthError ...)
                err = (r.error or "").lower()
                if "notfound" in err or "404" in err:
                    bucket["last_error_kind"] = "not_found"
                elif "ratauth" in err.replace("_", "") or " 401" in err or "scmauth" in err:
                    bucket["last_error_kind"] = "auth"
                elif "rate" in err or "429" in err:
                    bucket["last_error_kind"] = "rate_limited"
            # window 내 집계 (생성시간 기준) — SQLite 가 naive datetime 을 돌려주는
            # 경우 대비해 tz-aware UTC 로 정규화 후 비교.
            created = as_utc(r.created_at)
            if created and created >= window_start:
                if r.status == "done":
                    bucket["success_window"] += 1
                    if r.updated_at and r.created_at:
                        upd = as_utc(r.updated_at)
                        bucket["_done_durations"].append(
                            (upd - created).total_seconds())
                elif r.status == "failed":
                    bucket["failed_window"] += 1
                elif r.status == "running":
                    bucket["running"] += 1
                bucket["total_tokens_window"] += (
                    int(r.input_tokens or 0) + int(r.output_tokens or 0))

        out: list[dict] = []
        for (source_id, pipeline_id), bucket in grouped.items():
            durations = bucket.pop("_done_durations", [])
            bucket["mean_duration_sec"] = (
                round(sum(durations) / len(durations), 1) if durations else None)
            sched = schedules.get((source_id, pipeline_id), {})
            bucket.update(sched)
            bucket["enabled_schedule"] = bool(sched)
            out.append(bucket)
        # source_id, pipeline_id 순으로 정렬 — 프런트가 그룹핑하기 쉽게
        out.sort(key=lambda x: (x["source_id"], x["pipeline_id"]))
        return out
