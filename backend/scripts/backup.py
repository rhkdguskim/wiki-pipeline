"""wiki-pipeline backup utility — SQLite / PostgreSQL 양쪽 지원.

사용법:
  # SQLite 백업 (.backup) — DB lock 없이 일관 스냅샷
  python -m backend.scripts.backup --out /var/backups/wpipe

  # PostgreSQL 백업 (pg_dump 사용 — 컨테이너 안에서는 클라이언트 도구 필요)
  python -m backend.scripts.backup --out /var/backups/wpipe --pg-dump-bin /usr/bin/pg_dump

보존 정책:
  - 기본 7일치 보관. --retain-days N 으로 조정.
  - 백업 파일명: control-plane-YYYYMMDDTHHMMSSZ.{sqlite,sql.gz}
  - 검증: SQLite 는 .backup(PRAGMA integrity_check) 결과를 메타데이터로 동봉.

cron 예시 (매일 새벽 3:30):
  30 3 * * * cd /app && python -m backend.scripts.backup --out /var/backups/wpipe --retain-days 14
"""
from __future__ import annotations

import argparse
import gzip
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("wpipe.backup")


# ── SQLite backup ─────────────────────────────────────────────────

def backup_sqlite(src: Path, dest_dir: Path) -> Path:
    """SQLite 의 온라인 백업 API 로 lock-free 스냅샷."""
    if not src.is_file():
        raise FileNotFoundError(f"SQLite file not found: {src}")
    ts = _timestamp()
    out_path = dest_dir / f"control-plane-{ts}.sqlite"
    dest_dir.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(str(src))
    try:
        dst_conn = sqlite3.connect(str(out_path))
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
        # 무결성 검증
        check = sqlite3.connect(str(out_path))
        try:
            result = check.execute("PRAGMA integrity_check").fetchone()
            ok = bool(result) and result[0] == "ok"
        finally:
            check.close()
        if not ok:
            raise RuntimeError(f"integrity_check failed: {result}")
        size = out_path.stat().st_size
        log.info("sqlite backup ok: %s (%.1f KB)", out_path, size / 1024)
        return out_path
    finally:
        src_conn.close()


# ── PostgreSQL backup (pg_dump) ──────────────────────────────────

def backup_postgres(db_url: str, dest_dir: Path, pg_dump_bin: str) -> Path:
    """pg_dump 를 호출해 SQL 덤프 → gzip. pg_dump 가 없으면 RuntimeError.

    컨테이너에서 pg_dump 를 함께 설치해야 한다(Dockerfile 보강 필요).
    백업 형식: 평문 SQL 을 gzip — text 형식이라 복원/grep/스트리밍 모두 친화.
    """
    if not shutil.which(pg_dump_bin) and not Path(pg_dump_bin).is_file():
        raise RuntimeError(
            f"pg_dump not found at {pg_dump_bin} — install postgresql-client in the image")
    ts = _timestamp()
    raw_path = dest_dir / f"control-plane-{ts}.sql"
    gz_path = dest_dir / f"control-plane-{ts}.sql.gz"
    dest_dir.mkdir(parents=True, exist_ok=True)
    cmd = [pg_dump_bin, "--no-owner", "--no-privileges", "--format=plain", db_url]
    log.info("running pg_dump: %s", " ".join(cmd[:2]) + " <db_url>")
    with raw_path.open("wb") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            raw_path.unlink(missing_ok=True)
            raise RuntimeError(f"pg_dump failed: {proc.stderr.decode('utf-8', 'replace')[:500]}")
    # gzip
    with raw_path.open("rb") as src_f, gzip.open(gz_path, "wb") as dst_f:
        shutil.copyfileobj(src_f, dst_f)
    raw_path.unlink()
    log.info("postgres backup ok: %s (%.1f KB)", gz_path, gz_path.stat().st_size / 1024)
    return gz_path


# ── 보존 정책 ───────────────────────────────────────────────────

def prune_old_backups(dest_dir: Path, retain_days: int) -> int:
    """retain_days 보다 오래된 백업 제거. 0 이하=비활성. 제거된 파일 수 반환."""
    if retain_days <= 0:
        return 0
    cutoff = _now().timestamp() - retain_days * 86400
    removed = 0
    for p in dest_dir.glob("control-plane-*.*"):
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            try:
                p.unlink()
                removed += 1
            except OSError as e:
                log.warning("remove failed %s: %s", p, e)
    return removed


# ── DB URL 분류 ──────────────────────────────────────────────────

def detect_kind(db_url: str) -> str:
    """'sqlite' or 'postgres'."""
    if db_url.startswith("sqlite"):
        return "sqlite"
    if db_url.startswith(("postgresql", "postgres")):
        return "postgres"
    raise ValueError(f"unsupported db_url scheme: {db_url.split('://', 1)[0]}")


def extract_sqlite_path(db_url: str) -> Path:
    """sqlite:///absolute/path or sqlite:///./relative — URL → Path."""
    body = db_url.split("://", 1)[1]
    if body.startswith("/"):
        return Path(body)
    # sqlite:///./out/foo.sqlite  →  out/foo.sqlite (backend/.env 가 기준)
    return (Path.cwd() / body).resolve()


# ── 메인 ─────────────────────────────────────────────────────────

def _timestamp() -> str:
    return _now().strftime("%Y%m%dT%H%M%SZ")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_db_url() -> str:
    from backend.controlplane.settings import load_cp_settings
    return load_cp_settings().db_url


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="wiki-pipeline DB backup")
    parser.add_argument("--out", required=True, type=Path, help="backup output directory")
    parser.add_argument("--db-url", default="", help="override CONTROL_DB_URL")
    parser.add_argument("--pg-dump-bin", default=os.environ.get("PG_DUMP_BIN", "pg_dump"),
                        help="path to pg_dump (postgres only)")
    parser.add_argument("--retain-days", type=int, default=7,
                        help="backup retention; 0=keep all (default 7)")
    args = parser.parse_args()

    db_url = args.db_url.strip() or _resolve_db_url()
    kind = detect_kind(db_url)
    try:
        if kind == "sqlite":
            path = backup_sqlite(extract_sqlite_path(db_url), args.out)
        else:
            path = backup_postgres(db_url, args.out, args.pg_dump_bin)
    except Exception as e:
        log.error("backup failed: %s", e)
        return 1

    removed = prune_old_backups(args.out, args.retain_days)
    log.info("retention prune removed %d file(s)", removed)
    log.info("backup complete: %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
