"""Unit tests for the adapters/schemas Pydantic v2 DTOs (T-06).

These lock the *boundary shape* the API exposes (design §3.3):

  * ``SessionResultRequest`` validation is deliberately **thin** — it carries
    only the raw data, enforces the simple shape (non-negative counts, positive
    time limit), and must **not** reject a negative ``reaction_time`` (that is a
    business invariant the domain detects, keeping R-13's verification in the
    domain). It must not carry ``accuracy`` / ``avg_reaction_time`` (domain
    computes them, R-11/12), ``gun_id`` (server-resolved) or any client time
    (server-assigned ``created_at``, R-15).
  * ``ScoreResponse`` must represent the undefined accuracy / average as ``null``
    (``None``) — the R-18/R-19 "—" cases.
  * ``ErrorResponse`` is the consistent ``{detail, code}`` error envelope.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.adapters.schemas.scoring import (
    ErrorResponse,
    ScoreResponse,
    SessionResultRequest,
)


class TestSessionResultRequest:
    def test_accepts_valid_raw_data(self) -> None:
        req = SessionResultRequest(
            hits=5,
            total_clicks=8,
            reaction_times=[200, 300, 400, 500, 600],
            time_limit_ms=30000,
        )
        assert req.hits == 5
        assert req.total_clicks == 8
        assert req.reaction_times == [200, 300, 400, 500, 600]
        assert req.time_limit_ms == 30000

    def test_does_not_reject_negative_reaction_time(self) -> None:
        # The shape check is intentionally thin: a negative reaction_time is a
        # *business* invariant the domain (Score.create) detects (R-13). Pydantic
        # must accept it and pass it through, or the domain's check is bypassed.
        req = SessionResultRequest(
            hits=2,
            total_clicks=5,
            reaction_times=[100, -1],
            time_limit_ms=30000,
        )
        assert req.reaction_times == [100, -1]

    def test_zero_counts_are_valid(self) -> None:
        # R-18: hits=0/total_clicks=0 is a valid submission (ge=0 allows 0).
        req = SessionResultRequest(hits=0, total_clicks=0, reaction_times=[], time_limit_ms=30000)
        assert req.hits == 0
        assert req.total_clicks == 0
        assert req.reaction_times == []

    def test_rejects_negative_hits(self) -> None:
        # ge=0 on the count: a negative hit count is a malformed shape (422 by
        # FastAPI default), distinct from the domain invariants.
        with pytest.raises(ValidationError):
            SessionResultRequest(hits=-1, total_clicks=8, reaction_times=[], time_limit_ms=30000)

    def test_rejects_negative_total_clicks(self) -> None:
        with pytest.raises(ValidationError):
            SessionResultRequest(hits=0, total_clicks=-1, reaction_times=[], time_limit_ms=30000)

    def test_rejects_non_positive_time_limit(self) -> None:
        # gt=0: the session must have a positive time limit.
        with pytest.raises(ValidationError):
            SessionResultRequest(hits=0, total_clicks=0, reaction_times=[], time_limit_ms=0)

    def test_field_set_excludes_server_owned_and_computed_fields(self) -> None:
        # The contract must not expose accuracy / avg_reaction_time (domain
        # computes, R-11/12), gun_id (server resolves) or created_at / any client
        # time (server assigns, R-15). Guard the field set so a future edit can't
        # smuggle them in (design §3.3).
        names = set(SessionResultRequest.model_fields)
        assert names == {"hits", "total_clicks", "reaction_times", "time_limit_ms"}


class TestScoreResponse:
    def test_carries_all_output_fields(self) -> None:
        created = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
        resp = ScoreResponse(
            id=1,
            hits=5,
            total_clicks=8,
            accuracy=0.625,
            avg_reaction_time=400.0,
            time_limit_ms=30000,
            gun_id=7,
            created_at=created,
        )
        assert resp.id == 1
        assert resp.accuracy == 0.625
        assert resp.avg_reaction_time == 400.0
        assert resp.gun_id == 7
        assert resp.created_at == created

    def test_accuracy_and_average_accept_null(self) -> None:
        # R-18/R-19: undefined accuracy / average serialize as null (None).
        resp = ScoreResponse(
            id=2,
            hits=0,
            total_clicks=0,
            accuracy=None,
            avg_reaction_time=None,
            time_limit_ms=30000,
            gun_id=7,
            created_at=datetime(2026, 6, 21, 0, 0, 0, tzinfo=UTC),
        )
        assert resp.accuracy is None
        assert resp.avg_reaction_time is None
        dumped = resp.model_dump()
        assert dumped["accuracy"] is None
        assert dumped["avg_reaction_time"] is None


class TestErrorResponse:
    def test_carries_detail_and_code(self) -> None:
        err = ErrorResponse(detail="accuracy must be within [0, 1]", code="accuracy_out_of_range")
        assert err.detail == "accuracy must be within [0, 1]"
        assert err.code == "accuracy_out_of_range"
