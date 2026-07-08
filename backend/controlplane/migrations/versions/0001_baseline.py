"""baseline current schema

Initial schema for wiki-pipeline Control Plane. Mirrors what `init_db(create_all)`
emitted for the existing models at the time this migration was authored.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-08

This migration is the canonical starting point for production deployments.
Local dev (SQLite) can still use init_db(create_all) for quick bootstrap, but
prod (PostgreSQL) must run `alembic upgrade head` to evolve schema.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    json_type = sa.JSON() if is_sqlite else sa.dialects.postgresql.JSONB()

    # ?? scm_instances (decision-scm-multi-instance-github-mvp) ??
    op.create_table(
        "scm_instances",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("label", sa.String(200), nullable=True, server_default=""),
        sa.Column("base_url", sa.String(500), nullable=True, server_default=""),
        sa.Column("token", sa.Text(), nullable=True, server_default=""),
        sa.Column("token_header", sa.String(40), nullable=True,
                  server_default="PRIVATE-TOKEN"),
        sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ?? sources (decision-repo-dev-release-registration) ??
    op.create_table(
        "sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("instance_id", sa.String(64),
                  sa.ForeignKey("scm_instances.id"), nullable=False),
        sa.Column("label", sa.String(200), nullable=True, server_default=""),
        sa.Column("repo", sa.String(300), nullable=False),
        sa.Column("token", sa.Text(), nullable=True, server_default=""),
        sa.Column("doc_dir", sa.String(300), nullable=True, server_default=""),
        sa.Column("themes", sa.String(500), nullable=True, server_default=""),
        sa.Column("owner_email", sa.String(200), nullable=True, server_default=""),
        sa.Column("schedule_cron", sa.String(100), nullable=True, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("disabled_reason", sa.String(300), nullable=True, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ?? source_branches (concept-idempotent-sha) ??
    op.create_table(
        "source_branches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(64),
                  sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("branch", sa.String(200), nullable=True, server_default=""),
        sa.Column("baseline_sha", sa.String(64), nullable=True, server_default=""),
        sa.Column("last_processed_sha", sa.String(64), nullable=True, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source_id", "role", name="uq_source_branches_source_role"),
    )

    # ?? source_schedules (decision-schedule-per-source) ??
    op.create_table(
        "source_schedules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(64),
                  sa.ForeignKey("sources.id"), nullable=False, index=True),
        sa.Column("label", sa.String(120), nullable=True, server_default=""),
        sa.Column("pipeline_id", sa.String(32), nullable=True, server_default="static"),
        sa.Column("mode", sa.String(16), nullable=True, server_default="auto"),
        sa.Column("branch_role", sa.String(16), nullable=True, server_default="dev"),
        sa.Column("cron", sa.String(100), nullable=True, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ?? runs (concept-idempotent-sha + decision-observability-event-contract) ??
    op.create_table(
        "runs",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=True, index=True, server_default=""),
        sa.Column("pipeline_id", sa.String(32), nullable=True, server_default=""),
        sa.Column("mode", sa.String(16), nullable=True, server_default=""),
        sa.Column("branch_role", sa.String(16), nullable=True, server_default="dev"),
        sa.Column("trigger", sa.String(16), nullable=True, server_default="manual"),
        sa.Column("status", sa.String(16), nullable=True, server_default="pending"),
        sa.Column("from_sha", sa.String(64), nullable=True, server_default=""),
        sa.Column("to_sha", sa.String(64), nullable=True, server_default=""),
        sa.Column("doc_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("mr_url", sa.String(500), nullable=True, server_default=""),
        sa.Column("error", sa.Text(), nullable=True, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ?? run_events (decision-observability-event-contract) ??
    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(120), nullable=False, index=True),
        sa.Column("ts", sa.String(40), nullable=True, server_default=""),
        sa.Column("layer", sa.String(20), nullable=True, server_default=""),
        sa.Column("stage", sa.String(200), nullable=True, server_default=""),
        sa.Column("status", sa.String(16), nullable=True, server_default=""),
        sa.Column("payload", sa.Text(), nullable=True, server_default="{}"),
    )

    # ?? run_model_usage (cost aggregation) ??
    op.create_table(
        "run_model_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(120), nullable=False, index=True),
        sa.Column("source_id", sa.String(64), nullable=True, server_default="", index=True),
        sa.Column("pipeline_id", sa.String(32), nullable=True, server_default=""),
        sa.Column("provider", sa.String(80), nullable=True, server_default=""),
        sa.Column("model", sa.String(200), nullable=True, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("calls", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", "provider", "model",
                            name="uq_run_model_usage_run_provider_model"),
    )

    # ?? doc_targets (decision-mr-review-gate) ??
    op.create_table(
        "doc_targets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(200), nullable=True, server_default=""),
        sa.Column("kind", sa.String(16), nullable=True, server_default="gitlab"),
        sa.Column("url", sa.String(500), nullable=True, server_default=""),
        sa.Column("project_id", sa.String(100), nullable=True, server_default=""),
        sa.Column("project_path", sa.String(300), nullable=True, server_default=""),
        sa.Column("token", sa.Text(), nullable=True, server_default=""),
        sa.Column("token_header", sa.String(40), nullable=True,
                  server_default="PRIVATE-TOKEN"),
        sa.Column("default_branch", sa.String(100), nullable=True, server_default="master"),
        sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ?? source_release_tags (decision-release-tag-trigger) ??
    op.create_table(
        "source_release_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(64),
                  sa.ForeignKey("sources.id"), nullable=False, index=True),
        sa.Column("branch_role", sa.String(16), nullable=True, server_default="release"),
        sa.Column("last_seen_tag", sa.String(200), nullable=True, server_default=""),
        sa.Column("last_seen_sha", sa.String(64), nullable=True, server_default=""),
        sa.Column("last_run_id", sa.String(120), nullable=True, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source_id", "branch_role",
                            name="uq_source_release_tags_source_role"),
    )


def downgrade() -> None:
    op.drop_table("source_release_tags")
    op.drop_table("doc_targets")
    op.drop_table("run_model_usage")
    op.drop_table("run_events")
    op.drop_table("runs")
    op.drop_table("source_schedules")
    op.drop_table("source_branches")
    op.drop_table("sources")
    op.drop_table("scm_instances")
