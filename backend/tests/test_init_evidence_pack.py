"""static init 경로 evidence_pack 주입 회귀 테스트 (P0 품질 개선).

조사(raw/2026-07-08-ai-agent-output-quality-plan.md 대비 구현 갭)에서 확정된 사실:
init 경로는 evidence_pack 을 generate_with_critic 에 안 넘겨 chunked_critic +
deterministic_verifier 를 안 타고 9k 단절 LLM critic 만 돌았다. 이 테스트는
  1) _build_init_evidence_pack 이 단위 요약을 evidence pack 으로 만들고
  2) evidence_pack 이 주어지면 generate_with_critic 이 chunked_critic 경로를 타는 것을
LLM 없이 고정한다.
"""
from __future__ import annotations

from backend.static_pipeline import init_runner
from backend.static_pipeline import generate as static_generate
from backend.common_pipeline.verify import DOC_END_MARKER


class _FakeSettings:
    source_id = "demo"


class _FakeCtx:
    run_id = "run-1"
    settings = _FakeSettings()

    def __init__(self):
        self.events = []

    def rev(self, *a, **k):
        self.events.append((a, k))


# ── 1) init evidence pack 빌더 ──────────────────────────────────────────


def test_build_init_evidence_pack_from_summaries():
    ctx = _FakeCtx()
    summaries = [
        ("parser", "역할: 소스 파싱\n주요 컴포넌트: Lexer, Parser"),
        ("engine", "역할: 실행 엔진\n의존·통신: parser 를 호출"),
    ]
    pack = init_runner._build_init_evidence_pack(ctx, client=None, ref="abc123",
                                                 summaries=summaries)
    assert pack is not None
    assert pack["item_count"] == 2
    # init 근거는 요약이므로 observation kind.
    assert pack["observation_count"] == 2
    ids = [it["id"] for it in pack["items"]]
    assert ids == ["e1", "e2"]
    # evidence-build 이벤트가 emit 됐는가.
    assert any("evidence-build" in a for a, _ in ctx.events)


def test_build_init_evidence_pack_empty_returns_none():
    ctx = _FakeCtx()
    # 요약이 전부 비면 근거가 없으니 None → 기존 critic 경로 폴백.
    assert init_runner._build_init_evidence_pack(ctx, None, "abc", []) is None
    assert init_runner._build_init_evidence_pack(
        ctx, None, "abc", [("u", "   "), ("v", "")]) is None


# ── 2) evidence_pack 유무로 generate 경로가 갈리는가 ─────────────────────


# min_len(500자) 형식검증을 통과하도록 충분히 길게 — critic 호출까지 도달해야
# evidence_pack 유무에 따른 경로 분기를 검증할 수 있다.
_PARA = (
    "이 시스템은 parser 와 engine 두 컴포넌트로 구성된다 [e1]. parser 는 입력 소스를 "
    "토큰으로 분해해 구문 트리를 만들고, engine 은 그 트리를 받아 실행 계획으로 옮긴다 "
    "[e2]. 두 컴포넌트는 명확한 경계를 두고 분리되어 있어 각각 독립적으로 교체·확장할 "
    "수 있으며, 한쪽의 내부 변경이 다른 쪽으로 전파되지 않는다 [e1]. engine 은 parser 의 "
    "구현이 아니라 산출된 트리 계약에만 의존한다 [e2].\n"
)
_GOOD_DOC = (
    "---\ntheme: architecture-overview\nsource_files: [src/a.py]\n"
    "generated_from: init\n---\n\n"
    "# architecture-overview\n\n"
    "## Overview\n" + _PARA + "\n"
    "## Components\n" + _PARA + "\n"
    "## Data Flow\n" + _PARA + "\n"
    f"{DOC_END_MARKER}\n"
)


def _patch_writer_and_critics(monkeypatch):
    """writer 와 두 critic 경로를 목으로 대체하고, 어느 critic 이 불렸는지 기록."""
    called = {"chunked": 0, "json_verdict": 0}

    # writer 는 항상 형식 유효한 문서를 낸다.
    monkeypatch.setattr(static_generate, "run_writer",
                        lambda graph, prompt, observer: _GOOD_DOC)

    # chunked_critic (evidence_pack 경로) — 호출되면 카운트하고 pass.
    def fake_chunked(doc, ev_block, theme, *, chunk_size, critic_fn):
        called["chunked"] += 1
        return {"result": "pass", "score": 0.95,
                "blocking_findings": [], "nonblocking_notes": []}
    monkeypatch.setattr(static_generate, "chunked_critic", fake_chunked)

    # run_json_verdict (기존 9k critic 경로) — 호출되면 카운트하고 pass.
    def fake_json_verdict(factory, observer, **kw):
        called["json_verdict"] += 1
        return {"result": "pass", "score": 1.0}
    monkeypatch.setattr(static_generate, "run_json_verdict", fake_json_verdict)

    return called


def _run_generate(evidence_pack):
    events = []

    def emit_ctx(*a, **k):
        events.append((a, k))

    return static_generate.generate_with_critic(
        model=object(), client=object(), theme="architecture-overview",
        ref="abc", run_id="run-1", stage="repo:architecture-overview",
        writer_graph_factory=lambda **kw: object(),
        base_prompt="write it", observer=None, emit_ctx=emit_ctx,
        evidence_pack=evidence_pack,
    )


def test_evidence_pack_routes_to_chunked_critic(monkeypatch):
    called = _patch_writer_and_critics(monkeypatch)
    pack = init_runner._build_init_evidence_pack(
        _FakeCtx(), None, "abc",
        [("parser", "역할: 파싱"), ("engine", "역할: 실행")],
    )
    doc, verdict, warned = _run_generate(pack)
    assert verdict["result"] == "pass"
    assert not warned
    # evidence_pack 이 있으면 chunked_critic 만, 9k json_verdict 는 안 탄다.
    assert called["chunked"] == 1
    assert called["json_verdict"] == 0


def test_no_evidence_pack_uses_legacy_critic(monkeypatch):
    called = _patch_writer_and_critics(monkeypatch)
    doc, verdict, warned = _run_generate(None)
    assert verdict["result"] == "pass"
    # evidence_pack 이 없으면 기존 9k json_verdict 경로 (하위 호환).
    assert called["json_verdict"] == 1
    assert called["chunked"] == 0
