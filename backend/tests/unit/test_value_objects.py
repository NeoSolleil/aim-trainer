"""Pure unit tests for the domain value objects (T-01).

These lock the invariants and factories of ``ReactionTime``, ``Accuracy`` and
``AverageReactionTime`` directly, complementing the pytest-bdd scenarios that
exercise the same rules through the aggregate factory.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.domain.exceptions import DomainError, InvariantViolation
from app.domain.value_objects import Accuracy, AverageReactionTime, ReactionTime


class TestReactionTime:
    def test_zero_is_valid(self) -> None:
        # R-2: a same-frame hit records 0ms as a valid value.
        assert ReactionTime(ms=0).ms == 0

    def test_positive_is_valid(self) -> None:
        assert ReactionTime(ms=320).ms == 320

    def test_negative_is_rejected(self) -> None:
        # R-2/R-13: negative reaction_time must never be recorded.
        with pytest.raises(InvariantViolation) as exc_info:
            ReactionTime(ms=-1)
        assert exc_info.value.code == "negative_reaction_time"

    def test_invariant_violation_is_a_domain_error(self) -> None:
        with pytest.raises(DomainError):
            ReactionTime(ms=-5)

    def test_is_frozen(self) -> None:
        rt = ReactionTime(ms=100)
        with pytest.raises(FrozenInstanceError):
            rt.ms = 200  # type: ignore[misc]


class TestAccuracy:
    def test_zero_is_valid(self) -> None:
        assert Accuracy(value=Decimal(0)).value == Decimal(0)

    def test_one_is_valid(self) -> None:
        assert Accuracy(value=Decimal(1)).value == Decimal(1)

    def test_none_is_valid_undefined(self) -> None:
        # total_clicks == 0 => undefined accuracy (R-18).
        assert Accuracy(value=None).value is None

    def test_above_one_is_rejected(self) -> None:
        # R-13: out-of-range accuracy (1.5) is rejected at construction.
        with pytest.raises(InvariantViolation) as exc_info:
            Accuracy(value=Decimal("1.5"))
        assert exc_info.value.code == "accuracy_out_of_range"

    def test_below_zero_is_rejected(self) -> None:
        with pytest.raises(InvariantViolation) as exc_info:
            Accuracy(value=Decimal("-0.1"))
        assert exc_info.value.code == "accuracy_out_of_range"

    def test_from_counts_computes_ratio(self) -> None:
        # R-11: accuracy = hits / total_clicks (exact via Decimal).
        assert Accuracy.from_counts(5, 8).value == Decimal("0.625")

    def test_from_counts_zero_total_is_none(self) -> None:
        # R-18: total_clicks == 0 => None (undefined), no division by zero.
        assert Accuracy.from_counts(0, 0).value is None

    def test_from_counts_quantizes_repeating_decimal_to_four_places(self) -> None:
        # M-1: a repeating ratio (1/3) is quantized to the DB scale Numeric(5,4),
        # so domain == DB == API == display. Exact equality (not approx) on the
        # 4-dp Decimal — the full-precision 0.3333... must NOT leak.
        result = Accuracy.from_counts(1, 3).value
        assert result == Decimal("0.3333")
        # The undefined-vs-stored divergence the bug caused: NOT the full ratio.
        assert result != Decimal(1) / Decimal(3)

    def test_from_counts_quantizes_with_round_half_up(self) -> None:
        # M-1: 2/3 = 0.6666... rounds half-up at the 4th place to 0.6667.
        assert Accuracy.from_counts(2, 3).value == Decimal("0.6667")

    def test_from_counts_exact_ratio_is_unchanged_by_quantization(self) -> None:
        # 5/8 = 0.625 already fits in 4 dp, so quantization is a no-op (regression
        # guard: the existing exact cases keep their value).
        assert Accuracy.from_counts(5, 8).value == Decimal("0.625")


class TestAverageReactionTime:
    def test_none_is_valid_undefined(self) -> None:
        # hits == 0 => undefined average (R-19).
        assert AverageReactionTime(ms=None).ms is None

    def test_zero_is_valid(self) -> None:
        assert AverageReactionTime(ms=Decimal(0)).ms == Decimal(0)

    def test_negative_is_rejected(self) -> None:
        with pytest.raises(InvariantViolation) as exc_info:
            AverageReactionTime(ms=Decimal(-1))
        assert exc_info.value.code == "negative_reaction_time"

    def test_from_hits_computes_mean(self) -> None:
        # R-12: arithmetic mean over hit reaction_times only.
        avg = AverageReactionTime.from_hits([ReactionTime(ms=300), ReactionTime(ms=500)])
        assert avg.ms == Decimal(400)

    def test_from_hits_empty_is_none(self) -> None:
        # hits == 0 => None (R-19).
        assert AverageReactionTime.from_hits([]).ms is None

    def test_from_hits_single_value(self) -> None:
        assert AverageReactionTime.from_hits([ReactionTime(ms=320)]).ms == Decimal(320)

    def test_from_hits_quantizes_repeating_mean_to_three_places(self) -> None:
        # M-1: (100+100+101)/3 = 100.333... is quantized to the DB scale
        # Numeric(8,3), so domain == DB == API == display. Exact equality on the
        # 3-dp Decimal; the full-precision 100.3333... must NOT leak.
        rts = [ReactionTime(ms=100), ReactionTime(ms=100), ReactionTime(ms=101)]
        result = AverageReactionTime.from_hits(rts).ms
        assert result == Decimal("100.333")
        assert result != Decimal(301) / Decimal(3)

    def test_from_hits_quantizes_with_round_half_up(self) -> None:
        # M-1: (1+2+2)/3 = 1.6666... rounds half-up at the 3rd place to 1.667
        # (truncation would give 1.666, so this genuinely exercises ROUND_HALF_UP).
        rts = [ReactionTime(ms=1), ReactionTime(ms=2), ReactionTime(ms=2)]
        assert AverageReactionTime.from_hits(rts).ms == Decimal("1.667")
