"""LedgerRank FastAPI application entry point.

Wires the thin API layer onto the proven service layer:
* lifespan startup -> init_db() (register models, create schema once)
* centralized exception handlers (uniform error envelope)
* CORS (so the React frontend can call the API in the next phase)
* the aggregate api_router (/transaction, /summary/{user_id}, /ranking)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.router import api_router
from app.db.database import init_db

API_DESCRIPTION = """
**LedgerRank** is a transaction ledger with:

* **Idempotent writes** — a client-supplied `request_id` (UNIQUE) guarantees a
  retried request is applied exactly once; reuse with a different payload is a
  409 conflict.
* **Concurrency-safe aggregates** — per-user totals are updated atomically in
  the database (no lost updates), inside a single transaction with the ledger
  insert.
* **Fair, multi-factor ranking** — `0.5*amount + 0.3*count + 0.2*recency`, with
  amount and count log-scaled so a single large transaction cannot dominate.
"""

tags_metadata = [
    {"name": "transactions", "description": "Create transactions (idempotent)."},
    {"name": "summary", "description": "Per-user aggregate summaries."},
    {"name": "ranking", "description": "Multi-factor fairness leaderboard."},
    {"name": "system", "description": "Health / liveness."},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: create the schema (idempotent — no-op if it already exists).
    init_db()
    yield
    # Shutdown: nothing to tear down (engine/pool managed by SQLAlchemy).


app = FastAPI(
    title="LedgerRank API",
    description=API_DESCRIPTION,
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# CORS: permissive for the demo so the deployed frontend can call the API.
# Tighten `allow_origins` to the frontend origin for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["system"], summary="Liveness probe.")
def health() -> dict:
    return {"status": "ok"}
