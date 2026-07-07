"""소스/인스턴스/타깃 등록 — 자동 조회 + compare dry-run 검증.

decision-repo-dev-release-registration: 레포 1개 + 개발/배포 브랜치 2개.
decision-docs-hub-folder-rule: doc_dir 기본값 = full namespace path.
decision-scm-multi-instance-github-mvp: 소스는 scm_instances를 참조한다.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...connectors import ScmConnector, make_connector
from ..crypto import SecretBox
from ..models import DocTarget, ScmInstance, Source, SourceBranch

_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(value: str, fallback: str = "item") -> str:
    cleaned = _ID_RE.sub("-", value.strip()).strip("-").lower()
    return cleaned or fallback


class RegistrationService:
    def __init__(self, box: SecretBox):
        self.box = box

    # ── SCM 인스턴스 ─────────────────────────────────────────
    def upsert_instance(self, db: Session, payload: dict[str, Any], *,
                        preserve_token: bool = False) -> ScmInstance:
        iid = _slug(str(payload.get("id") or payload.get("label") or payload.get("base_url") or ""))
        inst = db.get(ScmInstance, iid)
        if inst is None:
            inst = ScmInstance(id=iid)
            db.add(inst)
        inst.kind = str(payload.get("kind") or inst.kind or "gitlab").lower()
        inst.label = str(payload.get("label") or inst.label or iid)
        inst.base_url = str(payload.get("base_url") or payload.get("url") or inst.base_url or "").rstrip("/")
        inst.token_header = str(payload.get("token_header") or inst.token_header or "PRIVATE-TOKEN")
        if "enabled" in payload:
            inst.enabled = bool(payload["enabled"])
        token = str(payload.get("token") or "")
        if token and not (preserve_token and not token.strip()):
            inst.token = self.box.encrypt(token)
        db.flush()
        return inst

    def find_or_create_instance(self, db: Session, *, kind: str, url: str,
                                token: str = "", token_header: str = "PRIVATE-TOKEN",
                                label: str = "") -> ScmInstance:
        """레거시(단일 페이로드) 소스 등록 호환 — kind+url이 같으면 재사용."""
        url = (url or "").rstrip("/")
        kind = (kind or "gitlab").lower()
        found = db.scalars(select(ScmInstance).where(
            ScmInstance.kind == kind, ScmInstance.base_url == url)).first()
        if found:
            if token:
                found.token = self.box.encrypt(token)
            return found
        host = url.split("://", 1)[-1].split("/", 1)[0] if url else ("github-com" if kind == "github" else kind)
        return self.upsert_instance(db, {
            "id": _slug(label or host), "kind": kind, "url": url,
            "token": token, "token_header": token_header, "label": label or host,
        })

    # ── 커넥터 해석 (source token > instance token) ──────────
    def connector_for_source(self, db: Session, source: Source, *, transport=None) -> ScmConnector:
        inst = source.instance or db.get(ScmInstance, source.instance_id)
        token = self.box.decrypt(source.token) if source.token else self.box.decrypt(inst.token)
        return make_connector(kind=inst.kind, url=inst.base_url, token=token,
                              token_header=inst.token_header, repo=source.repo,
                              transport=transport)

    # ── 소스 ─────────────────────────────────────────────────
    def upsert_source(self, db: Session, payload: dict[str, Any], *,
                      preserve_token: bool = False, verify: bool = True,
                      transport=None) -> tuple[Source, dict]:
        """소스 등록/수정. verify=True면 커넥터로 자동 조회 + dry-run 검증까지 수행."""
        repo = str(payload.get("repo") or payload.get("project_id") or "").strip()
        if not repo:
            raise ValueError("repo(project_id)가 필요합니다.")

        if payload.get("instance_id"):
            inst = db.get(ScmInstance, str(payload["instance_id"]))
            if inst is None:
                raise ValueError(f"알 수 없는 instance: {payload['instance_id']}")
            if payload.get("token") and payload.get("token_scope") == "instance":
                inst.token = self.box.encrypt(str(payload["token"]))
        else:
            inst = self.find_or_create_instance(
                db, kind=str(payload.get("kind") or "gitlab"),
                url=str(payload.get("url") or ""),
                token="" if payload.get("token_scope") == "source" else str(payload.get("token") or ""),
                token_header=str(payload.get("token_header") or "PRIVATE-TOKEN"),
            )

        sid = _slug(str(payload.get("id") or payload.get("label") or repo))
        source = db.get(Source, sid)
        if source is None:
            source = Source(id=sid, instance_id=inst.id, repo=repo)
            db.add(source)
        source.instance_id = inst.id
        source.repo = repo
        source.label = str(payload.get("label") or source.label or sid)
        source.themes = str(payload.get("themes") or source.themes or "")
        source.owner_email = str(payload.get("owner_email") or source.owner_email or "")
        source.schedule_cron = str(payload.get("schedule_cron") or source.schedule_cron or "")
        if "enabled" in payload:
            source.enabled = bool(payload["enabled"])
            if source.enabled:
                source.disabled_reason = ""
        token = str(payload.get("token") or "")
        if token and payload.get("token_scope", "source") == "source" and not preserve_token:
            source.token = self.box.encrypt(token)
        if payload.get("doc_dir"):
            source.doc_dir = str(payload["doc_dir"])
        db.flush()

        verification: dict = {"verified": False}
        if verify:
            verification = self.verify_source(db, source, transport=transport)

        # 브랜치 2역할 (dev/release) upsert — 배포 브랜치 기본값 = default_branch
        default_branch = verification.get("default_branch", "")
        dev_branch = str(payload.get("dev_branch") or "")
        release_branch = str(payload.get("release_branch") or default_branch or "")
        for role, branch in (("dev", dev_branch), ("release", release_branch)):
            row = db.scalars(select(SourceBranch).where(
                SourceBranch.source_id == source.id, SourceBranch.role == role)).first()
            if row is None:
                row = SourceBranch(source_id=source.id, role=role)
                db.add(row)
            if branch:
                if row.branch != branch:
                    row.baseline_sha = str(payload.get("baseline_sha") or "")
                    row.last_processed_sha = ""
                row.branch = branch
                row.enabled = True
            elif not row.branch:
                row.enabled = False   # 브랜치 미지정 역할은 배치 대상 제외
        db.flush()
        return source, verification

    def verify_source(self, db: Session, source: Source, *, transport=None) -> dict:
        """auth 검증 + 자동 조회 (decision-repo-dev-release-registration의 dry-run)."""
        try:
            with self.connector_for_source(db, source, transport=transport) as conn:
                info = conn.verify_access()
                branches = conn.list_branches()
                head = conn.resolve_ref(info.default_branch)
        except Exception as e:  # noqa: BLE001 — 검증 실패는 결과로 반환 (500 아님)
            return {"verified": False, "error": f"{type(e).__name__}: {e}"}
        if not source.doc_dir:
            source.doc_dir = info.namespace_path or source.id
        if not source.label or source.label == source.id:
            source.label = info.name or source.label
        db.flush()
        return {
            "verified": True,
            "name": info.name,
            "default_branch": info.default_branch,
            "namespace_path": info.namespace_path,
            "web_url": info.web_url,
            "branches": branches[:200],
            "head_sha": head,
        }

    # ── 직렬화 (프런트 계약 — 토큰 값은 절대 반환하지 않는다) ──
    def source_view(self, db: Session, source: Source) -> dict:
        inst = source.instance or db.get(ScmInstance, source.instance_id)
        branches = {b.role: b for b in source.branches}
        dev = branches.get("dev")
        release = branches.get("release")
        return {
            "id": source.id,
            "label": source.label,
            "kind": inst.kind if inst else "",
            "url": inst.base_url if inst else "",
            "instance_id": source.instance_id,
            "instance_label": inst.label if inst else "",
            "project_id": source.repo,
            "repo": source.repo,
            "doc_dir": source.doc_dir,
            "themes": source.themes,
            "owner_email": source.owner_email,
            "schedule_cron": source.schedule_cron,
            "enabled": source.enabled,
            "disabled_reason": source.disabled_reason,
            "has_token": bool(source.token or (inst.token if inst else "")),
            "dev_branch": dev.branch if dev else "",
            "release_branch": release.branch if release else "",
            "last_processed_sha": (dev.last_processed_sha if dev else "") or "",
            "release_last_processed_sha": (release.last_processed_sha if release else "") or "",
            "updated_at": source.updated_at.isoformat() if source.updated_at else "",
        }

    # ── docs-hub 타깃 ────────────────────────────────────────
    def upsert_doc_target(self, db: Session, payload: dict[str, Any], *,
                          preserve_token: bool = False) -> DocTarget:
        tid = _slug(str(payload.get("id") or payload.get("label") or "product-common"))
        target = db.get(DocTarget, tid)
        if target is None:
            target = DocTarget(id=tid)
            db.add(target)
        target.label = str(payload.get("label") or target.label or tid)
        target.kind = str(payload.get("kind") or target.kind or "gitlab").lower()
        target.url = str(payload.get("url") or target.url or "").rstrip("/")
        target.project_id = str(payload.get("project_id") or target.project_id or "")
        target.project_path = str(payload.get("project_path") or target.project_path or "")
        target.token_header = str(payload.get("token_header") or target.token_header or "PRIVATE-TOKEN")
        target.default_branch = str(payload.get("default_branch") or target.default_branch or "master")
        if "enabled" in payload:
            target.enabled = bool(payload["enabled"])
        token = str(payload.get("token") or "")
        if token and not preserve_token:
            target.token = self.box.encrypt(token)
        db.flush()
        return target

    def doc_target_view(self, target: DocTarget, *, with_token: bool = False) -> dict:
        view = {
            "id": target.id, "label": target.label, "kind": target.kind,
            "url": target.url, "project_id": target.project_id,
            "project_path": target.project_path, "token_header": target.token_header,
            "default_branch": target.default_branch, "enabled": target.enabled,
            "has_token": bool(target.token),
            "updated_at": target.updated_at.isoformat() if target.updated_at else "",
        }
        if with_token:
            view["token"] = self.box.decrypt(target.token) if target.token else ""
        return view
