"""Transaction model — the immutable, append-only ledger.

This is the source of truth. Rows are only ever inserted, never updated, so the
ledger has no update races. Two constraints carry most of the assignment's
weight:

* UNIQUE(request_id) — the foundation of idempotency. The storage engine, not
  application code, decides whether a logical request has been seen. Concurrent
  retries of the same request_id cannot both insert: exactly one wins, the rest
  raise an IntegrityError that the service layer turns into a replay of the
  original result. This is race-free without any application locking.

* CHECK(amount_cents > 0) — rejects zero/negative amounts at the storage layer,
  a backstop behind schema validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.user import User


class Transaction(Base):
    """A single, immutable money movement.

    Columns
    -------
    id            : surrogate auto-increment primary key.
    request_id    : client-supplied idempotency key (globally unique).
    user_id       : owning user (FK -> users.id).
    amount_cents  : positive integer minor units (never float).
    currency      : per-transaction currency, stored for future extensibility;
                    summaries/rankings assume a single-currency model.
    type          : "credit" | "debit" (validated at the schema layer).
    status        : lifecycle marker, defaults to "applied".
    created_at    : UTC insert time; feeds recency and tie-breaking.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        # Idempotency + fast replay lookup by request_id.
        Index("ux_transactions_request_id", "request_id", unique=True),
        # Storage-layer guard against non-positive amounts.
        CheckConstraint("amount_cents > 0", name="ck_transactions_amount_positive"),
        # Summary scans and recency reads by user, newest first.
        Index("ix_transactions_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String, nullable=False, default="USD", server_default="USD"
    )
    type: Mapped[str] = mapped_column(
        String, nullable=False, default="credit", server_default="credit"
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="applied", server_default="applied"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    # many -> 1
    user: Mapped["User"] = relationship(back_populates="transactions")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<Transaction id={self.id} request_id={self.request_id!r} "
            f"user_id={self.user_id!r} amount_cents={self.amount_cents}>"
        )
