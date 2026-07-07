"""GitLab 커넥터 — 사내 GitLab·gitlab.com 공용 (base_url/token 주입식).

실측 확인(entity-mirero-gitlab): compare / raw file / tree / commits / MR API.
기존 static_pipeline.gitlab_client(읽기)와 common.docshub(쓰기)를 이 계약으로 흡수.
"""
from __future__ import annotations

from urllib.parse import quote

import httpx

from ..common.retry import with_retry
from .base import ChangeRequest, ProjectInfo, ScmAuthError, ScmConnector, ScmError, ScmNotFoundError


def _wrap_http_error(e: httpx.HTTPStatusError) -> ScmError:
    code = e.response.status_code
    body = e.response.text[:400]
    msg = f"GitLab API {e.request.method} {e.request.url} failed: HTTP {code} {body}"
    if code == 404:
        return ScmNotFoundError(msg)
    if code in (401, 403):
        return ScmAuthError(msg, status_code=code)
    return ScmError(msg, status_code=code)


class GitLabConnector(ScmConnector):
    kind = "gitlab"

    def __init__(self, *, base_url: str, token: str, repo: str,
                 token_header: str = "PRIVATE-TOKEN", timeout: float = 30.0,
                 retry_attempts: int = 3, transport: httpx.BaseTransport | None = None):
        if not base_url:
            raise ValueError("GitLab base_url이 필요합니다.")
        if not repo:
            raise ValueError("GitLab project id 또는 full path가 필요합니다.")
        self.api = base_url.rstrip("/") + "/api/v4"
        self.project = quote(str(repo), safe="")
        self._retry_attempts = retry_attempts
        if token_header.lower() == "authorization":
            headers = {"Authorization": f"Bearer {token}"}
        else:
            headers = {"PRIVATE-TOKEN": token}
        self._client = httpx.Client(headers=headers, timeout=timeout, transport=transport)

    # ── 공통 요청 (읽기는 멱등이라 일시 오류 재시도, 쓰기는 1회) ──
    def _request(self, method: str, url: str, *, params: dict | None = None,
                 json: dict | None = None, retry: bool = True) -> httpx.Response:
        def _call() -> httpx.Response:
            resp = self._client.request(method, url, params=params, json=json)
            resp.raise_for_status()
            return resp

        try:
            if retry:
                return with_retry(_call, attempts=self._retry_attempts)
            return _call()
        except httpx.HTTPStatusError as e:
            raise _wrap_http_error(e) from e
        except httpx.HTTPError as e:
            raise ScmError(f"GitLab API {method} {url} failed: {type(e).__name__}: {e}") from e

    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        return self._request("GET", url, params=params)

    @property
    def _proj(self) -> str:
        return f"{self.api}/projects/{self.project}"

    # ── read ────────────────────────────────────────────────────
    def compare(self, from_sha: str, to_sha: str) -> list[dict]:
        data = self._get(f"{self._proj}/repository/compare",
                         params={"from": from_sha, "to": to_sha}).json()
        out = []
        for d in data.get("diffs", []):
            out.append({
                "new_path": d.get("new_path", ""),
                "old_path": d.get("old_path", ""),
                "new_file": bool(d.get("new_file")),
                "deleted_file": bool(d.get("deleted_file")),
                "renamed_file": bool(d.get("renamed_file")),
            })
        return out

    def raw_file(self, path: str, ref: str) -> str:
        enc = quote(path, safe="")
        return self._get(f"{self._proj}/repository/files/{enc}/raw", params={"ref": ref}).text

    def list_tree(self, path: str = "", ref: str = "HEAD") -> list[dict]:
        entries = self._get(f"{self._proj}/repository/tree",
                            params={"path": path, "ref": ref, "per_page": 100}).json()
        return [{"path": e.get("path", ""), "name": e.get("name", ""),
                 "type": e.get("type", "blob")} for e in entries]

    def list_tree_all(self, ref: str = "HEAD", recursive: bool = True) -> list[dict]:
        out: list[dict] = []
        page = 1
        while True:
            resp = self._get(f"{self._proj}/repository/tree", params={
                "ref": ref, "recursive": str(recursive).lower(),
                "per_page": 100, "page": page,
            })
            batch = resp.json()
            if not batch:
                break
            out.extend({"path": e.get("path", ""), "name": e.get("name", ""),
                        "type": e.get("type", "blob")} for e in batch)
            next_page = resp.headers.get("x-next-page", "")
            if not next_page:
                break
            page = int(next_page)
        return out

    def resolve_ref(self, ref: str) -> str:
        enc = quote(ref, safe="")
        return self._get(f"{self._proj}/repository/commits/{enc}").json()["id"]

    def default_branch(self) -> str:
        return self._get(self._proj).json().get("default_branch", "master")

    def project_info(self) -> ProjectInfo:
        data = self._get(self._proj).json()
        return ProjectInfo(
            name=data.get("name", ""),
            default_branch=data.get("default_branch", "master"),
            namespace_path=data.get("path_with_namespace", ""),
            web_url=data.get("web_url", ""),
            raw=data,
        )

    # ── write ───────────────────────────────────────────────────
    def ensure_branch(self, branch: str, ref: str) -> dict:
        enc = quote(branch, safe="")
        try:
            return self._get(f"{self._proj}/repository/branches/{enc}").json()
        except ScmNotFoundError:
            pass
        return self._request("POST", f"{self._proj}/repository/branches",
                             params={"branch": branch, "ref": ref}, retry=False).json()

    def upsert_file(self, *, branch: str, path: str, content: str, message: str) -> dict:
        enc = quote(path, safe="")
        payload = {"branch": branch, "content": content, "commit_message": message}
        try:
            return self._request("PUT", f"{self._proj}/repository/files/{enc}",
                                 json=payload, retry=False).json()
        except ScmNotFoundError:
            return self._request("POST", f"{self._proj}/repository/files/{enc}",
                                 json=payload, retry=False).json()

    def _to_cr(self, mr: dict) -> ChangeRequest:
        return ChangeRequest(
            id=str(mr.get("iid", "")), web_url=mr.get("web_url", ""),
            state=mr.get("state", ""), title=mr.get("title", ""), raw=mr,
        )

    def find_open_change_request(self, *, source_branch: str, target_branch: str) -> ChangeRequest | None:
        mrs = self._get(f"{self._proj}/merge_requests", params={
            "state": "opened", "source_branch": source_branch, "target_branch": target_branch,
        }).json()
        return self._to_cr(mrs[0]) if mrs else None

    def create_change_request(self, *, source_branch: str, target_branch: str,
                              title: str, description: str) -> ChangeRequest:
        mr = self._request("POST", f"{self._proj}/merge_requests", json={
            "source_branch": source_branch, "target_branch": target_branch,
            "title": title, "description": description, "remove_source_branch": True,
        }, retry=False).json()
        return self._to_cr(mr)

    def update_change_request(self, cr_id: str, *, title: str, description: str) -> ChangeRequest:
        mr = self._request("PUT", f"{self._proj}/merge_requests/{cr_id}",
                           json={"title": title, "description": description}, retry=False).json()
        return self._to_cr(mr)

    def close(self) -> None:
        self._client.close()
