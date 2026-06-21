"""SQLAlchemy 2.0 engine/session setup and declarative base (infrastructure).

The engine is built from :class:`Settings` so the database backend is a single
configuration value (SQLite by default, PostgreSQL via ``DATABASE_URL``). The
``SessionLocal`` factory is the basis for the one-session-per-request unit of
work (design §3.4); composition root supplies a session per request.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.infrastructure.config import Settings


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""


def _connect_args(database_url: str) -> Mapping[str, Any]:
    """SQLite needs ``check_same_thread=False`` under a threaded server.

    PostgreSQL (and others) take no special connect args here, keeping the
    engine construction portable across backends.
    """
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def create_engine_from_settings(settings: Settings) -> Engine:
    """Build the SQLAlchemy engine for the configured database URL."""
    return create_engine(
        settings.database_url,
        echo=False,
        connect_args=dict(_connect_args(settings.database_url)),
    )


# Default engine/session for the running app. Tests build their own engine
# against a throwaway SQLite database instead of importing these.
engine = create_engine_from_settings(Settings())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
