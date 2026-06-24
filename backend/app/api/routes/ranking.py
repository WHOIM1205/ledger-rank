"""GET /ranking — thin route over the ranking service.

Flow
----
1. Validated pagination (limit/offset) is injected as a reusable dependency.
2. A request-scoped session is injected.
3. The service computes the multi-factor, log-scaled leaderboard and returns it.
   Always 200 (an empty system yields an empty list).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import PaginationParams, get_db
from app.schemas.ranking import RankingResponse
from app.services.ranking_service import get_ranking

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get(
    "",
    response_model=RankingResponse,
    summary="Get the multi-factor leaderboard.",
    responses={200: {"description": "Ranked users (may be empty)."}},
)
def read_ranking(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
) -> RankingResponse:
    return get_ranking(db, limit=pagination.limit, offset=pagination.offset)
