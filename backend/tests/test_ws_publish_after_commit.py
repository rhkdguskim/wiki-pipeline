"""WS publish-after-commit — P2 docu-automation-data-plane-review.md.

핵심 계약:
- _publish(message, db) 가 commit 이전에 호출돼도 WS 가 pre-commit 행을
  알리지 않는다
- session 이 commit 되면 큐를 flush
- commit 이 실패 (rollback) 하면 큐는 비워진다
"""
from __future__ import annotations

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


def _make_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.controlplane.models import Base
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_publish_with_db_defers_until_commit():
    bc = FakeBroadcaster()
    svc = _svc(broadcaster=bc)
    db = _make_session()
    svc._publish({"type": "run_status", "run_id": "r1"}, db)
    assert bc.published == []
    db.commit()
    assert bc.published == [{"type": "run_status", "run_id": "r1"}]
    db.close()


def test_publish_without_db_publishes_immediately():
    bc = FakeBroadcaster()
    svc = _svc(broadcaster=bc)
    svc._publish({"type": "run_status", "run_id": "r1"})
    assert bc.published == [{"type": "run_status", "run_id": "r1"}]


def test_multiple_messages_all_flushed_on_commit():
    bc = FakeBroadcaster()
    svc = _svc(broadcaster=bc)
    db = _make_session()
    svc._publish({"type": "run_status", "run_id": "r1"}, db)
    svc._publish({"type": "run_heartbeat", "run_id": "r1"}, db)
    assert bc.published == []
    db.commit()
    assert len(bc.published) == 2
    assert bc.published[0]["type"] == "run_status"
    assert bc.published[1]["type"] == "run_heartbeat"
    db.close()


def test_rollback_discards_queued_messages():
    bc = FakeBroadcaster()
    svc = _svc(broadcaster=bc)
    db = _make_session()
    svc._publish({"type": "run_status", "run_id": "r1"}, db)
    db.rollback()
    assert bc.published == []
    db.close()


def test_hook_not_registered_twice():
    bc = FakeBroadcaster()
    svc = _svc(broadcaster=bc)
    db = _make_session()
    svc._publish({"type": "first"}, db)
    db.commit()
    svc._publish({"type": "second"}, db)
    db.commit()
    assert len(bc.published) == 2
    assert bc.published[0]["type"] == "first"
    assert bc.published[1]["type"] == "second"
    db.close()


def test_distinct_sessions_are_independent():
    bc = FakeBroadcaster()
    svc = _svc(broadcaster=bc)
    db1 = _make_session()
    db2 = _make_session()
    svc._publish({"type": "a"}, db1)
    svc._publish({"type": "b"}, db2)
    db1.commit()
    assert bc.published == [{"type": "a"}]
    db2.commit()
    assert bc.published == [{"type": "a"}, {"type": "b"}]
    db1.close()
    db2.close()


def test_no_broadcaster_is_safe():
    svc = _svc(broadcaster=None)
    db = _make_session()
    svc._publish({"type": "x"}, db)
    db.commit()
    db.close()
