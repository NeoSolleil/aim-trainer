"""Pure unit tests for the Score aggregate and its factory (T-02).

Covers the aggregate-level invariants and the ordering of validation in
``Score.create``, plus the R-18 domain capability (0/0 produces a Score with
undefined accuracy/average) that is *not* bound as a pytest-bdd scenario in this
increment because there is no repository/DB yet.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.exceptions import InvariantViolation
from app.domain.score import Score


def _create(
    *,
    hits: int,
    total_clicks: int,
    reaction_times: list[int],
    time_limit_ms: int = 30000,
    gun_id: int = 1,
) -> Score:
    return Score.create(
        hits=hits,
        total_clicks=total_clicks,
        reaction_times=reaction_times,
        time_limit_ms=time_limit_ms,
        gun_id=gun_id,
    )


class TestScoreCreateHappyPath:
    def test_computes_accuracy_and_average(self) -> None:
        score = _create(hits=2, total_clicks=5, reaction_times=[300, 500])
        assert score.accuracy.value == Decimal("0.4")
        assert score.avg_reaction_time.ms == Decimal(400)
        assert score.hits == 2
        assert score.total_clicks == 5
        assert score.time_limit_ms == 30000
        assert score.gun_id == 1

    def test_perfect_accuracy(self) -> None:
        score = _create(hits=3, total_clicks=3, reaction_times=[100, 200, 300])
        assert score.accuracy.value == Decimal(1)
        assert score.avg_reaction_time.ms == Decimal(200)

    def test_zero_ms_reaction_time_is_allowed(self) -> None:
        # R-2: a 0ms hit is valid and enters the average.
        score = _create(hits=1, total_clicks=1, reaction_times=[0])
        assert score.avg_reaction_time.ms == Decimal(0)


class TestScoreCreateZeroValues:
    def test_zero_total_clicks_produces_score_with_undefined_metrics(self) -> None:
        # R-18 domain capability: 0/0 must NOT raise; accuracy & average undefined.
        # (Persistence of this row is verified later in T-05/T-08.)
        score = _create(hits=0, total_clicks=0, reaction_times=[])
        assert score.accuracy.value is None
        assert score.avg_reaction_time.ms is None
        assert score.hits == 0
        assert score.total_clicks == 0

    def test_all_miss_zero_hits_has_zero_accuracy_and_undefined_average(self) -> None:
        # R-19 domain part: hits=0 & total_clicks>0 => accuracy 0, average None.
        score = _create(hits=0, total_clicks=8, reaction_times=[])
        assert score.accuracy.value == Decimal(0)
        assert score.avg_reaction_time.ms is None


class TestScoreCreateInvariantViolations:
    def test_hits_exceed_total_is_rejected(self) -> None:
        # R-13: hits > total_clicks.
        with pytest.raises(InvariantViolation) as exc_info:
            _create(hits=9, total_clicks=8, reaction_times=[100] * 9)
        assert exc_info.value.code == "hits_exceed_total"

    def test_negative_reaction_time_is_rejected(self) -> None:
        # R-13: a negative reaction_time among the hits.
        with pytest.raises(InvariantViolation) as exc_info:
            _create(hits=2, total_clicks=5, reaction_times=[100, -1])
        assert exc_info.value.code == "negative_reaction_time"

    def test_negative_hits_is_rejected(self) -> None:
        with pytest.raises(InvariantViolation) as exc_info:
            _create(hits=-1, total_clicks=5, reaction_times=[])
        assert exc_info.value.code == "negative_count"

    def test_negative_total_clicks_is_rejected(self) -> None:
        with pytest.raises(InvariantViolation) as exc_info:
            _create(hits=0, total_clicks=-1, reaction_times=[])
        assert exc_info.value.code == "negative_count"

    def test_reaction_time_count_must_equal_hits(self) -> None:
        # Internal consistency: number of hit reaction_times must equal hits.
        with pytest.raises(InvariantViolation) as exc_info:
            _create(hits=3, total_clicks=5, reaction_times=[100, 200])
        assert exc_info.value.code == "hit_count_mismatch"

    def test_negative_reaction_time_checked_before_count_mismatch(self) -> None:
        # Validation order (design §2.4): per-reaction non-negativity is step 1,
        # so a negative value is reported even when the count would also mismatch.
        with pytest.raises(InvariantViolation) as exc_info:
            _create(hits=5, total_clicks=8, reaction_times=[-1])
        assert exc_info.value.code == "negative_reaction_time"
