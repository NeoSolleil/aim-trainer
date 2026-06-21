"""Infrastructure tests for the concrete repositories, seed and clock (T-05).

These run against a throwaway in-memory SQLite database whose schema is built
from the ORM metadata (the same metadata Alembic autogenerates against). They
verify the persistence behaviour behind the @backend scenarios:

  * @R-14 (L152) — ``ScoreRepository.add`` writes exactly one ``score`` row and
    no per-hit detail rows exist (the schema has only gun/score).
  * @R-18 (L191) — a 0/0 session persists with ``accuracy`` / ``avg_reaction_time``
    stored as SQL ``NULL`` (the undefined "—" cases).
  * the default-gun seed is idempotent (running it twice keeps one gun), and
    ``GunRepository.get_default_id`` returns that gun's id.

The repository must return a *domain* ``PersistedScore`` (never an ORM object),
so the assertions read domain value objects back, not ORM rows.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.application.dto import PersistedScore
from app.domain.score import Score
from app.infrastructure.clock import SystemClock
from app.infrastructure.db import Base
from app.infrastructure.models import GunModel, ScoreModel
from app.infrastructure.repositories import (
    SqlAlchemyGunRepository,
    SqlAlchemyScoreRepository,
    ensure_default_gun,
)


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _make_score(
    *,
    hits: int,
    total_clicks: int,
    reaction_times: list[int],
    gun_id: int,
) -> Score:
    return Score.create(
        hits=hits,
        total_clicks=total_clicks,
        reaction_times=reaction_times,
        time_limit_ms=30000,
        gun_id=gun_id,
    )


class TestDefaultGunSeed:
    def test_seed_creates_one_gun(self, session_factory: sessionmaker[Session]) -> None:
        with session_factory() as session:
            ensure_default_gun(session)
            session.commit()

        with session_factory() as session:
            count = session.scalar(select(func.count()).select_from(GunModel))
            assert count == 1

    def test_seed_is_idempotent(self, session_factory: sessionmaker[Session]) -> None:
        # Running the seed twice must not duplicate the default gun (R-14 relies
        # on exactly one resolvable default gun).
        with session_factory() as session:
            ensure_default_gun(session)
            session.commit()
        with session_factory() as session:
            ensure_default_gun(session)
            session.commit()

        with session_factory() as session:
            count = session.scalar(select(func.count()).select_from(GunModel))
            assert count == 1

    def test_get_default_id_returns_seeded_gun(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        with session_factory() as session:
            ensure_default_gun(session)
            session.commit()

        with session_factory() as session:
            gun_id = SqlAlchemyGunRepository(session).get_default_id()
            assert isinstance(gun_id, int)
            assert gun_id >= 1


class TestScoreRepositoryAdd:
    def test_add_writes_exactly_one_row_and_returns_persisted_score(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        # @R-14 (L152): one valid session -> exactly one score row, with the
        # computed values mapped through; no per-hit detail (no such table).
        with session_factory() as session:
            ensure_default_gun(session)
            session.commit()
            gun_id = SqlAlchemyGunRepository(session).get_default_id()

            score = _make_score(
                hits=5, total_clicks=8, reaction_times=[200, 300, 400, 500, 600], gun_id=gun_id
            )
            created_at = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
            persisted = SqlAlchemyScoreRepository(session).add(score, created_at)
            session.commit()

        # Exactly one row persisted (R-14).
        with session_factory() as session:
            row_count = session.scalar(select(func.count()).select_from(ScoreModel))
            assert row_count == 1

        # The repository returns a domain PersistedScore, never an ORM object.
        assert isinstance(persisted, PersistedScore)
        assert not isinstance(persisted.score, ScoreModel)
        assert persisted.id >= 1
        assert persisted.created_at == created_at
        assert persisted.score.accuracy.value == Decimal(5) / Decimal(8)
        assert persisted.score.avg_reaction_time.ms == Decimal(2000) / Decimal(5)
        assert persisted.score.gun_id == gun_id

    def test_add_persists_columns_via_orm_read(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        # Read the raw ORM row back to confirm the columns were written (R-14:
        # accuracy / average / hits / total_clicks / time_limit / gun ref).
        with session_factory() as session:
            ensure_default_gun(session)
            session.commit()
            gun_id = SqlAlchemyGunRepository(session).get_default_id()
            score = _make_score(hits=2, total_clicks=5, reaction_times=[300, 500], gun_id=gun_id)
            SqlAlchemyScoreRepository(session).add(
                score, datetime(2026, 6, 21, 9, 30, 0, tzinfo=UTC)
            )
            session.commit()

        with session_factory() as session:
            row = session.scalars(select(ScoreModel)).one()
            assert row.hits == 2
            assert row.total_clicks == 5
            assert row.accuracy == Decimal("0.4")
            assert row.avg_reaction_time == Decimal("400")
            assert row.time_limit_ms == 30000
            assert row.gun_id == gun_id

    def test_repeating_decimal_round_trips_consistently_domain_equals_db(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        # M-1 consistency (most important): a repeating ratio (hits=3/total=9 =
        # 1/3, mean over [100,100,101] = 301/3) must satisfy
        #     domain value == DB value read back == (later) API value.
        # hits=3 keeps len(reaction_times) == hits while making both metrics
        # repeating. Before quantization the domain held 0.3333... (28 digits)
        # while the Numeric(5,4) column truncates to 0.3333 on read, so the
        # round-trip diverged. With quantization both sides are exactly equal.
        with session_factory() as session:
            ensure_default_gun(session)
            session.commit()
            gun_id = SqlAlchemyGunRepository(session).get_default_id()
            score = _make_score(
                hits=3, total_clicks=9, reaction_times=[100, 100, 101], gun_id=gun_id
            )
            # Domain values produced by the aggregate factory.
            domain_accuracy = score.accuracy.value
            domain_avg = score.avg_reaction_time.ms
            SqlAlchemyScoreRepository(session).add(
                score, datetime(2026, 6, 21, 6, 0, 0, tzinfo=UTC)
            )
            session.commit()

        # Read the raw ORM row back: the persisted (truncated-by-scale) values.
        with session_factory() as session:
            row = session.scalars(select(ScoreModel)).one()
            db_accuracy = row.accuracy
            db_avg = row.avg_reaction_time

        # domain == DB, exactly (no precision lost between the two).
        assert domain_accuracy == db_accuracy == Decimal("0.3333")
        assert domain_avg == db_avg == Decimal("100.333")

    def test_zero_clicks_persists_null_accuracy_and_average(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        # @R-18 (L191): hits=0/total_clicks=0 -> one row with accuracy and
        # avg_reaction_time stored as SQL NULL (the undefined "—" cases).
        with session_factory() as session:
            ensure_default_gun(session)
            session.commit()
            gun_id = SqlAlchemyGunRepository(session).get_default_id()
            score = _make_score(hits=0, total_clicks=0, reaction_times=[], gun_id=gun_id)
            persisted = SqlAlchemyScoreRepository(session).add(
                score, datetime(2026, 6, 21, 0, 0, 0, tzinfo=UTC)
            )
            session.commit()

        # Domain side: undefined values round-trip as None.
        assert persisted.score.accuracy.value is None
        assert persisted.score.avg_reaction_time.ms is None

        # DB side: the columns are actually NULL.
        with session_factory() as session:
            row = session.scalars(select(ScoreModel)).one()
            assert row.accuracy is None
            assert row.avg_reaction_time is None

    def test_hits_zero_total_positive_persists_zero_accuracy_null_average(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        # R-19 persistence corner: accuracy = 0 (stored, not NULL), average NULL.
        with session_factory() as session:
            ensure_default_gun(session)
            session.commit()
            gun_id = SqlAlchemyGunRepository(session).get_default_id()
            score = _make_score(hits=0, total_clicks=8, reaction_times=[], gun_id=gun_id)
            SqlAlchemyScoreRepository(session).add(
                score, datetime(2026, 6, 21, 0, 0, 0, tzinfo=UTC)
            )
            session.commit()

        with session_factory() as session:
            row = session.scalars(select(ScoreModel)).one()
            assert row.accuracy == Decimal("0")
            assert row.avg_reaction_time is None


class TestSystemClock:
    def test_now_is_timezone_aware_and_close_to_real_time(self) -> None:
        before = datetime.now(UTC)
        value = SystemClock().now()
        after = datetime.now(UTC)
        assert value.tzinfo is not None
        assert before <= value <= after
