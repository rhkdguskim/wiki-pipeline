"""state-advance 실패가 run 전체 실패로 전파되는지 회귀 테스트
(decision-state-advance-failure-propagates).

버그 재현: 문서는 전부 생성됐지만 last_processed_sha 저장 직전
client.resolve_ref()가 예외(예: SCM rate limit)를 던지면, 과거에는 이벤트만
"failed"로 남기고 조용히 넘어가 run 전체가 "done"으로 보고됐다 — 실제로는
sha가 전진하지 않아 다음 실행이 같은 작업을 반복하는데도 성공으로 보였다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.static_pipeline.runner import _advance


class _RaisingClient:
    def resolve_ref(self, ref: str) -> str:
        raise RuntimeError("ScmRateLimitError: API rate limit exceeded")


class _Settings:
    def __init__(self, out_path: Path):
        self.out_path = out_path
        self.gitlab_project_id = "947"
        self.scm_sources_json = ""
        self.source_id = "demo"
        self.source_label = "Demo"
        self.source_kind = "gitlab"


def test_advance_propagates_resolve_ref_failure(tmp_path):
    events: list[tuple] = []

    def rev(layer, stage, status, detail=None, progress=None):
        events.append((layer, stage, status, detail))

    settings = _Settings(tmp_path)
    summary = {"themes": {"intro": {"file": "x.md"}}}

    with pytest.raises(RuntimeError, match="rate limit"):
        _advance(settings, _RaisingClient(), "short-ref", summary, rev)

    # 실패 이벤트는 여전히 남아야 한다 (관측 계약 유지) — 다만 이제는 흡수되지 않고 재발생한다.
    assert events[-1] == ("stage", "state-advance", "failed",
                          {"error": "RuntimeError: ScmRateLimitError: API rate limit exceeded"})
    # summary는 last_processed_sha가 채워지지 않은 채 남는다 — sha 미전진 확인.
    assert "last_processed_sha" not in summary


def test_advance_succeeds_when_resolve_ref_ok(tmp_path):
    events: list[tuple] = []

    def rev(layer, stage, status, detail=None, progress=None):
        events.append((layer, stage, status, detail))

    settings = _Settings(tmp_path)
    summary = {"themes": {"intro": {"file": "x.md"}}}
    full_sha = "a" * 40

    # to_sha가 이미 40자면 resolve_ref를 호출하지 않는다 — 정상 경로 확인.
    _advance(settings, _RaisingClient(), full_sha, summary, rev)

    assert summary["last_processed_sha"] == full_sha
    assert events[-1][2] == "done"
