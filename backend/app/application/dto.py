"""Application input/output DTOs (plain dataclasses, design §3.2).

These are the application layer's own boundary types. They depend only on the
domain (``Score``) and use the standard library — no FastAPI / SQLAlchemy /
Pydantic (those belong to adapters/schemas and infrastructure).

* ``SessionResult`` is the *input* a completed session submits. It carries only
  the raw data the server needs to score the session. It deliberately has **no**
  ``gun_id`` (the server resolves the default gun, design §3.2) and **no** client
  timestamp (the server assigns ``created_at``, R-15).
* ``PersistedScore`` is the *output* a repository returns after persisting: it
  pairs the domain ``Score`` with the persistence-assigned ``id`` and the
  server-assigned ``created_at``. Keeping ``id`` / ``created_at`` here (not on the
  ``Score`` aggregate) preserves the design decision that the pure domain
  aggregate holds neither (design §2.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.score import Score


@dataclass(frozen=True)
class SessionResult:
    """Raw data of one completed session, submitted for scoring (design §3.2).

    ``reaction_times`` are the per-hit reaction times in milliseconds (only hits
    appear here; misses are never recorded). ``gun_id`` and any client time are
    intentionally absent — both are decided server-side (design §3.2, R-15).
    """

    hits: int
    total_clicks: int
    reaction_times: list[int]
    time_limit_ms: int


@dataclass(frozen=True)
class PersistedScore:
    """A scored session after persistence (use-case / repository output).

    Pairs the immutable domain ``Score`` with the database-assigned ``id`` and
    the server-assigned ``created_at`` (R-15). The adapters/api layer maps this
    to the ``ScoreResponse`` DTO (design §3.3).
    """

    id: int
    score: Score
    created_at: datetime
