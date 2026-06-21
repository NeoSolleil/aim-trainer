"""FastAPI router for the Scoring API: ``POST /api/sessions`` (adapters/api).

A thin controller (design §3.1/§3.3/§3.4): it validates the request DTO, maps it
to the application's ``SessionResult``, runs the **abstract**
``RecordSessionResult`` use case (injected via ``Depends``), and serialises the
result into ``ScoreResponse``. It contains no business logic and never imports
infrastructure — the composition root overrides ``get_record_session_result`` to
supply a use case wired to a per-request DB session (one-session-per-request unit
of work; commit on success / rollback on error live in that provider, §3.4).

Exception mapping (§3.4):
  * ``InvariantViolation`` (a business rejection, R-13) -> ``422`` + ``ErrorResponse``
    carrying the violation's ``code``. The domain raises *before* any persistence,
    so nothing is written.
  * any other error (e.g. a repository/DB failure) propagates and is converted to
    ``500`` + ``ErrorResponse`` by :func:`register_exception_handlers`, after the
    provider has rolled the transaction back. Business exceptions are never leaked
    as a raw 500, and DB exceptions never escape as an unstructured 500.
  * a malformed payload is rejected by FastAPI's default ``422`` (Pydantic).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.adapters.schemas.scoring import (
    ErrorResponse,
    ScoreResponse,
    SessionResultRequest,
)
from app.application.dto import PersistedScore, SessionResult
from app.application.use_cases import RecordSessionResult
from app.domain.exceptions import InvariantViolation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sessions"])


def get_record_session_result() -> RecordSessionResult:
    """Abstract dependency seam for the use case (overridden by composition root).

    The router depends only on this provider, never on a concrete repository or
    DB session. The composition root replaces it (via ``dependency_overrides``)
    with a provider that builds a ``RecordSessionResult`` over a per-request
    session and owns the commit/rollback boundary (design §3.4). The default
    raises so a missing wiring fails loudly rather than silently.
    """
    raise NotImplementedError(
        "get_record_session_result must be overridden by the composition root"
    )


def _to_float(value: Decimal | None) -> float | None:
    """Map a domain ``Decimal | None`` onto the response's ``float | None``.

    ``None`` (undefined accuracy / average) stays ``None`` so it serialises as
    JSON ``null`` (R-18/R-19); a value is widened to ``float`` for the JSON body.
    """
    return None if value is None else float(value)


def _to_response(persisted: PersistedScore) -> ScoreResponse:
    """Build the output DTO from the persisted domain result (design §3.3)."""
    score = persisted.score
    return ScoreResponse(
        id=persisted.id,
        hits=score.hits,
        total_clicks=score.total_clicks,
        accuracy=_to_float(score.accuracy.value),
        avg_reaction_time=_to_float(score.avg_reaction_time.ms),
        time_limit_ms=score.time_limit_ms,
        gun_id=score.gun_id,
        created_at=persisted.created_at,
    )


@router.post(
    "/sessions",
    status_code=HTTPStatus.CREATED,
    response_model=ScoreResponse,
    responses={
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        HTTPStatus.INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def create_session(
    payload: SessionResultRequest,
    use_case: Annotated[RecordSessionResult, Depends(get_record_session_result)],
) -> ScoreResponse | JSONResponse:
    """Submit a completed session's raw data and create its score (R-14).

    Validation of the *shape* is done by ``SessionResultRequest``; the *business*
    invariants (accuracy range, ``hits <= total_clicks``, non-negative
    ``reaction_time``) are enforced by the domain inside ``execute`` (R-13). On
    success returns ``201`` + ``ScoreResponse``; an ``InvariantViolation`` becomes
    ``422`` + ``ErrorResponse``.
    """
    result = SessionResult(
        hits=payload.hits,
        total_clicks=payload.total_clicks,
        reaction_times=payload.reaction_times,
        time_limit_ms=payload.time_limit_ms,
    )
    try:
        persisted = use_case.execute(result)
    except InvariantViolation as exc:
        # A business rejection (R-13): nothing was persisted (the domain raises
        # before the repository is touched). Return the consistent error envelope.
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=ErrorResponse(detail=exc.message, code=exc.code).model_dump(),
        )
    return _to_response(persisted)


async def _on_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Shape any non-business error into a stable 500 + ``ErrorResponse``.

    Reached only by errors other than ``InvariantViolation`` (handled in the
    endpoint) and FastAPI's own validation errors (its default 422). By the time
    this runs the use-case provider has rolled the transaction back (§3.4), so
    this just shapes the response — a DB exception never escapes as an
    unstructured 500 (design §3.4 "DB 例外を生の 500 で漏らさない").

    The original cause is logged with its stack trace before being shaped away,
    so the failure is diagnosable server-side even though the client only sees
    the opaque envelope (the internal detail is never leaked in the response).
    """
    logger.exception("unexpected error handling %s", request.url.path)
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            detail="Failed to persist the score.", code="persistence_error"
        ).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the catch-all 500 handler on the app (composition root calls this)."""
    app.add_exception_handler(Exception, _on_unexpected_error)


__all__ = ["get_record_session_result", "register_exception_handlers", "router"]
