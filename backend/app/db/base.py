"""Declarative base, shared time helper, and model registration point.

`Base` is the parent of every ORM model. This module is also the single place
that imports all model modules (via `init_models()`), so that by the time anyone
calls `Base.metadata.create_all(engine)` the full schema — including the
UNIQUE(request_id) index and CHECK(amount_cents > 0) constraint that enforce
idempotency and validity at the storage layer — is registered on the metadata.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all LedgerRank ORM models."""

    pass


def utcnow() -> datetime:
    """Timezone-aware current UTC timestamp.

    Used as the default for every `created_at` / `updated_at`. SQLite does not
    persist the offset, so writing UTC consistently is what keeps recency math
    correct across the ledger.
    """
    return datetime.now(timezone.utc)


def init_models() -> None:
    """Import all model modules so their tables register on `Base.metadata`.

    Imports are done inside the function (not at module top level) to avoid an
    import cycle: model modules import `Base` from here, so importing them at the
    top of this file would be circular. Calling `init_models()` before
    `create_all` guarantees every table, index, and constraint is known.
    """
    from app.models import transaction, user, user_stats  # noqa: F401
