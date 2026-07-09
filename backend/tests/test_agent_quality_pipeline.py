"""7-stage AI agent output quality pipeline tests.

raw/2026-07-08-ai-agent-output-quality-plan.md 의 7단계 파이프라인 모듈을
LLM 없이 deterministic 하게 검증한다:
- evidence_builder: pack 빌드·truncation·chunking
- deterministic_verifier: frontmatter·DOC-END·fence·mermaid·evidence id·secret
- grounding_critic: verdict 파싱·chunk 분배·aggregation
- quality_gates: pass/warning/fail 임계치·terminal status
- scope_planner: skip/create/update/deprecate 결정
"""
from __future__ import annotations

import json

import pytest

from backend.common_pipeline.evidence_builder import (
    build_evidence_pack,
    evidence_block_text,
    evidence_ids,
)
from backend.common_pipeline.deterministic_verifier import verify, summarize
from backend.common_pipeline.grounding_critic import (
    chunked_critic,
    format_critic_prompt,
    parse_critic_verdict,
    severity_counts,
)
from backend.common_pipeline.quality_gates import (
    DEFAULT_THRESHOLDS,
    determine_terminal_status,
    evaluate_quality_gate,
    to_webhook_payload,
)
from backend.common_pipeline.scope_planner import (
    actionable_plans,
    plan_manual_docs,
    plan_static_docs,
)
from backend.common_pipeline.verify import DOC_END_MARKER


# ── test fixtures ────────────────────────────────────────────

def _valid_static_doc(theme: str = "architecture-overview",
                      extra_sections: int = 0) -> str:
    sections = ["## Overview", "## Components"]
    for i in range(extra_sections):
        sections.append(f"## Extra {i}")
    body = "\n\n".join(sections)
    return (
        f"---\ntheme: {theme}\nsource_files: [src/main.py]\n"
        f"generated_from: aaa..bbb\n---\n\n"
        f"# {theme}\n\n시스템은 컴포넌트로 구성된다 [e1].\n\n{body}\n\n"
        f"{DOC_END_MARKER}"
    )


def _valid_manual_doc(theme: str = "manual/user-guide") -> str:
    return (
        "---\ntheme: manual/user-guide\nsource_id: demo\n"
        "release:\n  tag: v1.0.0\n  artifact: app.msi\n"
        "source_observations: [o1, o2]\n---\n\n"
        "# User Manual\n\n앱을 실행한다 [o1].\n\n"
        "## 절차\n\n로그인한다 [o2].\n\n"
        "## 관측 범위와 한계\n\n전체 커버됨.\n\n"
        f"{DOC_END_MARKER}"
    )


# ── evidence_builder ─────────────────────────────────────────

