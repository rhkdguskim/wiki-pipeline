"""init 전수 스캔 재설계 회귀 테스트 (SearchAgent).

2026-07-10 재설계: init 은 모든 소스 파일을 빠짐없이 읽는다. 단위를 청크로 쪼개
청크마다 독립 SearchAgent 가 전수 read 하고, 안 읽은 파일이 있으면 명시해 재스캔한다.
LLM 없이 run_graph/make_tools 를 대체해 다음을 고정한다:
  1) 청크 분할이 모든 파일을 커버한다 (누락 없음).
  2) SearchAgent 가 청크의 모든 파일을 실제로 read_file 한다.
  3) 커버리지가 낮으면 안 읽은 파일을 명시해 보강 스캔한다.
  4) 여러 청크면 SummaryComposer 가 단위 요약으로 합성한다.
"""
from __future__ import annotations

import backend.static_pipeline.deep_summary as ds
from backend.static_pipeline.theme_mapping import parse_submodule_paths, under_any


# ── 0) 서브모듈 배제 (사용자 요구: 서브모듈 참고 안 함) ──────────────────


_GITMODULES = """
[submodule "libs/foo"]
\tpath = libs/foo
\turl = https://example.com/foo.git
[submodule "vendor/bar"]
\tpath = vendor/bar
\turl = https://example.com/bar.git
"""


def test_parse_submodule_paths():
    assert parse_submodule_paths(_GITMODULES) == ["libs/foo", "vendor/bar"]
    assert parse_submodule_paths("") == []
    assert parse_submodule_paths("[core]\n\tx = 1") == []


def test_under_any_boundary():
    roots = ["libs/foo", "vendor/bar"]
    assert under_any("libs/foo/x.c", roots)
    assert under_any("libs/foo", roots)          # 경로 자체
    assert not under_any("libs/foobar/y.c", roots)   # 유사 접두사는 아님
    assert not under_any("src/main.py", roots)


def test_submodule_files_excluded():
    roots = parse_submodule_paths(_GITMODULES)
    files = ["src/a.py", "libs/foo/x.c", "vendor/bar/z.h", "libs/foobar/y.c"]
    kept = [f for f in files if not under_any(f, roots)]
    assert kept == ["src/a.py", "libs/foobar/y.c"]


# ── 1) 청크 분할 전수 커버 ──────────────────────────────────────────────


def test_split_chunks_covers_all_files():
    files = [f"f{i}.py" for i in range(25)]
    chunks = ds._split_chunks(files, 10)
    assert [len(c) for c in chunks] == [10, 10, 5]
    flat = [f for c in chunks for f in c]
    assert sorted(flat) == sorted(files)   # 누락·중복 없음


def test_split_chunks_single_when_small():
    assert ds._split_chunks(["a", "b"], 12) == [["a", "b"]]
    assert ds._split_chunks([], 12) == [[]]


# ── 2)/3) SearchAgent 전수 read + 보강 재시도 ───────────────────────────


_VALID = (
    "역할: 파서 단위. 주요 컴포넌트: Lexer, Parser 로 구성. "
    "의존·통신: engine 을 호출. 기술·플랫폼: C++17, CMake. "
    "실행·설정: 포트 없음, 환경변수 없음. 이 단위는 소스를 토큰화한다."
)


class _FakeClient:
    def raw_file(self, path, ref):
        return f"// {path}\ncode"

    def list_tree(self, path, ref):
        return []


