"""User model — canonical identity and FK anchor.

Every transaction and the per-user stats row point back here. A stable user id
means a replayed transaction always resolves to the same user, and the FK target
guarantees there are no orphan ledger rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:  # avoid runtime import cycles; only needed for type hints
    from app.models.transaction import Transaction
    from app.models.user_stats import UserStats


class User(Base):
    """A LedgerRank user.

    Columns
    -------
    id          : human-friendly string key, e.g. "u_123" (primary key).
    username    : unique display name.
    created_at  : UTC creation time; also the final deterministic tie-break key
                  in ranking.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    # 1 -> many: the immutable ledger of this user's transactions.
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # 1 -> 1: the denormalized aggregate row driving summary and ranking.
    stats: Mapped[Optional["UserStats"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<User id={self.id!r} username={self.username!r}>"