class TestEvidenceBuilder:

    def test_build_pack_basic_schema(self):
        pack = build_evidence_pack(
            "run-1", "src-1", "static", "sha-abc",
            [{"id": "e1", "kind": "source_file", "path": "a.py",
              "title": "A", "content": "short"}],
        )
        assert pack["pack_id"].startswith("evpack-")
        assert pack["run_id"] == "run-1"
        assert pack["pipeline_id"] == "static"
        assert pack["version_ref"] == "sha-abc"
        assert pack["item_count"] == 1
        assert pack["source_file_count"] == 1
        assert pack["observation_count"] == 0
        assert pack["truncated"] is False
        assert len(pack["items"]) == 1
        assert pack["items"][0]["id"] == "e1"

    def test_pack_id_deterministic(self):
        items = [{"id": "e1", "kind": "source_file", "content": "x"}]
        p1 = build_evidence_pack("r", "s", "static", "v", items)
        p2 = build_evidence_pack("r", "s", "static", "v", items)
        assert p1["pack_id"] == p2["pack_id"]

    def test_pack_id_changes_with_inputs(self):
        items = [{"id": "e1", "kind": "source_file", "content": "x"}]
        p1 = build_evidence_pack("r1", "s", "static", "v", items)
        p2 = build_evidence_pack("r2", "s", "static", "v", items)
        assert p1["pack_id"] != p2["pack_id"]

    def test_truncation_long_content(self):
        long_content = "x" * 20000
        pack = build_evidence_pack(
            "r", "s", "static", "v",
            [{"id": "e1", "kind": "source_file", "content": long_content}],
            max_item_chars=100,
        )
        assert pack["truncated"] is True
        assert len(pack["items"][0]["content"]) <= 200

    def test_chunking_long_file(self):
        long_content = "\n".join(f"line {i}" for i in range(500))
        pack = build_evidence_pack(
            "r", "s", "static", "v",
            [{"id": "big", "kind": "source_file", "path": "big.py",
              "title": "BIG", "content": long_content}],
            max_item_chars=500,
        )
        assert pack["item_count"] > 1
        chunk_ids = [it["id"] for it in pack["items"]]
        assert any("-c" in cid for cid in chunk_ids)

    def test_kind_normalization(self):
        pack = build_evidence_pack(
            "r", "s", "static", "v",
            [{"id": "e1", "kind": "unknown_kind", "content": "x"}],
        )
        assert pack["items"][0]["kind"] == "source_file"

    def test_max_items_cap(self):
        items = [
            {"id": f"e{i}", "kind": "source_file", "content": f"c{i}"}
            for i in range(50)
        ]
        pack = build_evidence_pack("r", "s", "static", "v", items, max_items=10)
        assert pack["item_count"] == 10
        assert pack["omitted_count"] == 40
        assert pack["truncated"] is True

    def test_evidence_block_text(self):
        pack = build_evidence_pack(
            "r", "s", "static", "v",
            [{"id": "e1", "kind": "source_file", "path": "a.py",
              "title": "A", "content": "def hello(): pass"}],
        )
        block = evidence_block_text(pack)
        assert "[e1|source_file]" in block
        assert "a.py" in block
        assert "def hello" in block

    def test_evidence_block_empty_pack(self):
        pack = build_evidence_pack("r", "s", "static", "v", [])
        assert evidence_block_text(pack) == "(근거 없음)"

    def test_evidence_ids_extraction(self):
        pack = build_evidence_pack(
            "r", "s", "static", "v",
            [{"id": "e1", "kind": "source_file", "content": "x"},
             {"id": "e2", "kind": "observation", "content": "y"}],
        )
        ids = evidence_ids(pack)
        assert set(ids) == {"e1", "e2"}

    def test_content_preview_populated(self):
        pack = build_evidence_pack(
            "r", "s", "static", "v",
            [{"id": "e1", "kind": "source_file", "content": "preview text"}],
        )
        assert "content_preview" in pack["items"][0]
        assert pack["items"][0]["content_preview"] == "preview text"


# ── deterministic_verifier ───────────────────────────────────

