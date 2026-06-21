"""Pydantic v2 DTOs for the Scoring API boundary (adapters/schemas, design §3.3).

These are the HTTP boundary types, kept separate from the domain ``Score`` and
the application ``SessionResult`` (they are converted to/from those at the
controller boundary). Validation here is deliberately **thin**: it enforces only
the simple shape, leaving the business invariants (accuracy range,
``hits <= total_clicks``, non-negative ``reaction_time``) to the domain so R-13's
verification stays in ``Score.create`` (design §3.3 "二段構え").
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class SessionResultRequest(BaseModel):
    """Raw data of one completed session submitted for scoring (design §3.3).

    Carries only what the server needs to score the session. It deliberately
    omits ``accuracy`` / ``avg_reaction_time`` (the domain computes them,
    R-11/12), ``gun_id`` (the server resolves the default gun) and any client
    time (the server assigns ``created_at``, R-15). ``reaction_times`` is *not*
    constrained to non-negative elements: a negative value is a domain invariant
    violation (R-13), so it is passed through to ``Score.create`` rather than
    rejected here.
    """

    model_config = ConfigDict(extra="forbid")

    hits: Annotated[int, Field(ge=0)]
    total_clicks: Annotated[int, Field(ge=0)]
    reaction_times: list[int]
    time_limit_ms: Annotated[int, Field(gt=0)]


class ScoreResponse(BaseModel):
    """The created score returned on success (201, design §3.3).

    ``accuracy`` / ``avg_reaction_time`` are ``float | None``: the undefined
    cases (``total_clicks == 0`` / ``hits == 0``) serialize as JSON ``null``
    (R-18/R-19), which the frontend renders as "—".
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    hits: int
    total_clicks: int
    accuracy: float | None
    avg_reaction_time: float | None
    time_limit_ms: int
    gun_id: int
    created_at: datetime


class ErrorResponse(BaseModel):
    """Consistent error envelope (design §3.3/§3.4).

    ``code`` carries the domain ``InvariantViolation`` code (e.g.
    ``"accuracy_out_of_range"``) so a client can distinguish a business rejection
    (422) from a malformed payload (FastAPI's default 422) without parsing the
    human-readable ``detail``.
    """

    model_config = ConfigDict(extra="forbid")

    detail: str
    code: str


__all__ = ["ErrorResponse", "ScoreResponse", "SessionResultRequest"]
