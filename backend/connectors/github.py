"""GitHub 커넥터 — github.com·GitHub Enterprise 공용 (base_url 주입식).

GitLab과 동일한 정규화 계약을 지킨다 (base.ScmConnector 참조):
- compare: GET /repos/{repo}/compare/{base}...{head} 의 files[] -> 변경 파일 dict
- 트리: git/trees?recursive=1 (list_tree_all) / contents API (list_tree)
- change request = Pull Request (iid 자리에 number 사용)
"""
from __future__ import annotations

import base64
from urllib.parse import quote

import httpx

from ..common.retry import with_retry
from .base import (
    ChangeRequest,
    ProjectInfo,
    ScmAuthError,
    ScmConnector,
    ScmError,
    ScmNotFoundError,
    ScmRateLimitError,
)

_API_VERSION = "2022-11-28"
# compare API는 페이지당 최대 300개 파일을 돌려준다 — 페이지네이션으로 끝까지 수집.
_MAX_COMPARE_PAGES = 20


def _is_rate_limited(resp: httpx.Response) -> bool:
    """GitHub rate limit 신호: 1차(primary) 한도는 403 + X-RateLimit-Remaining: 0,
    2차(secondary/abuse) 한도는 403/429 + Retry-After 헤더 또는 본문에 "rate limit" 문구."""
    if resp.status_code == 429:
        return True
    if resp.status_code != 403:
        return False
    if resp.headers.get("x-ratelimit-remaining") == "0":
        return True
    if resp.headers.get("retry-after"):
        return True
    return "rate limit" in resp.text.lower()


def _wrap_http_error(e: httpx.HTTPStatusError) -> ScmError:
    code = e.response.status_code
    body = e.response.text[:400]
    msg = f"GitHub API {e.request.method} {e.request.url} failed: HTTP {code} {body}"
    if code == 404:
        return ScmNotFoundError(msg)
    if _is_rate_limited(e.response):
        return ScmRateLimitError(msg, status_code=code)
    if code in (401, 403):
        return ScmAuthError(msg, status_code=code)
    return ScmError(msg, status_code=code)


