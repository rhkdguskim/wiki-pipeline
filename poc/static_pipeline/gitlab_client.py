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
from ..common.retry import with_retry


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

    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        """GET + raise_for_status. 전부 멱등 읽기라 일시 오류(타임아웃·5xx·429)는
        지수 백오프로 재시도한다 — 에이전트 도구 호출이 일시 오류로 실패하면
        LLM 턴(과 max_steps 예산)을 태우며 재요청하게 되므로 시스템 계층에서 흡수.
        영구 오류(404 등)는 즉시 전파한다."""
        def _call() -> httpx.Response:
            resp = self._client.get(url, params=params)
            resp.raise_for_status()
            return resp
        return with_retry(_call, attempts=3)

    def compare(self, from_sha: str, to_sha: str) -> list[dict]:
        """두 sha 사이 변경 파일 목록. 각 원소는 new_path/old_path/new_file/deleted_file 등."""
        url = f"{self.base}/projects/{self.project}/repository/compare"
        return self._get(url, params={"from": from_sha, "to": to_sha}).json().get("diffs", [])

    def raw_file(self, path: str, ref: str) -> str:
        """파일 원문. 바이너리/미존재는 예외."""
        enc = quote(path, safe="")
        url = f"{self.base}/projects/{self.project}/repository/files/{enc}/raw"
        return self._get(url, params={"ref": ref}).text

    def list_tree(self, path: str = "", ref: str = "HEAD") -> list[dict]:
        """디렉터리 트리 (name/type/path). 단일 페이지(최대 100)."""
        url = f"{self.base}/projects/{self.project}/repository/tree"
        return self._get(url, params={"path": path, "ref": ref, "per_page": 100}).json()

    def list_tree_all(self, ref: str = "HEAD", recursive: bool = True) -> list[dict]:
        """레포 전체 트리를 페이지네이션으로 끝까지 모은다 (init/backfill용)."""
        url = f"{self.base}/projects/{self.project}/repository/tree"
        out: list[dict] = []
        page = 1
        while True:
            resp = self._get(url, params={
                "ref": ref, "recursive": str(recursive).lower(),
                "per_page": 100, "page": page,
            })
            batch = resp.json()
            if not batch:
                break
            out.extend(batch)
            next_page = resp.headers.get("x-next-page", "")
            if not next_page:
                break
            page = int(next_page)
        return out

    def resolve_ref(self, ref: str) -> str:
        """브랜치명/태그/short-sha -> 전체 커밋 sha (상태 포인터는 항상 전체 sha로 저장)."""
        enc = quote(ref, safe="")
        url = f"{self.base}/projects/{self.project}/repository/commits/{enc}"
        return self._get(url).json()["id"]

    def default_branch(self) -> str:
        url = f"{self.base}/projects/{self.project}"
        return self._get(url).json().get("default_branch", "master")

    def project_name(self) -> str:
        """프로젝트 표시 이름 (init 문서의 저장소 서술용)."""
        url = f"{self.base}/projects/{self.project}"
        return self._get(url).json().get("name", "")

    def close(self) -> None:
        self._client.close()
