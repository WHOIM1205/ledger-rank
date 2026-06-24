"""Ranking response schemas for GET /ranking.

RankingEntry is one row of the leaderboard with the computed `score` and the
raw factors behind it (amount + count) so the result is explainable.
RankingResponse wraps the ordered list.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel


class RankingEntry(BaseModel):
    """A single leaderboard position."""

    rank: int
    user_id: str
    username: str
    score: float  # 0..100, rounded for display
    txn_count: int
    total_amount_cents: int


class RankingResponse(BaseModel):
    """Ordered leaderboard."""

    rankings: List[RankingEntry]
