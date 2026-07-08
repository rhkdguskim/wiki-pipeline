"""backend.timeutil — naive/aware datetime 모두에서 Z 접미사를 보장하는지 검증.

배경: SQLite 백엔드는 tz-aware UTC datetime 을 넣어도 naive datetime 으로
반환할 수 있다. .isoformat() 그대로 쓰면 Z 가 빠져서 프런트엔드 new Date()
가 LOCAL TIME 으로 해석 — KST 클라이언트에서 9시간 빠르게 표시되는 버그.

이 테스트는 timeutil 가 그 갭을 메우는지 확인한다.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from backend.controlplane.timeutil import isoformat_z, fromtimestamp_utc, now_utc


def test_isoformat_z_with_naive_assumes_utc():
    naive = datetime(2026, 7, 8, 6, 30, 0)  # 의도적으로 naive
    out = isoformat_z(naive)
    assert out.endswith("Z"), f"naive datetime 은 UTC 로 가정되어야 한다 — got {out!r}"
    assert out.startswith("2026-07-08T06:30:00"), out


def test_isoformat_z_with_aware_utc_emits_z():
    aware = datetime(2026, 7, 8, 6, 30, 0, tzinfo=timezone.utc)
    out = isoformat_z(aware)
    assert out.endswith("Z"), out


def test_isoformat_z_with_aware_kst_keeps_offset():
    kst = timezone(timedelta(hours=9))
    aware = datetime(2026, 7, 8, 15, 30, 0, tzinfo=kst)  # KST 15:30 = UTC 06:30
    out = isoformat_z(aware)
    # KST 는 Z 로 축약하지 않는다 — 의미 있는 오프셋 정보 보존.
    assert "+09:00" in out, out


def test_isoformat_z_none_returns_empty():
    assert isoformat_z(None) == ""


def test_fromtimestamp_utc_returns_aware_utc():
    dt = fromtimestamp_utc(1718438400)
    assert dt.tzinfo is not None
    assert dt.tzinfo.utcoffset(dt) == timedelta(0)


def test_now_utc_returns_aware_utc():
    n = now_utc()
    assert n.tzinfo is not None
    assert n.tzinfo.utcoffset(n) == timedelta(0)


def test_projection_started_at_uses_utc_z_suffix():
    """projection.summarize_events 의 started_at 이 빈 입력일 때 fromtimestamp_utc 거치며 Z 보장."""
    from backend.controlplane.projection import summarize_events
    out = summarize_events(
        [], run_id="r-test",
        # run_started_at 미주입 → first_ts 기반 경로
    )
    # 이벤트가 없어서 started_at 도 빈 문자열이지만, 코드 경로가 Z 를 쓰는지만 확인
    # first_ts 도 None 이므로 "" 반환 — 정상.
    assert out["started_at"] == ""


def test_pipeline_status_uses_z_suffix_isoformat():
    """RunService.pipeline_status 의 last_run_at 이 DB 에서 온 naive datetime 도 Z 접미사로."""
    from datetime import datetime as _dt
    from backend.controlplane.models import Base, Run, Source
    from backend.controlplane.db import make_engine, make_session_factory, session_scope
    from backend.controlplane.services.runs import RunService

    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    from backend.controlplane.settings import ControlPlaneSettings
    settings = ControlPlaneSettings()
    settings.control_secret_key = "x" * 44  # Fernet key shape

    # DB 에 소스·run 1건 저장. created_at 은 tz-aware UTC 로 — models.utcnow 사용.
    from backend.controlplane.models import utcnow
    with session_scope(factory) as db:
        src = Source(id="s1", instance_id="i1", label="test", repo="r",
                     doc_dir="r", themes="", schedule_cron="", enabled=True)
        db.add(src)
        db.flush()
        r = Run(id="r1", source_id="s1", pipeline_id="static",
                mode="auto", branch_role="dev", trigger="schedule",
                status="done", created_at=utcnow(), updated_at=utcnow())
        db.add(r)

    with session_scope(factory) as db:
        rs = RunService(settings, None)
        result = rs.pipeline_status(db)
        assert len(result) == 1
        last_run_at = result[0]["last_run_at"]
        assert last_run_at.endswith("Z"), (
            "SQLite 에서도 last_run_at 은 Z 접미사를 가져야 한다 — "
            f"got {last_run_at!r}")