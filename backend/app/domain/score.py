"""The Score aggregate and its factory (design §2.2 / §2.4).

``Score`` is the aggregate root of the Scoring context: one completed session
maps to one Score. It holds only confirmed, immutable values and never keeps
per-hit detail (R-14). ``created_at`` is server-assigned (R-15) and therefore
*not* held here; it is confirmed at persistence time (infrastructure).

``Score.create`` is the single place where the aggregate invariants are
enforced, so the pure unit / pytest-bdd tests (no DB, no framework) can cover
R-11/R-12/R-13/R-18/R-19. Inputs are plain values: the domain does not import
the application's ``SessionResult`` (no inward-pointing dependency is broken).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import InvariantViolation
from app.domain.value_objects import Accuracy, AverageReactionTime, ReactionTime


@dataclass(frozen=True)
class Score:
    """A scored, completed session (aggregate root).

    All attributes are confirmed values. Built via :meth:`create`; instances are
    immutable. No hit detail is stored (R-14); ``created_at`` is assigned by the
    server at persistence time and is not part of the domain aggregate (R-15).
    """

    hits: int
    total_clicks: int
    accuracy: Accuracy
    avg_reaction_time: AverageReactionTime
    time_limit_ms: int
    gun_id: int

    @classmethod
    def create(
        cls,
        *,
        hits: int,
        total_clicks: int,
        reaction_times: list[int],
        time_limit_ms: int,
        gun_id: int,
    ) -> Score:
        """Build a Score from raw values, enforcing all invariants (design §2.4).

        Validation order (each violation raises ``InvariantViolation`` and no
        Score is produced — R-13):

        1. Per-reaction non-negativity: each raw reaction_time becomes a
           ``ReactionTime`` (negative => rejected).
        2. Count consistency: ``hits >= 0``, ``total_clicks >= 0``,
           ``hits <= total_clicks``, and ``len(reaction_times) == hits``.
        3. Accuracy via ``Accuracy.from_counts`` (0..1 guaranteed, None if 0/0).
        4. Average via ``AverageReactionTime.from_hits`` (None if no hits).
        5. Return the Score (``created_at`` unset; assigned at persistence).
        """
        # 1. Per-reaction non-negativity (raises negative_reaction_time).
        hit_reaction_times = [ReactionTime(ms=ms) for ms in reaction_times]

        # 2. Count consistency.
        if hits < 0 or total_clicks < 0:
            raise InvariantViolation(
                "negative_count",
                f"hits and total_clicks must be non-negative, "
                f"got hits={hits}, total_clicks={total_clicks}",
            )
        if hits > total_clicks:
            raise InvariantViolation(
                "hits_exceed_total",
                f"hits ({hits}) must not exceed total_clicks ({total_clicks})",
            )
        if len(hit_reaction_times) != hits:
            raise InvariantViolation(
                "hit_count_mismatch",
                f"number of hit reaction_times ({len(hit_reaction_times)}) "
                f"must equal hits ({hits})",
            )

        # 3. Accuracy. 4. Average.
        accuracy = Accuracy.from_counts(hits, total_clicks)
        avg_reaction_time = AverageReactionTime.from_hits(hit_reaction_times)

        # 5. All invariants satisfied.
        return cls(
            hits=hits,
            total_clicks=total_clicks,
            accuracy=accuracy,
            avg_reaction_time=avg_reaction_time,
            time_limit_ms=time_limit_ms,
            gun_id=gun_id,
        )
