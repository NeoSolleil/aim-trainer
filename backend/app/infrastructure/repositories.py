"""Concrete repositories and the default-gun seed (infrastructure, design §4.3).

These implement the application's ``ScoreRepository`` / ``GunRepository`` ports
against SQLAlchemy. They convert between the domain ``Score`` aggregate and the
``ScoreModel`` ORM row (entity <-> ORM) and **never return ORM objects** —
``add`` returns a domain ``PersistedScore`` (design §4.3).

The default gun is seeded with an **idempotent startup seed**: ``ensure_default_gun``
inserts one gun only if none exists. This was chosen over a data migration so
that (a) re-running it is safe (idempotent), and (b) tests that build a throwaway
SQLite schema can seed without running Alembic. Alembic migrations stay purely
structural.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.dto import PersistedScore
from app.domain.score import Score
from app.domain.value_objects import Accuracy, AverageReactionTime
from app.infrastructure.models import GunModel, ScoreModel

#: Display name of the single default gun seeded for 0001 (no behaviour columns).
DEFAULT_GUN_NAME = "Default Pistol"


def ensure_default_gun(session: Session) -> int:
    """Ensure exactly one default gun exists, returning its id (idempotent).

    "If none, insert one." Safe to run repeatedly (e.g. on every startup): when a
    gun already exists this is a no-op that returns the existing id. R-14 relies
    on exactly one resolvable default gun.
    """
    existing = session.scalar(select(GunModel.id).order_by(GunModel.id).limit(1))
    if existing is not None:
        return existing

    gun = GunModel(name=DEFAULT_GUN_NAME)
    session.add(gun)
    session.flush()  # assign the primary key without ending the transaction
    return gun.id


class SqlAlchemyGunRepository:
    """``GunRepository`` over SQLAlchemy (implements the application port)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_default_id(self) -> int:
        """Return the seeded default gun's id (the lowest id, deterministically).

        Raises ``LookupError`` if no gun has been seeded — a programming/setup
        error, since the startup seed guarantees one exists.
        """
        gun_id = self._session.scalar(select(GunModel.id).order_by(GunModel.id).limit(1))
        if gun_id is None:
            raise LookupError("no default gun has been seeded")
        return gun_id


class SqlAlchemyScoreRepository:
    """``ScoreRepository`` over SQLAlchemy (implements the application port)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, score: Score, created_at: datetime) -> PersistedScore:
        """Persist ``score`` as one ``score`` row and return a domain result.

        The value objects map straight onto the nullable columns: an undefined
        accuracy / average (``None``) becomes SQL ``NULL`` (R-18/R-19). After the
        flush assigns the id, a fresh domain ``Score`` is rebuilt and wrapped in a
        ``PersistedScore`` so no ORM object escapes this layer (design §4.3).
        """
        row = ScoreModel(
            hits=score.hits,
            total_clicks=score.total_clicks,
            accuracy=score.accuracy.value,
            avg_reaction_time=score.avg_reaction_time.ms,
            time_limit_ms=score.time_limit_ms,
            gun_id=score.gun_id,
            created_at=created_at,
        )
        self._session.add(row)
        self._session.flush()  # assign the primary key (id) within the transaction

        return PersistedScore(
            id=row.id,
            score=self._to_domain(row),
            created_at=row.created_at,
        )

    @staticmethod
    def _to_domain(row: ScoreModel) -> Score:
        """Rebuild the domain ``Score`` from a persisted row (ORM -> entity).

        The aggregate factory is bypassed deliberately: the row holds already
        validated, computed values, so the value objects are reconstructed
        directly (re-deriving accuracy/average from counts would be redundant and
        could disagree with what was stored).
        """
        return Score(
            hits=row.hits,
            total_clicks=row.total_clicks,
            accuracy=Accuracy(value=row.accuracy),
            avg_reaction_time=AverageReactionTime(ms=row.avg_reaction_time),
            time_limit_ms=row.time_limit_ms,
            gun_id=row.gun_id,
        )


__all__ = [
    "DEFAULT_GUN_NAME",
    "SqlAlchemyGunRepository",
    "SqlAlchemyScoreRepository",
    "ensure_default_gun",
]
