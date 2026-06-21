"""Application settings (infrastructure layer, design §4 preamble).

A single ``database_url`` keeps the persistence backend swappable: SQLite for
local/dev by default, PostgreSQL by setting ``DATABASE_URL`` — a one-line change
with no code edits. pydantic-settings reads from the environment (and a local
``.env`` if present).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from the environment.

    ``database_url`` defaults to a local SQLite file so the app runs with zero
    configuration; production/PostgreSQL overrides it via the ``DATABASE_URL``
    environment variable.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./aim_trainer.db"
