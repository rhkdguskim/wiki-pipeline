"""DB 엔진/세션 — PostgreSQL 대상(운영), SQLite(개발·테스트).

decision-db-source-of-truth: 서버 DB가 sources/branches/runs의 유일한 source of truth.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def make_engine(db_url: str):
    kwargs: dict = {"pool_pre_ping": True}
    if db_url.startswith("sqlite"):
        # 단일 파일 SQLite: FastAPI 스레드풀에서 접근하므로 check_same_thread 해제
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(db_url, **kwargs)


def make_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine) -> None:
    """스키마 부트스트랩. 운영 마이그레이션은 Alembic 도입 전까지 additive만 허용."""
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
