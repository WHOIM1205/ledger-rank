"""Transaction request/response schemas.

TransactionCreate is the input contract: it enforces types, ranges, and the
allowed transaction types *before* the service runs, so structurally invalid
requests fail fast with 422 and never reach business logic.

TransactionResponse is the output contract returned by the write path. It adds
the `duplicate` flag (not stored on the ledger) so clients can tell a fresh
create (201) from an idempotent replay (200).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Upper bound on a single transaction. Rejects absurd values (overflow / abuse)
# while leaving ample headroom (10^11 cents = 1,000,000,000.00 of a currency).
MAX_AMOUNT_CENTS = 100_000_000_000


class TransactionCreate(BaseModel):
    """Validated body for POST /transaction."""

    # Reject unknown fields so a typo'd/extra key is a clear 422, not silent.
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "request_id": "req_12345678",
                "user_id": "u_1",
                "amount_cents": 2599,
                "currency": "USD",
                "type": "credit",
            }
        },
    )

    # request_id is the idempotency key: long enough to be collision-resistant,
    # bounded so it cannot be abused as an unbounded blob.
    request_id: str = Field(min_length=8, max_length=128)
    user_id: str = Field(min_length=1, max_length=64)
    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    type: Literal["credit", "debit"] = "credit"

    @field_validator("request_id", "user_id", mode="before")
    @classmethod
    def _strip_text(cls, v):
        # Trim BEFORE the length checks so that surrounding whitespace never
        # counts toward length and "   " collapses to "" -> fails min_length.
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, v):
        # Normalize case + trim BEFORE the length check so "usd" / " Usd " ->
        # "USD". Persisting only uppercase keeps storage, summaries, ranking and
        # the idempotency payload-comparison all consistent.
        if isinstance(v, str):
            return v.strip().upper()
        return v


class TransactionResponse(BaseModel):
    """Result of a write. `duplicate=True` means an idempotent replay."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: str
    user_id: str
    amount_cents: int
    currency: str
    type: str
    created_at: datetime
    duplicate: bool

    @classmethod
    def from_transaction(cls, txn, *, duplicate: bool) -> "TransactionResponse":
        """Build the response from a Transaction ORM row plus the replay flag."""
        return cls(
            id=txn.id,
            request_id=txn.request_id,
            user_id=txn.user_id,
            amount_cents=txn.amount_cents,
            currency=txn.currency,
            type=txn.type,
            created_at=txn.created_at,
            duplicate=duplicate,
        )
