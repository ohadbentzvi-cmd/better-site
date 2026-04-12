"""Alembic environment config.

Reads ``DATABASE_URL`` from .env via pipeline.config and imports all models
so autogenerate can diff them against the live DB.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Side-effect import registers every model on Base.metadata
from pipeline import models  # noqa: F401
from pipeline.config import get_settings
from pipeline.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the DB URL from .env so alembic.ini can stay empty
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL without a live DB."""
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
    """Run migrations with a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
