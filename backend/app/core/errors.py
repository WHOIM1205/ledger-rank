"""Typed domain exceptions for LedgerRank.

These are deliberately framework-agnostic: they carry an HTTP status, a stable
machine-readable `code`, a human message, and optional structured `details`.
The service layer raises them; a single FastAPI handler (added in a later step)
translates them into the uniform error envelope:

    {"error": {"code": ..., "message": ..., "details": {...}}}

Why typed exceptions beat generic ones
--------------------------------------
* The service never imports FastAPI or decides status codes inline.
* One handler maps exception -> envelope, so every client sees an identical
  error shape and a stable `code` for each failure mode (API consistency).
* Each failure mode is independently catchable and unit-testable.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class LedgerRankError(Exception):
    """Base class for all domain errors.

    Subclasses set `code` and `http_status`. `details` carries structured,
    machine-readable context (never a stack trace).
    """

    code: str = "INTERNAL_ERROR"
    http_status: int = 500

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_envelope(self) -> Dict[str, Any]:
        """Serialize to the uniform error envelope payload."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class UserNotFoundError(LedgerRankError):
    """Raised when a referenced user does not exist. -> 404"""

    code = "USER_NOT_FOUND"
    http_status = 404

    def __init__(self, user_id: str) -> None:
        super().__init__(
            f"User '{user_id}' does not exist.",
            details={"user_id": user_id},
        )


class DuplicateRequestConflictError(LedgerRankError):
    """Raised when a request_id was already used for a *different* payload. -> 409

    This is the idempotency security guard: a request_id must name exactly one
    logical operation. Reusing it with different data is rejected, not replayed.
    """

    code = "IDEMPOTENCY_CONFLICT"
    http_status = 409

    def __init__(
        self, request_id: str, *, conflicting_fields: Optional[list] = None
    ) -> None:
        super().__init__(
            (
                f"request_id '{request_id}' has already been used for a "
                f"different transaction. The same request_id cannot be reused "
                f"with a different payload."
            ),
            details={
                "request_id": request_id,
                "conflicting_fields": conflicting_fields or [],
            },
        )


class InvalidTransactionTypeError(LedgerRankError):
    """Raised when transaction type is not 'credit' or 'debit'. -> 422"""

    code = "INVALID_TRANSACTION_TYPE"
    http_status = 422

    def __init__(self, value: Any) -> None:
        super().__init__(
            f"Invalid transaction type '{value}'. Allowed: 'credit', 'debit'.",
            details={"allowed": ["credit", "debit"], "received": value},
        )


class TransactionProcessingError(LedgerRankError):
    """Raised for unexpected, non-recoverable processing failures. -> 500

    Used as a defensive wrapper (e.g. an integrity error fired but the original
    row could not be located) so callers still get a typed, enveloped error
    rather than a raw 500.
    """

    code = "TRANSACTION_PROCESSING_ERROR"
    http_status = 500
