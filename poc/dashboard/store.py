"""Control Plane SQLite store.

This is the first durable slice of the management server described in the
LLM Wiki decisions: source registration lives in server DB, not in files.
"""
from __future__ import annotations

import datetime as _dt
import re
import sqlite3
from pathlib import Path
from typing import Any

from ..common.config import Settings, SourceConfig

_SOURCE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


def source_id(value: str) -> str:
    cleaned = _SOURCE_ID_RE.sub("-", value.strip()).strip("-").lower()
    return cleaned or "source"


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


class ControlStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def init_schema(self) -> None:
        with self.connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                  id TEXT PRIMARY KEY,
                  kind TEXT NOT NULL DEFAULT 'gitlab',
                  label TEXT NOT NULL,
                  url TEXT NOT NULL,
                  project_id TEXT NOT NULL,
                  token TEXT NOT NULL DEFAULT '',
                  token_header TEXT NOT NULL DEFAULT 'PRIVATE-TOKEN',
                  doc_dir TEXT NOT NULL DEFAULT '',
                  themes TEXT NOT NULL DEFAULT '',
                  enabled INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS source_branches (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                  role TEXT NOT NULL CHECK(role IN ('dev', 'release')),
                  branch TEXT NOT NULL DEFAULT '',
                  baseline_sha TEXT NOT NULL DEFAULT '',
                  last_processed_sha TEXT NOT NULL DEFAULT '',
                  enabled INTEGER NOT NULL DEFAULT 1,
                  updated_at TEXT NOT NULL,
                  UNIQUE(source_id, role)
                );

                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY,
                  type TEXT NOT NULL,
                  status TEXT NOT NULL,
                  source_id TEXT NOT NULL DEFAULT '',
                  target TEXT NOT NULL DEFAULT '',
                  pipeline_url TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS run_items (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  run_id TEXT NOT NULL,
                  source_id TEXT NOT NULL DEFAULT '',
                  branch_role TEXT NOT NULL DEFAULT '',
                  from_sha TEXT NOT NULL DEFAULT '',
                  to_sha TEXT NOT NULL DEFAULT '',
                  doc_count INTEGER NOT NULL DEFAULT 0,
                  mr_url TEXT NOT NULL DEFAULT '',
                  error TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS doc_targets (
                  id TEXT PRIMARY KEY,
                  label TEXT NOT NULL,
                  kind TEXT NOT NULL DEFAULT 'gitlab',
                  url TEXT NOT NULL,
                  project_id TEXT NOT NULL DEFAULT '',
                  project_path TEXT NOT NULL DEFAULT '',
                  token TEXT NOT NULL DEFAULT '',
                  token_header TEXT NOT NULL DEFAULT 'PRIVATE-TOKEN',
                  default_branch TEXT NOT NULL DEFAULT 'master',
                  enabled INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                """
            )

    def seed_from_settings(self, settings: Settings) -> None:
        sources = settings.source_list
        if not sources:
            self.seed_doc_target(settings)
            return
        with self.connect() as con:
            existing = con.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"]
        if existing:
            self.seed_doc_target(settings)
            return
        for source in sources:
            self.upsert_source(source_to_payload(source), preserve_token=False)
        self.seed_doc_target(settings)

    def seed_doc_target(self, settings: Settings) -> None:
        if not settings.docshub_project_url and not settings.docshub_project_path:
            return
        payload = {
            "id": "product-common",
            "label": "product-common",
            "kind": "gitlab",
            "url": settings.docshub_project_url,
            "project_id": settings.docshub_project_id,
            "project_path": settings.docshub_project_path,
            "token": settings.docshub_token,
            "token_header": settings.docshub_token_header,
            "default_branch": settings.docshub_default_branch,
            "enabled": settings.docshub_mr_enabled,
        }
        with self.connect() as con:
            existing = con.execute("SELECT * FROM doc_targets WHERE id = 'product-common'").fetchone()
        if existing:
            if settings.docshub_token and not existing["token"]:
                self.upsert_doc_target(payload, preserve_token=False)
            return
        self.upsert_doc_target(payload, preserve_token=False)

    def list_sources(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT s.*,
                       dev.branch AS dev_branch,
                       dev.baseline_sha AS dev_baseline_sha,
                       dev.last_processed_sha AS dev_last_processed_sha,
                       dev.enabled AS dev_enabled,
                       rel.branch AS release_branch,
                       rel.baseline_sha AS release_baseline_sha,
                       rel.last_processed_sha AS release_last_processed_sha,
                       rel.enabled AS release_enabled
                FROM sources s
                LEFT JOIN source_branches dev
                  ON dev.source_id = s.id AND dev.role = 'dev'
                LEFT JOIN source_branches rel
                  ON rel.source_id = s.id AND rel.role = 'release'
                ORDER BY s.updated_at DESC, s.id ASC
                """
            ).fetchall()
        return [self._source_dict(r) for r in rows]

    def get_source(self, sid: str) -> dict[str, Any] | None:
        sid = source_id(sid)
        return next((s for s in self.list_sources() if s["id"] == sid), None)

    def upsert_source(self, payload: dict[str, Any], *, preserve_token: bool = True) -> dict[str, Any]:
        sid = source_id(str(payload.get("id") or payload.get("label") or payload.get("project_id") or "source"))
        label = str(payload.get("label") or sid).strip()
        kind = str(payload.get("kind") or "gitlab").strip().lower()
        url = str(payload.get("url") or "").strip().rstrip("/")
        project_id = str(payload.get("project_id") or "").strip()
        token = str(payload.get("token") or "")
        token_header = str(payload.get("token_header") or "PRIVATE-TOKEN").strip() or "PRIVATE-TOKEN"
        themes = normalize_themes(payload.get("themes"))
        doc_dir = str(payload.get("doc_dir") or "").strip()
        enabled = 1 if payload.get("enabled", True) else 0
        dev_branch = str(payload.get("dev_branch") or "").strip()
        release_branch = str(payload.get("release_branch") or "").strip()
        ts = now()
        if not label or not kind or not url or not project_id:
            raise ValueError("label, kind, url, project_id는 필수입니다.")

        with self.connect() as con:
            prev = con.execute("SELECT token FROM sources WHERE id = ?", (sid,)).fetchone()
            if preserve_token and prev and not token:
                token = prev["token"]
            con.execute(
                """
                INSERT INTO sources
                  (id, kind, label, url, project_id, token, token_header, doc_dir, themes, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  kind=excluded.kind,
                  label=excluded.label,
                  url=excluded.url,
                  project_id=excluded.project_id,
                  token=excluded.token,
                  token_header=excluded.token_header,
                  doc_dir=excluded.doc_dir,
                  themes=excluded.themes,
                  enabled=excluded.enabled,
                  updated_at=excluded.updated_at
                """,
                (sid, kind, label, url, project_id, token, token_header, doc_dir, themes, enabled, ts, ts),
            )
            self._upsert_branch(con, sid, "dev", dev_branch, bool(enabled), ts)
            self._upsert_branch(con, sid, "release", release_branch, bool(enabled), ts)
        return self.get_source(sid) or {}

    def set_source_enabled(self, sid: str, enabled: bool) -> dict[str, Any] | None:
        sid = source_id(sid)
        with self.connect() as con:
            con.execute("UPDATE sources SET enabled = ?, updated_at = ? WHERE id = ?", (1 if enabled else 0, now(), sid))
        return self.get_source(sid)

    def list_doc_targets(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM doc_targets ORDER BY updated_at DESC, id ASC").fetchall()
        return [self._doc_target_dict(r) for r in rows]

    def get_doc_target(self, target_id: str = "product-common") -> dict[str, Any] | None:
        target_id = source_id(target_id)
        return next((t for t in self.list_doc_targets() if t["id"] == target_id), None)

    def get_doc_target_private(self, target_id: str = "product-common") -> dict[str, Any] | None:
        target_id = source_id(target_id)
        with self.connect() as con:
            row = con.execute("SELECT * FROM doc_targets WHERE id = ?", (target_id,)).fetchone()
        if not row:
            return None
        data = self._doc_target_dict(row)
        data["token"] = row["token"]
        return data

    def upsert_doc_target(self, payload: dict[str, Any], *, preserve_token: bool = True) -> dict[str, Any]:
        target_id = source_id(str(payload.get("id") or "product-common"))
        label = str(payload.get("label") or target_id).strip()
        kind = str(payload.get("kind") or "gitlab").strip().lower()
        url = str(payload.get("url") or "").strip().rstrip("/")
        project_id = str(payload.get("project_id") or "").strip()
        project_path = str(payload.get("project_path") or "").strip()
        token = str(payload.get("token") or "")
        token_header = str(payload.get("token_header") or "PRIVATE-TOKEN").strip() or "PRIVATE-TOKEN"
        default_branch = str(payload.get("default_branch") or "master").strip()
        enabled = 1 if payload.get("enabled", True) else 0
        ts = now()
        if not label or not kind or not url:
            raise ValueError("label, kind, url은 필수입니다.")
        with self.connect() as con:
            prev = con.execute("SELECT token FROM doc_targets WHERE id = ?", (target_id,)).fetchone()
            if preserve_token and prev and not token:
                token = prev["token"]
            con.execute(
                """
                INSERT INTO doc_targets
                  (id, label, kind, url, project_id, project_path, token, token_header, default_branch, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  label=excluded.label,
                  kind=excluded.kind,
                  url=excluded.url,
                  project_id=excluded.project_id,
                  project_path=excluded.project_path,
                  token=excluded.token,
                  token_header=excluded.token_header,
                  default_branch=excluded.default_branch,
                  enabled=excluded.enabled,
                  updated_at=excluded.updated_at
                """,
                (target_id, label, kind, url, project_id, project_path, token, token_header, default_branch, enabled, ts, ts),
            )
        return self.get_doc_target(target_id) or {}

    def _upsert_branch(self, con: sqlite3.Connection, sid: str, role: str, branch: str, enabled: bool, ts: str) -> None:
        con.execute(
            """
            INSERT INTO source_branches (source_id, role, branch, enabled, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_id, role) DO UPDATE SET
              branch=excluded.branch,
              enabled=excluded.enabled,
              updated_at=excluded.updated_at
            """,
            (sid, role, branch, 1 if enabled else 0, ts),
        )

    def _source_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        themes = [x.strip() for x in (row["themes"] or "").split(",") if x.strip()]
        return {
            "id": row["id"],
            "kind": row["kind"],
            "label": row["label"],
            "url": row["url"],
            "project_id": row["project_id"],
            "token_header": row["token_header"],
            "doc_dir": row["doc_dir"],
            "themes": themes,
            "enabled": bool(row["enabled"]),
            "dev_branch": row["dev_branch"] or "",
            "release_branch": row["release_branch"] or "",
            "last_processed_sha": row["dev_last_processed_sha"] or row["release_last_processed_sha"] or "",
            "branches": [
                {
                    "role": "dev",
                    "branch": row["dev_branch"] or "",
                    "baseline_sha": row["dev_baseline_sha"] or "",
                    "last_processed_sha": row["dev_last_processed_sha"] or "",
                    "enabled": bool(row["dev_enabled"]) if row["dev_enabled"] is not None else bool(row["enabled"]),
                },
                {
                    "role": "release",
                    "branch": row["release_branch"] or "",
                    "baseline_sha": row["release_baseline_sha"] or "",
                    "last_processed_sha": row["release_last_processed_sha"] or "",
                    "enabled": bool(row["release_enabled"]) if row["release_enabled"] is not None else bool(row["enabled"]),
                },
            ],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _doc_target_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "label": row["label"],
            "kind": row["kind"],
            "url": row["url"],
            "project_id": row["project_id"],
            "project_path": row["project_path"],
            "token_header": row["token_header"],
            "has_token": bool(row["token"]),
            "default_branch": row["default_branch"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def source_to_payload(source: SourceConfig) -> dict[str, Any]:
    return {
        "id": source.id,
        "kind": source.kind,
        "label": source.label or source.id,
        "url": source.url,
        "project_id": source.project_id,
        "token": source.token,
        "token_header": source.token_header,
        "themes": source.themes,
        "enabled": True,
    }


def normalize_themes(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(x).strip() for x in value if str(x).strip())
    return ",".join(x.strip() for x in str(value or "").split(",") if x.strip())


def default_db_path(out_dir: Path) -> Path:
    return out_dir / "control-plane.sqlite"
