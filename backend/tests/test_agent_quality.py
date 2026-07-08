"""7-stage agent output quality pipeline (2026-07-08 ai-agent-output-quality-plan).

5개 모듈 검증:
- evidence_builder: build_evidence_pack
- scope_planner: plan_static_docs, plan_manual_docs
- deterministic_verifier: 문서 형식/근거/시크릿/마커 검증
- grounding_critic: prompt + parse + chunked
- quality_gates: evaluate_quality_gate + determine_terminal_status
"""
from __future__ import annotations

import json

import pytest

from backend.common_pipeline import agent_quality as aq


def test_build_evidence_pack_normalizes_items():
    pack = aq.build_evidence_pack(
        run_id="r1", pipeline_id="static", version_ref="abc123",
        items=[
            {"id": "e1", "kind": "source_file", "path": "backend/x.py",
             "title": "x module", "content": "short content"},
            {"id": "e2", "kind": "diff_hunk", "title": "auth change",
             "content": "+ line\n- line"},
        ],
        source_id="demo",
    )
    assert pack["pack_id"] == "evpack-r1"
    assert pack["item_count"] == 2
    assert pack["truncated"] is False
    ids = {it["id"] for it in pack["items"]}
    assert ids == {"e1", "e2"}


def test_build_evidence_pack_truncates_large_content():
    big = "x" * 50000
    pack = aq.build_evidence_pack(
        run_id="r1", pipeline_id="static", version_ref="v1",
        items=[{"id": "big", "content": big}],
    )
    assert pack["items"][0]["truncated"] is True


def test_plan_static_docs_skips_trivial_test_changes():
    plans = aq.plan_static_docs([
        {"id": "cu1", "files": ["a.py"], "change_type": "test",
         "significance": "trivial", "doc_impact": []},
    ], {"items": []})
    assert plans and plans[0]["action"] == "skip"


def test_plan_static_docs_creates_architecture_doc():
    plans = aq.plan_static_docs([
        {"id": "cu1", "files": ["x.py"], "change_type": "architecture",
         "significance": "material",
         "doc_impact": ["architecture-overview", "requirements"],
         "summary": "control/data plane 분리", "required_evidence": ["e1"]},
    ], {"items": [{"id": "e1"}]})
    assert any(p["theme"] == "architecture-overview" and p["action"] == "update"
               for p in plans)


def test_plan_manual_docs_includes_user_and_operator():
    plans = aq.plan_manual_docs(
        {"critical_failed": False},
        {"status": "pass", "percentage": 85},
    )
    themes = {p["theme"] for p in plans}
    assert themes == {"user-manual", "operator-manual"}


def test_plan_manual_docs_marks_critical_failed_user_manual_as_deprecate_candidate():
    plans = aq.plan_manual_docs(
        {"critical_failed": True},
        {"status": "fail"},
    )
    user = next(p for p in plans if p["theme"] == "user-manual")
    assert user["action"] == "deprecate-candidate"


def test_deterministic_verifier_pass_for_valid_doc():
    doc = ("---\ntheme: architecture-overview\nsource_id: demo\n---\n\n"
           "# Title\n\n## Section\n\n본문 [e1]\n\n" + aq._DOC_END_MARKER)
    r = aq.deterministic_verifier(doc, evidence_ids=["e1"])
    assert r["result"] == "pass", r["errors"]


def test_deterministic_verifier_detects_missing_frontmatter():
    doc = "# No frontmatter\n\n본문.\n\n" + aq._DOC_END_MARKER
    r = aq.deterministic_verifier(doc)
    assert any(e["code"] == "frontmatter_missing" for e in r["errors"])


def test_deterministic_verifier_detects_missing_end_marker():
    doc = "---\ntheme: t\n---\n\n# Title\n\n중단된 본문"
    r = aq.deterministic_verifier(doc)
    assert any(e["code"] == "doc_end_missing" for e in r["errors"])


def test_deterministic_verifier_detects_unclosed_fence():
    doc = "---\ntheme: t\n---\n\n```python\nimport os\n\n" + aq._DOC_END_MARKER
    r = aq.deterministic_verifier(doc)
    assert any(e["code"] == "fence_unclosed" for e in r["errors"])


def test_deterministic_verifier_detects_secret_pattern():
    doc = ("---\ntheme: t\n---\n\n# T\n\nDB: password=supersecret123 [e1]\n\n"
           + aq._DOC_END_MARKER)
    r = aq.deterministic_verifier(doc, evidence_ids=["e1"])
    assert any(e["code"] == "secret_pattern" for e in r["errors"])


def test_deterministic_verifier_detects_unknown_evidence_ref():
    doc = "---\ntheme: t\n---\n\n# T\n\n## S\n\n본문 [e99]\n\n" + aq._DOC_END_MARKER
    r = aq.deterministic_verifier(doc, evidence_ids=["e1"])
    assert any(e["code"] == "missing_evidence_id" for e in r["errors"])


