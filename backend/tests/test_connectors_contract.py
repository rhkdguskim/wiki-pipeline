"""커넥터 계약 테스트 — 동일 스위트를 GitLab/GitHub 구현에 적용.

decision-scm-connector-abstraction: 두 커넥터는 동등 1급이며 같은 정규화 계약을 지킨다.
"""
from __future__ import annotations

import pytest

from backend.connectors import ScmNotFoundError
from backend.connectors.github import GitHubConnector
from backend.connectors.gitlab import GitLabConnector

from .fake_scm import HEAD_SHA, OLD_SHA, FakeGitHub, FakeGitLab


def _gitlab():
    fake = FakeGitLab()
    conn = GitLabConnector(base_url="http://gitlab.local", token="t", repo="grp/demo",
                           retry_attempts=1, transport=fake.transport)
    return conn, fake


def _github():
    fake = FakeGitHub()
    conn = GitHubConnector(token="t", repo="octo/demo",
                           retry_attempts=1, transport=fake.transport)
    return conn, fake


@pytest.fixture(params=["gitlab", "github"])
def scm(request):
    conn, fake = _gitlab() if request.param == "gitlab" else _github()
    yield conn, fake
    conn.close()


def test_compare_normalization(scm):
    conn, _ = scm
    changes = conn.compare(OLD_SHA, HEAD_SHA)
    by_path = {c["new_path"]: c for c in changes}
    assert set(by_path) == {"src/app.py", "docs/new.md", "src/gone.py", "src/util.py"}
    assert by_path["docs/new.md"]["new_file"] is True
    assert by_path["src/gone.py"]["deleted_file"] is True
    assert by_path["src/util.py"]["renamed_file"] is True
    assert by_path["src/util.py"]["old_path"] == "src/old_util.py"
    assert by_path["src/app.py"]["new_file"] is False


def test_compare_unknown_sha_raises_not_found(scm):
    conn, _ = scm
    with pytest.raises(ScmNotFoundError):
        conn.compare("zzz", HEAD_SHA)


def test_raw_file(scm):
    conn, _ = scm
    assert conn.raw_file("src/app.py", HEAD_SHA) == "print('hi')\n"
    with pytest.raises(ScmNotFoundError):
        conn.raw_file("nope.md", HEAD_SHA)


def test_list_tree_root(scm):
    conn, _ = scm
    entries = conn.list_tree("", "HEAD")
    types = {e["path"]: e["type"] for e in entries}
    assert types["README.md"] == "blob"
    assert types["src"] == "tree"


def test_list_tree_all_blobs(scm):
    conn, _ = scm
    entries = conn.list_tree_all(ref="HEAD", recursive=True)
    blobs = {e["path"] for e in entries if e["type"] == "blob"}
    assert {"README.md", "src/app.py", "src/util.py"} <= blobs


def test_resolve_ref_and_default_branch(scm):
    conn, _ = scm
    assert conn.default_branch() == "main"
    assert conn.resolve_ref("main") == HEAD_SHA
    assert len(conn.resolve_ref("main")) == 40


def test_project_info_and_verify_access(scm):
    conn, _ = scm
    info = conn.verify_access()
    assert info.default_branch == "main"
    assert info.name
    assert "/" in info.namespace_path


def test_ensure_branch_idempotent(scm):
    conn, fake = scm
    conn.ensure_branch("docs/agent/x", "main")
    assert "docs/agent/x" in fake.state.branches
    # 이미 있으면 재호출해도 예외 없이 통과
    conn.ensure_branch("docs/agent/x", "main")


def test_upsert_file_create_then_update(scm):
    conn, fake = scm
    conn.ensure_branch("b1", "main")
    conn.upsert_file(branch="b1", path="docs/x.md", content="v1", message="add")
    conn.upsert_file(branch="b1", path="docs/x.md", content="v2", message="update")
    stored = fake.state.files["docs/x.md"]
    assert "v2" in stored or stored == "v2"   # gitlab fake는 원문, github fake는 디코딩 저장


def test_change_request_create_then_update(scm):
    conn, fake = scm
    conn.ensure_branch("b2", "main")
    first = conn.create_or_update_change_request(
        source_branch="b2", target_branch="main", title="t1", description="d1")
    assert first.id and first.web_url
    second = conn.create_or_update_change_request(
        source_branch="b2", target_branch="main", title="t2", description="d2")
    # 열린 MR/PR 갱신 규칙: 새로 만들지 않고 같은 것을 갱신 (decision-mr-review-gate)
    assert second.id == first.id
    assert len(fake.state.change_requests) == 1
    assert fake.state.change_requests[0]["title"] == "t2"


def test_find_open_change_request_none(scm):
    conn, _ = scm
    assert conn.find_open_change_request(source_branch="none", target_branch="main") is None
