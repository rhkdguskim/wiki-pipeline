"""커넥터 팩토리 — kind 라우팅·GitHub API base 정규화."""
from __future__ import annotations

import pytest

from backend.connectors import GitHubConnector, GitLabConnector, make_connector
from backend.connectors.factory import _github_api_base


def test_kind_routing():
    gl = make_connector(kind="gitlab", url="http://wish.mirero.co.kr", token="t", repo="947")
    assert isinstance(gl, GitLabConnector)
    assert gl.api == "http://wish.mirero.co.kr/api/v4"
    gh = make_connector(kind="github", url="", token="t", repo="octo/demo")
    assert isinstance(gh, GitHubConnector)
    assert gh.api == "https://api.github.com"


def test_gitlab_com_instance():
    gl = make_connector(kind="gitlab", url="https://gitlab.com", token="t", repo="grp/proj")
    assert isinstance(gl, GitLabConnector)
    assert gl.api == "https://gitlab.com/api/v4"


@pytest.mark.parametrize("url,expected", [
    ("", "https://api.github.com"),
    ("https://github.com", "https://api.github.com"),
    ("https://api.github.com", "https://api.github.com"),
    ("https://ghe.corp.local", "https://ghe.corp.local/api/v3"),
    ("https://ghe.corp.local/api/v3", "https://ghe.corp.local/api/v3"),
])
def test_github_api_base_normalization(url, expected):
    assert _github_api_base(url) == expected


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        make_connector(kind="svn", url="http://x", token="t", repo="r")


def test_github_repo_format_required():
    with pytest.raises(ValueError):
        make_connector(kind="github", url="", token="t", repo="not-owner-repo")
