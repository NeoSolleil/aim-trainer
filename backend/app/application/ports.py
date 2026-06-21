"""Repository and service abstractions (ports) for the Scoring use cases.

These are the **interfaces** the application depends on; concrete
implementations live in the infrastructure layer (dependency inversion,
design §3.1/§3.2). They are ``typing.Protocol`` so infrastructure classes
satisfy them structurally without importing this module.

No framework / ORM / Pydantic here — the application stays persistence- and
web-agnostic (import-linter enforces this).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.application.dto import PersistedScore
from app.domain.score import Score


class ScoreRepository(Protocol):
    """Persists scored sessions (design §4.3)."""

    def add(self, score: Score, created_at: datetime) -> PersistedScore:
        """Persist ``score`` with the server-assigned ``created_at``.

        Returns a :class:`PersistedScore` carrying the persistence-assigned
        ``id`` and the same ``created_at``. Implementations must return a domain
        ``Score`` (never an ORM object) — they do not leak persistence types.
        """
        ...


class GunRepository(Protocol):
    """Resolves the default gun (design §3.2)."""

    def get_default_id(self) -> int:
        """Return the seeded default gun's id (R-14, server-resolved)."""
        ...


class Clock(Protocol):
    """Supplies the server's current time (design §3.2, R-15)."""

    def now(self) -> datetime:
        """Return the current server timestamp used for ``created_at``."""
        ...
