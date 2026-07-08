"""audit log + scm_instance token rotation (ENT-F + Track B-1)

   ?    /    .

  - audit_logs  (   )
  - scm_instances.token_rotated_at  (  )
  - scm_instance_token_rotations  ( )

Revision ID: 0002_audit_and_token_rotation
Revises: 0001_baseline
Create Date: 2026-07-08
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_audit_and_token_rotation"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ?? scm_instances  token_rotated_at   (Track B-1) ??
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    with op.batch_alter_table("scm_instances") as batch:
        batch.add_column(sa.Column(
            "token_rotated_at", sa.DateTime(timezone=True), nullable=True))

    # ?? scm_instance_token_rotations  (Track B-1) ??
    op.create_table(
        "scm_instance_token_rotations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.String(64),
                  sa.ForeignKey("scm_instances.id"), nullable=False, index=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_by_token", sa.String(120), nullable=True, server_default=""),
        sa.Column("note", sa.String(200), nullable=True, server_default=""),
        sa.UniqueConstraint("instance_id", "rotated_at",
                            name="uq_scm_instance_token_rotations_instance_ts"),
    )

    # ?? audit_logs  (ENT-F) ??
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("actor", sa.String(120), nullable=True, server_default="", index=True),
        sa.Column("action", sa.String(80), nullable=True, server_default="", index=True),
        sa.Column("target_kind", sa.String(40), nullable=True, server_default=""),
        sa.Column("target_id", sa.String(200), nullable=True, server_default="", index=True),
        sa.Column("request_id", sa.String(40), nullable=True, server_default=""),
        sa.Column("detail", sa.Text(), nullable=True, server_default=""),
        sa.Column("remote_addr", sa.String(64), nullable=True, server_default=""),
    )
    #   :  audit (ts DESC) + / 
    op.create_index("ix_audit_logs_action_ts", "audit_logs",
                    ["action", "ts"])
    op.create_index("ix_audit_logs_actor_ts", "audit_logs",
                    ["actor", "ts"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_actor_ts", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action_ts", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("scm_instance_token_rotations")
    with op.batch_alter_table("scm_instances") as batch:
        batch.drop_column("token_rotated_at")