def test_deterministic_verifier_detects_forbidden_guess_word():
    doc = ("---\ntheme: t\n---\n\n# T\n\n## S\n\n아마 이렇게 동작할 것이다 [e1].\n\n"
           + aq._DOC_END_MARKER)
    r = aq.deterministic_verifier(doc, evidence_ids=["e1"])
    assert any(e["code"] == "forbidden_word" for e in r["errors"])


def test_parse_critic_verdict_valid_json():
    raw = '{"result": "pass", "score": 0.9, "blocking_findings": [], "nonblocking_notes": []}'
    v = aq.parse_critic_verdict(raw)
    assert v["result"] == "pass"
    assert v["score"] == 0.9


def test_parse_critic_verdict_auto_promotes_when_blockers_zero_and_score_high():
    raw = json.dumps({"result": "auto", "score": 0.95, "blocking_findings": [],
                      "nonblocking_notes": ["minor"]}) if False else (
        '{"score": 0.9, "blocking_findings": [], "nonblocking_notes": []}')
    v = aq.parse_critic_verdict(raw)
    assert v["result"] == "pass"


def test_parse_critic_verdict_recovers_from_markdown_fence():
    raw = '```json\n{"score": 0.92, "blocking_findings": []}\n```'
    v = aq.parse_critic_verdict(raw)
    assert v["score"] == 0.92


def test_parse_critic_verdict_empty_returns_fail():
    v = aq.parse_critic_verdict("")
    assert v["result"] == "fail"
    assert v["blocking_findings"]


def test_chunked_critic_short_doc_single_section():
    """짧은 문서는 한 chunk 로 critic 호출."""
    chunked = aq.chunked_critic("## S", "evidence", {}, critic_fn=lambda d, e: '{"score": 0.95, "blocking_findings": []}')
    assert chunked["result"] == "pass"
    assert chunked["score"] == 0.95


def test_chunked_critic_long_doc_aggregates_findings():
    """긴 문서는 chunked 로 처리되며 blocker 가 합산."""
    sections = []
    for i in range(5):
        body = "본문은 길이가 충분히 길어서 chunk_size 를 넘기게 한다. " * 30
        sections.append(f"## Section {i}\n\n{body} [{i+1}]\n\n" + aq._DOC_END_MARKER)
    long_doc = "\n\n".join(sections)
    assert len(long_doc) > 500

    def failing_critic(doc_chunk, _evidence):
        return json.dumps({"score": 0.4,
                          "blocking_findings": [{"severity": "blocker",
                                                  "claim": "test",
                                                  "reason": "bad"}]})
    r = aq.chunked_critic(long_doc, "evidence", {}, chunk_size=200, critic_fn=failing_critic)
    assert r["result"] == "fail"
    blockers = [f for f in r["blocking_findings"] if f["severity"] == "blocker"]
    assert len(blockers) >= 2


def test_chunked_critic_uses_deterministic_when_no_critic_fn():
    """critic_fn 없이도 결정적 verdict 로 chunked 동작 (테스트 안전판)."""
    r = aq.chunked_critic("## S\n\n본문\n" + aq._DOC_END_MARKER, "evidence", {}, critic_fn=None)
    assert r["result"] == "fail"


def test_evaluate_quality_gate_pass():
    g = aq.evaluate_quality_gate(
        verifier={"result": "pass", "errors": []},
        critic={"score": 0.95, "blocking_findings": []})
    assert g["status"] == "pass"
    assert g["failed_gate"] == ""


def test_evaluate_quality_gate_fails_on_verifier():
    g = aq.evaluate_quality_gate(
        verifier={"result": "fail", "errors": [{"code": "frontmatter_missing"}]},
        critic={"score": 0.95, "blocking_findings": []})
    assert g["status"] == "fail"
    assert g["failed_gate"] == "deterministic_verifier"


def test_evaluate_quality_gate_fails_on_blocker():
    g = aq.evaluate_quality_gate(
        verifier={"result": "pass", "errors": []},
        critic={"score": 0.95,
                "blocking_findings": [{"severity": "blocker", "claim": "x", "reason": "y"}]})
    assert g["status"] == "fail"
    assert g["failed_gate"] == "grounding_critic.blocker"


def test_evaluate_quality_gate_warning_on_major():
    g = aq.evaluate_quality_gate(
        verifier={"result": "pass", "errors": []},
        critic={"score": 0.95,
                "blocking_findings": [{"severity": "major", "claim": "x", "reason": "y"}]})
    assert g["status"] == "warning"


def test_evaluate_quality_gate_warning_on_low_score():
    g = aq.evaluate_quality_gate(
        verifier={"result": "pass", "errors": []},
        critic={"score": 0.5, "blocking_findings": []})
    assert g["status"] == "warning"


def test_determine_terminal_status_quality_fail():
    assert aq.determine_terminal_status("fail") == "failed_quality_gate"


def test_determine_terminal_status_quality_warning():
    assert aq.determine_terminal_status("warning") == "done_with_warnings"


def test_determine_terminal_status_quality_pass_with_errors():
    assert aq.determine_terminal_status("pass", summary_errors=1) == "partial"


def test_determine_terminal_status_quality_pass_clean():
    assert aq.determine_terminal_status("pass") == "done"
