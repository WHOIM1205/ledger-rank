"""POST /transaction — thin route over the transaction service.

Flow
----
1. FastAPI validates the body into TransactionCreate (422 on failure).
2. A request-scoped session is injected (the transaction boundary).
3. The service does ALL the work: user check, idempotent insert, atomic stats
   update, conflict detection.
4. The route's only logic: a fresh create returns 201, an idempotent replay
   returns 200. Everything else is raised by the service and rendered by the
   centralized handlers (404 / 409 / 422 / 500).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.transaction import TransactionCreate, TransactionResponse
from app.services import transaction_service

router = APIRouter(prefix="/transaction", tags=["transactions"])


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a transaction (idempotent).",
    responses={
        200: {"description": "Idempotent replay of an existing transaction."},
        201: {"description": "Transaction created."},
        404: {"description": "User not found."},
        409: {"description": "request_id reused with a different payload."},
        422: {"description": "Validation failure."},
    },
)
def create_transaction(
    payload: TransactionCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> TransactionResponse:
    result = transaction_service.create_transaction(db, payload)
    # Same endpoint, two success codes: 201 for a new write, 200 for a replay.
    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    return result