class GitHubConnector(ScmConnector):
    kind = "github"

    def __init__(self, *, token: str, repo: str, base_url: str = "https://api.github.com",
                 timeout: float = 30.0, retry_attempts: int = 3,
                 transport: httpx.BaseTransport | None = None):
        if not repo or "/" not in repo:
            raise ValueError("GitHub repo는 'owner/repo' 형식이어야 합니다.")
        self.api = (base_url or "https://api.github.com").rstrip("/")
        self.repo = repo.strip("/")
        self.owner = self.repo.split("/", 1)[0]
        self._retry_attempts = retry_attempts
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(headers=headers, timeout=timeout, transport=transport)

    def _request(self, method: str, url: str, *, params: dict | None = None,
                 json: dict | None = None, headers: dict | None = None,
                 retry: bool = True) -> httpx.Response:
        def _call() -> httpx.Response:
            resp = self._client.request(method, url, params=params, json=json, headers=headers)
            resp.raise_for_status()
            return resp

        try:
            if retry:
                return with_retry(_call, attempts=self._retry_attempts)
            return _call()
        except httpx.HTTPStatusError as e:
            raise _wrap_http_error(e) from e
        except httpx.HTTPError as e:
            raise ScmError(f"GitHub API {method} {url} failed: {type(e).__name__}: {e}") from e

    def _get(self, url: str, params: dict | None = None,
             headers: dict | None = None) -> httpx.Response:
        return self._request("GET", url, params=params, headers=headers)

    @property
    def _repo(self) -> str:
        return f"{self.api}/repos/{self.repo}"

    # ── read ────────────────────────────────────────────────────
    def compare(self, from_sha: str, to_sha: str) -> list[dict]:
        basehead = f"{quote(from_sha, safe='')}...{quote(to_sha, safe='')}"
        seen: dict[str, dict] = {}
        for page in range(1, _MAX_COMPARE_PAGES + 1):
            data = self._get(f"{self._repo}/compare/{basehead}",
                             params={"per_page": 100, "page": page}).json()
            files = data.get("files") or []
            for f in files:
                path = f.get("filename", "")
                if not path or path in seen:
                    continue
                status = f.get("status", "modified")
                seen[path] = {
                    "new_path": path,
                    "old_path": f.get("previous_filename") or path,
                    "new_file": status == "added",
                    "deleted_file": status == "removed",
                    "renamed_file": status == "renamed",
                }
            # files가 300개 미만이면 마지막 페이지 (compare 파일 페이지 상한 300).
            if len(files) < 300:
                break
        return list(seen.values())

    def raw_file(self, path: str, ref: str) -> str:
        enc = quote(path.lstrip("/"))
        resp = self._get(f"{self._repo}/contents/{enc}", params={"ref": ref},
                         headers={"Accept": "application/vnd.github.raw+json"})
        return resp.text

    def list_tree(self, path: str = "", ref: str = "HEAD") -> list[dict]:
        ref = self._norm_ref(ref)
        enc = quote(path.strip("/"))
        url = f"{self._repo}/contents/{enc}" if enc else f"{self._repo}/contents"
        entries = self._get(url, params={"ref": ref}).json()
        if isinstance(entries, dict):   # path가 파일 1개를 가리키는 경우
            entries = [entries]
        return [{
            "path": e.get("path", ""),
            "name": e.get("name", ""),
            "type": "tree" if e.get("type") == "dir" else "blob",
        } for e in entries]

    def list_tree_all(self, ref: str = "HEAD", recursive: bool = True) -> list[dict]:
        sha = self.resolve_ref(self._norm_ref(ref))
        params = {"recursive": "1"} if recursive else None
        data = self._get(f"{self._repo}/git/trees/{sha}", params=params).json()
        return [{
            "path": e.get("path", ""),
            "name": e.get("path", "").rsplit("/", 1)[-1],
            "type": e.get("type", "blob"),
        } for e in data.get("tree", [])]

    def _norm_ref(self, ref: str) -> str:
        return self.default_branch() if (not ref or ref.upper() == "HEAD") else ref

    def resolve_ref(self, ref: str) -> str:
        enc = quote(self._norm_ref(ref), safe="")
        return self._get(f"{self._repo}/commits/{enc}").json()["sha"]

    def default_branch(self) -> str:
        return self._get(self._repo).json().get("default_branch", "main")

    def list_branches(self) -> list[str]:
        out: list[str] = []
        page = 1
        while True:
            batch = self._get(f"{self._repo}/branches",
                              params={"per_page": 100, "page": page}).json()
            if not batch:
                break
            out.extend(b.get("name", "") for b in batch)
            if len(batch) < 100:
                break
            page += 1
        return [b for b in out if b]

    def project_info(self) -> ProjectInfo:
        data = self._get(self._repo).json()
        return ProjectInfo(
            name=data.get("name", ""),
            default_branch=data.get("default_branch", "main"),
            namespace_path=data.get("full_name", self.repo),
            web_url=data.get("html_url", ""),
            raw=data,
        )

    # ── write ───────────────────────────────────────────────────
    def ensure_branch(self, branch: str, ref: str) -> dict:
        enc = quote(branch, safe="")
        try:
            return self._get(f"{self._repo}/git/ref/heads/{enc}").json()
        except ScmNotFoundError:
            pass
        sha = self.resolve_ref(ref)
        return self._request("POST", f"{self._repo}/git/refs", json={
            "ref": f"refs/heads/{branch}", "sha": sha,
        }, retry=False).json()

    def upsert_file(self, *, branch: str, path: str, content: str, message: str) -> dict:
        enc = quote(path.lstrip("/"))
        payload: dict = {
            "message": message, "branch": branch,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        try:
            existing = self._get(f"{self._repo}/contents/{enc}", params={"ref": branch}).json()
            if isinstance(existing, dict) and existing.get("sha"):
                payload["sha"] = existing["sha"]   # 갱신에는 기존 blob sha 필요
        except ScmNotFoundError:
            pass
        return self._request("PUT", f"{self._repo}/contents/{enc}",
                             json=payload, retry=False).json()

    def _to_cr(self, pr: dict) -> ChangeRequest:
        return ChangeRequest(
            id=str(pr.get("number", "")), web_url=pr.get("html_url", ""),
            state=pr.get("state", ""), title=pr.get("title", ""), raw=pr,
        )

    def find_open_change_request(self, *, source_branch: str, target_branch: str) -> ChangeRequest | None:
        prs = self._get(f"{self._repo}/pulls", params={
            "state": "open", "head": f"{self.owner}:{source_branch}", "base": target_branch,
        }).json()
        return self._to_cr(prs[0]) if prs else None

    def create_change_request(self, *, source_branch: str, target_branch: str,
                              title: str, description: str) -> ChangeRequest:
        pr = self._request("POST", f"{self._repo}/pulls", json={
            "title": title, "head": source_branch, "base": target_branch, "body": description,
        }, retry=False).json()
        return self._to_cr(pr)

    def update_change_request(self, cr_id: str, *, title: str, description: str) -> ChangeRequest:
        pr = self._request("PATCH", f"{self._repo}/pulls/{cr_id}",
                           json={"title": title, "body": description}, retry=False).json()
        return self._to_cr(pr)

    def close(self) -> None:
        self._client.close()
