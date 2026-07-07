"""커넥터 계약 테스트용 in-memory 가짜 SCM 서버 (httpx.MockTransport 핸들러).

동일한 시드 상태(파일·브랜치·sha)를 GitLab/GitHub API 형태로 노출해,
두 커넥터가 같은 계약 테스트를 통과하는지 검증한다.
"""
from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, unquote, urlparse

import httpx

HEAD_SHA = "a" * 40
OLD_SHA = "b" * 40

SEED_FILES = {
    "README.md": "# demo\n",
    "src/app.py": "print('hi')\n",
    "src/util.py": "def f(): pass\n",
}

SEED_COMPARE = [
    {"path": "src/app.py", "old": "src/app.py", "status": "modified"},
    {"path": "docs/new.md", "old": "docs/new.md", "status": "added"},
    {"path": "src/gone.py", "old": "src/gone.py", "status": "removed"},
    {"path": "src/util.py", "old": "src/old_util.py", "status": "renamed"},
]


class _State:
    def __init__(self):
        self.files = dict(SEED_FILES)
        self.branches = {"main": HEAD_SHA}
        self.change_requests: list[dict] = []   # {id, source, target, title, description, state}
        self.next_cr_id = 1


def _json(status: int, data, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=data, headers=headers or {})


class FakeGitLab:
    """GitLab v4 API 최소 구현 — project 'grp/demo' (id 947)."""

    def __init__(self):
        self.state = _State()
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        st = self.state
        url = urlparse(str(request.url))
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        path = unquote(url.path)
        parts = path.split("/api/v4/projects/", 1)
        if len(parts) != 2:
            return _json(404, {"message": "no project"})
        rest = unquote(parts[1])
        # project 식별자(인코딩 해제 후 'grp/demo' 또는 '947') 제거
        for pid in ("grp/demo", "947"):
            if rest.startswith(pid):
                rest = rest[len(pid):]
                break
        else:
            return _json(404, {"message": "unknown project"})

        if rest == "" and request.method == "GET":
            return _json(200, {"name": "Demo", "default_branch": "main",
                               "path_with_namespace": "grp/demo",
                               "web_url": "http://gitlab.local/grp/demo"})
        if rest == "/repository/compare":
            if q.get("from") == "zzz":
                return _json(404, {"message": "404 commit not found"})
            diffs = [{"new_path": c["path"], "old_path": c["old"],
                      "new_file": c["status"] == "added",
                      "deleted_file": c["status"] == "removed",
                      "renamed_file": c["status"] == "renamed"} for c in SEED_COMPARE]
            return _json(200, {"diffs": diffs})
        if rest.startswith("/repository/files/") and rest.endswith("/raw"):
            fp = rest[len("/repository/files/"):-len("/raw")]
            if fp in st.files:
                return httpx.Response(200, text=st.files[fp])
            return _json(404, {"message": "file not found"})
        if rest == "/repository/tree":
            req_path = q.get("path", "")
            recursive = q.get("recursive") == "true"
            page = int(q.get("page", "1"))
            entries = self._tree_entries(req_path, recursive)
            # 페이지네이션: per_page=100 가정, 시드는 1페이지로 끝
            headers = {"x-next-page": ""} if page >= 1 else {}
            return _json(200, entries if page == 1 else [], headers)
        if rest.startswith("/repository/commits/"):
            ref = rest[len("/repository/commits/"):]
            if ref in ("main", "HEAD", HEAD_SHA):
                return _json(200, {"id": HEAD_SHA})
            if ref in (OLD_SHA,):
                return _json(200, {"id": OLD_SHA})
            if ref in st.branches:
                return _json(200, {"id": st.branches[ref]})
            return _json(404, {"message": "commit not found"})
        if rest.startswith("/repository/branches"):
            if request.method == "GET":
                name = rest[len("/repository/branches/"):]
                if name in st.branches:
                    return _json(200, {"name": name, "commit": {"id": st.branches[name]}})
                return _json(404, {"message": "branch not found"})
            if request.method == "POST":
                name, ref = q["branch"], q["ref"]
                st.branches[name] = st.branches.get(ref, HEAD_SHA)
                return _json(201, {"name": name})
        if rest.startswith("/repository/files/"):
            fp = rest[len("/repository/files/"):]
            payload = json.loads(request.content.decode() or "{}")
            if request.method == "PUT":
                if fp not in st.files:
                    return _json(404, {"message": "file not found"})
                st.files[fp] = payload["content"]
                return _json(200, {"file_path": fp, "branch": payload.get("branch")})
            if request.method == "POST":
                st.files[fp] = payload["content"]
                return _json(201, {"file_path": fp, "branch": payload.get("branch")})
        if rest.startswith("/merge_requests"):
            if request.method == "GET":
                found = [m for m in st.change_requests
                         if m["state"] == "opened"
                         and m["source"] == q.get("source_branch")
                         and m["target"] == q.get("target_branch")]
                return _json(200, [self._mr(m) for m in found])
            if request.method == "POST":
                payload = json.loads(request.content.decode())
                mr = {"id": st.next_cr_id, "source": payload["source_branch"],
                      "target": payload["target_branch"], "title": payload["title"],
                      "description": payload.get("description", ""), "state": "opened"}
                st.next_cr_id += 1
                st.change_requests.append(mr)
                return _json(201, self._mr(mr))
            if request.method == "PUT":
                iid = int(rest.rsplit("/", 1)[-1])
                payload = json.loads(request.content.decode())
                for m in st.change_requests:
                    if m["id"] == iid:
                        m["title"] = payload.get("title", m["title"])
                        m["description"] = payload.get("description", m["description"])
                        return _json(200, self._mr(m))
                return _json(404, {"message": "mr not found"})
        if rest == "/unauthorized":
            return _json(401, {"message": "401 Unauthorized"})
        return _json(404, {"message": f"unhandled {request.method} {path}"})

    def _tree_entries(self, path: str, recursive: bool) -> list[dict]:
        out = []
        dirs = set()
        for fp in self.state.files:
            if path and not fp.startswith(path.rstrip("/") + "/"):
                continue
            rel = fp[len(path.rstrip("/")) + 1:] if path else fp
            if "/" in rel and not recursive:
                dirs.add(rel.split("/", 1)[0])
                continue
            out.append({"path": fp, "name": fp.rsplit("/", 1)[-1], "type": "blob"})
        prefix = (path.rstrip("/") + "/") if path else ""
        out.extend({"path": f"{prefix}{d}", "name": d, "type": "tree"} for d in sorted(dirs))
        return out

    @staticmethod
    def _mr(m: dict) -> dict:
        return {"id": m["id"] * 1000, "iid": m["id"], "title": m["title"],
                "description": m["description"], "state": m["state"],
                "web_url": f"http://gitlab.local/grp/demo/-/merge_requests/{m['id']}"}


