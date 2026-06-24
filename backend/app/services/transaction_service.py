"""Transaction write path — idempotent, atomic, concurrency-safe.

This is the most important module in the backend. It guarantees:

* Idempotency      — enforced by the UNIQUE(request_id) index, not app code.
* Atomicity        — ledger insert + UserStats update share ONE transaction.
* Consistency      — UserStats can never diverge from the ledger.
* Concurrency       — lost updates are impossible (atomic UPDATE), duplicates
                      are serialized by the unique index. No locks, no Redis.

Flow (all inside a single get_db session / transaction)
-------------------------------------------------------
1. Fetch user            -> 404 if missing
2. Defensive type check  -> 422 if not credit/debit
3. db.add(transaction)
4. db.flush()            -> forces UNIQUE(request_id) check NOW
5. IntegrityError?       -> rollback, look up original, compare payload:
                              match    -> replay (duplicate=true, 200)
                              mismatch -> 409 conflict
6. Atomic UserStats UPDATE (col = col + delta)
7. Single commit()
8. db.refresh()          -> ORM state reflects the committed update
9. Return TransactionResponse
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    DuplicateRequestConflictError,
    InvalidTransactionTypeError,
    TransactionProcessingError,
    UserNotFoundError,
)
from app.db.base import utcnow
from app.models.transaction import Transaction
from app.models.user import User
from app.models.user_stats import UserStats
from app.schemas.transaction import TransactionCreate, TransactionResponse

_ALLOWED_TYPES = ("credit", "debit")

# Fields that define the logical identity of a request. If a duplicate
# request_id arrives, all of these must match the original for it to count as a
# legitimate retry; any difference is a 409 conflict.
_IDENTITY_FIELDS = ("user_id", "amount_cents", "currency", "type")


def create_transaction(
    db: Session, payload: TransactionCreate
) -> TransactionResponse:
    """Process one POST /transaction, idempotently and atomically."""

    # --- 1. User must exist (clean 404 instead of a later FK error) ---
    user = db.get(User, payload.user_id)
    if user is None:
        raise UserNotFoundError(payload.user_id)

    # --- 2. Defensive type validation (schema already enforces this) ---
    if payload.type not in _ALLOWED_TYPES:
        raise InvalidTransactionTypeError(payload.type)

    # --- 3. Stage the immutable ledger row ---
    txn = Transaction(
        request_id=payload.request_id,
        user_id=payload.user_id,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        type=payload.type,
        status="applied",
    )
    db.add(txn)

    # --- 4. flush(): force the UNIQUE(request_id) check BEFORE we mutate
    #         UserStats. See module note "Why flush() first" below. ---
    try:
        db.flush()
    except IntegrityError:
        # --- 5. Duplicate request_id. The transaction is now aborted, so we
        #         MUST roll back before issuing the lookup SELECT. ---
        db.rollback()
        return _resolve_duplicate(db, payload)

    # --- 6. Atomic aggregate update. The arithmetic happens INSIDE the DB
    #         (col = col + :delta), which the engine serializes per row, so two
    #         concurrent transactions for the same user can never lose an
    #         update. We never read-then-write in Python. ---
    result = db.execute(
        update(UserStats)
        .where(UserStats.user_id == payload.user_id)
        .values(
            txn_count=UserStats.txn_count + 1,
            total_amount_cents=UserStats.total_amount_cents + payload.amount_cents,
            last_txn_at=utcnow(),
            updated_at=utcnow(),
        )
    )

    # Invariant: every user has a UserStats row (created with the user). This is
    # a defensive fallback in case it is missing, kept inside the same
    # transaction so atomicity still holds.
    if result.rowcount == 0:
        db.add(
            UserStats(
                user_id=payload.user_id,
                txn_count=1,
                total_amount_cents=payload.amount_cents,
                last_txn_at=utcnow(),
            )
        )

    # --- 7. ONE commit: ledger insert + stats update become durable together
    #         (or, on failure above, neither did). ---
    db.commit()

    # --- 8. Refresh: the atomic UPDATE was emitted as Core SQL and bypassed the
    #         ORM identity map. Refresh so any subsequent read in this session
    #         sees the committed values rather than a stale cached row. We also
    #         refresh the txn to load the DB-persisted created_at consistently. ---
    db.refresh(txn)
    stats = db.get(UserStats, payload.user_id)
    if stats is not None:
        db.refresh(stats)

    # --- 9. Fresh create -> duplicate=False ---
    return TransactionResponse.from_transaction(txn, duplicate=False)


def _resolve_duplicate(
    db: Session, payload: TransactionCreate
) -> TransactionResponse:
    """Handle a request_id collision: legitimate retry vs. conflicting reuse."""
    original = db.execute(
        select(Transaction).where(Transaction.request_id == payload.request_id)
    ).scalar_one_or_none()

    if original is None:
        # Unique violation fired but no row found -> something is genuinely
        # wrong; surface a typed 500 rather than a raw crash.
        raise TransactionProcessingError(
            "Duplicate detected but original transaction is missing.",
            details={"request_id": payload.request_id},
        )

    # Compare the logical identity of the request against the stored original.
    incoming = {
        "user_id": payload.user_id,
        "amount_cents": payload.amount_cents,
        "currency": payload.currency,
        "type": payload.type,
    }
    conflicting = [
        field
        for field in _IDENTITY_FIELDS
        if getattr(original, field) != incoming[field]
    ]

    if conflicting:
        # Same request_id, different payload -> reject, never replay.
        raise DuplicateRequestConflictError(
            payload.request_id, conflicting_fields=conflicting
        )

    # Exact match -> legitimate retry -> replay original, duplicate=true.
    return TransactionResponse.from_transaction(original, duplicate=True)
