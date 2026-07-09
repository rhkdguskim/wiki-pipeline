"""Manual profile app environment + branch role policy.

SourceManualProfile 에 app_environment_json 컬럼 추가 — 앱 실행 환경 설정
(app_path, app_args, env_vars, working_dir 등). MCP 가 이 정보를 받아
원격 호스트에서 앱을 환경에 맞게 실행한다.

또한 브랜치 고정 정책을 코드에 반영:
- docu-automation (static) → dev 브랜치 고정
- manual-automation (manual) → release 브랜치 고정
이 정책은 서비스 계층에서 강제하므로 마이그레이션에 컬럼 변경은 없다.

Revision ID: 0007_manual_profile_app_env
Revises: 0006_doc_content_persistence
Create Date: 2026-07-09
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_manual_profile_app_env"
down_revision: Union[str, None] = "0006_doc_content_persistence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    json_type = sa.JSON() if is_sqlite else postgresql.JSONB()

    # source_manual_profiles 에 앱 실행 환경 JSON 컬럼 추가.
    op.add_column("source_manual_profiles",
                  sa.Column("app_environment_json", json_type, nullable=True))


def downgrade() -> None:
    op.drop_column("source_manual_profiles", "app_environment_json")
