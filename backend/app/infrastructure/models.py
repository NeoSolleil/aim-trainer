"""SQLAlchemy 2.0 ORM models for the Scoring schema (design §4.1/§4.2).

Typed declarative style (``Mapped`` + ``mapped_column``). These models are an
infrastructure concern only: the domain ``Score`` aggregate is separate, and the
repository converts between them (entity <-> ORM, design §4.3) so ORM objects
never leak outward.

The schema is deliberately minimal for 0001:

* ``gun`` has only ``id`` / ``name`` — the 0002 behaviour columns
  (fire_rate / recoil / target_size) are not added yet (non-breaking later).
* ``score`` is one row per completed session with **no** per-hit detail table
  (R-14). ``accuracy`` / ``avg_reaction_time`` are NULLable to represent the
  undefined ("—") cases (R-18/R-19); both are ``Numeric`` (Decimal) to avoid
  float rounding. ``created_at`` is timezone-aware and server-assigned (R-15).

Only portable types are used (``Numeric``, ``DateTime(timezone=True)``, standard
FK) so a move to PostgreSQL needs no schema rewrite.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base


class GunModel(Base):
    """The ``gun`` master table (design §4.1)."""

    __tablename__ = "gun"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class ScoreModel(Base):
    """The ``score`` table: one row per completed session (design §4.2)."""

    __tablename__ = "score"

    id: Mapped[int] = mapped_column(primary_key=True)
    hits: Mapped[int] = mapped_column(nullable=False)
    total_clicks: Mapped[int] = mapped_column(nullable=False)
    # NULLable: undefined accuracy (total_clicks == 0) persists as NULL (R-18).
    accuracy: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    # NULLable: undefined average (hits == 0) persists as NULL (R-19). ms.
    avg_reaction_time: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    time_limit_ms: Mapped[int] = mapped_column(nullable=False)
    gun_id: Mapped[int] = mapped_column(ForeignKey("gun.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
