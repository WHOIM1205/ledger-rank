"""Aggregate API router.

A single `api_router` collects every feature router. main.py includes just this
one object, so adding a feature means adding one `include_router` line here, not
touching startup.

Versioning
----------
Endpoints are mounted at the root to match the assignment contract exactly
(/transaction, /summary/{user_id}, /ranking). To introduce versioning later,
give this router a prefix (e.g. APIRouter(prefix="/api/v1")) in ONE place and
every endpoint moves together — no per-route changes.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import ranking, summary, transactions

api_router = APIRouter()
api_router.include_router(transactions.router)
api_router.include_router(summary.router)
api_router.include_router(ranking.router)
