"""Infrastructure tests for application settings (T-04).

The DB URL is a single setting so SQLite <-> PostgreSQL is a one-line switch
(design §4 preamble). pydantic-settings reads it from the environment, with a
sensible SQLite default for local/dev.
"""

from __future__ import annotations

import pytest

from app.infrastructure.config import Settings


class TestSettings:
    def test_default_database_url_is_sqlite(self) -> None:
        settings = Settings()
        assert settings.database_url.startswith("sqlite")

    def test_database_url_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A single env var flips the backend to PostgreSQL without code changes.
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/aim")
        settings = Settings()
        assert settings.database_url == "postgresql+psycopg://u:p@localhost/aim"
