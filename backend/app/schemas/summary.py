"""Summary response schema for GET /summary/{user_id}.

Mirrors the O(1) read from user_stats (joined to users for the username). No
ledger scan is involved; these fields come straight from the aggregate row.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SummaryResponse(BaseModel):
    """Per-user aggregate snapshot."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    username: str
    txn_count: int
    total_amount_cents: int
    last_txn_at: Optional[datetime]  # None when the user has no transactions yet
