"""Alembic setup; DATABASE_URL is supplied by the environment."""

from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import create_engine, pool

from backend.database import Base
import backend.models  # noqa: F401 - registers tables with Base.metadata

config = context.config
if config.config_file_name and config.get_section(config.config_ini_section).get("loggers"):
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Set DATABASE_URL to a postgresql+psycopg:// URL")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(), target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
