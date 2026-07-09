"""Alembic environment ? Control Plane  .

:
  #    (  )
  alembic revision --autogenerate -m "add foo column"

  # 
  alembic upgrade head

  #   
  alembic downgrade -1

init_db() (create_all)      ?   alembic
upgrade head  schema  . control_db_url    SQLite  .
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# backend  path   Base.metadata  import .
import sys
from pathlib import Path
_REPO_DIR = Path(__file__).resolve().parents[3]
if str(_REPO_DIR) not in sys.path:
    sys.path.insert(0, str(_REPO_DIR))

from backend.controlplane.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    # alembic.ini     cp949    .
    # UTF-8   ?        .
    fileConfig(config.config_file_name, encoding="utf-8")

target_metadata = Base.metadata


def _resolve_db_url() -> str:
    """Alembic  alembic.ini  sqlalchemy.url   CONTROL_DB_URL 
     ?   URL  /INI    .
    """
    env = os.environ.get("CONTROL_DB_URL", "").strip()
    if env:
        return env
    # : .env  control_db_url (Settings )
    try:
        from backend.controlplane.settings import load_cp_settings
        return load_cp_settings().db_url
    except Exception:  # noqa: BLE001
        return "sqlite:///./out/control-plane.sqlite"


def run_migrations_offline() -> None:
    """SQL  migration SQL   ? dry run/CI ."""
    url = _resolve_db_url()
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _resolve_db_url()
    config.set_main_option("sqlalchemy.url", url)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            render_as_batch=url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
