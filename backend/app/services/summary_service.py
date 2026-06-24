"""Summary read path — O(1) per-user aggregate lookup.

Reads straight from `user_stats` (joined to `users` for the username). It never
scans the ledger: totals and counts are already maintained on the aggregate row
by the write path, so this is a primary-key point read regardless of how many
transactions the user has.

Why this scales
---------------
Computing the summary from the ledger would mean SUM()/COUNT()/MAX() over every
transaction the user has ever made — O(n) per request and increasingly slow as
the ledger grows, while also contending with concurrent writers. Maintaining the
aggregate at write time turns the read into O(1): join two rows on their primary
keys. Reads stay fast and constant-time no matter the history size.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import UserNotFoundError
from app.models.user import User
from app.models.user_stats import UserStats
from app.schemas.summary import SummaryResponse


def get_summary(db: Session, user_id: str) -> SummaryResponse:
    """Return the aggregate snapshot for one user, or raise 404."""
    row = db.execute(
        select(
            User.id,
            User.username,
            UserStats.txn_count,
            UserStats.total_amount_cents,
            UserStats.last_txn_at,
        )
        .join(UserStats, UserStats.user_id == User.id)
        .where(User.id == user_id)
    ).first()

    # Every user has a UserStats row (created together), so a missing row means
    # the user itself does not exist -> clean 404.
    if row is None:
        raise UserNotFoundError(user_id)

    return SummaryResponse(
        user_id=row.id,
        username=row.username,
        txn_count=row.txn_count,
        total_amount_cents=row.total_amount_cents,
        last_txn_at=row.last_txn_at,
    )
