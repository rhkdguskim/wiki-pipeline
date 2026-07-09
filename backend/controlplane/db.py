"""DB 엔진/세션 — PostgreSQL 대상(운영), SQLite(개발·테스트).

decision-db-source-of-truth: 서버 DB가 sources/branches/runs의 유일한 source of truth.

스키마 진화(ENT-A):
  init_db() 는 Alembic upgrade head 를 호출한다.
  - 신규 DB: 0001_baseline + 0002_audit_and_token_rotation 가 스키마를 만든다.
  - 기존 DB: alembic 0001 이 CREATE TABLE 로 충돌할 수 있어 실패한다. 이때는
    create_all 폴백 + "critical columns" 안전장치로 누락된 컬럼을 직접 ALTER 한다.

왜 "critical columns" 가 필요한가:
  create_all 은 additive only — 새 컬럼이 모델에 추가돼도 기존 테이블에는
  반영되지 않는다. alembic 마이그레이션은 0001 이 기존 테이블과 충돌해 막다른
  골목에 빠질 수 있다. 둘 다 실패할 때를 대비해, init_db 끝에 핵심 컬럼의
  존재를 강제 확인하고 없으면 직접 ALTER 한다.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

log = logging.getLogger("controlplane.db")

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def make_engine(db_url: str):
    kwargs: dict = {"pool_pre_ping": True}
    if db_url.startswith("sqlite"):
        # 단일 파일 SQLite: FastAPI 스레드풀에서 접근하므로 check_same_thread 해제
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(db_url, **kwargs)


def make_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def _migration_db_url(engine) -> str:
    url = engine.url
    if hasattr(url, "render_as_string"):
        return url.render_as_string(hide_password=False)
    return str(url)


def _alembic_upgrade_to_head(db_url: str) -> bool:
    """Alembic API 로 upgrade head. 성공하면 True, 실패하면 False.

    컨트롤 플레인 lifespan 시작 시점에 호출 — 예외가 나면 create_all 폴백.
    """
    try:
        from alembic import command as alembic_cmd
        from alembic.config import Config as AlembicConfig

        cfg = AlembicConfig()
        # alembic.ini 는 script_location + prepend_sys_path 를 포함.
        # db_url 은 환경변수(CONTROL_DB_URL) 또는 load_cp_settings() 에서 읽는다.
        cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
        cfg.set_main_option("prepend_sys_path", "../..")
        cfg.set_main_option("sqlalchemy.url", db_url)

        # CONTROL_DB_URL 환경변수 보존 (env.py 가 우선 사용).
        prev = os.environ.get("CONTROL_DB_URL")
        os.environ["CONTROL_DB_URL"] = db_url
        try:
            alembic_cmd.upgrade(cfg, "head")
        finally:
            if prev is None:
                os.environ.pop("CONTROL_DB_URL", None)
            else:
                os.environ["CONTROL_DB_URL"] = prev
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("alembic upgrade 실패 — create_all + critical-columns 폴백: %s: %s",
                    type(e).__name__, e)
        return False


def _alembic_stamp_head(db_url: str) -> None:
    from alembic import command as alembic_cmd
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("prepend_sys_path", "../..")
    cfg.set_main_option("sqlalchemy.url", db_url)

    prev = os.environ.get("CONTROL_DB_URL")
    os.environ["CONTROL_DB_URL"] = db_url
    try:
        alembic_cmd.stamp(cfg, "head")
    finally:
        if prev is None:
            os.environ.pop("CONTROL_DB_URL", None)
        else:
            os.environ["CONTROL_DB_URL"] = prev


def _is_unversioned_existing_schema(engine) -> bool:
    insp = inspect(engine)
    if insp.has_table("alembic_version"):
        return False
    return any(insp.has_table(table) for table in ("scm_instances", "sources", "runs"))


# ── critical columns 안전장치 ───────────────────────────────────
# 모델에는 있지만 기존 DB 에 누락될 수 있는 컬럼을 직접 ALTER 한다.
# 새 컬럼을 추가할 때마다 이 목록에 한 줄을 더하면 init_db 가 자동 보정한다.
# (alembic 이 정상 동작하면 이 경로는 실행되지 않는다.)

_CRITICAL_COLUMNS: list[tuple[str, str, str, str]] = [
    # (table, column, type_with_modifiers, default_sql)
    # type: 'ALTER TABLE t ADD COLUMN c TYPE'
    # default_sql: '' for nullable, 'DEFAULT ...' for backfill
    ("scm_instances", "token_rotated_at", "DATETIME", ""),
    ("scm_instances", "created_at", "DATETIME", ""),
    ("scm_instances", "updated_at", "DATETIME", ""),
    ("sources", "created_at", "DATETIME", ""),
    ("sources", "updated_at", "DATETIME", ""),
    ("source_branches", "updated_at", "DATETIME", ""),
    ("runs", "created_at", "DATETIME", ""),
    ("runs", "updated_at", "DATETIME", ""),
    ("run_events", "id", "INTEGER", ""),
    ("source_release_tags", "id", "INTEGER", ""),
    # 0006: RunDocOutput 콘텐츠 영속화 — alembic 실패 시 안전장치.
    ("run_doc_outputs", "content_text", "TEXT", ""),
    ("run_doc_outputs", "content_size", "INTEGER", ""),
]


def _ensure_critical_columns(engine) -> int:
    """누락된 컬럼을 직접 ALTER TABLE 로 추가. 추가된 컬럼 수 반환.

    SQLite/PostgreSQL 모두 호환되게 컬럼 추가만 한다 (type modifier 없이).
    컬럼이 이미 있으면 SKIP — 멱등성 보장.
    """
    insp = inspect(engine)
    added = 0
    with engine.begin() as conn:
        for table, column, ctype, default in _CRITICAL_COLUMNS:
            try:
                if not insp.has_table(table):
                    continue  # create_all 이 테이블을 아직 안 만든 경우 (백업 경로)
                cols = {c["name"] for c in insp.get_columns(table)}
                if column in cols:
                    continue
                # ADD COLUMN. DEFAULT 가 있으면 함께 지정 (SQLite/Postgres 호환).
                ddl = f"ALTER TABLE {table} ADD COLUMN {column} {ctype}"
                if default:
                    ddl += f" {default}"
                conn.execute(text(ddl))
                log.info("critical column added: %s.%s (%s)", table, column, ctype)
                added += 1
            except Exception as e:  # noqa: BLE001
                # 일부 column 은 모델/실제 매핑이 안 맞을 수 있다 (예: server_default=...).
                # 무시 — alembic 이 이미 처리했거나 다음 부팅에서 재시도.
                log.debug("critical column skip: %s.%s — %s", table, column, e)
    # 인스펙터를 무효화 — 다음 get_columns 호출이 새 스키마를 본다.
    if added:
        insp._schemas.clear() if hasattr(insp, "_schemas") else None
    return added


def init_db(engine) -> None:
    """스키마 부트스트랩.

    순서:
      1. alembic upgrade head 시도  (성공 시 끝)
      2. 실패 시 Base.metadata.create_all  (누락 테이블 생성)
      3. _ensure_critical_columns  (누락 컬럼 직접 ALTER — 멱등성)

    create_all 은 additive only 라서 운영 마이그레이션 수단으로 부적합 — 이건 단지
    개발자가 alembic 없이 빠르게 띄울 수 있는 편의 경로.
    """
    db_url = _migration_db_url(engine)

    if _is_unversioned_existing_schema(engine):
        log.warning(
            "existing control-plane schema has no alembic_version — "
            "creating missing tables and stamping head"
        )
        Base.metadata.create_all(engine)
        _alembic_stamp_head(db_url)

    alembic_ok = _alembic_upgrade_to_head(db_url)
    if not alembic_ok:
        # alembic 실패 — create_all 로 누락 테이블 생성.
        Base.metadata.create_all(engine)

    # 어느 경로든 마지막에 critical columns 를 보정. idempotent.
    added = _ensure_critical_columns(engine)
    if added:
        log.info("init_db: %d critical column(s) added via safety net", added)


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