class FakeGitHub:
    """GitHub REST API 최소 구현 — repo 'octo/demo'."""

    def __init__(self):
        self.state = _State()
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        st = self.state
        url = urlparse(str(request.url))
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        path = unquote(url.path)
        if not path.startswith("/repos/octo/demo"):
            return _json(404, {"message": "unknown repo"})
        rest = path[len("/repos/octo/demo"):]

        if rest == "" and request.method == "GET":
            return _json(200, {"name": "demo", "default_branch": "main",
                               "full_name": "octo/demo",
                               "html_url": "https://github.com/octo/demo"})
        if rest.startswith("/compare/"):
            basehead = rest[len("/compare/"):]
            if basehead.startswith("zzz"):
                return _json(404, {"message": "Not Found"})
            files = [{"filename": c["path"],
                      "previous_filename": c["old"] if c["status"] == "renamed" else None,
                      "status": c["status"]} for c in SEED_COMPARE]
            page = int(q.get("page", "1"))
            return _json(200, {"files": files if page == 1 else []})
        if rest.startswith("/contents"):
            fp = rest[len("/contents"):].lstrip("/")
            accept = request.headers.get("Accept", "")
            if request.method == "GET":
                if fp and fp in st.files:
                    if "raw" in accept:
                        return httpx.Response(200, text=st.files[fp])
                    return _json(200, {"name": fp.rsplit("/", 1)[-1], "path": fp,
                                       "sha": "blob-" + fp, "type": "file"})
                # 디렉터리 리스팅
                entries = self._dir_entries(fp)
                if entries:
                    return _json(200, entries)
                return _json(404, {"message": "Not Found"})
            if request.method == "PUT":
                payload = json.loads(request.content.decode())
                is_update = fp in st.files
                if is_update and not payload.get("sha"):
                    return _json(409, {"message": "sha required for update"})
                st.files[fp] = base64.b64decode(payload["content"]).decode()
                return _json(200 if is_update else 201, {"content": {"path": fp}})
        if rest.startswith("/git/trees/"):
            tree = [{"path": fp, "type": "blob"} for fp in sorted(st.files)]
            return _json(200, {"sha": HEAD_SHA, "tree": tree})
        if rest.startswith("/commits/"):
            ref = rest[len("/commits/"):]
            if ref in ("main", HEAD_SHA):
                return _json(200, {"sha": HEAD_SHA})
            if ref == OLD_SHA:
                return _json(200, {"sha": OLD_SHA})
            if ref in st.branches:
                return _json(200, {"sha": st.branches[ref]})
            return _json(404, {"message": "No commit found"})
        if rest.startswith("/git/ref/heads/"):
            name = rest[len("/git/ref/heads/"):]
            if name in st.branches:
                return _json(200, {"ref": f"refs/heads/{name}",
                                   "object": {"sha": st.branches[name]}})
            return _json(404, {"message": "Not Found"})
        if rest == "/git/refs" and request.method == "POST":
            payload = json.loads(request.content.decode())
            name = payload["ref"].removeprefix("refs/heads/")
            st.branches[name] = payload["sha"]
            return _json(201, {"ref": payload["ref"]})
        if rest.startswith("/pulls"):
            if request.method == "GET":
                head = q.get("head", "")
                branch = head.split(":", 1)[-1]
                found = [m for m in st.change_requests
                         if m["state"] == "open" and m["source"] == branch
                         and m["target"] == q.get("base")]
                return _json(200, [self._pr(m) for m in found])
            if request.method == "POST":
                payload = json.loads(request.content.decode())
                pr = {"id": st.next_cr_id, "source": payload["head"],
                      "target": payload["base"], "title": payload["title"],
                      "description": payload.get("body", ""), "state": "open"}
                st.next_cr_id += 1
                st.change_requests.append(pr)
                return _json(201, self._pr(pr))
            if request.method == "PATCH":
                num = int(rest.rsplit("/", 1)[-1])
                payload = json.loads(request.content.decode())
                for m in st.change_requests:
                    if m["id"] == num:
                        m["title"] = payload.get("title", m["title"])
                        m["description"] = payload.get("body", m["description"])
                        return _json(200, self._pr(m))
                return _json(404, {"message": "Not Found"})
        return _json(404, {"message": f"unhandled {request.method} {path}"})

    def _dir_entries(self, prefix: str) -> list[dict]:
        out, dirs = [], set()
        for fp in self.state.files:
            if prefix and not fp.startswith(prefix.rstrip("/") + "/"):
                continue
            rel = fp[len(prefix.rstrip("/")) + 1:] if prefix else fp
            if "/" in rel:
                dirs.add(rel.split("/", 1)[0])
            else:
                out.append({"name": rel, "path": fp, "type": "file"})
        pre = (prefix.rstrip("/") + "/") if prefix else ""
        out.extend({"name": d, "path": f"{pre}{d}", "type": "dir"} for d in sorted(dirs))
        return out

    @staticmethod
    def _pr(m: dict) -> dict:
        return {"id": m["id"] * 1000, "number": m["id"], "title": m["title"],
                "body": m["description"], "state": m["state"],
                "html_url": f"https://github.com/octo/demo/pull/{m['id']}"}
