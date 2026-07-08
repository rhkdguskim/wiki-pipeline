"""ISO timestamp 정규화 — 모든 백엔드 응답이 Z(UTC) 접미사를 갖게 한다.

문제 배경:
  SQLAlchemy 의 DateTime(timezone=True) 컬럼에서 tz-aware UTC datetime 을 넣어도
  SQLite 백엔드(개발 모드)는 naive datetime 으로 돌려준다. 그대로 .isoformat() 하면
  Z 접미사가 없고, 프런트엔드 new Date("2026-07-08T15:30:00") 는 그걸 LOCAL TIME
  으로 해석한다 — 한국(KST) 클라이언트에서는 9시간 빠르게 표시되는 버그.

해결:
  isoformat_z(dt) 는 datetime 이 naive 면 UTC 로 간주해 "Z" 접미사를 붙이고,
  tz-aware 면 그 타임존 오프셋을 유지한 ISO 문자열을 반환한다. 빈 입력은 "".

또한 datetime.fromtimestamp(ts) 도 naive local time 을 반환하므로, fromtimestamp_utc
헬퍼로 tz=UTC 를 강제한다.
"""
from __future__ import annotations

from datetime import datetime, timezone


def isoformat_z(dt: datetime | None) -> str:
    """datetime → ISO 문자열 (항상 TZ 명시). naive 면 UTC 로 간주."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        # naive → UTC 가정. "+00:00" 대신 "Z" 를 써서 짧고 표준적으로.
        return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    # tz-aware — UTC 면 Z 로, 다른 타임존이면 offset 유지
    iso = dt.isoformat()
    if iso.endswith("+00:00"):
        return iso[:-6] + "Z"
    return iso


def fromtimestamp_utc(ts: float) -> datetime:
    """epoch → tz-aware UTC datetime. datetime.fromtimestamp(ts) 의 naive 함 정정."""
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def now_utc() -> datetime:
    """현재 시각(tz-aware UTC). models.utcnow 와 동일하지만 isoformat_z 와 짝."""
    return datetime.now(timezone.utc)


def as_utc(dt: datetime | None) -> datetime | None:
    """DB 에서 나온 datetime 을 tz-aware UTC 로 정규화.

    - None → None
    - tz-aware → 그대로
    - naive → UTC 가정 (개발 모드 SQLite 가 naive 를 돌려주는 경로 차단)

    SQLAlchemy `DateTime(timezone=True)` 컬럼은 PostgreSQL 에선 tz-aware 를
    보장하지만 SQLite 는 naive 를 돌려주는 경우가 있다. tz 비교/산술 전에
    항상 이 헬퍼를 거치면 DB 백엔드에 무관하게 동작한다.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
