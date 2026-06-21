"""Domain exceptions (innermost layer).

Pure: no framework, no HTTP. The mapping from these exceptions to HTTP status
codes is the responsibility of the adapters/api layer (design §2.6).
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""


class InvariantViolation(DomainError):
    """Raised when a domain invariant is violated (design §2.6, R-13).

    Carries a stable ``code`` (e.g. ``"accuracy_out_of_range"``,
    ``"hits_exceed_total"``, ``"negative_reaction_time"``,
    ``"hit_count_mismatch"``) so adapters can translate it into a consistent
    error response without parsing the human-readable message.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
