"""system_settings table (ENT-F 후속 · LLM Settings DB-persisted)

LLM settings 를 .env 에서 DB 로 옮긴다. 운영 중 대시보드에서 변경 가능.
SecretBox 와 별개 컨텍스트 — v1 은 평문 저장 (운영에서는 Fernet 추가 권장).

Revision ID: 0003_system_settings
Revises: 0002_audit_and_token_rotation
Create Date: 2026-07-08
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_system_settings"
down_revision: Union[str, None] = "0002_audit_and_token_rotation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(120), nullable=True, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
