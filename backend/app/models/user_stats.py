"""UserStats model — denormalized per-user aggregates.

One hot row per user, kept in lock-step with the ledger inside the same
transaction as each insert. It exists so that:

* GET /summary is a primary-key point read, not a SUM/COUNT over the ledger.
* GET /ranking is a small full scan over one row per user.
* The write path can do an atomic `UPDATE ... = col + :delta`, which the engine
  serializes per row — defeating the lost-update race without app-level locks.

Invariant (always true because both writes share one transaction):
    txn_count          == COUNT(transactions for user)
    total_amount_cents == SUM(transactions.amount_cents for user)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.user import User


class UserStats(Base):
    """Aggregated ranking/summary inputs for one user.

    Columns
    -------
    user_id            : PK and FK -> users.id (1:1 with User).
    txn_count          : number of applied transactions (ranking: count factor).
    total_amount_cents : summed minor units (ranking: amount factor; summary total).
    last_txn_at        : UTC time of most recent transaction; NULL when none yet
                         (ranking: recency factor).
    updated_at         : UTC time of last mutation to this row.
    """

    __tablename__ = "user_stats"
    __table_args__ = (
        CheckConstraint("txn_count >= 0", name="ck_user_stats_txn_count_nonneg"),
        CheckConstraint(
            "total_amount_cents >= 0", name="ck_user_stats_total_nonneg"
        ),
    )

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), primary_key=True
    )
    txn_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_amount_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    last_txn_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    # 1 -> 1
    user: Mapped["User"] = relationship(back_populates="stats")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<UserStats user_id={self.user_id!r} txn_count={self.txn_count} "
            f"total_amount_cents={self.total_amount_cents}>"
        )
