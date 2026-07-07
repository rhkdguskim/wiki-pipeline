"""커넥터 팩토리 — kind·base_url·token으로 구현체를 고른다.

소스 등록의 단위는 "SCM 인스턴스 × 레포" (decision-scm-multi-instance-github-mvp):
- gitlab: base_url = 인스턴스 URL(사내·gitlab.com), repo = project id 또는 full path
- github: base_url 생략 시 github.com(api.github.com), GHE는 https://<host>/api/v3,
          repo = "owner/repo"
"""
from __future__ import annotations

from typing import Any

import httpx

from .base import ScmConnector
from .github import GitHubConnector
from .gitlab import GitLabConnector

_GITHUB_HOSTS = ("github.com", "www.github.com", "api.github.com")


def _github_api_base(url: str) -> str:
    """웹 URL을 API base로 정규화 — github.com -> api.github.com, GHE -> /api/v3."""
    url = (url or "").rstrip("/")
    if not url:
        return "https://api.github.com"
    host = url.split("://", 1)[-1].split("/", 1)[0].lower()
    if host in _GITHUB_HOSTS:
        return "https://api.github.com"
    if url.endswith("/api/v3"):
        return url
    return f"{url}/api/v3"


def make_connector(*, kind: str, url: str, token: str, repo: str,
                   token_header: str = "PRIVATE-TOKEN", timeout: float = 30.0,
                   transport: httpx.BaseTransport | None = None) -> ScmConnector:
    kind = (kind or "gitlab").strip().lower()
    if kind == "gitlab":
        return GitLabConnector(base_url=url, token=token, repo=repo,
                               token_header=token_header, timeout=timeout, transport=transport)
    if kind == "github":
        return GitHubConnector(base_url=_github_api_base(url), token=token, repo=repo,
                               timeout=timeout, transport=transport)
    raise ValueError(f"지원하지 않는 SCM kind: {kind} (gitlab | github)")


def connector_for_settings(settings: Any) -> ScmConnector:
    """활성 source로 스코프된 Settings에서 커넥터 생성 (파이프라인 진입점용)."""
    return make_connector(
        kind=getattr(settings, "source_kind", "gitlab"),
        url=settings.gitlab_url,
        token=settings.gitlab_token,
        token_header=settings.gitlab_token_header,
        repo=str(settings.gitlab_project_id),
    )


def connector_for_target(target: dict[str, Any],
                         transport: httpx.BaseTransport | None = None) -> ScmConnector:
    """doc target(dict — docshub.DocHubTarget 원형)에서 커넥터 생성 (제출용)."""
    return make_connector(
        kind=str(target.get("kind") or "gitlab"),
        url=str(target.get("url") or ""),
        token=str(target.get("token") or ""),
        token_header=str(target.get("token_header") or "PRIVATE-TOKEN"),
        repo=str(target.get("project_id") or target.get("project_path") or ""),
        transport=transport,
    )
