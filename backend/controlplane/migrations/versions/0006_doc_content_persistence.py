"""RunDocOutput content persistence — DB 기반 문서 콘텐츠 서빙.

docu-automation(static) · manual-automation 산출물의 마크다운 원문을 DB 에 저장해
프런트엔드가 디스크(out/) 의존 없이 접근할 수 있게 한다. runner 가 doc-outputs
webhook 으로 content 를 함께 전송 → upsert 시 content_text 컬럼에 저장.

Revision ID: 0006_doc_content_persistence
Revises: 0005_requirements_collector
Create Date: 2026-07-09
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_doc_content_persistence"
down_revision: Union[str, None] = "0005_requirements_collector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # run_doc_outputs 에 문서 원문 저장 컬럼 추가.
    # content_text: 마크다운 원문 (deferred — 리스트 조회 시 로드 안 함)
    # content_size: 원문 바이트 수 (리스트에서 크기 표시용)
    op.add_column("run_doc_outputs",
                  sa.Column("content_text", sa.Text(), nullable=True, server_default=""))
    op.add_column("run_doc_outputs",
                  sa.Column("content_size", sa.Integer(), nullable=True, server_default="0"))


def downgrade() -> None:
    op.drop_column("run_doc_outputs", "content_size")
    op.drop_column("run_doc_outputs", "content_text")
