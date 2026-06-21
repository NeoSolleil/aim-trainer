"""Infrastructure test: the initial Alembic migration builds the schema (T-05).

Upgrading a *fresh* database to ``head`` must create exactly the ``gun`` / ``score``
tables the design specifies (design §4.1/§4.2), with the nullability and foreign
key that the R-18/R-19/R-14 behaviour depends on. Reflecting the real schema
(rather than the ORM metadata, which ``test_models`` already covers) proves the
migration itself — env.py wiring included — is correct.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command

BACKEND_ROOT = Path(__file__).parents[2]


@pytest.fixture
def migrated_db_url(tmp_path: Path) -> Iterator[str]:
    """A throwaway SQLite file upgraded to Alembic head."""
    db_path = tmp_path / "migrated.db"
    url = f"sqlite:///{db_path}"

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    # env.py reads the URL from Settings/DATABASE_URL; point it at the temp DB.
    config.set_main_option("sqlalchemy.url", url)

    command.upgrade(config, "head")
    yield url


def test_migration_creates_gun_and_score_tables(migrated_db_url: str) -> None:
    engine = create_engine(migrated_db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        # Only the two domain tables (plus Alembic's bookkeeping table).
        assert {"gun", "score"} <= tables
        assert "alembic_version" in tables
        # No per-hit detail table (R-14): nothing beyond gun/score/bookkeeping.
        assert tables - {"gun", "score", "alembic_version"} == set()
    finally:
        engine.dispose()


def test_score_columns_have_expected_nullability(migrated_db_url: str) -> None:
    engine = create_engine(migrated_db_url)
    try:
        inspector = inspect(engine)
        columns = {c["name"]: c for c in inspector.get_columns("score")}

        # The R-18/R-19 hinge: accuracy / avg_reaction_time are NULLable.
        assert columns["accuracy"]["nullable"] is True
        assert columns["avg_reaction_time"]["nullable"] is True

        # Required columns are NOT NULL.
        for name in ("hits", "total_clicks", "time_limit_ms", "gun_id", "created_at"):
            assert columns[name]["nullable"] is False, name
    finally:
        engine.dispose()


def test_score_has_foreign_key_to_gun(migrated_db_url: str) -> None:
    engine = create_engine(migrated_db_url)
    try:
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("score")
        assert len(fks) == 1
        fk = fks[0]
        assert fk["referred_table"] == "gun"
        assert fk["referred_columns"] == ["id"]
        assert fk["constrained_columns"] == ["gun_id"]
    finally:
        engine.dispose()
