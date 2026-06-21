"""Infrastructure tests for the SQLAlchemy ORM metadata (T-04).

These lock the schema shape declared by the ORM models (design §4.1/§4.2)
*without* a live database: table names, column nullability (the R-18/R-19 hinge
is that ``accuracy`` / ``avg_reaction_time`` are NULLable), the FK
``score.gun_id -> gun.id``, and that no per-hit detail table exists (R-14).

Reflection of the actual schema (CREATE TABLE on a real engine) is asserted in
T-05's repository tests; here we assert the declarative mapping itself.
"""

from __future__ import annotations

from sqlalchemy import DateTime, Numeric

from app.infrastructure.db import Base
from app.infrastructure.models import GunModel, ScoreModel


class TestGunModel:
    def test_table_name(self) -> None:
        assert GunModel.__tablename__ == "gun"

    def test_columns(self) -> None:
        cols = GunModel.__table__.columns
        assert set(cols.keys()) == {"id", "name"}
        assert cols["id"].primary_key is True
        # name is required (NOT NULL).
        assert cols["name"].nullable is False

    def test_no_0002_behaviour_columns_yet(self) -> None:
        # The 0002 gun-behaviour columns (fire_rate / recoil / target_size) are
        # intentionally NOT added in 0001 (design §4.1).
        cols = set(GunModel.__table__.columns.keys())
        assert {"fire_rate", "recoil", "target_size"} & cols == set()


class TestScoreModel:
    def test_table_name(self) -> None:
        assert ScoreModel.__tablename__ == "score"

    def test_columns_present(self) -> None:
        cols = ScoreModel.__table__.columns
        assert set(cols.keys()) == {
            "id",
            "hits",
            "total_clicks",
            "accuracy",
            "avg_reaction_time",
            "time_limit_ms",
            "gun_id",
            "created_at",
        }

    def test_primary_key(self) -> None:
        assert ScoreModel.__table__.columns["id"].primary_key is True

    def test_not_null_columns(self) -> None:
        cols = ScoreModel.__table__.columns
        for name in ("hits", "total_clicks", "time_limit_ms", "gun_id", "created_at"):
            assert cols[name].nullable is False, name

    def test_accuracy_and_average_are_nullable(self) -> None:
        # The hinge of R-18/R-19: undefined accuracy / average persist as NULL.
        cols = ScoreModel.__table__.columns
        assert cols["accuracy"].nullable is True
        assert cols["avg_reaction_time"].nullable is True

    def test_accuracy_and_average_use_numeric(self) -> None:
        # Numeric (Decimal) avoids float rounding (design §4.2); the domain is
        # also Decimal, so the mapping is exact.
        cols = ScoreModel.__table__.columns
        assert isinstance(cols["accuracy"].type, Numeric)
        assert isinstance(cols["avg_reaction_time"].type, Numeric)

    def test_created_at_is_timezone_aware(self) -> None:
        created_at_type = ScoreModel.__table__.columns["created_at"].type
        assert isinstance(created_at_type, DateTime)
        assert created_at_type.timezone is True

    def test_gun_id_foreign_key_targets_gun_id(self) -> None:
        fks = list(ScoreModel.__table__.columns["gun_id"].foreign_keys)
        assert len(fks) == 1
        assert fks[0].column is GunModel.__table__.columns["id"]


class TestSchemaScope:
    def test_only_gun_and_score_tables(self) -> None:
        # No per-hit reaction_time detail table exists (R-14: aggregate-only).
        assert set(Base.metadata.tables.keys()) == {"gun", "score"}
