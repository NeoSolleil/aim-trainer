"""Application use cases for the Scoring context (design §3.2).

``RecordSessionResult`` records a completed session and produces one score. It
orchestrates domain scoring and the injected ports; it holds no business rules
of its own (those live in ``Score.create``) and knows nothing about HTTP or the
database.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto import PersistedScore, SessionResult
from app.application.ports import Clock, GunRepository, ScoreRepository
from app.domain.score import Score


@dataclass(frozen=True)
class RecordSessionResult:
    """Record a completed session and create its score (design §3.2).

    Dependencies are injected as **abstractions** (ports); composition root wires
    the concrete infrastructure implementations (``app/main.py``). The class is a
    frozen dataclass so the three collaborators are held as immutable fields.
    """

    score_repository: ScoreRepository
    gun_repository: GunRepository
    clock: Clock

    def execute(self, result: SessionResult) -> PersistedScore:
        """Score and persist a completed session (R-11/12/13/14/15).

        Steps (design §3.2):

        1. Resolve the default gun id server-side (R-14; client never declares
           it).
        2. ``Score.create`` computes accuracy / average and enforces every
           invariant. A violation raises ``InvariantViolation`` here and the
           method returns nothing — so the Clock is never read and the
           repository is never touched (R-13: nothing is persisted).
        3. Take the server timestamp from the Clock (R-15).
        4. Persist exactly one score row (R-14) and return the persisted result.

        Repository failures propagate unchanged; the adapters/api layer maps
        them to a 5xx response (design §3.4).
        """
        gun_id = self.gun_repository.get_default_id()

        # Scoring + invariant validation. Raises before any side effect (R-13).
        score = Score.create(
            hits=result.hits,
            total_clicks=result.total_clicks,
            reaction_times=result.reaction_times,
            time_limit_ms=result.time_limit_ms,
            gun_id=gun_id,
        )

        created_at = self.clock.now()  # server-assigned (R-15)
        return self.score_repository.add(score, created_at)
