"""Alembic migration environment.

Wired to the application's own sources of truth so migrations never drift:

* ``target_metadata`` is the ORM ``Base.metadata`` (importing the models module
  registers ``gun`` / ``score`` on it), so ``--autogenerate`` diffs against the
  real models.
* the database URL comes from :class:`Settings` (the single ``DATABASE_URL``
  setting), not a hardcoded value in ``alembic.ini`` — the same SQLite/PostgreSQL
  switch the app uses.

This module is migration glue (outside the Clean Architecture layer contract),
so importing infrastructure here is intentional.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.infrastructure.config import Settings
from app.infrastructure.db import Base

# Importing the models module registers GunModel / ScoreModel on Base.metadata.
import app.infrastructure.models  # noqa: F401  (side-effect import for metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Resolve the database URL from the application's settings (the single
# DATABASE_URL switch) so Alembic and the running app target the same database.
# A URL explicitly set on the Config (e.g. by a test harness pointing at a
# throwaway database) takes precedence over the default; the placeholder left in
# alembic.ini does not.
_configured_url = config.get_main_option("sqlalchemy.url")
if not _configured_url or _configured_url == "driver://user:pass@localhost/dbname":
    config.set_main_option("sqlalchemy.url", Settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a DBAPI connection (emits SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