class TestDeterministicVerifier:

    def test_pass_valid_doc(self):
        doc = _valid_static_doc()
        result = verify(doc, theme="architecture-overview",
                        evidence_ids=["e1"], doc_type="static")
        assert result["result"] == "pass"
        assert result["errors"] == []

    def test_fail_missing_frontmatter(self):
        doc = f"# No frontmatter\n\nbody [e1]\n\n## A\n## B\n{DOC_END_MARKER}"
        result = verify(doc, evidence_ids=["e1"], doc_type="static")
        codes = [e["code"] for e in result["errors"]]
        assert "frontmatter_missing" in codes
        assert result["result"] == "fail"

    def test_fail_theme_mismatch(self):
        doc = _valid_static_doc(theme="architecture-overview")
        result = verify(doc, theme="api-protocol", evidence_ids=["e1"],
                        doc_type="static", checks=("frontmatter",))
        codes = [e["code"] for e in result["errors"]]
        assert "frontmatter_theme_mismatch" in codes

    def test_fail_missing_doc_end(self):
        doc = _valid_static_doc().replace(DOC_END_MARKER, "")
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("doc_end",))
        codes = [e["code"] for e in result["errors"]]
        assert "missing_doc_end" in codes

    def test_fail_unclosed_fence(self):
        doc = _valid_static_doc().replace(
            DOC_END_MARKER, "```python\nimport os\n")
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("fences",))
        codes = [e["code"] for e in result["errors"]]
        assert "unclosed_fence" in codes

    def test_pass_closed_fence(self):
        doc = _valid_static_doc().replace(
            DOC_END_MARKER, "```python\nimport os\n```\n" + DOC_END_MARKER)
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("fences",))
        assert result["result"] == "pass"

    def test_mermaid_valid(self):
        doc = (_valid_static_doc().replace(
            DOC_END_MARKER,
            "```mermaid\ngraph LR\n  A-->B\n```\n" + DOC_END_MARKER))
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("mermaid",))
        assert result["result"] == "pass"

    def test_mermaid_invalid_type(self):
        doc = (_valid_static_doc().replace(
            DOC_END_MARKER,
            "```mermaid\nnot_a_diagram_type\n  A-->B\n```\n" + DOC_END_MARKER))
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("mermaid",))
        codes = [e["code"] for e in result["errors"]]
        assert any("mermaid" in c for c in codes)

    def test_fail_missing_evidence_id(self):
        doc = _valid_static_doc()
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("evidence_ids",))
        assert result["result"] == "pass"
        result2 = verify(doc, evidence_ids=["e2"], doc_type="static",
                         checks=("evidence_ids",))
        codes = [e["code"] for e in result2["errors"]]
        assert "missing_evidence_id" in codes

    def test_fail_secret_leak_assignment(self):
        doc = _valid_static_doc().replace(
            "[e1]", "password=supersecret123 [e1]")
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("secrets",))
        codes = [e["code"] for e in result["errors"]]
        assert any("secret" in c for c in codes)

    def test_fail_secret_leak_url(self):
        doc = _valid_static_doc().replace(
            "[e1]", "postgres://user:pass@host:5432/db [e1]")
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("secrets",))
        codes = [e["code"] for e in result["errors"]]
        assert any("secret" in c for c in codes)

    def test_pass_redacted_secret(self):
        doc = _valid_static_doc().replace(
            "[e1]", "password=***REDACTED*** [e1]")
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("secrets",))
        assert result["result"] == "pass"

    def test_fail_forbidden_word_korean(self):
        doc = _valid_static_doc().replace(
            "[e1]", "일반적으로 시스템은 [e1]")
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("forbidden_words",))
        codes = [e["code"] for e in result["errors"]]
        assert "forbidden_word" in codes

    def test_fail_forbidden_word_english(self):
        doc = _valid_static_doc().replace(
            "[e1]", "usually the system [e1]")
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("forbidden_words",))
        codes = [e["code"] for e in result["errors"]]
        assert "forbidden_word" in codes

    def test_fail_insufficient_sections(self):
        doc = (
            "---\ntheme: architecture-overview\nsource_files: [a.py]\n---\n\n"
            f"# Title\n\nbody [e1]\n\n{DOC_END_MARKER}"
        )
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("section_coverage",))
        codes = [e["code"] for e in result["errors"]]
        assert "insufficient_sections" in codes

    def test_pass_sufficient_sections(self):
        doc = _valid_static_doc()
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("section_coverage",))
        assert result["result"] == "pass"

    def test_manual_doc_type_requires_release(self):
        doc = _valid_manual_doc()
        result = verify(doc, evidence_ids=["o1", "o2"], doc_type="manual",
                        checks=("frontmatter",))
        assert result["result"] == "pass"

    def test_manual_missing_release_field(self):
        doc = _valid_manual_doc().replace("release:\n  tag: v1.0.0\n  artifact: app.msi\n", "")
        result = verify(doc, evidence_ids=["o1", "o2"], doc_type="manual",
                        checks=("frontmatter",))
        codes = [e["code"] for e in result["errors"]]
        assert "frontmatter_missing_field" in codes

    def test_partial_checks(self):
        doc = _valid_static_doc()
        result = verify(doc, evidence_ids=["e1"], doc_type="static",
                        checks=("doc_end",))
        assert result["result"] == "pass"

    def test_summarize_schema_status_pass(self):
        result = {"result": "pass", "errors": []}
        s = summarize(result)
        assert s["schema_status"] == "pass"
        assert s["mermaid_status"] == "pass"
        assert s["redaction_status"] == "pass"

    def test_summarize_schema_status_fail(self):
        result = {"result": "fail", "errors": [
            {"code": "frontmatter_missing", "location": "", "message": ""},
            {"code": "secret_leak", "location": "", "message": ""},
            {"code": "mermaid_parse", "location": "", "message": ""},
        ]}
        s = summarize(result)
        assert s["schema_status"] == "fail"
        assert s["redaction_status"] == "fail"
        assert s["mermaid_status"] == "fail"


