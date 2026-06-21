"""pytest-bdd step definitions for the @backend Scoring scenarios that require
the HTTP/API + persistence path (T-07).

The Gherkin source of truth is the single original feature file under
``specs/0001-shooting-session/acceptance.feature`` (referenced relatively, never
copied). Only the persistence scenarios are bound here via explicit
``@scenario(...)`` so the domain-only scenarios already bound in
``test_scoring_domain.py`` (L132/L119/L125/L138) are **not** double-bound:

Bound this increment (T-07, API level):
  * L152 @R-14 — a validated session creates exactly one score row (no detail).
  * L160 @R-15 — ``created_at`` is server-assigned; the client time is unused.
  * L191 @R-18 — hits=0/total_clicks=0 is saved (accuracy / average null).

The router depends on an **abstract** ``RecordSessionResult`` via ``Depends``;
the test wires a real use case over a throwaway in-memory SQLite database (schema
from the ORM metadata + the idempotent default-gun seed), proving the same
composition the production root performs (without importing ``app.main``).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenario, then, when
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.api.sessions import get_record_session_result, router
from app.adapters.schemas.scoring import SessionResultRequest
from app.application.use_cases import RecordSessionResult
from app.infrastructure.db import Base
from app.infrastructure.models import ScoreModel
from app.infrastructure.repositories import (
    SqlAlchemyGunRepository,
    SqlAlchemyScoreRepository,
    ensure_default_gun,
)


def _post(client: TestClient, url: str, payload: dict[str, Any]) -> httpx.Response:
    # The starlette TestClient stub types .post partially unknown; isolate that
    # framework-stub limitation to this single boundary so call sites stay typed.
    return client.post(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        url, json=payload
    )


# Original feature file, referenced relatively (no copy) per the SDD rules.
FEATURE = str(
    (Path(__file__).parents[3] / "specs" / "0001-shooting-session" / "acceptance.feature").resolve()
)


# A fixed, recognisable server time so the @R-15 assertion can prove the response
# carries the *server's* created_at (the request never sends a time at all).
SERVER_NOW = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)


class _FixedClock:
    """Clock returning a known server time (so created_at is verifiable)."""

    def now(self) -> datetime:
        return SERVER_NOW


# --- Scenario bindings (explicit by name; no whole-file autocollection) --------


@scenario(FEATURE, "検証を通った完了セッションは score を1行だけ保存する（正常）")
def test_validated_session_saves_one_row() -> None:
    """L152 @R-14: 201 + exactly one score row, no per-hit detail."""


@scenario(FEATURE, "created_at はシステムが付与し、クライアント時刻を信用しない（正常）")
def test_created_at_is_server_assigned() -> None:
    """L160 @R-15: created_at is the server's, not the client's."""


@scenario(FEATURE, "total_clicks が 0 でも score は保存できる（境界）")
def test_zero_clicks_is_saved() -> None:
    """L191 @R-18: hits=0/total_clicks=0 -> 201, accuracy/avg null."""


# --- Test application + DB wiring ---------------------------------------------


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    """A throwaway in-memory SQLite schema with the default gun seeded.

    ``StaticPool`` shares one connection across the whole engine so every session
    (including the request handler's, which runs on the TestClient's worker
    thread) sees the same in-memory database — otherwise each connection would
    get its own empty ``:memory:`` and the seeded ``gun`` table would be missing.
    """
    engine: Engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        ensure_default_gun(session)
        session.commit()
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    """A TestClient over a FastAPI app wired exactly as the composition root.

    The router declares ``get_record_session_result`` as an abstract dependency;
    here it is overridden with a real use case built over the test DB session
    (one session per request, committed on success / rolled back on error).
    """
    app = FastAPI()
    app.include_router(router)

    def override() -> Iterator[RecordSessionResult]:
        session = session_factory()
        try:
            use_case = RecordSessionResult(
                score_repository=SqlAlchemyScoreRepository(session),
                gun_repository=SqlAlchemyGunRepository(session),
                clock=_FixedClock(),
            )
            yield use_case
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_record_session_result] = override
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def context(session_factory: sessionmaker[Session]) -> dict[str, Any]:
    """Mutable bag carrying state between Given/When/Then steps."""
    return {"session_factory": session_factory}


# === Given: build the request payload from the scenario's described data =======


@given(
    parsers.parse(
        "hits={hits:d}・total_clicks={total_clicks:d} の検証を通る完了セッションのデータがある"
    )
)
def given_valid_session_data(context: dict[str, Any], hits: int, total_clicks: int) -> None:
    # L152 @R-14: hits=5/total_clicks=8. Provide exactly `hits` reaction_times so
    # the submission is internally consistent (len == hits); ms values are
    # irrelevant to the "one row saved" assertion.
    context["payload"] = {
        "hits": hits,
        "total_clicks": total_clicks,
        "reaction_times": [100] * hits,
        "time_limit_ms": 30000,
    }


@given(parsers.parse("クライアント時刻を含む完了セッションのデータが提出される"))
def given_session_data_with_client_time(context: dict[str, Any]) -> None:
    # L160 @R-15: even though the scenario speaks of a "client time", the request
    # contract has no time field — there is nowhere to put one. The payload is a
    # normal valid submission; the point is the response created_at is the
    # server's. (extra="forbid" also means a smuggled time field would 422.)
    context["payload"] = {
        "hits": 1,
        "total_clicks": 1,
        "reaction_times": [100],
        "time_limit_ms": 30000,
    }


@given(parsers.parse("hits={hits:d}・total_clicks={total_clicks:d} の完了セッションのデータがある"))
def given_zero_session_data(context: dict[str, Any], hits: int, total_clicks: int) -> None:
    # L191 @R-18: hits=0/total_clicks=0 -> no reaction_times.
    context["payload"] = {
        "hits": hits,
        "total_clicks": total_clicks,
        "reaction_times": [],
        "time_limit_ms": 30000,
    }


# === When: submit the data to the API =========================================


@when("そのデータが提出される")
def when_data_posted(context: dict[str, Any], client: TestClient) -> None:
    context["response"] = _post(client, "/api/sessions", context["payload"])


@when("score が保存される")
def when_score_persisted(context: dict[str, Any], client: TestClient) -> None:
    # L160 phrases the When as "score が保存される" (the save happens). Driving it
    # is the same single POST; the Then inspects the server-assigned created_at.
    context["response"] = _post(client, "/api/sessions", context["payload"])


# === Then: assert on the HTTP response and the persisted rows =================


@then("score が 1 行だけ保存される")
def then_one_row_saved(context: dict[str, Any]) -> None:
    response = context["response"]
    assert response.status_code == 201, response.text
    factory: sessionmaker[Session] = context["session_factory"]
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(ScoreModel))
    assert count == 1


@then(
    parsers.parse(
        "保存項目に accuracy・平均 reaction_time・hits・total_clicks・"
        "制限時間・既定銃参照が含まれる"
    )
)
def then_saved_fields_present(context: dict[str, Any]) -> None:
    factory: sessionmaker[Session] = context["session_factory"]
    with factory() as session:
        row = session.scalars(select(ScoreModel)).one()
        assert row.hits == 5
        assert row.total_clicks == 8
        assert row.accuracy is not None  # computed, persisted
        assert row.avg_reaction_time is not None  # computed, persisted
        assert row.time_limit_ms == 30000
        assert row.gun_id is not None  # default-gun reference (R-14)


@then("各 reaction_time の明細は保存されない")
def then_no_detail_rows(context: dict[str, Any]) -> None:
    # R-14: there is no per-hit detail table at all (only gun / score exist), and
    # exactly one score row was written. The schema's table set proves "no detail".
    factory: sessionmaker[Session] = context["session_factory"]
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {"gun", "score"}
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(ScoreModel))
    assert count == 1


@then("created_at はシステムが付与する")
def then_created_at_is_server(context: dict[str, Any]) -> None:
    response = context["response"]
    assert response.status_code == 201, response.text
    body = response.json()
    returned = datetime.fromisoformat(body["created_at"])
    assert returned == SERVER_NOW


@then("クライアントが申告した時刻は created_at に使われない")
def then_client_time_unused(context: dict[str, Any]) -> None:
    # The request contract has no client timestamp field at all, so created_at
    # can only be the server clock's value (asserted above). The structural
    # guarantee behind R-15: there is nowhere in the request to put a client time
    # (the only "time" field, time_limit_ms, is a duration, not a wall clock).
    assert "created_at" not in context["payload"]
    assert "created_at" not in SessionResultRequest.model_fields
    body = context["response"].json()
    assert datetime.fromisoformat(body["created_at"]) == SERVER_NOW


@then("score が保存される")
def then_score_saved(context: dict[str, Any]) -> None:
    # L191 @R-18: a 0/0 session is accepted and persisted (201). accuracy and
    # avg_reaction_time come back as null (the undefined "—" cases).
    response = context["response"]
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["accuracy"] is None
    assert body["avg_reaction_time"] is None
    factory: sessionmaker[Session] = context["session_factory"]
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(ScoreModel))
    assert count == 1
