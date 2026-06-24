"""Reusable FastAPI dependencies (dependency-injection entry points).

Centralizing dependencies here keeps routes thin and makes them easy to test
(any dependency can be overridden via `app.dependency_overrides`). It is also
where future cross-cutting concerns (auth, rate-limiting, request context) will
hook in without touching individual routes.
"""

from __future__ import annotations

from fastapi import Query

# Re-export the request-scoped DB session as the canonical DI entry point.
# The single source of truth for session/transaction lifecycle remains
# app/db/database.py; the API layer imports it from here for a clean boundary.
from app.db.database import get_db  # noqa: F401  (re-exported)


class PaginationParams:
    """Reusable, validated pagination for list endpoints.

    Bounds are enforced by FastAPI/OpenAPI: limit in [1, 200], offset >= 0.
    Used by GET /ranking; available to any future list endpoint.
    """

    def __init__(
        self,
        limit: int = Query(50, ge=1, le=200, description="Max rows to return."),
        offset: int = Query(0, ge=0, description="Rows to skip."),
    ) -> None:
        self.limit = limit
        self.offset = offset


# --- Future extensibility hooks (intentionally not wired yet) ---------------
#
# def get_current_user(...): ...        # authentication
# def rate_limiter(...): ...            # per-user write throttling -> 429
# def get_request_context(...): ...     # correlation id / tracing
#
# Adding any of these later means decorating the relevant route with
# `Depends(...)` — no service-layer changes required.
