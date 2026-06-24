"""Ranking read path — fair, multi-factor, manipulation-resistant.

Approved formula (weights live in core/config.py):

    score = 100 * ( 0.5 * amount_norm
                  + 0.3 * count_norm
                  + 0.2 * recency_score )

    amount_norm   = minmax( log(1 + total_amount_cents) )   # log-scaled
    count_norm    = minmax( log(1 + txn_count) )            # log-scaled
    recency_score = exp( -days_since_last_txn / tau )       # tau = 7 days

Normalization — why "highest amount" does NOT win
-------------------------------------------------
Each factor is squashed into [0, 1] before weighting, so no single dimension can
run away with the score. Amount and count are first passed through log(1 + x):
this gives diminishing returns, so a user who spends 100x more earns only ~2x
the amount sub-score rather than 100x. A min-max over the current cohort then
rescales to [0, 1]. The result: a consistent, recently-active user can out-rank
a one-shot whale. Amount has the largest weight (0.5) but, being log-scaled and
capped at 1.0, it cannot dominate the other factors.

Recency — deterministic decay
------------------------------
recency_score = exp(-days_since_last_txn / tau). A transaction "now" scores ~1.0;
it decays smoothly toward 0 as the user goes idle (half-life ~ tau*ln2 days).
Given a fixed evaluation time it is fully deterministic. Users with no
transactions score 0.

Tie-breaking (deterministic, stable)
------------------------------------
1. higher score wins
2. then higher total_amount_cents
3. then earlier user.created_at
4. then user_id ascending
Using strictly ordered keys (not float-equality branches) makes the leaderboard
reproducible and flicker-free.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import utcnow
from app.models.user import User
from app.models.user_stats import UserStats
from app.schemas.ranking import RankingEntry, RankingResponse


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Coerce a possibly-naive DB datetime to aware UTC.

    SQLite stores datetimes without an offset, so values read back are naive. We
    interpret them as UTC to subtract safely from an aware 'now'.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _recency_score(last_txn_at: Optional[datetime], now: datetime) -> float:
    """Exponential decay in [0, 1]; 0.0 when the user has no transactions."""
    last = _as_utc(last_txn_at)
    if last is None:
        return 0.0
    days = max(0.0, (now - last).total_seconds() / 86400.0)
    return math.exp(-days / settings.recency_tau_days)


def _minmax(value: float, lo: float, hi: float) -> float:
    """Scale `value` into [0, 1]. Degenerate cohort (hi == lo) -> neutral 1.0."""
    if hi <= lo:
        return 1.0
    return (value - lo) / (hi - lo)


def get_ranking(db: Session, limit: int = 50, offset: int = 0) -> RankingResponse:
    """Compute the multi-factor leaderboard."""
    rows = db.execute(
        select(
            User.id,
            User.username,
            User.created_at,
            UserStats.txn_count,
            UserStats.total_amount_cents,
            UserStats.last_txn_at,
        ).join(UserStats, UserStats.user_id == User.id)
    ).all()

    if not rows:
        return RankingResponse(rankings=[])

    now = utcnow()

    # Pre-compute the log-scaled values and their cohort min/max for min-max.
    log_amounts = [math.log1p(r.total_amount_cents) for r in rows]
    log_counts = [math.log1p(r.txn_count) for r in rows]
    a_lo, a_hi = min(log_amounts), max(log_amounts)
    c_lo, c_hi = min(log_counts), max(log_counts)

    scored = []
    for r in rows:
        amount_norm = _minmax(math.log1p(r.total_amount_cents), a_lo, a_hi)
        count_norm = _minmax(math.log1p(r.txn_count), c_lo, c_hi)
        recency = _recency_score(r.last_txn_at, now)
        score = 100.0 * (
            settings.weight_amount * amount_norm
            + settings.weight_count * count_norm
            + settings.weight_recency * recency
        )
        scored.append((score, r))

    # Deterministic ordering: score desc, total desc, created_at asc, user_id asc.
    scored.sort(
        key=lambda item: (
            -item[0],
            -item[1].total_amount_cents,
            _as_utc(item[1].created_at),
            item[1].id,
        )
    )

    # Rank assignment, then pagination window.
    entries: List[RankingEntry] = []
    window = scored[offset : offset + limit]
    for idx, (score, r) in enumerate(window):
        entries.append(
            RankingEntry(
                rank=offset + idx + 1,
                user_id=r.id,
                username=r.username,
                score=round(score, 2),
                txn_count=r.txn_count,
                total_amount_cents=r.total_amount_cents,
            )
        )

    return RankingResponse(rankings=entries)
