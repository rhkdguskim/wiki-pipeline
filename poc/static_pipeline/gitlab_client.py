"""사내 GitLab REST 클라이언트 — compare / raw file 조회 (httpx).

실측 확인(entity-mirero-gitlab):
- compare: GET /projects/:id/repository/compare?from=&to= -> diffs[].new_path
- raw file: GET /projects/:id/repository/files/:path/raw?ref=
토큰은 PRIVATE-TOKEN 헤더(또는 Authorization: Bearer). 자격증명은 Settings에서만.
"""
from __future__ import annotations

from urllib.parse import quote

import httpx

from ..common.config import Settings


class GitLabClient:
    def __init__(self, settings: Settings):
        self.base = settings.gitlab_url.rstrip("/") + "/api/v4"
        self.project = quote(str(settings.gitlab_project_id), safe="")
        header = settings.gitlab_token_header
        if header.lower() == "authorization":
            headers = {"Authorization": f"Bearer {settings.gitlab_token}"}
        else:
            headers = {"PRIVATE-TOKEN": settings.gitlab_token}
        self._client = httpx.Client(headers=headers, timeout=30.0)

    def compare(self, from_sha: str, to_sha: str) -> list[dict]:
        """두 sha 사이 변경 파일 목록. 각 원소는 new_path/old_path/new_file/deleted_file 등."""
        url = f"{self.base}/projects/{self.project}/repository/compare"
        resp = self._client.get(url, params={"from": from_sha, "to": to_sha})
        resp.raise_for_status()
        return resp.json().get("diffs", [])

    def raw_file(self, path: str, ref: str) -> str:
        """파일 원문. 바이너리/미존재는 예외."""
        enc = quote(path, safe="")
        url = f"{self.base}/projects/{self.project}/repository/files/{enc}/raw"
        resp = self._client.get(url, params={"ref": ref})
        resp.raise_for_status()
        return resp.text

    def list_tree(self, path: str = "", ref: str = "HEAD") -> list[dict]:
        """디렉터리 트리 (name/type/path). 단일 페이지(최대 100)."""
        url = f"{self.base}/projects/{self.project}/repository/tree"
        resp = self._client.get(
            url, params={"path": path, "ref": ref, "per_page": 100}
        )
        resp.raise_for_status()
        return resp.json()

    def list_tree_all(self, ref: str = "HEAD", recursive: bool = True) -> list[dict]:
        """레포 전체 트리를 페이지네이션으로 끝까지 모은다 (init/backfill용)."""
        url = f"{self.base}/projects/{self.project}/repository/tree"
        out: list[dict] = []
        page = 1
        while True:
            resp = self._client.get(url, params={
                "ref": ref, "recursive": str(recursive).lower(),
                "per_page": 100, "page": page,
            })
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            out.extend(batch)
            next_page = resp.headers.get("x-next-page", "")
            if not next_page:
                break
            page = int(next_page)
        return out

    def default_branch(self) -> str:
        url = f"{self.base}/projects/{self.project}"
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json().get("default_branch", "master")

    def close(self) -> None:
        self._client.close()