# ── grounding_critic ─────────────────────────────────────────

class TestGroundingCritic:

    def test_format_critic_prompt_returns_messages(self):
        msgs = format_critic_prompt("doc content", "evidence block",
                                    {"perspective": "test", "audience": "dev"})
        assert isinstance(msgs, list)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert "test" in msgs[1]["content"]

    def test_format_critic_prompt_string_contract(self):
        msgs = format_critic_prompt("doc", "evidence", "custom contract text")
        assert "custom contract text" in msgs[1]["content"]

    def test_parse_verdict_pass(self):
        raw = '{"result": "pass", "score": 0.95, "blocking_findings": [], "nonblocking_notes": ["ok"]}'
        v = parse_critic_verdict(raw)
        assert v["result"] == "pass"
        assert v["score"] == 0.95
        assert v["blocking_findings"] == []

    def test_parse_verdict_fail_with_findings(self):
        raw = json.dumps({
            "result": "fail", "score": 0.3,
            "blocking_findings": [
                {"severity": "blocker", "claim": "hallucination",
                 "reason": "not in evidence", "required_fix": "remove",
                 "evidence_refs": ["e1"]},
            ],
            "nonblocking_notes": [],
        })
        v = parse_critic_verdict(raw)
        assert v["result"] == "fail"
        assert v["score"] == 0.3
        assert len(v["blocking_findings"]) == 1
        assert v["blocking_findings"][0]["severity"] == "blocker"

    def test_parse_verdict_in_fence(self):
        raw = '```json\n{"result": "pass", "score": 0.9, "blocking_findings": []}\n```'
        v = parse_critic_verdict(raw)
        assert v["result"] == "pass"
        assert v["score"] == 0.9

    def test_parse_verdict_with_prose(self):
        raw = 'Here is my verdict:\n{"result": "fail", "score": 0.2, "blocking_findings": []}\nDone.'
        v = parse_critic_verdict(raw)
        assert v["result"] == "fail"

    def test_parse_verdict_empty(self):
        v = parse_critic_verdict("")
        assert v["result"] == "fail"
        assert v["score"] == 0.0

    def test_parse_verdict_invalid_json(self):
        v = parse_critic_verdict("not json at all")
        assert v["result"] == "fail"

    def test_parse_verdict_normalizes_severity(self):
        raw = json.dumps({
            "result": "fail", "score": 0.5,
            "blocking_findings": [
                {"severity": "BLOCKER", "claim": "x"},
                {"severity": "unknown", "claim": "y"},
            ],
        })
        v = parse_critic_verdict(raw)
        assert v["blocking_findings"][0]["severity"] == "blocker"
        assert v["blocking_findings"][1]["severity"] == "minor"

    def test_severity_counts(self):
        verdict = {
            "result": "fail",
            "blocking_findings": [
                {"severity": "blocker"}, {"severity": "blocker"},
                {"severity": "major"}, {"severity": "minor"},
            ],
        }
        counts = severity_counts(verdict)
        assert counts == {"blocker": 2, "major": 1, "minor": 1}

    def test_chunked_critic_short_doc_single_chunk(self):
        doc = _valid_static_doc()
        calls = []

        def mock_critic(messages):
            calls.append(messages)
            return '{"result": "pass", "score": 0.9, "blocking_findings": []}'

        result = chunked_critic(doc, "evidence", {"perspective": "x"},
                                chunk_size=6000, critic_fn=mock_critic)
        assert result["result"] == "pass"
        assert result["chunk_count"] == 1
        assert len(calls) == 1

    def test_chunked_critic_long_doc_multiple_chunks(self):
        long_body = "\n\n".join(f"## Section {i}\n\n{'content ' * 200}" for i in range(20))
        doc = (
            "---\ntheme: architecture-overview\n---\n\n"
            f"# Title\n\n{long_body}\n\n{DOC_END_MARKER}"
        )
        calls = []

        def mock_critic(messages):
            calls.append(messages)
            return '{"result": "pass", "score": 0.85, "blocking_findings": []}'

        result = chunked_critic(doc, "evidence", "contract",
                                chunk_size=2000, critic_fn=mock_critic)
        assert result["chunk_count"] > 1
        assert result["result"] == "pass"
        assert result["score"] == 0.85
        assert len(calls) == result["chunk_count"]

    def test_chunked_critic_aggregates_fail(self):
        long_body = "\n\n".join(f"## Section {i}\n\n{'content ' * 200}" for i in range(10))
        doc = f"---\ntheme: x\n---\n\n# T\n\n{long_body}\n\n{DOC_END_MARKER}"

        def mock_critic(messages):
            return '{"result": "fail", "score": 0.3, "blocking_findings": [{"severity": "major", "claim": "x"}]}'

        result = chunked_critic(doc, "evidence", "c", chunk_size=2000, critic_fn=mock_critic)
        assert result["result"] == "fail"
        assert result["score"] == 0.3
        assert len(result["blocking_findings"]) == result["chunk_count"]

    def test_chunked_critic_no_fn_returns_fail(self):
        doc = _valid_static_doc()
        result = chunked_critic(doc, "evidence", {"perspective": "x"},
                                chunk_size=6000, critic_fn=None)
        assert result["result"] == "fail"
        assert result["chunk_count"] >= 1

    def test_chunked_critic_handles_critic_exception(self):
        doc = _valid_static_doc()

        def failing_critic(messages):
            raise RuntimeError("LLM down")

        result = chunked_critic(doc, "evidence", "c", critic_fn=failing_critic)
        assert result["result"] == "fail"


