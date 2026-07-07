"""docs-hub 제출 — 두 파이프라인이 공유하는 MR 게이트 (decision-mr-review-gate).

관리 서버·docs-hub·MR 게이트는 두 파이프라인의 유일한 공유 접점이다
(decision-manual-pipeline-separate) — 그래서 이 모듈만 common에 있다.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any
from urllib import error, parse, request


_PATH_RE = re.compile(r"[^A-Za-z0-9._/-]+")


@dataclass(frozen=True)
class DocHubTarget:
    id: str
    label: str
    kind: str
    url: str
    project_id: str = ""
    project_path: str = ""
    token: str = ""
    token_header: str = "PRIVATE-TOKEN"
    default_branch: str = "master"
    enabled: bool = False

    @property
    def project_ref(self) -> str:
        return self.project_id or self.project_path

    @property
    def api_base(self) -> str:
        url = self.url.rstrip("/")
        if self.project_path and url.endswith(self.project_path.rstrip("/")):
            url = url[: -len(self.project_path.rstrip("/"))].rstrip("/")
        return f"{url}/api/v4"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DocHubTarget":
        return cls(
            id=str(raw.get("id") or "product-common"),
            label=str(raw.get("label") or raw.get("id") or "product-common"),
            kind=str(raw.get("kind") or "gitlab").lower(),
            url=str(raw.get("url") or "").rstrip("/"),
            project_id=str(raw.get("project_id") or ""),
            project_path=str(raw.get("project_path") or ""),
            token=str(raw.get("token") or ""),
            token_header=str(raw.get("token_header") or "PRIVATE-TOKEN") or "PRIVATE-TOKEN",
            default_branch=str(raw.get("default_branch") or "master"),
            enabled=bool(raw.get("enabled")),
        )


def submit_mr_stub(name: str, path: Path, enabled: bool) -> str:
    if enabled:
        return f"[MR 제출 훅] {name}: 실제 MR API 연결 지점 (미구현)"
    return f"[MR 스텁] {name} -> {path.name} (DOCSHUB_MR_ENABLED=false, 로컬 저장만)"


def _clean_segment(value: str, fallback: str = "unknown") -> str:
    value = _PATH_RE.sub("-", value.strip().replace("\\", "/"))
    value = re.sub(r"/+", "/", value).strip("/.")
    return value or fallback


def _artifact_relpath(artifact: dict[str, Any], *, source_id: str, run_id: str) -> str:
    raw = str(artifact.get("path") or artifact.get("name") or "artifact.md").replace("\\", "/")
    raw = raw.lstrip("/")
    for prefix in (source_id, run_id):
        if prefix and raw.startswith(f"{prefix}/"):
            raw = raw[len(prefix) + 1:]
    return _clean_segment(raw, artifact.get("name") or "artifact.md")


def _generated_artifacts(summary: dict[str, Any], out_dir: Path) -> list[dict[str, Any]]:
    generated = summary.get("generated") or []
    artifacts = []
    seen = set()
    for item in generated:
        raw = str(item.get("path") or "").strip()
        if not raw or not raw.endswith(".md") or raw in seen:
            continue
        seen.add(raw)
        path = (out_dir / raw).resolve()
        size = path.stat().st_size if path.is_file() else 0
        artifacts.append({
            "path": raw,
            "name": Path(raw).name,
            "size": size,
            "stage": item.get("stage", ""),
            "warned": bool(item.get("warned")),
        })
    return artifacts


def infer_branch_role(summary: dict[str, Any], source: dict[str, Any] | None = None) -> str:
    pipeline = str(summary.get("pipeline_id") or "").lower()
    run_id = str(summary.get("run_id") or "").lower()
    if "manual" in pipeline or "release" in pipeline or "release" in run_id:
        return "release"
    if source and not source.get("dev_branch") and source.get("release_branch"):
        return "release"
    return "dev"


def build_mr_plan(
    summary: dict[str, Any],
    *,
    target: dict[str, Any],
    source: dict[str, Any] | None,
    out_dir: Path,
) -> dict[str, Any]:
    """Map generated Markdown artifacts to product-common paths without mutating GitLab."""
    target_model = DocHubTarget.from_dict(target)
    source_id = str(summary.get("source_id") or (source.get("id") if source else "")) or "legacy"
    source_label = str(source.get("label") if source else source_id) if source else source_id
    doc_root = str(source.get("doc_dir") if source else "") or source_id
    branch_role = infer_branch_role(summary, source)
    pipeline = _clean_segment(str(summary.get("pipeline_id") or "pipeline"))
    run_id = _clean_segment(str(summary.get("run_id") or "run"))
    branch_name = f"docs/agent/{source_id}/{run_id}"[:180].rstrip("/")
    artifacts = _generated_artifacts(summary, out_dir)
    if not artifacts:
        artifacts = [a for a in summary.get("artifacts", []) if str(a.get("name") or a.get("path") or "").endswith(".md")]
    files = []
    for artifact in artifacts:
        rel = _artifact_relpath(artifact, source_id=source_id, run_id=run_id)
        target_path = "/".join([
            _clean_segment(doc_root, source_id),
            branch_role,
            pipeline,
            rel,
        ])
        files.append({
            "local_path": str(artifact.get("path") or ""),
            "target_path": target_path,
            "size": int(artifact.get("size") or 0),
            "action": "upsert",
        })
    warnings = []
    if not files:
        warnings.append("MR에 포함할 Markdown 산출물이 없습니다.")
    if target_model.kind != "gitlab":
        warnings.append("현재 제출 구현은 GitLab target만 지원합니다.")
    if not target_model.project_ref:
        warnings.append("GitLab project_id 또는 project_path가 필요합니다.")
    return {
        "run_id": summary.get("run_id"),
        "source_id": source_id,
        "source_label": source_label,
        "target": {
            "id": target_model.id,
            "label": target_model.label,
            "kind": target_model.kind,
            "url": target_model.url,
            "project_id": target_model.project_id,
            "project_path": target_model.project_path,
            "default_branch": target_model.default_branch,
            "enabled": target_model.enabled,
            "has_token": bool(target_model.token),
        },
        "base_branch": target_model.default_branch,
        "branch_name": branch_name,
        "branch_role": branch_role,
        "title": f"[AI Docs] {source_label} {run_id}",
        "description": (
            f"wiki-pipeline run `{run_id}` generated {len(files)} document artifact(s).\n\n"
            f"- Source: `{source_id}`\n"
            f"- Pipeline: `{summary.get('pipeline_id') or 'pipeline'}`\n"
            f"- Target role: `{branch_role}`\n"
        ),
        "files": files,
        "file_count": len(files),
        "total_bytes": sum(f["size"] for f in files),
        "warnings": warnings,
        "can_submit": target_model.enabled and bool(target_model.token) and target_model.kind == "gitlab"
                      and bool(target_model.project_ref) and bool(files),
        "out_dir": str(out_dir),
    }


def read_plan_files(plan: dict[str, Any], out_dir: Path) -> list[dict[str, str]]:
    payloads = []
    for file in plan.get("files", []):
        rel = Path(str(file.get("local_path") or ""))
        path = (out_dir / rel).resolve()
        if out_dir.resolve() not in (path, *path.parents):
            raise ValueError(f"산출물 경로가 out_dir 밖입니다: {rel}")
        if not path.is_file():
            raise ValueError(f"산출물 파일을 찾을 수 없습니다: {rel}")
        payloads.append({
            "target_path": str(file["target_path"]),
            "content": path.read_text(encoding="utf-8"),
        })
    return payloads


class GitLabDocHubClient:
    def __init__(self, target: DocHubTarget, *, timeout: float = 30.0):
        self.target = target
        self.timeout = timeout
        if not target.project_ref:
            raise ValueError("GitLab project_id 또는 project_path가 필요합니다.")
        if not target.token:
            raise ValueError("GitLab token이 필요합니다.")

    @property
    def project_api(self) -> str:
        project = parse.quote(self.target.project_ref, safe="")
        return f"{self.target.api_base}/projects/{project}"

    def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {self.target.token_header: self.target.token}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as res:  # noqa: S310 - target is user-configured GitLab
                body = res.read().decode("utf-8", "replace")
                return json.loads(body) if body else {}
        except error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"GitLab API {method} {url} failed: HTTP {e.code} {body[:400]}") from e

    def ensure_branch(self, branch: str, ref: str) -> dict[str, Any]:
        encoded = parse.quote(branch, safe="")
        try:
            return self._request("GET", f"{self.project_api}/repository/branches/{encoded}")
        except RuntimeError as e:
            if "HTTP 404" not in str(e):
                raise
        qs = parse.urlencode({"branch": branch, "ref": ref})
        return self._request("POST", f"{self.project_api}/repository/branches?{qs}")

    def upsert_file(self, *, branch: str, path: str, content: str, message: str) -> dict[str, Any]:
        encoded = parse.quote(path, safe="")
        payload = {"branch": branch, "content": content, "commit_message": message}
        try:
            return self._request("PUT", f"{self.project_api}/repository/files/{encoded}", payload)
        except RuntimeError as e:
            if "HTTP 404" not in str(e):
                raise
        return self._request("POST", f"{self.project_api}/repository/files/{encoded}", payload)

    def create_merge_request(self, *, source_branch: str, target_branch: str, title: str, description: str) -> dict[str, Any]:
        payload = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
            "remove_source_branch": True,
        }
        return self._request("POST", f"{self.project_api}/merge_requests", payload)


def submit_gitlab_mr(plan: dict[str, Any], *, target: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    target_model = DocHubTarget.from_dict(target)
    if not plan.get("can_submit"):
        raise ValueError("MR 제출 조건이 충족되지 않았습니다.")
    client = GitLabDocHubClient(target_model)
    branch = str(plan["branch_name"])
    base = str(plan["base_branch"])
    client.ensure_branch(branch, base)
    files = read_plan_files(plan, out_dir)
    commit_message = f"{plan['title']} ({plan['run_id']})"
    updated = [
        client.upsert_file(branch=branch, path=f["target_path"], content=f["content"], message=commit_message)
        for f in files
    ]
    mr = client.create_merge_request(
        source_branch=branch,
        target_branch=base,
        title=str(plan["title"]),
        description=str(plan["description"]),
    )
    return {
        "ok": True,
        "branch": branch,
        "files": len(updated),
        "merge_request": {
            "id": mr.get("id"),
            "iid": mr.get("iid"),
            "web_url": mr.get("web_url"),
            "state": mr.get("state"),
        },
    }
