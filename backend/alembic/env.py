"""Alembic environment — DATABASE.md §14 (single-head chain).

The URL resolves in this order:
1. ``-x db_url=...`` CLI override (used by tests for throwaway databases)
2. ``DATABASE_URL`` from the app settings (.env / environment)
3. SQLite fallback for the local demo
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.database import create_db_engine
from app import models  # noqa: F401  — registers every table on Base.metadata
from app.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    if x_args.get("db_url"):
        return x_args["db_url"]
    env_url = os.environ.get("DATABASE_URL") or os.environ.get("database_url")
    if env_url:
        return env_url
    try:
        from app.core.config import settings

        if settings.database_url:
            return settings.database_url
    except Exception:
        pass
    return "sqlite:///./alembic_scratch.db"


def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests pass a throwaway engine via x:db_url; everything else reads settings.
    if context.get_x_argument(as_dictionary=True).get("db_url"):
        engine = create_db_engine(_resolve_url())
    else:
        engine = create_db_engine()
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
