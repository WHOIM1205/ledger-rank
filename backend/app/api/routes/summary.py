"""GET /summary/{user_id} — thin route over the summary service.

Flow
----
1. Path param `user_id` is bound by FastAPI.
2. A request-scoped session is injected.
3. The service performs the O(1) aggregate read and raises UserNotFoundError
   (-> 404) for an unknown user. The route adds no logic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.summary import SummaryResponse
from app.services.summary_service import get_summary

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get(
    "/{user_id}",
    response_model=SummaryResponse,
    summary="Get a user's aggregate summary.",
    responses={
        200: {"description": "User summary."},
        404: {"description": "User not found."},
    },
)
def read_summary(
    user_id: str,
    db: Session = Depends(get_db),
) -> SummaryResponse:
    return get_summary(db, user_id)
