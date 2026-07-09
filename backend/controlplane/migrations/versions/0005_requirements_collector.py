"""Requirements Collector tables (LLM Wiki future pipeline — requirements intake)

raw/2026-07-08-llm-wiki-development-pipeline-future-plan.md §3.
요구사항 수집·명확화·승격 단계의 storage.
Draft requirement + clarification question 으로 분리.

Revision ID: 0005_requirements_collector
Revises: 0004_pipeline_quality_evidence
Create Date: 2026-07-08
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_requirements_collector"
down_revision: Union[str, None] = "0004_pipeline_quality_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    json_type = sa.JSON() if is_sqlite else postgresql.JSONB()

    op.create_table(
        "requirements",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source_kind", sa.String(40), nullable=False, server_default="chat"),
        sa.Column("source_uri", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("problem", sa.Text(), nullable=False, server_default=""),
        sa.Column("users_json", json_type, nullable=True),
        sa.Column("goals_json", sa.Text(), nullable=True),
        sa.Column("non_goals_json", sa.Text(), nullable=True),
        sa.Column("functional_reqs_json", sa.Text(), nullable=True),
        sa.Column("non_functional_reqs_json", sa.Text(), nullable=True),
        sa.Column("constraints_json", sa.Text(), nullable=True),
        sa.Column("risks_json", sa.Text(), nullable=True),
        sa.Column("dependencies_json", sa.Text(), nullable=True),
        sa.Column("wiki_targets_json", sa.Text(), nullable=True),
        sa.Column("dev_ticket_candidates_json", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(120), nullable=False, server_default=""),
        sa.Column("priority", sa.String(16), nullable=False, server_default="should"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "requirement_questions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("requirement_id", sa.String(64),
                  sa.ForeignKey("requirements.id"), nullable=False, index=True),
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
        sa.Column("blocking", sa.String(8), nullable=False, server_default="false"),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answered_by", sa.String(120), nullable=True, server_default=""),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("requirement_questions")
    op.drop_table("requirements")
