"""Concrete clock (infrastructure, design §3.2/§4.2).

``SystemClock`` is the production implementation of the application's ``Clock``
port: it supplies the server's current time for ``created_at`` (R-15). Keeping
the timestamp in an application-supplied value (rather than a DB
``server_default``) makes "the server assigned it" explicit and testable.
"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """Supplies the real, timezone-aware server time (implements ``Clock``)."""

    def now(self) -> datetime:
        """Return the current UTC time as a timezone-aware ``datetime``."""
        return datetime.now(UTC)