def _install_fakes(monkeypatch, *, read_ratio_first=1.0):
    """run_graph 를 대체 — read_file 를 호출한 뒤 유효 요약을 반환.

    read_ratio_first: 첫 호출에서 목록 중 몇 비율을 읽을지 (커버리지 재시도 검증용).
    make_tools 는 실제 것을 쓰되 raw_file 만 fake 라 read_log 추적은 진짜로 동작한다.
    """
    calls = {"n": 0}

    def fake_run_graph(graph, initial, observer, config=None):
        calls["n"] += 1
        # graph 에 바인딩된 read_file 을 직접 부를 수 없으니, 여기서는 spec 의
        # tools 로 노출된 read_file 를 통해 read_log 를 채운다. 대신 _run_search_agent
        # 이 넘긴 read_log 를 알 수 없으므로, 모듈 전역 훅으로 마지막 tools 를 잡는다.
        rf = _LAST_TOOLS.get("read_file")
        files = _LAST_TOOLS.get("files") or []
        if rf:
            n = max(1, int(len(files) * (read_ratio_first if calls["n"] == 1 else 1.0)))
            for p in files[:n]:
                rf.func(p)

        class _Msg:
            content = _VALID
        return {"messages": [_Msg()]}

    # make_tools 를 감싸 마지막 생성 tools/파일목록을 잡는다.
    real_make_tools = ds.make_tools

    def spy_make_tools(client, ref, *, read_log=None):
        tools = real_make_tools(client, ref, read_log=read_log)
        _LAST_TOOLS["read_file"] = [t for t in tools if t.name == "read_file"][0]
        return tools

    # build_agent_graph 는 실제 model 을 요구하므로 스텁으로 대체 (그래프 객체 불필요).
    monkeypatch.setattr(ds, "build_agent_graph", lambda spec, model: object())
    monkeypatch.setattr(ds, "run_graph", fake_run_graph)
    monkeypatch.setattr(ds, "make_tools", spy_make_tools)
    return calls


_LAST_TOOLS: dict = {}


def _set_files(files):
    _LAST_TOOLS["files"] = files


def test_search_agent_reads_all_files(monkeypatch):
    files = [f"src/f{i}.py" for i in range(5)]
    _set_files(files)
    calls = _install_fakes(monkeypatch, read_ratio_first=1.0)
    out = ds._run_search_agent(
        object(), _FakeClient(), "abc", "run-1", "parser", "dir", "src",
        files, None, chunk_idx=1, chunk_total=1)
    assert out == _VALID
    # 전부 읽었으면 보강 재시도 없음 (run_graph 1회).
    assert calls["n"] == 1


def test_search_agent_reretries_when_undercovered(monkeypatch):
    files = [f"src/f{i}.py" for i in range(10)]
    _set_files(files)
    # 첫 호출에서 절반만 읽음 → 커버리지 50% < 95% → 보강 스캔 1회 더.
    calls = _install_fakes(monkeypatch, read_ratio_first=0.5)
    events = []
    ds._run_search_agent(
        object(), _FakeClient(), "abc", "run-1", "parser", "dir", "src",
        files, None, chunk_idx=1, chunk_total=1,
        emit_ctx=lambda *a, **k: events.append((a, k)))
    assert calls["n"] == 2   # 보강 재시도가 돌았다
    assert any("chunk_undercovered" in str(k.get("detail", {})) for _a, k in events)


# ── 4) 여러 청크 → SummaryComposer 합성 ─────────────────────────────────


def test_multi_chunk_unit_composes_summary(monkeypatch):
    # chunk_files=3 으로 낮춰 7파일이 3청크가 되게.
    monkeypatch.setattr(ds, "_chunk_files", lambda: 3)
    monkeypatch.setattr(ds, "_max_concurrency", lambda: 4)
    # 커버리지 재시도 배선을 이 테스트에서 배제 — 각 청크 SearchAgent 는 유효 요약 반환만.
    monkeypatch.setattr(ds, "_run_search_agent",
                        lambda *a, **k: _VALID)

    composed = {"n": 0}

    def spy_compose(model, run_id, unit_name, chunk_summaries, observer, *, hint=""):
        composed["n"] += 1
        composed["chunks"] = len(chunk_summaries)
        return _VALID
    monkeypatch.setattr(ds, "_compose_unit_summary", spy_compose)

    unit = {"name": "parser", "kind": "dir", "root_path": "src",
            "_files": [f"src/f{i}.py" for i in range(7)]}
    name, summary = ds._summarize_unit(
        object(), _FakeClient(), "abc", "run-1", unit, None)
    assert name == "parser"
    # 7파일 / chunk 3 = 3청크 → composer 가 3개 청크요약으로 합성.
    assert composed["n"] == 1
    assert composed["chunks"] == 3
    assert summary == _VALID
