"""AI pipeline quality + evidence + manual profile tables (2026-07-08).

P0 backend API extension based on:
  - raw/2026-07-08-backend-api-ai-pipeline-improvement-plan.md
  - raw/2026-07-08-docu-automation-data-plane-review.md
  - raw/2026-07-08-manual-automation-data-plane-review.md

Revision ID: 0004_pipeline_quality_evidence
Revises: 0003_system_settings
Create Date: 2026-07-08
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_pipeline_quality_evidence"
down_revision: Union[str, None] = "0003_system_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    json_type = sa.JSON() if is_sqlite else sa.dialects.postgresql.JSONB()

    # --- runs extension ---
    op.add_column("runs", sa.Column("attempt", sa.Integer(), nullable=True, server_default="1"))
    op.add_column("runs", sa.Column("runner_pid", sa.String(20), nullable=True, server_default=""))
    op.add_column("runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("runs", sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("runs", sa.Column("status_reason", sa.Text(), nullable=True, server_default=""))
    op.add_column("runs", sa.Column("publishable", sa.Boolean(), nullable=True, server_default=sa.false()))
    op.add_column("runs", sa.Column("blocked_reason", sa.Text(), nullable=True, server_default=""))
    op.add_column("runs", sa.Column("quality_status", sa.String(24), nullable=True, server_default="not_evaluated"))
    op.add_column("runs", sa.Column("quality_score", sa.Integer(), nullable=True))
    op.add_column("runs", sa.Column("publish_state", sa.String(24), nullable=True, server_default="unknown"))
    op.add_column("runs", sa.Column("warning_publish_policy", sa.String(24), nullable=True, server_default="review_required"))
    op.add_column("runs", sa.Column("artifact_version", sa.String(120), nullable=True, server_default=""))
    op.add_column("runs", sa.Column("release_tag", sa.String(120), nullable=True, server_default=""))
    op.add_column("runs", sa.Column("source_version_ref", sa.String(120), nullable=True, server_default=""))
    op.add_column("runs", sa.Column("snapshot_version", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("runs", sa.Column("from_sha_snapshot", sa.String(64), nullable=True, server_default=""))
    op.add_column("runs", sa.Column("stale_complete", sa.Boolean(), nullable=True, server_default=sa.false()))
    op.create_index("ix_runs_status", "runs", ["status"], unique=False)
    op.create_index("ix_runs_quality_status", "runs", ["quality_status"], unique=False)
    op.create_index("ix_runs_publishable", "runs", ["publishable"], unique=False)
    op.create_index("ix_runs_heartbeat", "runs", ["heartbeat_at"], unique=False)

    # --- run_events extension ---
    op.add_column("run_events", sa.Column("event_id", sa.String(120), nullable=True, server_default=""))
    op.add_column("run_events", sa.Column("seq", sa.Integer(), nullable=True))
    op.add_column("run_events", sa.Column("kind", sa.String(120), nullable=True, server_default=""))
    op.add_column("run_events", sa.Column("severity", sa.String(16), nullable=True, server_default="info"))
    op.add_column("run_events", sa.Column("role", sa.String(80), nullable=True, server_default=""))
    op.add_column("run_events", sa.Column("dedupe_key", sa.String(200), nullable=True, server_default=""))
    op.add_column("run_events", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_run_events_run_seq", "run_events", ["run_id", "seq"], unique=False)
    op.create_index("ix_run_events_run_kind", "run_events", ["run_id", "kind"], unique=False)

    # --- run_quality_reports ---
    op.create_table(
        "run_quality_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(120),
                  sa.ForeignKey("runs.id"), nullable=False, index=True, unique=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="not_evaluated"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("publishable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failed_gate", sa.String(80), nullable=True, server_default=""),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repair_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deterministic_verifier_status", sa.String(16), nullable=True, server_default=""),
        sa.Column("grounding_critic_status", sa.String(16), nullable=True, server_default=""),
        sa.Column("schema_status", sa.String(16), nullable=True, server_default=""),
        sa.Column("mermaid_status", sa.String(16), nullable=True, server_default=""),
        sa.Column("redaction_status", sa.String(16), nullable=True, server_default=""),
        sa.Column("gates_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- run_quality_findings ---
    op.create_table(
        "run_quality_findings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(120),
                  sa.ForeignKey("runs.id"), nullable=False, index=True),
        sa.Column("doc_id", sa.String(200), nullable=True, server_default=""),
        sa.Column("gate", sa.String(80), nullable=False, server_default=""),
        sa.Column("code", sa.String(120), nullable=False, server_default=""),
        sa.Column("severity", sa.String(16), nullable=False, server_default="warning"),
        sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("message", sa.Text(), nullable=True, server_default=""),
        sa.Column("location", sa.String(200), nullable=True, server_default=""),
        sa.Column("evidence_ref", sa.String(200), nullable=True, server_default=""),
        sa.Column("repair_status", sa.String(40), nullable=True, server_default=""),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_run_quality_findings_blocking",
                    "run_quality_findings", ["run_id", "blocking"], unique=False)

    # --- run_evidence_packs ---
    op.create_table(
        "run_evidence_packs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(120),
                  sa.ForeignKey("runs.id"), nullable=False, index=True),
        sa.Column("source_id", sa.String(64), nullable=True, server_default=""),
        sa.Column("pipeline_id", sa.String(32), nullable=True, server_default=""),
        sa.Column("version_ref", sa.String(120), nullable=True, server_default=""),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unsupported_claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("omitted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manifest_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- run_evidence_items ---
    op.create_table(
        "run_evidence_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("pack_id", sa.String(64),
                  sa.ForeignKey("run_evidence_packs.id"), nullable=False, index=True),
        sa.Column("run_id", sa.String(120),
                  sa.ForeignKey("runs.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(40), nullable=False, server_default="source_file"),
        sa.Column("title", sa.String(300), nullable=True, server_default=""),
        sa.Column("path", sa.String(500), nullable=True, server_default=""),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("observation_id", sa.String(64), nullable=True, server_default=""),
        sa.Column("scenario_id", sa.String(64), nullable=True, server_default=""),
        sa.Column("artifact_ref", sa.String(500), nullable=True, server_default=""),
        sa.Column("content_preview", sa.Text(), nullable=True, server_default=""),
        sa.Column("content_uri", sa.String(500), nullable=True, server_default=""),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_run_evidence_items_run_kind",
                    "run_evidence_items", ["run_id", "kind"], unique=False)

    # --- run_doc_outputs ---
    op.create_table(
        "run_doc_outputs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(120),
                  sa.ForeignKey("runs.id"), nullable=False, index=True),
        sa.Column("theme", sa.String(200), nullable=True, server_default=""),
        sa.Column("path", sa.String(500), nullable=True, server_default=""),
        sa.Column("title", sa.String(300), nullable=True, server_default=""),
        sa.Column("action", sa.String(40), nullable=False, server_default="create"),
        sa.Column("quality_status", sa.String(24), nullable=True, server_default="not_evaluated"),
        sa.Column("publishable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unsupported_claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("schema_status", sa.String(16), nullable=True, server_default=""),
        sa.Column("mermaid_status", sa.String(16), nullable=True, server_default=""),
        sa.Column("mr_inclusion_status", sa.String(24), nullable=True, server_default="candidate"),
        sa.Column("content_sha256", sa.String(64), nullable=True, server_default=""),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- source_manual_profiles ---
    op.create_table(
        "source_manual_profiles",
        sa.Column("source_id", sa.String(64),
                  sa.ForeignKey("sources.id"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mcp_endpoint_url", sa.String(500), nullable=True, server_default=""),
        sa.Column("mcp_transport", sa.String(16), nullable=True, server_default="sse"),
        sa.Column("host_label", sa.String(200), nullable=True, server_default=""),
        sa.Column("host_ip", sa.String(64), nullable=True, server_default=""),
        sa.Column("host_port", sa.Integer(), nullable=True),
        sa.Column("vnc_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vnc_host", sa.String(64), nullable=True, server_default=""),
        sa.Column("vnc_port", sa.Integer(), nullable=True),
        sa.Column("vnc_gateway_policy", sa.String(40), nullable=True, server_default="view_only"),
        sa.Column("tool_allowlist_json", json_type, nullable=True),
        sa.Column("secret_refs_json", json_type, nullable=True),
        sa.Column("artifact_selector_json", json_type, nullable=True),
        sa.Column("install_profile_json", json_type, nullable=True),
        sa.Column("readiness_check_json", json_type, nullable=True),
        sa.Column("smoke_check_json", json_type, nullable=True),
        sa.Column("coverage_threshold", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("failure_policy", sa.String(40), nullable=False, server_default="block"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(120), nullable=True, server_default=""),
    )

    # --- manual_scenario_sets ---
    op.create_table(
        "manual_scenario_sets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source_id", sa.String(64),
                  sa.ForeignKey("sources.id"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False, server_default="default"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("scenario_json", json_type, nullable=True),
        sa.Column("lint_status", sa.String(16), nullable=True, server_default=""),
        sa.Column("lint_errors_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(120), nullable=True, server_default=""),
        sa.UniqueConstraint("source_id", "name", name="uq_manual_scenario_sets_src_name"),
    )

    # --- run_artifacts ---
    op.create_table(
        "run_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(120),
                  sa.ForeignKey("runs.id"), nullable=False, index=True),
        sa.Column("source_id", sa.String(64), nullable=True, server_default=""),
        sa.Column("release_tag", sa.String(120), nullable=True, server_default=""),
        sa.Column("artifact_name", sa.String(200), nullable=True, server_default=""),
        sa.Column("artifact_url", sa.String(500), nullable=True, server_default=""),
        sa.Column("artifact_sha256", sa.String(64), nullable=True, server_default=""),
        sa.Column("artifact_type", sa.String(16), nullable=True, server_default="unknown"),
        sa.Column("selected_by", sa.String(32), nullable=True, server_default="policy"),
        sa.Column("build_status", sa.String(16), nullable=True, server_default="unknown"),
        sa.Column("download_status", sa.String(16), nullable=True, server_default="unknown"),
        sa.Column("deploy_status", sa.String(16), nullable=True, server_default="unknown"),
        sa.Column("install_status", sa.String(16), nullable=True, server_default="unknown"),
        sa.Column("readiness_status", sa.String(16), nullable=True, server_default="unknown"),
        sa.Column("smoke_status", sa.String(16), nullable=True, server_default="unknown"),
        sa.Column("installed_version", sa.String(120), nullable=True, server_default=""),
        sa.Column("error", sa.Text(), nullable=True, server_default=""),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- run_coverage_reports ---
    op.create_table(
        "run_coverage_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(120),
                  sa.ForeignKey("runs.id"), nullable=False, unique=True, index=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="not_applicable"),
        sa.Column("percentage", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("reached", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("misses_json", json_type, nullable=True),
        sa.Column("scenario_results_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- run_vnc_sessions ---
    op.create_table(
        "run_vnc_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(120),
                  sa.ForeignKey("runs.id"), nullable=False, unique=True, index=True),
        sa.Column("session_id", sa.String(64), nullable=True, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="unavailable"),
        sa.Column("host_label", sa.String(200), nullable=True, server_default=""),
        sa.Column("host_ip_encrypted", sa.Text(), nullable=True, server_default=""),
        sa.Column("host_port", sa.Integer(), nullable=True),
        sa.Column("gateway_url", sa.String(500), nullable=True, server_default=""),
        sa.Column("view_only", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("current_scenario_step", sa.String(200), nullable=True, server_default=""),
        sa.Column("current_action", sa.String(200), nullable=True, server_default=""),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("resolution", sa.String(40), nullable=True, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True, server_default=""),
    )

    # --- source_release_tags extension (manual processed-release pointer) ---
    op.add_column("source_release_tags", sa.Column("last_triggered_tag", sa.String(200), nullable=True, server_default=""))
    op.add_column("source_release_tags", sa.Column("last_submitted_tag", sa.String(200), nullable=True, server_default=""))
    op.add_column("source_release_tags", sa.Column("last_merged_tag", sa.String(200), nullable=True, server_default=""))
    op.add_column("source_release_tags", sa.Column("last_successful_run_id", sa.String(120), nullable=True, server_default=""))
    op.add_column("source_release_tags", sa.Column("artifact_digest", sa.String(64), nullable=True, server_default=""))
    op.add_column("source_release_tags", sa.Column("last_launch_status", sa.String(24), nullable=True, server_default=""))


def downgrade() -> None:
    op.drop_index("ix_run_evidence_items_run_kind", table_name="run_evidence_items")
    op.drop_index("ix_run_quality_findings_blocking", table_name="run_quality_findings")
    op.drop_index("ix_run_events_run_kind", table_name="run_events")
    op.drop_index("ix_run_events_run_seq", table_name="run_events")
    op.drop_index("ix_runs_heartbeat", table_name="runs")
    op.drop_index("ix_runs_publishable", table_name="runs")
    op.drop_index("ix_runs_quality_status", table_name="runs")
    op.drop_index("ix_runs_status", table_name="runs")

    op.drop_table("run_vnc_sessions")
    op.drop_table("run_coverage_reports")
    op.drop_table("run_artifacts")
    op.drop_table("manual_scenario_sets")
    op.drop_table("source_manual_profiles")
    op.drop_table("run_doc_outputs")
    op.drop_table("run_evidence_items")
    op.drop_table("run_evidence_packs")
    op.drop_table("run_quality_findings")
    op.drop_table("run_quality_reports")

    for col in (
        "received_at", "dedupe_key", "role", "severity", "kind", "seq", "event_id",
    ):
        op.drop_column("run_events", col)

    for col in (
        "snapshot_version", "source_version_ref", "release_tag", "artifact_version",
        "warning_publish_policy", "publish_state", "quality_score", "quality_status",
        "blocked_reason", "publishable", "status_reason", "terminal_at", "heartbeat_at",
        "started_at", "runner_pid", "attempt", "from_sha_snapshot", "stale_complete",
    ):
        op.drop_column("runs", col)

    for col in (
        "last_launch_status", "artifact_digest", "last_successful_run_id",
        "last_merged_tag", "last_submitted_tag", "last_triggered_tag",
    ):
        op.drop_column("source_release_tags", col)
