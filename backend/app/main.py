"""Composition root: FastAPI application wiring (T-08, design §3.1/§3.4/§4).

This module is the only place allowed to depend on every layer (it wires the
adapters/api controller, the application use case and the infrastructure
implementations together). It is intentionally outside the import-linter layer
contract.

Responsibilities (design §3.1 末/§4):

* build the engine/session (one-session-per-request unit of work),
* inject the **concrete** infrastructure (``SqlAlchemyScoreRepository`` /
  ``SqlAlchemyGunRepository`` / ``SystemClock``) into the abstract use case by
  overriding the router's ``get_record_session_result`` dependency,
* own the transaction boundary: commit on success, rollback on error (§3.4),
* run the idempotent default-gun seed once at startup (R-14),
* register the ``POST /api/sessions`` router and the 500 exception handler,
* keep the existing ``/health`` liveness probe.

The schema itself is owned by Alembic (design §4.1/§8.5 decision 2): this module
does **not** call ``create_all`` — migrations are applied as a separate step.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.adapters.api.sessions import (
    get_record_session_result,
    register_exception_handlers,
    router,
)
from app.application.use_cases import RecordSessionResult
from app.infrastructure.clock import SystemClock
from app.infrastructure.db import engine as default_engine
from app.infrastructure.repositories import (
    SqlAlchemyGunRepository,
    SqlAlchemyScoreRepository,
    ensure_default_gun,
)


def create_app(*, engine: Engine | None = None) -> FastAPI:
    """Build and wire the FastAPI application (composition root).

    ``engine`` defaults to the application engine (SQLite/PostgreSQL per
    ``DATABASE_URL``); tests pass a throwaway engine pointed at a migrated test
    database. The default-gun seed runs once here, against an already-migrated
    schema (Alembic owns the tables).
    """
    active_engine = engine if engine is not None else default_engine
    session_factory = sessionmaker(bind=active_engine, autoflush=False, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        # Startup seed (idempotent): ensure exactly one default gun exists (R-14).
        # Done on startup (not at import) so merely importing this module never
        # touches the database; it runs against an already-migrated schema.
        with session_factory() as session:
            ensure_default_gun(session)
            session.commit()
        yield

    app = FastAPI(title="Aim Trainer API", lifespan=lifespan)

    def provide_record_session_result() -> Iterator[RecordSessionResult]:
        """Supply the use case over a per-request session (unit of work, §3.4).

        One session per request: the concrete repositories and clock are wired
        here, the use case is yielded to the endpoint, then the transaction is
        committed on success or rolled back if the endpoint raised (so an
        ``InvariantViolation`` or a DB failure never leaves a partial write).
        """
        session = session_factory()
        try:
            yield RecordSessionResult(
                score_repository=SqlAlchemyScoreRepository(session),
                gun_repository=SqlAlchemyGunRepository(session),
                clock=SystemClock(),
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Inject the concrete wiring in place of the router's abstract seam.
    app.dependency_overrides[get_record_session_result] = provide_record_session_result

    register_exception_handlers(app)
    app.include_router(router)
    app.add_api_route("/health", _health, methods=["GET"])

    return app


def _health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


app = create_app()
