"""Unit tests for the application use case ``RecordSessionResult`` (T-03).

The use case is exercised with **in-memory fakes** for its three abstractions
(``ScoreRepository`` / ``GunRepository`` / ``Clock``), so these tests need no DB
and stay fast. They lock the application-layer *logic* of two @backend
scenarios:

  * @R-14 (L152) — exactly one ``add`` call (one row), carrying the computed
    accuracy / average / hits / total_clicks / time_limit / default-gun
    reference; no per-hit detail is passed.
  * @R-15 (L160) — ``created_at`` comes from the injected ``Clock`` (server
    time), never from client input (the input ``SessionResult`` has no time
    field at all).

The real-DB persistence of these scenarios lands in T-05; the API/422 path in
T-07/T-08. Invariant violations from ``Score.create`` must propagate *before*
any ``add``, so nothing is saved (R-13).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.dto import PersistedScore, SessionResult
from app.application.use_cases import RecordSessionResult
from app.domain.exceptions import InvariantViolation
from app.domain.score import Score

# --- In-memory fakes for the three application abstractions -------------------


@dataclass
class FakeScoreRepository:
    """Records ``add`` calls and returns a deterministic ``PersistedScore``.

    Mirrors the contract a real repository must honour: ``add`` returns a
    ``PersistedScore`` that pairs the *domain* ``Score`` (never an ORM object)
    with the persisted ``id`` and the server-assigned ``created_at`` — keeping
    those persistence concerns out of the pure domain aggregate (design §2.2).
    """

    added: list[tuple[Score, datetime]] = field(default_factory=list[tuple[Score, datetime]])
    next_id: int = 1

    def add(self, score: Score, created_at: datetime) -> PersistedScore:
        self.added.append((score, created_at))
        return PersistedScore(id=self.next_id, score=score, created_at=created_at)


@dataclass
class FakeGunRepository:
    """Returns a fixed default-gun id; records that it was asked."""

    default_id: int = 7
    get_default_called: int = 0

    def get_default_id(self) -> int:
        self.get_default_called += 1
        return self.default_id


@dataclass
class FakeClock:
    """Returns a fixed, recognisable server timestamp."""

    fixed: datetime = field(default_factory=lambda: datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC))

    def now(self) -> datetime:
        return self.fixed


# --- Tests --------------------------------------------------------------------


class TestRecordSessionResultHappyPath:
    def test_saves_exactly_one_score_with_computed_values(self) -> None:
        # @R-14 (L152): a valid completed session -> exactly one add (one row),
        # carrying accuracy / average / counts / time_limit / default-gun ref.
        repo = FakeScoreRepository()
        guns = FakeGunRepository(default_id=7)
        clock = FakeClock()
        use_case = RecordSessionResult(score_repository=repo, gun_repository=guns, clock=clock)

        result = SessionResult(
            hits=5,
            total_clicks=8,
            reaction_times=[200, 300, 400, 500, 600],
            time_limit_ms=30000,
        )

        saved = use_case.execute(result)

        # Exactly one persistence call -> one row (R-14).
        assert len(repo.added) == 1
        score, created_at = repo.added[0]

        # The default gun id was resolved server-side and attached (R-14).
        assert guns.get_default_called == 1
        assert score.gun_id == 7

        # Domain computed the derived values (accuracy = 5/8 = 0.625).
        assert score.accuracy.value == Decimal(5) / Decimal(8)
        assert score.avg_reaction_time.ms == Decimal(2000) / Decimal(5)
        assert score.hits == 5
        assert score.total_clicks == 8
        assert score.time_limit_ms == 30000

        # created_at handed to the repository is the Clock's value (R-15).
        assert created_at == clock.fixed

        # The returned PersistedScore carries the confirmed id + created_at and
        # the same domain Score (id/created_at stay out of the aggregate).
        assert isinstance(saved, PersistedScore)
        assert saved.id == repo.next_id
        assert saved.created_at == clock.fixed
        assert saved.score is score

    def test_created_at_is_server_time_not_client_input(self) -> None:
        # @R-15 (L160): the input DTO has no time field, so the only possible
        # source of created_at is the injected Clock. Even if the caller "knows"
        # a different wall-clock time, the persisted created_at is the Clock's.
        repo = FakeScoreRepository()
        clock = FakeClock(fixed=datetime(2030, 1, 1, 0, 0, 0, tzinfo=UTC))
        use_case = RecordSessionResult(
            score_repository=repo,
            gun_repository=FakeGunRepository(),
            clock=clock,
        )

        use_case.execute(
            SessionResult(hits=1, total_clicks=1, reaction_times=[100], time_limit_ms=30000)
        )

        _score, created_at = repo.added[0]
        assert created_at == datetime(2030, 1, 1, 0, 0, 0, tzinfo=UTC)

    def test_session_result_has_no_gun_id_or_created_at(self) -> None:
        # The input DTO must not carry gun_id (server-resolved) or a client time
        # (server-assigned). Guard the contract so a future edit can't smuggle
        # them in (design §3.2 / R-15).
        field_names = {f.name for f in SessionResult.__dataclass_fields__.values()}
        assert field_names == {"hits", "total_clicks", "reaction_times", "time_limit_ms"}

    def test_zero_clicks_still_records_one_score(self) -> None:
        # R-18 application logic: 0/0 is valid -> one add, accuracy/avg undefined.
        repo = FakeScoreRepository()
        use_case = RecordSessionResult(
            score_repository=repo,
            gun_repository=FakeGunRepository(),
            clock=FakeClock(),
        )

        use_case.execute(
            SessionResult(hits=0, total_clicks=0, reaction_times=[], time_limit_ms=30000)
        )

        assert len(repo.added) == 1
        score, _ = repo.added[0]
        assert score.accuracy.value is None
        assert score.avg_reaction_time.ms is None


class TestRecordSessionResultInvariantViolations:
    def test_hits_exceed_total_propagates_and_nothing_saved(self) -> None:
        # R-13: hits > total_clicks -> InvariantViolation, no add called.
        repo = FakeScoreRepository()
        use_case = RecordSessionResult(
            score_repository=repo,
            gun_repository=FakeGunRepository(),
            clock=FakeClock(),
        )

        with pytest.raises(InvariantViolation) as exc:
            use_case.execute(
                SessionResult(hits=9, total_clicks=8, reaction_times=[1] * 9, time_limit_ms=30000)
            )

        assert exc.value.code == "hits_exceed_total"
        assert repo.added == []  # nothing persisted (R-13)

    def test_negative_reaction_time_propagates_and_nothing_saved(self) -> None:
        # R-13: a negative reaction_time -> InvariantViolation, no add called.
        repo = FakeScoreRepository()
        use_case = RecordSessionResult(
            score_repository=repo,
            gun_repository=FakeGunRepository(),
            clock=FakeClock(),
        )

        with pytest.raises(InvariantViolation) as exc:
            use_case.execute(
                SessionResult(hits=2, total_clicks=5, reaction_times=[100, -1], time_limit_ms=30000)
            )

        assert exc.value.code == "negative_reaction_time"
        assert repo.added == []

    def test_violation_is_raised_before_clock_is_read(self) -> None:
        # The order matters: validation precedes timestamping/persistence, so a
        # rejected submission never even consults the Clock (R-13 + R-15 order).
        class ExplodingClock:
            def now(self) -> datetime:  # pragma: no cover - must not be called
                raise AssertionError("Clock.now() must not be called on violation")

        repo = FakeScoreRepository()
        use_case = RecordSessionResult(
            score_repository=repo,
            gun_repository=FakeGunRepository(),
            clock=ExplodingClock(),
        )

        with pytest.raises(InvariantViolation):
            use_case.execute(
                SessionResult(hits=9, total_clicks=8, reaction_times=[1] * 9, time_limit_ms=30000)
            )

        assert repo.added == []
