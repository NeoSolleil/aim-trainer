"""End-to-end backend integration test for the composition root (T-08).

This exercises the *real* wiring in ``app.main.create_app`` — the production
repositories (``SqlAlchemyScoreRepository`` / ``SqlAlchemyGunRepository``), the
real ``SystemClock``, the one-session-per-request boundary, the startup
default-gun seed and the ``POST /api/sessions`` route — against a throwaway
SQLite database whose schema is built by the **real Alembic migration** (not
``create_all``), exactly as production builds it.

It is a plain integration test (not a Gherkin binding): the @backend scenarios
are already bound at the API level in ``test_scoring_api.py``. Here we confirm the
fully wired application persists a score end-to-end and that ``/health`` still
works (the composition root must not break the existing liveness probe).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.infrastructure.models import GunModel, ScoreModel

BACKEND_ROOT = Path(__file__).parents[2]


def _post(client: TestClient, url: str, payload: dict[str, Any]) -> httpx.Response:
    # The starlette TestClient stub types .post partially unknown; isolate that
    # framework-stub limitation to this single boundary so call sites stay typed.
    return client.post(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        url, json=payload
    )


def _get(client: TestClient, url: str) -> httpx.Response:
    return client.get(url)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


@pytest.fixture
def migrated_engine(tmp_path: Path) -> Iterator[Engine]:
    """A temp SQLite file upgraded to Alembic head (the production schema path)."""
    db_path = tmp_path / "e2e.db"
    url = f"sqlite:///{db_path}"

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    engine = create_engine(url, connect_args={"check_same_thread": False})
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def client(migrated_engine: Engine) -> Iterator[TestClient]:
    """A TestClient over the real ``create_app`` wired to the migrated DB."""
    from app.main import create_app

    app = create_app(engine=migrated_engine)
    with TestClient(app) as test_client:
        yield test_client


def test_startup_seeds_exactly_one_default_gun(client: TestClient, migrated_engine: Engine) -> None:
    # The composition root runs the idempotent seed once at startup, so the
    # default gun R-14 depends on exists after the app comes up.
    factory: sessionmaker[Session] = sessionmaker(bind=migrated_engine)
    with factory() as session:
        gun_count = session.scalar(select(func.count()).select_from(GunModel))
    assert gun_count == 1


def test_post_session_persists_one_row_end_to_end(
    client: TestClient, migrated_engine: Engine
) -> None:
    # @R-14/@R-15/@R-18 integration: the fully wired app accepts a valid
    # submission, returns 201 + ScoreResponse, and writes exactly one score row
    # via the real repository over the migrated schema.
    before = datetime.now(UTC)
    response = _post(
        client,
        "/api/sessions",
        {
            "hits": 5,
            "total_clicks": 8,
            "reaction_times": [200, 300, 400, 500, 600],
            "time_limit_ms": 30000,
        },
    )
    after = datetime.now(UTC)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["accuracy"] == pytest.approx(0.625)
    assert body["avg_reaction_time"] == pytest.approx(400.0)
    assert body["gun_id"] >= 1
    # created_at is server-assigned (R-15): it falls within the request window.
    created = datetime.fromisoformat(body["created_at"])
    assert before <= created <= after

    factory: sessionmaker[Session] = sessionmaker(bind=migrated_engine)
    with factory() as session:
        row_count = session.scalar(select(func.count()).select_from(ScoreModel))
    assert row_count == 1


def test_repeating_decimal_is_consistent_api_equals_db_end_to_end(
    client: TestClient, migrated_engine: Engine
) -> None:
    # M-1 consistency (most important, full stack): a repeating ratio
    # (hits=3/total=9 = 1/3, mean over [100,100,101] = 301/3) must come back
    # from the API *exactly* equal to the value stored in the DB, with no
    # precision drift. hits=3 keeps len(reaction_times) == hits while making
    # both metrics repeating. accuracy = 1/3 -> 0.3333 (Numeric(5,4));
    # avg = 301/3 -> 100.333 (Numeric(8,3)). Before quantization the API body
    # (built from the in-memory domain value) was 0.3333333... while the column
    # held 0.3333, so they diverged.
    response = _post(
        client,
        "/api/sessions",
        {
            "hits": 3,
            "total_clicks": 9,
            "reaction_times": [100, 100, 101],
            "time_limit_ms": 30000,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()

    # API values, taken as exact Decimals from the JSON numbers.
    api_accuracy = Decimal(str(body["accuracy"]))
    api_avg = Decimal(str(body["avg_reaction_time"]))

    factory: sessionmaker[Session] = sessionmaker(bind=migrated_engine)
    with factory() as session:
        row = session.scalars(select(ScoreModel)).one()
        db_accuracy = row.accuracy
        db_avg = row.avg_reaction_time

    # API == DB == the quantized value, exactly (no full-precision leak).
    assert api_accuracy == db_accuracy == Decimal("0.3333")
    assert api_avg == db_avg == Decimal("100.333")


def test_zero_clicks_persists_with_null_accuracy_end_to_end(
    client: TestClient, migrated_engine: Engine
) -> None:
    # @R-18 integration: a 0/0 session is accepted (201) and persisted with
    # accuracy / avg_reaction_time as null.
    response = _post(
        client,
        "/api/sessions",
        {"hits": 0, "total_clicks": 0, "reaction_times": [], "time_limit_ms": 30000},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["accuracy"] is None
    assert body["avg_reaction_time"] is None

    factory: sessionmaker[Session] = sessionmaker(bind=migrated_engine)
    with factory() as session:
        row = session.scalars(select(ScoreModel)).one()
    assert row.accuracy is None
    assert row.avg_reaction_time is None


def test_invariant_violation_returns_422_and_saves_nothing(
    client: TestClient, migrated_engine: Engine
) -> None:
    # R-13 end-to-end: hits > total_clicks is rejected with 422 + the consistent
    # error envelope, and no row is written.
    response = _post(
        client,
        "/api/sessions",
        {
            "hits": 9,
            "total_clicks": 8,
            "reaction_times": [100] * 9,
            "time_limit_ms": 30000,
        },
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "hits_exceed_total"
    assert "detail" in body

    factory: sessionmaker[Session] = sessionmaker(bind=migrated_engine)
    with factory() as session:
        row_count = session.scalar(select(func.count()).select_from(ScoreModel))
    assert row_count == 0


def test_malformed_payload_returns_422(client: TestClient) -> None:
    # A negative hit count is a shape error -> FastAPI's default 422 (Pydantic),
    # distinct from the domain's 422 envelope.
    response = _post(
        client,
        "/api/sessions",
        {"hits": -1, "total_clicks": 8, "reaction_times": [], "time_limit_ms": 30000},
    )
    assert response.status_code == 422


def test_health_still_works(client: TestClient) -> None:
    # The composition root must not break the existing liveness probe.
    response = _get(client, "/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
