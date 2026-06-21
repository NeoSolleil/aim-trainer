"""Value objects for the Scoring context (design §2.3).

Immutable, self-validating value objects. Built with the standard library only
(``dataclasses`` / ``decimal``); no framework, ORM or Pydantic imports.

``Accuracy`` and ``AverageReactionTime`` allow an *undefined* state (``None``)
to model the "—" cases (total_clicks == 0 / hits == 0), while ``ReactionTime``
is a single, always-non-negative value used to validate each submitted hit.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.domain.exceptions import InvariantViolation

#: Quantization step for ``accuracy`` — matches the DB column ``Numeric(5, 4)``
#: (4 decimal places). Quantizing in the domain keeps domain == DB == API ==
#: display: a repeating ratio (e.g. 1/3) would otherwise be a high-precision
#: ``Decimal`` here but truncated to 4 dp by the column, diverging on read.
_ACCURACY_STEP = Decimal("0.0001")

#: Quantization step for ``avg_reaction_time`` — matches ``Numeric(8, 3)`` (3
#: decimal places). Same rationale as :data:`_ACCURACY_STEP`.
_AVG_REACTION_TIME_STEP = Decimal("0.001")


@dataclass(frozen=True)
class ReactionTime:
    """A single hit's reaction time in milliseconds (R-1/R-2).

    Invariant: ``ms >= 0``. ``0`` is a valid value (a same-frame hit); a
    negative value is impossible under a monotonic clock and is rejected.
    """

    ms: int

    def __post_init__(self) -> None:
        if self.ms < 0:
            raise InvariantViolation(
                "negative_reaction_time",
                f"reaction_time must be non-negative, got {self.ms}",
            )


@dataclass(frozen=True)
class Accuracy:
    """Hit ratio, hits / total_clicks (R-11/R-13/R-18).

    Internal representation is ``Decimal | None`` to hold values such as 0.625
    exactly and to model the undefined case (total_clicks == 0) as ``None``.
    Invariant: when not ``None``, ``0 <= value <= 1``.
    """

    value: Decimal | None

    def __post_init__(self) -> None:
        if self.value is not None and not (Decimal(0) <= self.value <= Decimal(1)):
            raise InvariantViolation(
                "accuracy_out_of_range",
                f"accuracy must be within [0, 1], got {self.value}",
            )

    @classmethod
    def from_counts(cls, hits: int, total_clicks: int) -> Accuracy:
        """Compute accuracy from raw counts (R-11).

        ``total_clicks == 0`` yields an undefined accuracy (``None``, R-18),
        avoiding a division by zero. Otherwise the ratio is **quantized to 4
        decimal places (ROUND_HALF_UP)** to match the persisted scale
        ``Numeric(5, 4)``, so domain == DB == API == display (design §2.3); a
        repeating ratio such as 1/3 is stored and reported as ``0.3333``.
        Out-of-range results only arise when ``hits > total_clicks``, which the
        aggregate factory rejects earlier (design §2.4); the range invariant
        (0..1) is unaffected by quantization.
        """
        if total_clicks == 0:
            return cls(value=None)
        ratio = Decimal(hits) / Decimal(total_clicks)
        return cls(value=ratio.quantize(_ACCURACY_STEP, rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class AverageReactionTime:
    """Average reaction time over hits only (R-12/R-19).

    Internal representation is ``Decimal | None``; ``None`` models the undefined
    case (hits == 0). Invariant: when not ``None``, ``ms >= 0``.
    """

    ms: Decimal | None

    def __post_init__(self) -> None:
        if self.ms is not None and self.ms < Decimal(0):
            raise InvariantViolation(
                "negative_reaction_time",
                f"average reaction_time must be non-negative, got {self.ms}",
            )

    @classmethod
    def from_hits(cls, reaction_times: list[ReactionTime]) -> AverageReactionTime:
        """Arithmetic mean over hit reaction_times only (R-12).

        An empty list (hits == 0) yields an undefined average (``None``, R-19).
        Misses never enter this list, so they cannot affect the mean. The mean
        is **quantized to 3 decimal places (ROUND_HALF_UP)** to match the
        persisted scale ``Numeric(8, 3)``, so domain == DB == API == display
        (design §2.3); a repeating mean such as 301/3 becomes ``100.333``. The
        non-negativity invariant is unaffected by quantization.
        """
        if not reaction_times:
            return cls(ms=None)
        total = sum(rt.ms for rt in reaction_times)
        mean = Decimal(total) / Decimal(len(reaction_times))
        return cls(ms=mean.quantize(_AVG_REACTION_TIME_STEP, rounding=ROUND_HALF_UP))
