"""
migrations/env.py — Alembic environment configuration for FinSight data pipeline.

Reads DATABASE_URL from environment (via src.news.config) so that migration
commands use the same database as the application without duplicating the URL.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Ensure src/ is on sys.path so `from src.news...` imports work ─────────────
# This file is run by `alembic` from the project root, so we add the project
# root to sys.path explicitly.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ── Import project's Base so Alembic can introspect ORM metadata ──────────────
# We import Base (and thereby all ORM model files) so that
# `target_metadata = Base.metadata` includes all tables.
from src.news.database.models import Base  # noqa: E402
import src.news.database.models  # noqa: E402, F401 — register all ORM models with Base

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ── Read DATABASE_URL from environment (overrides alembic.ini sqlalchemy.url) ─
from src.news.config import DATABASE_URL  # noqa: E402

if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — outputs SQL to stdout rather than
    connecting to a database. Useful for generating migration scripts to
    review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode against a live database connection.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
