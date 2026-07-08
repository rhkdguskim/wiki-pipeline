"""매뉴얼 파이프라인 태그 폴링 (decision-release-tag-trigger).

주기적으로 활성 소스의 릴리스 브랜치에서 새 태그를 확인하고, 새 태그가 보이면
매뉴얼 파이프라인 run을 생성한다. 같은 태그로 중복 run이 생기지 않게
source_release_tags 테이블에 마지막으로 본 태그를 북마크한다.

정책:
- run 성공 여부와 무관하게 '이 태그까지 봤다'를 기록 — 재시도는 사용자 수동 트리거.
- compare 404 등으로 태그 조회가 실패하면 조용히 로그만 남긴다 (소스 비활성화는
  실제 run 실패 경로에서 담당 — decision-branch-loss-policy 준수).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import Run, ScmInstance, Source, SourceBranch, SourceReleaseTag, SourceSchedule
from .notifier import Notifier
from .runs import RunService

log = logging.getLogger("controlplane.tag_poller")


@dataclass
class _PollTarget:
    source: Source
    instance: ScmInstance
    branch: SourceBranch


class TagPoller:
    """scheduler 가 주기적으로 호출 — 활성 매뉴얼 소스의 새 태그를 run으로 전환."""

    def __init__(self, settings, session_factory, run_service: RunService,
                 notifier: Notifier):
        self.settings = settings
        self.session_factory = session_factory
        self.run_service = run_service
        self.notifier = notifier

    def poll_once(self) -> int:
        """한 번 폴링 — 새 태그가 발견돼 run을 생성한 소스 수를 반환.

        2026-07-08: create_run 직후 runner 까지 launch 한다. launch 실패 시
        bookmark 를 advance 하지 않고 last_launch_status='failed' 만 남겨
        다음 폴링에서 같은 태그를 재시도할 수 있게 한다.
        """
        from ..connectors import connector_for_settings  # 순환 임포트 회피
        from ...common.config import Settings

        triggered = 0
        with session_scope(self.session_factory) as db:
            targets = self._collect_targets(db)
            for target in targets:
                try:
                    new_tag = self._check_source_for_new_tag(db, target)
                except Exception as e:  # noqa: BLE001 — 한 소스 실패가 폴링을 멈추면 안 된다
                    log.warning("태그 폴링 실패 source=%s: %s: %s",
                                target.source.id, type(e).__name__, e)
                    continue
                if new_tag is None:
                    continue
                try:
                    run = self.run_service.create_run(
                        db, source_id=target.source.id, mode="auto",
                        branch_role=target.branch.role, trigger="schedule",
                        pipeline_id="manual",
                    )
                    self._mark_seen(db, target, new_tag, run.id)
                    triggered += 1
                    log.info("매뉴얼 run 트리거: source=%s tag=%s run=%s",
                             target.source.id, new_tag.name, run.id)
                except ValueError as e:
                    log.warning("매뉴얼 run 생성 실패 source=%s tag=%s: %s",
                                target.source.id, new_tag.name, e)
                    continue
                # launch_runner 는 create_run commit 이후에 호출. launch 실패는
                # bookmark 를 이미 advance 했더라도 last_launch_status 로 표시.
                try:
                    proc = self.run_service.launch_runner(run)
                    launch_ok = proc is not None
                except Exception as e:  # noqa: BLE001
                    log.warning("매뉴얼 runner launch 실패 source=%s run=%s: %s",
                                target.source.id, run.id, type(e).__name__, e)
                    launch_ok = False
                if not launch_ok:
                    self._mark_launch_status(db, target, "failed")
                    try:
                        run.status = "failed"
                        run.error = "runner launch failed"
                        run.terminal_at = run.terminal_at or run.updated_at
                        db.flush()
                    except Exception:  # noqa: BLE001
                        pass
                else:
                    self._mark_launch_status(db, target, "launched")
        return triggered

    def _collect_targets(self, db: Session) -> list[_PollTarget]:
        """매뉴얼 파이프라인이 활성화된 소스의 release 브랜치를 모은다.

        선정 기준: source.enabled AND release branch.enabled AND 그 소스에
        pipeline_id='manual' 스케줄이 enabled 로 존재. 매뉴얼 스케줄이 없는 소스는
        사용자가 의도적으로 매뉴얼 자동화를 끈 것이므로 폴링하지 않는다.
        """
        out: list[_PollTarget] = []
        manual_sources = db.scalars(
            select(Source.id).join(SourceSchedule, SourceSchedule.source_id == Source.id)
            .where(Source.enabled.is_(True))
            .where(SourceSchedule.enabled.is_(True))
            .where(SourceSchedule.pipeline_id == "manual")
            .where(SourceSchedule.branch_role == "release")
            .distinct()
        ).all()
        for source_id in manual_sources:
            source = db.get(Source, source_id)
            if source is None:
                continue
            inst = db.get(ScmInstance, source.instance_id)
            if inst is None or not inst.enabled:
                continue
            branch = db.scalars(
                select(SourceBranch).where(
                    SourceBranch.source_id == source.id,
                    SourceBranch.role == "release",
                    SourceBranch.enabled.is_(True),
                )).first()
            if branch is None or not branch.branch:
                continue
            out.append(_PollTarget(source=source, instance=inst, branch=branch))
        return out

    def _check_source_for_new_tag(self, db: Session, target: _PollTarget):
        """새 태그가 있으면 TagRef 반환, 없으면 None. 북마크를 업데이트하지는 않는다."""
        from ..connectors import make_connector
        from ..crypto import SecretBox

        box: SecretBox = SecretBox(self.settings.control_secret_key)
        token = box.decrypt(target.source.token) if target.source.token \
            else (box.decrypt(target.instance.token) if target.instance.token else "")
        if not token:
            log.debug("태그 폴링 skip — 토큰 없음: source=%s", target.source.id)
            return None
        try:
            with make_connector(kind=target.instance.kind, url=target.instance.base_url,
                                token=token, token_header=target.instance.token_header,
                                repo=target.source.repo) as conn:
                tags = conn.list_tags()
        except Exception as e:  # noqa: BLE001 — compare 404 등은 폴링 단계에서는 경고만
            log.warning("태그 조회 실패 source=%s: %s: %s",
                        target.source.id, type(e).__name__, e)
            return None
        if not tags:
            return None
        latest = tags[0]
        bookmark = db.scalars(
            select(SourceReleaseTag).where(
                SourceReleaseTag.source_id == target.source.id,
                SourceReleaseTag.branch_role == target.branch.role,
            )).first()
        if bookmark and bookmark.last_seen_tag == latest.name:
            return None  # 이미 본 태그
        return latest

    def _mark_seen(self, db: Session, target: _PollTarget, tag, run_id: str) -> None:
        bookmark = db.scalars(
            select(SourceReleaseTag).where(
                SourceReleaseTag.source_id == target.source.id,
                SourceReleaseTag.branch_role == target.branch.role,
            )).first()
        if bookmark is None:
            bookmark = SourceReleaseTag(
                source_id=target.source.id, branch_role=target.branch.role)
            db.add(bookmark)
        bookmark.last_seen_tag = tag.name
        bookmark.last_seen_sha = tag.sha
        bookmark.last_run_id = run_id
        bookmark.last_triggered_tag = tag.name

    def _mark_launch_status(self, db: Session, target: _PollTarget, status: str) -> None:
        bookmark = db.scalars(
            select(SourceReleaseTag).where(
                SourceReleaseTag.source_id == target.source.id,
                SourceReleaseTag.branch_role == target.branch.role,
            )).first()
        if bookmark is None:
            return
        bookmark.last_launch_status = status[:24]
