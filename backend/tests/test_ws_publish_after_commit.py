"""WS publish-after-commit — P2 docu-automation-data-plane-review.md.

핵심 계약:
- _publish / publish_deferred 가 commit 이전에 호출돼도 WS 가 pre-commit 행을
  알리지 않는다
- install_after_commit_publish 가 등록된 session 이 commit 되면 큐를 flush
- commit 이 실패 (rollback) 하면 큐는 비워진다
"""
from __future__ import annotations

import pytest

from backend.controlplane.services.runs import RunService


class FakeBroadcaster:
    def __init__(self):
        self.published = []

    def publish(self, msg):
        self.published.append(msg)


def _svc(broadcaster=None):
    from backend.controlplane.settings import ControlPlaneSettings
    from backend.controlplane.services.notifier import Notifier
    settings = ControlPlaneSettings()
    notifier = Notifier(settings)
    return RunService(settings, notifier, broadcaster=broadcaster)


def test_publish_deferred_accumulates_messages():
    svc = _svc(broadcaster=FakeBroadcaster())
    assert svc.flush_pending_publishes() == 0
    svc.publish_deferred({"type": "run_status", "run_id": "r1"})
    svc.publish_deferred({"type": "run_status", "run_id": "r2"})
    assert len(svc._pending_publishes) == 2


def test_flush_pending_publishes_sends_to_broadcaster():
    bc = FakeBroadcaster()
    svc = _svc(broadcaster=bc)
    svc.publish_deferred({"type": "run_status", "run_id": "r1"})
    svc.publish_deferred({"type": "run_heartbeat", "run_id": "r1"})
    n = svc.flush_pending_publishes()
    assert n == 2
    assert bc.published == [
        {"type": "run_status", "run_id": "r1"},
        {"type": "run_heartbeat", "run_id": "r1"},
    ]
    assert svc._pending_publishes == []


def test_flush_with_no_broadcaster_clears_queue():
    svc = _svc(broadcaster=None)
    svc.publish_deferred({"type": "x"})
    assert svc.flush_pending_publishes() == 0
    assert svc._pending_publishes == []


def test_after_commit_listener_flushes_on_commit():
    """install_after_commit_publish 가 등록된 session 이 commit 되면 큐가 flush."""
    bc = FakeBroadcaster()
    svc = _svc(broadcaster=bc)

    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from backend.controlplane.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    svc.install_after_commit_publish(db)
    svc.publish_deferred({"type": "x", "from": "service"})

    assert bc.published == []
    db.commit()
    assert bc.published == [{"type": "x", "from": "service"}]
    assert svc._pending_publishes == []
    db.close()


def test_after_commit_rollback_does_not_publish():
    """commit 실패 (rollback) 시 큐는 비워지지만 broadcaster 로 발송되지 않음."""
    bc = FakeBroadcaster()
    svc = _svc(broadcaster=bc)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.controlplane.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    svc.install_after_commit_publish(db)
    svc.publish_deferred({"type": "x"})

    try:
        with db.begin_nested():
            pass
            raise RuntimeError("nested transaction fail")
    except RuntimeError:
        db.rollback()

    assert bc.published == []
    assert svc._pending_publishes == []
    db.close()


def test_after_commit_listener_does_not_register_twice_on_same_session():
    bc = FakeBroadcaster()
    svc = _svc(broadcaster=bc)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.controlplane.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    svc.install_after_commit_publish(db)
    svc.publish_deferred({"type": "first"})
    db.commit()
    svc.install_after_commit_publish(db)
    svc.publish_deferred({"type": "second"})
    db.commit()

    assert len(bc.published) == 2
    assert bc.published[0]["type"] == "first"
    assert bc.published[1]["type"] == "second"
    db.close()


def test_multiple_services_with_distinct_queues():
    """각 RunService 인스턴스는 별개의 queue 를 갖는다 (서비스가 매 request 생성될 때)."""
    bc1, bc2 = FakeBroadcaster(), FakeBroadcaster()
    svc1, svc2 = _svc(broadcaster=bc1), _svc(broadcaster=bc2)
    svc1.publish_deferred({"type": "a"})
    svc2.publish_deferred({"type": "b"})
    svc1.flush_pending_publishes()
    svc2.flush_pending_publishes()
    assert bc1.published == [{"type": "a"}]
    assert bc2.published == [{"type": "b"}]
