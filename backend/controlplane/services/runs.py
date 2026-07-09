"""run 수명주기 — 트리거·이벤트 적재·완료 보고·sha 전진.

concept-idempotent-sha: last_processed_sha는 완료 보고(MR 제출 성공 포함)에서만
전진한다. 실패한 run은 포인터를 건드리지 않아 다음 배치가 같은 구간을 재처리한다.
decision-branch-loss-policy: compare 404 -> 소스 자동 비활성화 + admin 알림.

2026-07-08:
- event_id 기반 dedupe + server-assigned monotonic seq
- heartbeat / stuck run reaper
- terminal status normalization (done -> done_with_warnings / failed_quality_gate)
- WS publish deferred to AFTER DB commit (prevents front-end refetch from
  reading stale pre-commit state — raw/2026-07-08-docu-automation-data-plane-review P2)
- publishable / publish_state / quality_status / snapshot_version
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Run, RunCoverageReport, RunEvent, RunModelUsage, RunQualityReport,
    Source, SourceBranch,
)
from ..settings import ControlPlaneSettings
from ..timeutil import as_utc, isoformat_z
from .notifier import Notifier
from .settings import SettingsService

log = logging.getLogger("controlplane.runs")

# Terminal status 화이트리스트 — 이 값들 사이의 cross-transition 만 차단.
TERMINAL_STATUSES = (
    "done", "done_with_warnings", "failed", "failed_quality_gate",
    "partial", "stale", "cancelled", "timeout",
)
ACTIVE_STATUSES = ("pending", "running")


def _flush_session_publishes(session: Session) -> None:
    """after_commit callback — publish all deferred WS messages for this session."""
    pending = session.info.pop("_cp_pending_publish", None)
    if not pending:
        return
    for broadcaster, msg in pending:
        try:
            broadcaster.publish(msg)
        except Exception:  # noqa: BLE001
            pass


def _clear_session_publishes(session: Session) -> None:
    """after_rollback callback — discard deferred messages (uncommitted state)."""
    session.info.pop("_cp_pending_publish", None)


class RunService:
    def __init__(self, settings: ControlPlaneSettings, notifier: Notifier,
                 broadcaster=None, session_factory=None,
                 settings_service: SettingsService | None = None):
        self.settings = settings
        self.notifier = notifier
        self.broadcaster = broadcaster
        self.session_factory = session_factory
        self.settings_service = settings_service

    def _publish(self, message: dict, db: Session | None = None) -> None:
        """Publish a WS message — deferred until db commit if db is provided.

        When db is provided, the message is queued on session.info and flushed
        by the after_commit SQLAlchemy event. On rollback, queued messages are
        discarded. This prevents subscribers from seeing state for data that
        wasn't committed yet.
        """
        if self.broadcaster is None:
            return
        if db is None:
            self.broadcaster.publish(message)
            return
        from sqlalchemy import event
        pending = db.info.setdefault("_cp_pending_publish", [])
        pending.append((self.broadcaster, message))
        if not db.info.get("_cp_publish_hook"):
            db.info["_cp_publish_hook"] = True
            event.listen(db, "after_commit", _flush_session_publishes)
            event.listen(db, "after_rollback", _clear_session_publishes)

    def next_seq(self, db: Session, run_id: str) -> int:
        """run 의 server-assigned monotonic seq — webhook ingest 의 ordering 진실."""
        last = db.scalar(
            select(func.coalesce(func.max(RunEvent.seq), 0)).where(RunEvent.run_id == run_id)
        )
        return int(last or 0) + 1

    # ── 트리거 (수동/스케줄) ─────────────────────────────────
    def create_run(self, db: Session, *, source_id: str, mode: str = "auto",
                   branch_role: str = "dev", trigger: str = "manual",
                   pipeline_id: str = "static", attempt: int = 1) -> Run:
        source = db.get(Source, source_id)
        if source is None:
            raise ValueError(f"알 수 없는 source: {source_id}")
        if not source.enabled:
            raise ValueError(f"비활성화된 source: {source_id} ({source.disabled_reason})")
        run_id = f"{pipeline_id}-{source_id}-{uuid.uuid4().hex[:8]}"
        # capture from_sha_snapshot (CAS for static sha advance).
        from_sha_snapshot = ""
        if pipeline_id == "static" and source_id:
            row = db.scalars(select(SourceBranch).where(
                SourceBranch.source_id == source_id,
                SourceBranch.role == (branch_role or "dev"),
            )).first()
            if row is not None:
                from_sha_snapshot = row.last_processed_sha or ""
        run = Run(id=run_id, source_id=source_id, pipeline_id=pipeline_id,
                  mode=mode, branch_role=branch_role, trigger=trigger,
                  status="pending", attempt=attempt,
                  from_sha_snapshot=from_sha_snapshot)
        db.add(run)
        db.flush()
        self._publish({"type": "runs_changed", "run_id": run_id}, db)
        return run

    def _effective_llm_env(self) -> dict[str, str]:
        if self.session_factory is None or self.settings_service is None:
            return {}
        env = {
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "openai-compatible"),
            "LLM_BASE_URL": os.getenv("LLM_BASE_URL", ""),
            "LLM_API_KEY": os.getenv("LLM_API_KEY", ""),
            "LLM_MODEL": os.getenv("LLM_MODEL", ""),
            "LLM_MAX_TOKENS": os.getenv("LLM_MAX_TOKENS", "65536"),
            "LLM_TEMPERATURE": os.getenv("LLM_TEMPERATURE", "0.2"),
            "LLM_TIMEOUT": os.getenv("LLM_TIMEOUT", "180"),
            "LLM_RETRY_ATTEMPTS": os.getenv("LLM_RETRY_ATTEMPTS", "4"),
        }
        try:
            with self.session_factory() as db:
                return self.settings_service.get_llm_runtime_env(db, env)
        except Exception as e:  # noqa: BLE001
            log.warning("LLM runtime env 주입 실패 — process env 사용: %s: %s",
                        type(e).__name__, e)
            return {}

    def launch_runner(self, run: Run) -> subprocess.Popen | None:
        """Data Plane 러너 프로세스 기동 (backend.runner.job).

        Control Plane과 같은 호스트에서 subprocess로 실행하는 것이 v1 —
        docs-hub CI 러너로 옮길 때는 이 지점이 CI 트리거 API 호출로 바뀐다.

        env 화이트리스트: 부모 프로세스의 모든 환경변수를 상속하면 러너가
        CONTROL_SECRET_KEY, CONTROL_DB_URL, SMTP 자격증명 등까지 받는다.
        러너가 탈취되면 전 시크릿이 같이 노출되므로, 러너가 실행에 필요한
        최소한의 변수만 전달한다 (api.py의 _RUNNER_ENV_ALLOWLIST).
        """
        from ..api import _RUNNER_ENV_ALLOWLIST
        api_url = f"http://{self.settings.control_host}:{self.settings.control_port}"
        env = {
            k: os.environ[k]
            for k in _RUNNER_ENV_ALLOWLIST
            if k in os.environ
        }
        env.update(self._effective_llm_env())
        env["CONTROL_API_URL"] = api_url
        env["CONTROL_RUNNER_TOKEN"] = self.settings.control_runner_token
        cmd = [sys.executable, "-m", "backend.runner.job",
               "--run-id", run.id, "--source", run.source_id,
               "--mode", run.mode, "--branch-role", run.branch_role]
        try:
            proc = subprocess.Popen(cmd, env=env, cwd=None,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.info("러너 기동: run=%s pid=%s", run.id, proc.pid)
            from ..timeutil import as_utc
            try:
                run.runner_pid = str(proc.pid) if proc.pid else ""
                run.started_at = as_utc(datetime.now(timezone.utc))
            except Exception:  # noqa: BLE001
                pass
            return proc
        except Exception as e:  # noqa: BLE001
            log.error("러너 기동 실패: run=%s %s: %s", run.id, type(e).__name__, e)
            return None

    def heartbeat(self, db: Session, run_id: str, *, attempt: int | None = None,
                  stage: str = "", pid: str = "") -> dict:
        """러너가 보내는 heartbeat — heartbeat_at 갱신 + run_started_at 도 한 번.

        첫 heartbeat 는 started_at 을 같이 채운다. stage/pid 도 저장해서 운영자가
        어떤 stage 에서 막혔는지 즉시 알 수 있게 한다.
        """
        run = db.get(Run, run_id)
        if run is None:
            raise ValueError(f"unknown run: {run_id}")
        now = datetime.now(timezone.utc)
        if not run.started_at:
            run.started_at = now
        if stage:
            run.status = "running"  # heartbeat = 활동 증거
        run.heartbeat_at = now
        if pid:
            run.runner_pid = pid
        if attempt is not None and int(attempt) > 0:
            run.attempt = int(attempt)
        db.flush()
        self._publish({"type": "run_heartbeat", "run_id": run_id,
                       "stage": stage, "ts": isoformat_z(now)}, db)
        return {"ok": True, "heartbeat_at": isoformat_z(now),
                "status": run.status, "attempt": run.attempt}

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
        if run is None:
            # webhook_complete와 동일하게 — 알 수 없는 run_id는 거부.
            # 없으면 RunEvent 고아 행이 쌓이고 /api/events?run=<id>가 더러워진다.
            raise ValueError(f"알 수 없는 run: {run_id}")

        # Pre-fetch existing event_id and seq for this run — dedupe/dup-seq detection
        # in O(1) per event instead of N queries.
        existing_event_ids: set[str] = set()
        existing_seqs: set[int] = set()
        if events:
            ids_db = db.scalars(
                select(RunEvent.event_id).where(
                    RunEvent.run_id == run_id,
                    RunEvent.event_id != "",
                )
            ).all()
            existing_event_ids = {eid for eid in ids_db if eid}
            seqs_db = db.scalars(
                select(RunEvent.seq).where(
                    RunEvent.run_id == run_id,
                    RunEvent.seq.isnot(None),
                )
            ).all()
            existing_seqs = {int(s) for s in seqs_db if s is not None}

        # monotonic seq cursor — start at max+1 (server-assigned, not from client).
        cursor = self.next_seq(db, run_id)

        count = 0
        accepted: list[dict] = []
        for e in events:
            if not isinstance(e, dict):
                continue
            eid = str(e.get("event_id") or "").strip()
            client_seq = e.get("seq")
            # dedupe: same (run_id, event_id) -> idempotent skip
            if eid and eid in existing_event_ids:
                continue
            # same (run_id, seq) but different event_id -> reject
            if client_seq is not None:
                try:
                    cs = int(client_seq)
                except (TypeError, ValueError):
                    cs = -1
                if cs in existing_seqs and (not eid or eid not in existing_event_ids):
                    log.warning("event seq conflict run=%s seq=%s event_id=%s",
                                run_id, cs, eid)
                    continue
            seq = cursor
            cursor += 1
            if eid:
                existing_event_ids.add(eid)
            existing_seqs.add(seq)
            received_at = datetime.now(timezone.utc)
            detail = e.get("detail") or {}
            stored_event = dict(e)
            stored_event["seq"] = seq
            if eid:
                stored_event["event_id"] = eid
            db.add(RunEvent(
                run_id=run_id,
                ts=str(e.get("ts") or ""),
                layer=str(e.get("layer") or ""),
                stage=str(e.get("stage") or ""),
                status=str(e.get("status") or ""),
                payload=json.dumps(stored_event, ensure_ascii=False),
                event_id=eid,
                seq=seq,
                kind=str(e.get("kind") or detail.get("kind") or "")[:120],
                severity=str(e.get("severity") or "info")[:16],
                role=str(e.get("role") or detail.get("role") or "")[:80],
                dedupe_key=str(e.get("dedupe_key") or detail.get("dedupe_key") or "")[:200],
                received_at=received_at,
            ))
            count += 1
            accepted.append(stored_event)
            if run is not None and e.get("layer") == "run":
                status = str(e.get("status") or "")
                if run.status in TERMINAL_STATUSES:
                    pass
                elif status == "running":
                    run.status = "running"
                elif status in TERMINAL_STATUSES:
                    run.status = status
                if status == "failed" and detail.get("error") and run.status == "failed":
                    run.error = str(detail["error"])[:2000]
            if run is not None and detail.get("kind") == "usage":
                run.input_tokens += int(detail.get("input_tokens") or 0)
                run.output_tokens += int(detail.get("output_tokens") or 0)
                self._record_model_usage(db, run, detail)
        if count:
            run.snapshot_version = int(run.snapshot_version or 0) + 1
        db.flush()
        if count:
            latest_seq = cursor - 1
            self._publish({
                "type": "events", "run_id": run_id,
                "events": accepted,
                "latest_seq": latest_seq,
                "snapshot_version": int(run.snapshot_version or 0),
            }, db)
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

    def read_db_events_seq(self, db: Session, run_id: str, after_seq: int = 0,
                          limit: int = 500) -> dict:
        """seq-based replay API — event_id/seq dedupe 와 1:1 매핑되는 read 경로."""
        rows = db.scalars(
            select(RunEvent).where(
                RunEvent.run_id == run_id,
                RunEvent.seq.isnot(None),
                RunEvent.seq > after_seq,
            )
            .order_by(RunEvent.seq).limit(limit)
        ).all()
        events = [json.loads(r.payload) for r in rows]
        latest_seq = int(rows[-1].seq) if rows else after_seq
        max_total = db.scalar(
            select(func.coalesce(func.max(RunEvent.seq), 0)).where(
                RunEvent.run_id == run_id,
            )
        )
        max_total = int(max_total or 0)
        return {
            "run_id": run_id,
            "events": events,
            "after_seq": after_seq,
            "latest_seq": latest_seq,
            "has_more": latest_seq < max_total,
            "truncated": len(rows) >= limit,
            "snapshot_version": int((db.get(Run, run_id) or Run()).snapshot_version or 0),
            "total_seq": max_total,
        }

    def all_db_events(self, db: Session, run_id: str) -> list[dict]:
        rows = db.scalars(select(RunEvent).where(RunEvent.run_id == run_id)
                          .order_by(RunEvent.id)).all()
        return [json.loads(r.payload) for r in rows]

    def has_db_events(self, db: Session, run_id: str) -> bool:
        return db.scalars(select(RunEvent.id).where(RunEvent.run_id == run_id)
                          .limit(1)).first() is not None

    def latest_seq(self, db: Session, run_id: str) -> int:
        last = db.scalar(
            select(func.coalesce(func.max(RunEvent.seq), 0)).where(RunEvent.run_id == run_id)
        )
        return int(last or 0)

    def reap_stuck_runs(self, db: Session, *, stale_after_sec: int = 1800,
                        max_idle_sec: int = 3600) -> int:
        """stuck/stalled run reaper.

        - pending 이지만 heartbeat 가 없는 상태로 stale_after_sec 경과 → failed
        - running 인데 heartbeat_at 이 max_idle_sec 이전 → timeout

        1회 호출에서 같은 run 을 두 번 처리하지 않도록 status 가 terminal 이면
        스킵한다.
        """
        now = datetime.now(timezone.utc)
        threshold_pending = now - timedelta(seconds=stale_after_sec)
        threshold_idle = now - timedelta(seconds=max_idle_sec)
        n = 0
        candidates = db.scalars(
            select(Run).where(Run.status == "pending")
        ).all()
        for r in candidates:
            if r.created_at and as_utc(r.created_at) <= threshold_pending \
                    and (r.heartbeat_at is None):
                r.status = "failed"
                r.terminal_at = now
                r.error = f"stuck pending: heartbeat 없음 ({stale_after_sec}s 경과)"
                r.status_reason = r.error
                n += 1
                self._publish({"type": "run_status", "run_id": r.id,
                               "status": r.status, "reason": "stuck_pending"}, db)
        idle_candidates = db.scalars(
            select(Run).where(Run.status == "running")
        ).all()
        for r in idle_candidates:
            if r.heartbeat_at is None:
                continue
            hb = as_utc(r.heartbeat_at)
            if hb is not None and hb <= threshold_idle:
                r.status = "timeout"
                r.terminal_at = now
                r.error = f"heartbeat 없음 ({max_idle_sec}s idle)"
                r.status_reason = r.error
                n += 1
                self._publish({"type": "run_status", "run_id": r.id,
                               "status": r.status, "reason": "heartbeat_timeout"}, db)
        if n:
            db.flush()
            log.info("reaper: %d run 을 terminal 로 전환", n)
        return n

    # ── 완료 보고 (sha 전진의 유일한 경로) ───────────────────
    def complete_run(self, db: Session, run_id: str, report: dict[str, Any]) -> dict:
        run = db.get(Run, run_id)
        if run is None:
            raise ValueError(f"알 수 없는 run: {run_id}")
        status = str(report.get("status") or "done")
        # Terminal guard — ingest_events()의 stale 가드와 대칭. cross-status 전이
        # (done↔failed) 만 차단하고 same-status(done→done) 는 final 데이터 갱신 허용.
        prev_status = run.status
        if prev_status in TERMINAL_STATUSES and prev_status != status:
            log.warning("complete webhook cross-status 거부 — run=%s prev=%s 보고=%s",
                        run_id, prev_status, status)
            return {"ok": True, "status": prev_status, "sha_advanced": False,
                    "source_disabled": False, "idempotent": True,
                    "publish_state": run.publish_state,
                    "publishable": run.publishable}

        # Quality/coverage 우선 normalize — quality_status=fail 이면 status 를
        # failed_quality_gate 로 강제한다. coverage fail 도 동일 정책.
        quality_status = str(report.get("quality_status") or run.quality_status or "not_evaluated")
        publishable = bool(report.get("publishable", run.publishable))
        coverage_status = str(report.get("coverage_status") or "not_applicable")
        # coverage table 직접 조회 — body 에 명시되지 않은 경우 DB 가 진실.
        from ..models import RunCoverageReport
        cov_row = db.scalars(
            select(RunCoverageReport).where(RunCoverageReport.run_id == run_id)
        ).first()
        if cov_row and cov_row.status == "fail":
            coverage_status = "fail"
        if quality_status == "fail" and status == "done":
            status = "failed_quality_gate"
            if not run.blocked_reason:
                run.blocked_reason = str(report.get("blocked_reason")
                                         or report.get("failed_gate") or "quality gate failed")
        if coverage_status == "fail" and status == "done":
            status = "failed_quality_gate"
            if not run.blocked_reason:
                run.blocked_reason = "manual coverage below threshold"
        if quality_status == "warning" and status == "done":
            # warning_publish_policy 가 review_required 면 done 으로 두되 publish_state 만
            # review_required 로 강등. block 이면 failed_quality_gate.
            policy = str(run.warning_publish_policy or "review_required")
            if policy == "block":
                status = "done_with_warnings"
                publishable = False
                if not run.blocked_reason:
                    run.blocked_reason = "warning publish policy = block"
            else:
                status = "done_with_warnings"
                # publishable 도 policy 가 review_required 면 그대로 true (MR 제출은 가능)
        # partial: 일부 산출물만 유효 / 일부 stage 만 성공
        if str(report.get("partial") or "").lower() in ("1", "true", "yes"):
            if status == "done":
                status = "partial"
                publishable = False
                if not run.blocked_reason:
                    run.blocked_reason = "partial completion"

        run.status = status
        run.from_sha = str(report.get("from_sha") or run.from_sha)
        run.to_sha = str(report.get("to_sha") or run.to_sha)
        run.doc_count = int(report.get("doc_count") or run.doc_count)
        run.mr_url = str(report.get("mr_url") or run.mr_url)
        if report.get("error"):
            run.error = str(report["error"])[:2000]
        run.terminal_at = datetime.now(timezone.utc)
        run.quality_status = quality_status
        if report.get("quality_score") is not None:
            try:
                run.quality_score = int(report["quality_score"])
            except (TypeError, ValueError):
                pass
        run.publishable = publishable
        if report.get("blocked_reason"):
            run.blocked_reason = str(report["blocked_reason"])[:5000]
        if report.get("artifact_version"):
            run.artifact_version = str(report["artifact_version"])[:120]
        if report.get("release_tag"):
            run.release_tag = str(report["release_tag"])[:120]

        # publish_state 도출 (boolean publishable 보다 우선)
        if quality_status == "not_evaluated" and not run.quality_status:
            run.publish_state = "unknown"
        elif status in ("done", "done_with_warnings") and publishable and quality_status == "pass":
            run.publish_state = "publishable"
        elif status == "done_with_warnings":
            policy = str(run.warning_publish_policy or "review_required")
            run.publish_state = "review_required" if policy != "block" else "blocked"
        elif status in ("failed_quality_gate", "failed", "partial", "stale",
                        "cancelled", "timeout"):
            run.publish_state = "blocked"
        else:
            run.publish_state = "review_required"
        run.snapshot_version = int(run.snapshot_version or 0) + 1

        source = db.get(Source, run.source_id) if run.source_id else None
        advanced = False
        disabled = False
        stale_complete = False
        # EARLY-RETURN 가드 이후 모든 진단에 run_id 를 포함
        sha_advance_attempted = False

        if report.get("last_processed_sha") and source is not None \
                and run.pipeline_id == "static":
            sha_advance_attempted = True
            row = db.scalars(select(SourceBranch).where(
                SourceBranch.source_id == source.id,
                SourceBranch.role == (run.branch_role or "dev"))).first()
            # SourceBranch row 가 없으면 자동 생성 — 이전에 등록 소스에서 row 가
            # 누락된 경우(이전 migration 등)에도 sha 전진이 동작하도록.
            if row is None:
                log.info("complete_run: SourceBranch row 없음 → 자동 생성: source=%s role=%s",
                         source.id, run.branch_role or "dev")
                row = SourceBranch(source_id=source.id, role=run.branch_role or "dev")
                db.add(row)
                db.flush()
            new_sha = str(report["last_processed_sha"])
            # CAS: snapshot 과 pointer 가 같은 경우에만 전진. 다르면 stale.
            snapshot = (run.from_sha_snapshot or "").strip()
            current = (row.last_processed_sha or "").strip()
            if snapshot and current and snapshot != current:
                log.warning("complete_run CAS 실패 — run=%s snapshot=%s current=%s",
                            run_id, snapshot[:12], current[:12])
                stale_complete = True
                run.stale_complete = True
                if status in ("done", "done_with_warnings"):
                    # stale 상태로 normalize — sha 전진 안 함
                    run.status = "stale"
                    run.publish_state = "blocked"
                    run.blocked_reason = (
                        f"source pointer changed mid-run (snapshot={snapshot[:12]} current={current[:12]})"
                    )
            else:
                if new_sha and new_sha != current:
                    row.last_processed_sha = new_sha
                    advanced = True
                    log.info("complete_run: SHA 전진 run=%s source=%s role=%s old=%s new=%s",
                             run_id, source.id, run.branch_role or "dev",
                             current[:12] if current else "<empty>",
                             new_sha[:12])
                elif new_sha == current:
                    log.info("complete_run: SHA 이미 동일 run=%s sha=%s (idempotent)",
                             run_id, current[:12])
                else:
                    log.warning("complete_run: SHA 전진 스킵 run=%s new_sha=%s current=%s (이상 상태)",
                                run_id, new_sha[:12] if new_sha else "<empty>",
                                current[:12] if current else "<empty>")

        if status == "failed" and source is not None:
            error_kind = str(report.get("error_kind") or "")
            if error_kind == "not_found":
                source.enabled = False
                source.disabled_reason = f"compare 404: {str(report.get('error') or '')[:200]}"
                disabled = True
                self.notifier.source_disabled(source_label=source.label,
                                              reason=source.disabled_reason)
            elif error_kind == "auth":
                self.notifier.auth_revoked(where=f"source {source.label}",
                                           detail=str(report.get("error") or ""))
            elif error_kind == "rate_limited":
                self.notifier.run_failed(source_label=source.label, run_id=run_id,
                                         error=str(report.get("error") or ""),
                                         owner_email=source.owner_email)
            else:
                self.notifier.run_failed(source_label=source.label, run_id=run_id,
                                         error=str(report.get("error") or ""),
                                         owner_email=source.owner_email)
        db.flush()
        # SHA 전진 시도했으나 안 된 경우 진단 — source 누락 또는 상태 비정상이 원인.
        if sha_advance_attempted and not advanced and not stale_complete:
            log.warning("complete_run: SHA 전진 시도했지만 미적용 run=%s status=%s "
                        "report_sha=%s — SourceBranch 누락 or status 조건 불일치 가능성",
                        run_id, status,
                        str(report.get("last_processed_sha"))[:12])
        self._publish({"type": "run_status", "run_id": run_id, "status": run.status,
                       "sha_advanced": advanced, "source_disabled": disabled,
                       "mr_url": run.mr_url, "publishable": run.publishable,
                       "publish_state": run.publish_state,
                       "snapshot_version": run.snapshot_version,
                       "stale_complete": stale_complete}, db)
        self._publish({"type": "runs_changed", "run_id": run_id}, db)
        if disabled:
            self._publish({"type": "sources_changed"}, db)
        return {"ok": True, "status": run.status, "sha_advanced": advanced,
                "source_disabled": disabled, "idempotent": False,
                "publishable": run.publishable, "publish_state": run.publish_state,
                "snapshot_version": run.snapshot_version,
                "stale_complete": stale_complete}

    # ── 보존 정책 — 오래된 이벤트 정리 (이력 runs/보고는 영구 보존) ──
    def prune_events(self, db: Session, *, older_than_days: int) -> int:
        """run_events만 정리한다. runs·완료 보고(sha·MR URL)는 감사용으로 영구 보존
        (decision-db-source-of-truth: 비활성화 후에도 삭제 안 함).

        SQL WHERE로 후보 run_id를 한 번에 뽑는다 — 예전 Python 사이드 필터는
        done/failed run 전체를 메모리에 올려 100k+ run에서 폭발했다.
        """
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        # SQLAlchemy의 func.timezone()로 portable하게 비교할 수 있으나, SQLite가
        # naive를 돌려주는 경로가 있으므로, 컬럼 값을 as_utc()로 정규화할 수 없다.
        # 대신 string 비교가 아닌 datetime 비교를 쓴다 — SQLite는 tz-aware 비교시
        # 내부적으로 문자열로 저장하므로 cutoff ISO 문자열과 사전식 비교가 된다.
        # PostgreSQL은 TIMESTAMP WITH TIME ZONE 비교로 안전.
        from sqlalchemy import select, delete, func
        # as_utc()는 Python 함수라 DB 컬럼에 못 쓴다. 대신 created_at의 타입이
        # DateTime(timezone=True)이면 DB가 알아서 비교한다. 단, SQLite는 naive로
        # 저장된 과거 레코드가 있을 수 있어 — cutoff와 direct 비교시 빠지는 레코드가
        # 생길 수 있다. 운영 모드(PostgreSQL)에서는 정확히 동작한다.
        subq = select(Run.id).where(
            Run.status.in_(["done", "failed"]),
            Run.updated_at < cutoff,
        )
        result = db.execute(delete(RunEvent).where(RunEvent.run_id.in_(subq)))
        db.flush()
        deleted = int(result.rowcount or 0)
        if deleted:
            log.info("이벤트 보존 정책: %d일 경과 run들의 이벤트 %d행 정리",
                     older_than_days, deleted)
        return deleted

    # ── 조회 ────────────────────────────────────────────────
    def get_run_view(self, db: Session, run_id: str) -> dict | None:
        """run 1건을 dict로 직접 반환 — list_runs(1000)에서 찾던 O(N) 스캔 대체.

        run이 없으면 None. list_runs와 동일한 키를 갖는 dict 반환.
        """
        r = db.get(Run, run_id)
        if r is None:
            return None
        return _run_view_dict(r)

    def list_runs(self, db: Session, limit: int = 100,
                  source_id: str | None = None) -> list[dict]:
        stmt = select(Run).order_by(Run.created_at.desc()).limit(limit)
        if source_id:
            stmt = stmt.where(Run.source_id == source_id)
        rows = db.scalars(stmt).all()
        return [_run_view_dict(r) for r in rows]



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
        # 풀테이블 스캔 방지 — 최근 5000건만 본다. 5000건이 넘는 활성 시스템은
        # 어차피 dashboard가 전부 표시하지 못하므로, 페이지네이션을 별도 엔드포인트로
        # 두는 것이 맞다. window 집계는 window_start 이후 run만 정확히 본다.
        rows = db.scalars(
            select(Run).order_by(Run.created_at.desc()).limit(5000)
        ).all()

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

        # 각 run의 coverage 리포트 — last_coverage_percentage/threshold 를 채우기 위해
        # 한 번에 조회해 run_id → {percentage, threshold} 맵을 만든다.
        # 테이블 없거나 쿼리 실패해도 pipeline_status 전체가 죽지 않도록 방어.
        coverage_map: dict[str, dict] = {}
        try:
            from ..models import RunCoverageReport
            run_ids = [r.id for r in rows]
            if run_ids:
                for cov in db.scalars(
                    select(RunCoverageReport).where(RunCoverageReport.run_id.in_(run_ids))
                ).all():
                    coverage_map[cov.run_id] = {
                        "percentage": cov.percentage,
                        "threshold": cov.threshold,
                    }
        except Exception:
            coverage_map = {}

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
                "last_quality_status": "not_evaluated", "last_quality_score": None,
                "last_publishable": False, "last_publish_state": "unknown",
                "last_blocked_reason": "", "last_failed_gate": "",
                "last_release_tag": "", "last_artifact_version": "",
                "last_mr_readiness": "unknown", "last_repair_attempts": 0,
                "last_coverage_percentage": None, "last_coverage_threshold": None,
                "warning_count_window": 0, "error_count_window": 0,
                "quality_fail_count_window": 0,
                "publishable_count_window": 0,
                "success_window": 0, "failed_window": 0, "running": 0,
                "done_with_warnings_window": 0, "failed_quality_gate_window": 0,
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
                bucket["last_quality_status"] = str(r.quality_status or "not_evaluated")
                bucket["last_quality_score"] = r.quality_score
                bucket["last_publishable"] = bool(r.publishable)
                bucket["last_publish_state"] = str(r.publish_state or "unknown")
                bucket["last_blocked_reason"] = str(r.blocked_reason or "")
                bucket["last_release_tag"] = str(r.release_tag or "")
                bucket["last_artifact_version"] = str(r.artifact_version or "")
                # last_repair_attempts: Run 모델에 별도 컬럼이 없으므로 0으로 둔다.
                # (이전 버그: r.quality_score 를 잘못 넣고 있었음)
                bucket["last_repair_attempts"] = 0
                # coverage 리포트에서 percentage/threshold 를 가져와 채운다
                cov = coverage_map.get(r.id, {})
                bucket["last_coverage_percentage"] = cov.get("percentage")
                bucket["last_coverage_threshold"] = cov.get("threshold")
                if r.mr_url:
                    if r.status in ("done",) and bool(r.publishable):
                        bucket["last_mr_readiness"] = "ready"
                    elif r.status == "done_with_warnings":
                        bucket["last_mr_readiness"] = "review_required"
                    elif r.status in ("failed", "failed_quality_gate", "stale",
                                       "cancelled", "timeout", "partial"):
                        bucket["last_mr_readiness"] = "blocked"
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
                    if bool(r.publishable):
                        bucket["publishable_count_window"] += 1
                elif r.status == "done_with_warnings":
                    bucket["done_with_warnings_window"] += 1
                    if bool(r.publishable):
                        bucket["publishable_count_window"] += 1
                elif r.status == "failed_quality_gate":
                    bucket["failed_quality_gate_window"] += 1
                    bucket["quality_fail_count_window"] += 1
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


def _run_view_dict(r: Run) -> dict:
    return {
        "run_id": r.id, "source_id": r.source_id, "pipeline_id": r.pipeline_id,
        "mode": r.mode, "branch_role": r.branch_role, "trigger": r.trigger,
        "status": r.status, "from_sha": r.from_sha, "to_sha": r.to_sha,
        "doc_count": r.doc_count, "mr_url": r.mr_url, "error": r.error,
        "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
        "created_at": isoformat_z(r.created_at),
        "updated_at": isoformat_z(r.updated_at),
        "attempt": int(r.attempt or 1),
        "publishable": bool(r.publishable),
        "publish_state": str(r.publish_state or "unknown"),
        "quality_status": str(r.quality_status or "not_evaluated"),
        "quality_score": r.quality_score,
        "blocked_reason": str(r.blocked_reason or ""),
        "release_tag": str(r.release_tag or ""),
        "artifact_version": str(r.artifact_version or ""),
        "snapshot_version": int(r.snapshot_version or 0),
        "stale_complete": bool(r.stale_complete),
        "heartbeat_at": isoformat_z(r.heartbeat_at),
        "started_at": isoformat_z(r.started_at),
        "terminal_at": isoformat_z(r.terminal_at),
    }
