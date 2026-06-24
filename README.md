# LedgerRank

A transaction-ledger service with **idempotent writes**, **concurrency-safe aggregates**, and a **fair, multi-factor ranking** — plus a small React frontend that demonstrates the full flow live.

---

## Overview

LedgerRank records financial transactions and ranks users fairly. It is built to demonstrate backend fundamentals: clean API design, data consistency, duplicate-request prevention, race-condition safety, and a ranking system that resists manipulation.

Three endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/transaction` | Record a transaction (idempotent). |
| `GET` | `/summary/{user_id}` | Per-user aggregate snapshot. |
| `GET` | `/ranking` | Multi-factor fairness leaderboard. |

The design centers on the three hard problems the assignment tests:

- **Duplicate prevention** — a client-supplied `request_id`, enforced unique by the database; retries replay exactly-once; reuse with a different payload is a conflict.
- **Consistency under concurrency** — the ledger insert and the per-user aggregate update happen in one transaction, with an atomic SQL increment, so concurrent writers cannot lose updates.
- **Fair ranking** — a normalized, log-scaled, multi-factor score so a single large transaction (or spam) cannot dominate.

---

## Architecture

```
        ┌──────────────────────────────────────────────┐
        │  Frontend (React + Vite, plain CSS)          │
        │   • Health banner (GET /health)              │
        │   • TransactionForm (new / retry / conflict) │
        │   • UserSummary    • RankingLeaderboard      │
        └───────────────────────┬──────────────────────┘
                                 │  HTTPS / JSON (CORS)
                                 ▼
        ┌──────────────────────────────────────────────┐
        │  FastAPI app  (app/main.py)                  │
        │   ├─ CORS + lifespan startup → init_db()     │
        │   └─ centralized exception handlers          │
        │                                              │
        │   Routes (api/routes/*)      ← THIN          │
        │        │  validate · 1 service call          │
        │        ▼                                     │
        │   Services (services/*)      ← ALL LOGIC     │
        │        │  idempotency · atomicity · ranking  │
        │        ▼                                     │
        │   Models (models/*) + Session                │
        │        │  one session = one transaction      │
        │        ▼                                     │
        │   SQLite (WAL)                               │
        └──────────────────────────────────────────────┘

  users (1) ──< (∞) transactions        users (1) ── (1) user_stats
```

**Why layered:** routes are a one-line contract; all business logic lives in services (independently tested); the storage layer enforces invariants (unique key, checks, FKs).

---

## Features

- **Transaction processing** — validated writes stored as immutable ledger rows (money as integer cents, never float).
- **Idempotency** — `request_id` + a unique DB index guarantee exactly-once processing across retries and concurrent duplicates.
- **Concurrency handling** — single-transaction boundaries, atomic in-DB aggregate updates, SQLite WAL + busy-timeout. No application-level locks.
- **Ranking system** — multi-factor score (amount, count, recency) with tunable weights and deterministic tie-breaking.
- **Fairness protection** — log-scaling and recency decay so whales and spammers can't dominate; duplicates never inflate scores.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| API framework | FastAPI |
| ORM | SQLAlchemy 2.0 (typed `Mapped[]`) |
| Validation | Pydantic v2 + pydantic-settings |
| Database | SQLite (WAL mode) |
| Server | Uvicorn |
| Frontend | React 18 + Vite, plain CSS (no UI frameworks) |

---

## Database Schema

Three tables. Money is stored as **integer cents**; timestamps are UTC.

```
users (1) ───────────< (∞) transactions
   │  id ◀────────────── user_id (FK)
   └── (1) ──────────── (1) user_stats
       id ◀──────────── user_id (PK/FK)
```

### `users` — canonical identity
| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT | PK (e.g. `"u_1"`) |
| `username` | TEXT | UNIQUE, NOT NULL |
| `created_at` | DATETIME (UTC) | NOT NULL — final ranking tie-break |

Purpose: the FK anchor for transactions and stats; enables clean `404`s for unknown users.

### `transactions` — immutable, append-only ledger
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK, autoincrement |
| `request_id` | TEXT | **UNIQUE**, NOT NULL — idempotency key |
| `user_id` | TEXT | FK → users.id, NOT NULL |
| `amount_cents` | BIGINT | `CHECK > 0`, NOT NULL |
| `currency` | TEXT | NOT NULL, default `USD` |
| `type` | TEXT | NOT NULL (`credit`/`debit`) |
| `status` | TEXT | NOT NULL, default `applied` |
| `created_at` | DATETIME (UTC) | NOT NULL |

Indexes: `UNIQUE(request_id)`, `(user_id, created_at)`. Never updated → no update races on the ledger. It is the source of truth.

### `user_stats` — denormalized aggregates (atomic-update target)
| Column | Type | Constraints |
|---|---|---|
| `user_id` | TEXT | PK, FK → users.id |
| `txn_count` | INTEGER | `CHECK ≥ 0`, default 0 |
| `total_amount_cents` | BIGINT | `CHECK ≥ 0`, default 0 |
| `last_txn_at` | DATETIME (UTC) | nullable (NULL = no transactions) |
| `updated_at` | DATETIME (UTC) | NOT NULL |

Purpose: O(1) summaries and cheap ranking inputs. **Invariant:** `txn_count = COUNT(transactions)` and `total_amount_cents = SUM(amount_cents)` per user — guaranteed because both writes share one transaction.

---

## API Documentation

Interactive docs: **`/docs`** (Swagger) and **`/redoc`**. All errors share one envelope:

```json
{ "error": { "code": "STRING_CODE", "message": "Human readable", "details": { } } }
```

### `POST /transaction`

**Request**
| Field | Type | Rules |
|---|---|---|
| `request_id` | string | required, trimmed, length 8–128 |
| `user_id` | string | required, must exist |
| `amount_cents` | integer | required, `> 0`, ≤ 100,000,000,000 |
| `currency` | string | optional, 3 chars, uppercased (default `USD`) |
| `type` | string | optional, `credit`\|`debit` (default `credit`) |

```json
{ "request_id": "req_12345678", "user_id": "u_1", "amount_cents": 2599, "currency": "USD", "type": "credit" }
```

**Response (201 fresh / 200 replay)**
```json
{ "id": 1, "request_id": "req_12345678", "user_id": "u_1", "amount_cents": 2599,
  "currency": "USD", "type": "credit", "created_at": "2026-06-24T17:26:35", "duplicate": false }
```

**Status codes**
| Code | Meaning |
|---|---|
| `201` | New transaction applied (`duplicate: false`). |
| `200` | Idempotent replay — same `request_id` + same payload (`duplicate: true`). |
| `404` | `USER_NOT_FOUND`. |
| `409` | `IDEMPOTENCY_CONFLICT` — `request_id` reused with a different payload. |
| `422` | `VALIDATION_ERROR`. |

**409 example**
```json
{ "error": { "code": "IDEMPOTENCY_CONFLICT",
  "message": "request_id 'req_12345678' has already been used for a different transaction...",
  "details": { "request_id": "req_12345678", "conflicting_fields": ["amount_cents"] } } }
```

### `GET /summary/{user_id}`

**Response (200)**
```json
{ "user_id": "u_1", "username": "alice", "txn_count": 2,
  "total_amount_cents": 7099, "last_txn_at": "2026-06-24T17:27:11" }
```
**Status codes:** `200` OK · `404` `USER_NOT_FOUND`.

### `GET /ranking`

Query: `limit` (1–200, default 50), `offset` (≥0, default 0). Always `200` (empty list if no data).

**Response (200)**
```json
{ "rankings": [
  { "rank": 1, "user_id": "u_3", "username": "carol", "score": 84.13, "txn_count": 30, "total_amount_cents": 60000 },
  { "rank": 2, "user_id": "u_2", "username": "bob",   "score": 76.06, "txn_count": 1,  "total_amount_cents": 10000000 }
] }
```
> `bob` made one $100,000 transaction yet ranks **below** `carol`'s 30 consistent transactions — fairness in action.

---

## Idempotency Design

**The database is the source of truth for "have I seen this request?"** — not application code.

- **`request_id`** — a mandatory client-supplied key (length 8–128) representing one logical operation; reused on retries, new for new transactions.
- **Unique constraint** — `transactions.request_id` has a `UNIQUE` index. The service **inserts and flushes first**, triggering the uniqueness check *before* aggregates are touched.

```
INSERT transaction + flush
 ├─ success          → atomic stats update → COMMIT → 201 { duplicate: false }
 └─ UNIQUE violation → ROLLBACK → SELECT original by request_id → compare payload:
        ├─ user_id, amount_cents, currency, type ALL match → 200 { duplicate: true }   (replay)
        └─ any field differs                              → 409 IDEMPOTENCY_CONFLICT  (reject)
```

- **Replay behavior** — a legitimate retry returns the **original** stored result with `duplicate: true`; the aggregate is applied exactly once.
- **Conflict behavior** — same `request_id` with a different payload is rejected (`409`), never replayed and never inserted, because a `request_id` must name exactly one operation.

Insert-first beats check-then-insert because the latter has a race (two retries both pass the check and both insert). The unique index rejecting the loser is race-free and lock-free.

---

## Concurrency Design

Two races are defeated **without any application-level locks** (no Redis, no mutexes):

- **WAL mode** — `journal_mode=WAL` lets readers (`/summary`, `/ranking`) run while a writer (`/transaction`) commits; `busy_timeout=5000` makes concurrent writers wait instead of failing with `SQLITE_BUSY`. `foreign_keys=ON`, `synchronous=NORMAL`. PRAGMAs are applied per-connection via a `connect` event listener.
- **Transactions** — one request = one session = one transaction. The ledger insert and the stats update commit together or roll back together (single `commit()`), so there is no partially-applied state.
- **Atomic updates** — the aggregate is updated with arithmetic **inside the database**, never read-modify-write in Python:
  ```sql
  UPDATE user_stats
  SET txn_count = txn_count + 1,
      total_amount_cents = total_amount_cents + :amount,
      last_txn_at = :now
  WHERE user_id = :uid;
  ```
  The engine serializes the single-row write, so concurrent increments all apply — no lost updates.
- **Duplicate protection** — the `UNIQUE(request_id)` index serializes concurrent duplicates; exactly one wins, the rest replay.

---

## Ranking Logic

Ranking is intentionally **not** "highest amount wins."

```
score = 100 × ( 0.5 · amount_norm
              + 0.3 · count_norm
              + 0.2 · recency_score )

amount_norm   = minmax( log(1 + total_amount_cents) )   # log-scaled
count_norm    = minmax( log(1 + txn_count) )            # log-scaled
recency_score = exp( −days_since_last_txn / 7 )         # exponential decay
```

- **Factors** — total amount, transaction count, recency. Each normalized to `[0, 1]` before weighting.
- **Weights** — `0.5 / 0.3 / 0.2` (sum 1.0), tunable in `core/config.py`.
- **Anti-whale protection** — amount has the highest weight but is **log-scaled**; spending 100× more yields only ~2× the amount sub-score. Count + recency (50% combined) let consistent, active users out-rank dormant whales; recency decay prevents an inactive user staying at #1; duplicates never count.
- **Log scaling** — `log(1 + x)` on amount and count gives diminishing returns, the core manipulation defense against both single huge transactions and micro-spam.
- **Tie-breaking** (deterministic) — `score DESC → total_amount_cents DESC → created_at ASC → user_id ASC`.

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # optional; defaults work
python -m app.db.seed                                 # seed users u_1 … u_5
uvicorn app.main:app --reload --port 8000
```
API → `http://localhost:8000` · Swagger → `http://localhost:8000/docs`

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local      # set VITE_API_BASE_URL=http://localhost:8000
npm run dev                     # → http://localhost:5173
# production: npm run build && npm run preview
```

---

## Deployment Instructions

### Backend — Render
A `render.yaml` blueprint is included at the repo root.

1. Push the repo to GitHub.
2. Render → **New + → Blueprint** → select the repo. Render reads `render.yaml`:
   - root dir `backend`, build `pip install -r requirements.txt`
   - start `python -m app.db.seed && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. (Manual alternative) New **Web Service**, root `backend`, same build/start commands.

CORS is open (`allow_origins=["*"]`, no credentials), so the Vercel frontend can call it immediately.

> **Note:** Render's free tier has an ephemeral filesystem — SQLite data resets on redeploy. The start command re-seeds demo users so the live demo is always populated. For persistence, attach a Render Disk or switch to Postgres (see Future Improvements).

### Frontend — Vercel
1. Vercel → **New Project** → import the repo, set **Root Directory** to `frontend`.
2. Framework preset **Vite** (auto-detected): build `npm run build`, output `dist`.
3. Add env var **`VITE_API_BASE_URL`** = your Render backend URL (e.g. `https://ledgerrank-backend.onrender.com`).
4. Deploy. The frontend reads the API base URL from `VITE_API_BASE_URL` at build time.

---

## Assumptions

- **Pre-seeded users.** No user-creation endpoint (out of scope); users `u_1`–`u_5` are seeded via `python -m app.db.seed`. Each user is created with a paired `user_stats` row in one transaction.
- **Single-currency aggregation.** `currency` is stored per transaction for future extensibility, but summaries/rankings are computed **without conversion**.
- **`request_id` = one logical operation.** Reuse with a different payload is a conflict, not a new transaction.
- **UTC everywhere.** SQLite doesn't persist offsets; timestamps are written/interpreted as UTC; the frontend renders local time.
- **Ranking is evaluated at read time**, so `recency` depends on "now".

---

## Trade-offs

| Decision | Trade-off |
|---|---|
| **SQLite (WAL)** vs Postgres | Zero-config and perfect for review; correctness relies on the unique index + atomic UPDATE, which work identically on Postgres. SQLite serializes writers at high concurrency. |
| **Denormalized `user_stats`** | O(1) reads at the cost of maintaining the aggregate — kept consistent in the same transaction as the ledger. |
| **Ranking computed on read** | Always fresh, simple to reason about; O(n) over users per call. Fine at demo scale. |
| **Insert-first idempotency** | Relies on catching `IntegrityError` (normal control flow). Race-free and lock-free. |
| **No application locks** | Simpler and correct via storage-engine guarantees. |

---

## Future Improvements

- Per-user write **rate limiting** (`429`) — hook stubbed in `api/dependencies.py`.
- **Postgres + Alembic** migrations for scale and durability; `SELECT … FOR UPDATE` if logic outgrows single-row atomic updates.
- **Cached / materialized ranking** for large user bases.
- **Authentication** and a **user-creation endpoint** (replacing seeding).
- Explicit **UTC serialization** (`Z` suffix) in API responses.
- An **automated pytest suite** (`backend/tests/`) encoding the scenarios validated below.

---

## Testing

All scenarios below were executed and verified during development (manual + scripted validation against a live server and a temp database). The `backend/tests/` package is scaffolded for porting these into an automated suite.

### Schema & constraints
| Check | Result |
|---|---|
| `UNIQUE(request_id)` rejects duplicates | ✅ |
| FK integrity (unknown `user_id` rejected, `foreign_keys=ON`) | ✅ |
| `CHECK(amount_cents > 0)` and `CHECK(... ≥ 0)` on stats | ✅ |
| Relationships (`user.transactions`, `user.stats`) resolve | ✅ |
| Indexes present (`request_id`, `(user_id, created_at)`) | ✅ |
| WAL / busy_timeout / FK pragmas applied per connection | ✅ |

### Service layer
| Check | Result |
|---|---|
| Duplicate retry replays original (`duplicate: true`, same id) | ✅ |
| Payload mismatch → `409 IDEMPOTENCY_CONFLICT`, no insert/replay | ✅ |
| Idempotency storage-enforced: 20 concurrent identical `request_id` → 1 row, 19 replays | ✅ |
| Atomicity: injected failure between insert and commit → neither row persists | ✅ |
| Consistency: `user_stats == SUM/COUNT(ledger)` | ✅ |
| Concurrency: 50 concurrent distinct transactions → count 50, total exact (no lost updates) | ✅ |
| Ranking: active consistent user out-ranks one-shot whale | ✅ |
| Summary: O(1) read + `404` on unknown user | ✅ |

### API layer (FastAPI TestClient)
| Check | Result |
|---|---|
| `201` fresh / `200` idempotent replay | ✅ |
| `409` payload mismatch | ✅ |
| `404` unknown user (POST + GET summary) | ✅ |
| `422` invalid input (short/blank `request_id`, `amount=0`, bad `type`, `limit=0`) | ✅ |
| `currency` normalization (`usd` → `USD`) | ✅ |
| OpenAPI schema generates with all paths | ✅ |
| Routes thin; business logic isolated to services | ✅ |

### End-to-end (live servers)
| Flow | Result |
|---|---|
| Health → `{"status":"ok"}` | ✅ |
| Create → `201`, currency normalized | ✅ |
| Retry → `200`, `duplicate: true` | ✅ |
| Conflict → `409`, `conflicting_fields:["amount_cents"]` | ✅ |
| Summary → `200` / `404` | ✅ |
| Ranking → fairness verified (carol 84.13 > whale bob 76.06) | ✅ |
| Refresh flow (post → summary + ranking update) | ✅ |
| CORS preflight from frontend origin allowed | ✅ |
| Frontend production build (`npm run build`) clean | ✅ |

**How to reproduce a quick smoke test**
```bash
curl -X POST http://localhost:8000/transaction -H 'Content-Type: application/json' \
  -d '{"request_id":"req_demo_0001","user_id":"u_1","amount_cents":2599}'      # 201
curl -X POST http://localhost:8000/transaction -H 'Content-Type: application/json' \
  -d '{"request_id":"req_demo_0001","user_id":"u_1","amount_cents":2599}'      # 200 duplicate
curl -X POST http://localhost:8000/transaction -H 'Content-Type: application/json' \
  -d '{"request_id":"req_demo_0001","user_id":"u_1","amount_cents":9999}'      # 409 conflict
curl http://localhost:8000/summary/u_1
curl http://localhost:8000/ranking
```

---

*LedgerRank — built to be correct first, and simple enough to explain in an interview.*
