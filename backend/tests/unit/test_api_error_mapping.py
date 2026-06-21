"""Unit tests for the adapters/api exception -> HTTP mapping (T-07, design §3.4).

These exercise the controller's error translation directly, with the use case
faked, so they assert the contract without a database:

  * an ``InvariantViolation`` (business rejection, R-13) -> ``422`` + the
    consistent ``ErrorResponse`` carrying the violation ``code``.
  * any other failure (e.g. a repository/DB error) -> ``500`` + ``ErrorResponse``
    (a business exception is never leaked as a raw 500, and a DB exception never
    escapes as an unstructured 500 — design §3.4).

The router depends on the abstract ``get_record_session_result``; here it is
overridden with a fake use case that raises, isolating the mapping from the
domain/persistence layers.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.api.sessions import (
    get_record_session_result,
    register_exception_handlers,
    router,
)
from app.application.dto import PersistedScore, SessionResult
from app.domain.exceptions import InvariantViolation

_VALID_BODY: dict[str, Any] = {
    "hits": 5,
    "total_clicks": 8,
    "reaction_times": [100, 200, 300, 400, 500],
    "time_limit_ms": 30000,
}


def _post(client: TestClient, url: str, payload: dict[str, Any]) -> httpx.Response:
    return client.post(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        url, json=payload
    )


class _RaisingUseCase:
    """A use case whose ``execute`` always raises the configured exception."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def execute(self, _result: SessionResult) -> PersistedScore:
        raise self._error


def _client_raising(error: Exception, *, raise_server_exceptions: bool = True) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)

    def override() -> Iterator[_RaisingUseCase]:
        yield _RaisingUseCase(error)

    app.dependency_overrides[get_record_session_result] = override
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_invariant_violation_maps_to_422_with_code() -> None:
    # R-13: a business rejection becomes 422 + ErrorResponse with the domain code.
    client = _client_raising(
        InvariantViolation("hits_exceed_total", "hits (9) must not exceed total_clicks (8)")
    )
    response = _post(client, "/api/sessions", _VALID_BODY)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "hits_exceed_total"
    assert body["detail"] == "hits (9) must not exceed total_clicks (8)"


def test_repository_failure_maps_to_500_with_error_envelope() -> None:
    # Design §3.4: a DB/repository failure is shaped into a stable 500 +
    # ErrorResponse — the raw exception (and any stack trace) never leaks.
    # raise_server_exceptions=False lets the client observe the handled 500
    # response instead of re-raising it.
    client = _client_raising(RuntimeError("database is locked"), raise_server_exceptions=False)
    response = _post(client, "/api/sessions", _VALID_BODY)

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "persistence_error"
    assert "database is locked" not in body["detail"]  # internal detail not leaked


class _RecordingHandler(logging.Handler):
    """A handler that keeps every emitted record (for a self-contained assertion)."""

    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_unexpected_error_is_logged_with_stack_trace() -> None:
    # m-1: the 500 handler must record the swallowed cause (with its stack trace)
    # before shaping the opaque envelope, so the failure is diagnosable server-side
    # even though the response hides the internal detail. A handler is attached
    # directly to the sessions logger so the assertion is immune to any session-wide
    # logging state left by other tests (caplog relies on root propagation).
    logger = logging.getLogger("app.adapters.api.sessions")
    handler = _RecordingHandler()
    previous_level = logger.level
    previous_disabled = logger.disabled
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    # Other tests in the session run Alembic, whose fileConfig() defaults to
    # disable_existing_loggers=True and flips this logger's `disabled` flag. Force
    # it on so this test deterministically asserts the handler's own behaviour.
    logger.disabled = False
    try:
        client = _client_raising(RuntimeError("database is locked"), raise_server_exceptions=False)
        response = _post(client, "/api/sessions", _VALID_BODY)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.disabled = previous_disabled

    assert response.status_code == 500
    assert handler.records, "the 500 handler did not log the unexpected error"
    record = handler.records[-1]
    assert record.levelno == logging.ERROR
    # logger.exception attaches the active exception so the stack trace is kept.
    assert record.exc_info is not None
    assert record.exc_info[0] is RuntimeError


def test_malformed_payload_maps_to_422() -> None:
    # A negative hit count is a *shape* error -> FastAPI's default 422 (Pydantic),
    # which does not reach the domain at all (no use case is invoked).
    client = _client_raising(InvariantViolation("unused", "unused"))
    response = _post(
        client,
        "/api/sessions",
        {"hits": -1, "total_clicks": 8, "reaction_times": [], "time_limit_ms": 30000},
    )
    assert response.status_code == 422


def test_unknown_field_is_rejected() -> None:
    # extra="forbid" on the request: a smuggled accuracy field (which the client
    # must not declare, R-11) is rejected as a shape error (422), so the "accuracy
    # 1.5" input path simply does not exist (design §3.3 / §8.5 decision 1).
    client = _client_raising(InvariantViolation("unused", "unused"))
    response = _post(
        client,
        "/api/sessions",
        {**_VALID_BODY, "accuracy": 1.5},
    )
    assert response.status_code == 422