# ── quality_gates ────────────────────────────────────────────

class TestQualityGates:

    def test_pass_all_clear(self):
        gate = evaluate_quality_gate(
            {"result": "pass", "errors": []},
            {"result": "pass", "score": 0.95, "blocking_findings": []},
        )
        assert gate["status"] == "pass"
        assert gate["failed_gate"] == ""

    def test_fail_verifier_fail(self):
        gate = evaluate_quality_gate(
            {"result": "fail", "errors": [{"code": "x"}]},
            {"result": "pass", "score": 1.0, "blocking_findings": []},
        )
        assert gate["status"] == "fail"
        assert gate["failed_gate"] == "deterministic_verifier"

    def test_fail_blocker_finding(self):
        gate = evaluate_quality_gate(
            {"result": "pass", "errors": []},
            {"result": "fail", "score": 0.5,
             "blocking_findings": [{"severity": "blocker"}]},
        )
        assert gate["status"] == "fail"
        assert gate["failed_gate"] == "grounding"

    def test_fail_major_finding(self):
        gate = evaluate_quality_gate(
            {"result": "pass", "errors": []},
            {"result": "fail", "score": 0.7,
             "blocking_findings": [{"severity": "major"}]},
        )
        assert gate["status"] == "fail"

    def test_warning_minor_only(self):
        gate = evaluate_quality_gate(
            {"result": "pass", "errors": []},
            {"result": "pass", "score": 0.9,
             "blocking_findings": [{"severity": "minor"}]},
        )
        assert gate["status"] == "warning"

    def test_fail_score_below_threshold(self):
        gate = evaluate_quality_gate(
            {"result": "pass", "errors": []},
            {"result": "pass", "score": 0.5, "blocking_findings": []},
        )
        assert gate["status"] == "fail"
        assert "score" in gate["failed_reason"]

    def test_custom_threshold(self):
        gate = evaluate_quality_gate(
            {"result": "pass", "errors": []},
            {"result": "pass", "score": 0.7, "blocking_findings": []},
            thresholds={"min_score": 0.6},
        )
        assert gate["status"] == "pass"

    def test_none_results_treated_as_pass(self):
        gate = evaluate_quality_gate(None, None)
        assert gate["status"] == "pass"

    def test_critic_result_fail_overrides(self):
        gate = evaluate_quality_gate(
            {"result": "pass", "errors": []},
            {"result": "fail", "score": 1.0, "blocking_findings": []},
        )
        assert gate["status"] == "fail"

    def test_determine_terminal_done(self):
        assert determine_terminal_status("pass") == "done"

    def test_determine_terminal_done_with_warnings(self):
        assert determine_terminal_status("warning") == "done_with_warnings"
        assert determine_terminal_status("pass", summary_warnings=1) == "done_with_warnings"

    def test_determine_terminal_failed_quality_gate(self):
        assert determine_terminal_status("fail") == "failed_quality_gate"

    def test_determine_terminal_failed_on_errors(self):
        assert determine_terminal_status("pass", summary_errors=1) == "failed"
        assert determine_terminal_status("fail", summary_errors=1) == "failed"

    def test_determine_terminal_not_evaluated(self):
        assert determine_terminal_status("not_evaluated") == "done_with_warnings"

    def test_to_webhook_payload(self):
        gate = evaluate_quality_gate(
            {"result": "pass", "errors": []},
            {"result": "pass", "score": 0.95, "blocking_findings": []},
        )
        payload = to_webhook_payload(gate, repair_attempts=2)
        assert payload["status"] == "pass"
        assert payload["score"] == 95
        assert payload["publishable"] is True
        assert payload["repair_attempts"] == 2
        assert len(payload["gates"]) == 2

    def test_default_thresholds(self):
        assert DEFAULT_THRESHOLDS["min_score"] == 0.75
        assert DEFAULT_THRESHOLDS["max_blocker"] == 0
        assert DEFAULT_THRESHOLDS["warning_major"] == 3


# ── scope_planner ────────────────────────────────────────────

class TestScopePlanner:

    def test_static_no_changes_all_skip(self):
        pack = build_evidence_pack("r", "s", "static", "v", [])
        plans = plan_static_docs([], pack)
        assert len(plans) > 0
        assert all(p["action"] == "skip" for p in plans)

    def test_static_api_change_creates_api_protocol(self):
        pack = build_evidence_pack("r", "s", "static", "v", [
            {"id": "e1", "kind": "source_file", "path": "api.py", "content": "x"},
        ])
        plans = plan_static_docs([{
            "id": "cu1", "files": ["api.py"], "change_type": "api",
            "significance": "material", "summary": "new endpoint",
            "doc_impact": ["api-protocol"],
        }], pack)
        api_plan = next(p for p in plans if p["theme"] == "api-protocol")
        assert api_plan["action"] == "create"
        assert api_plan["risk"] == "medium"
        assert "e1" in api_plan["required_evidence"]

    def test_static_risky_escalates_risk(self):
        pack = build_evidence_pack("r", "s", "static", "v", [
            {"id": "e1", "kind": "source_file", "path": "migration.py", "content": "x"},
        ])
        plans = plan_static_docs([{
            "id": "cu1", "files": ["migration.py"], "change_type": "architecture",
            "significance": "risky", "summary": "DB migration",
            "doc_impact": ["architecture-overview"],
        }], pack)
        arch_plan = next(p for p in plans if p["theme"] == "architecture-overview")
        assert arch_plan["risk"] == "high"

    def test_static_test_only_change_skipped(self):
        pack = build_evidence_pack("r", "s", "static", "v", [
            {"id": "e1", "kind": "source_file", "path": "test_x.py", "content": "x"},
        ])
        plans = plan_static_docs([{
            "id": "cu1", "files": ["test_x.py"], "change_type": "test",
            "significance": "trivial", "summary": "test only",
        }], pack)
        assert all(p["action"] == "skip" for p in plans if "test" not in p["theme"])

    def test_static_existing_doc_updates(self):
        pack = build_evidence_pack("r", "s", "static", "v", [
            {"id": "e1", "kind": "source_file", "path": "a.py", "content": "x"},
        ])
        plans = plan_static_docs([{
            "id": "cu1", "files": ["a.py"], "change_type": "architecture",
            "significance": "minor", "doc_impact": ["intro"],
        }], pack, existing_docs=["intro"])
        intro_plan = next(p for p in plans if p["theme"] == "intro")
        assert intro_plan["action"] == "update"

    def test_manual_normal_creates_both(self):
        plans = plan_manual_docs(
            {"completed": ["s1", "s2"], "failed": [], "observation_count": 10},
            {"coverage_pct": 85.0, "unreached": []},
        )
        user_plan = next(p for p in plans if p["theme"] == "user-manual")
        ops_plan = next(p for p in plans if p["theme"] == "operator-manual")
        assert user_plan["action"] == "create"
        assert ops_plan["action"] == "create"

    def test_manual_terminal_failure_skips_user(self):
        plans = plan_manual_docs(
            {"completed": [], "failed": ["s1"], "terminal_failure": "s1",
             "observation_count": 5},
            {"coverage_pct": 50.0, "unreached": [{"id": "settings"}]},
        )
        user_plan = next(p for p in plans if p["theme"] == "user-manual")
        assert user_plan["action"] == "skip"
        assert "required scenario" in user_plan["reason"]

    def test_manual_no_observations_skips_both(self):
        plans = plan_manual_docs(
            {"completed": [], "failed": [], "observation_count": 0},
            {"coverage_pct": 0.0, "unreached": []},
        )
        assert all(p["action"] == "skip" for p in plans)

    def test_manual_low_coverage_warning(self):
        plans = plan_manual_docs(
            {"completed": ["s1"], "failed": [], "observation_count": 5},
            {"coverage_pct": 40.0, "unreached": [{"id": "settings"}]},
            coverage_threshold=70.0,
        )
        user_plan = next(p for p in plans if p["theme"] == "user-manual")
        assert user_plan["coverage_gate"] != "pass"
        assert user_plan["risk"] == "high"

    def test_manual_deprecate_candidate(self):
        plans = plan_manual_docs(
            {"completed": ["s1"], "failed": [], "observation_count": 5},
            {"coverage_pct": 90.0, "unreached": []},
            existing_docs=["user-manual", "old-legacy-manual"],
        )
        legacy = next(p for p in plans if p["theme"] == "old-legacy-manual")
        assert legacy["action"] == "deprecate-candidate"

    def test_actionable_plans_filters_skip(self):
        plans = [
            {"theme": "a", "action": "create"},
            {"theme": "b", "action": "skip"},
            {"theme": "c", "action": "deprecate-candidate"},
            {"theme": "d", "action": "update"},
        ]
        actionable = actionable_plans(plans)
        assert len(actionable) == 2
        assert {p["theme"] for p in actionable} == {"a", "d"}
