"""Engine, session factory, and per-connection SQLite tuning.

This module is the single place where the database connection is configured.
Everything that touches persistence goes through `SessionLocal` / `get_db`,
which gives us **one session == one transaction per request** — the boundary
that makes the ledger insert and the aggregate update atomic.

Why the PRAGMAs matter for this assignment
-------------------------------------------
SQLite PRAGMAs are *per-connection*, not per-database. A connection pool hands
out multiple connections, so the settings must be (re)applied every time a new
connection is opened. We therefore register a `connect` event listener instead
of running the PRAGMAs once at startup.

- journal_mode = WAL    -> readers never block the single writer; concurrent
                           GET /summary and GET /ranking run while a
                           POST /transaction is committing.
- busy_timeout          -> a writer that finds the write-lock held will retry
                           for N ms instead of immediately failing with
                           SQLITE_BUSY. This is how simultaneous POSTs are
                           handled gracefully rather than erroring out.
- synchronous = NORMAL  -> the recommended, durable setting under WAL; safe and
                           fast (full fsync only at checkpoint).
- foreign_keys = ON     -> SQLite disables FK enforcement by default; we turn it
                           on so transactions.user_id integrity is guaranteed.
"""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# SQLite + the default threadpool used by FastAPI requires check_same_thread
# to be disabled so a connection can be used by the worker thread handling the
# request. Session-per-request keeps usage single-threaded in practice.
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

# Ensure the parent directory of a SQLite file exists. On a fresh clone or a
# fresh deploy (where the gitignored .db file has not been created yet) the
# ./data folder may not exist, which would make SQLite fail to open the file.
if settings.database_url.startswith("sqlite"):
    _db_path = make_url(settings.database_url).database
    if _db_path and _db_path != ":memory:":
        _db_dir = os.path.dirname(os.path.abspath(_db_path))
        os.makedirs(_db_dir, exist_ok=True)

engine: Engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    connect_args=_connect_args,
    # pool_pre_ping keeps pooled connections healthy across the app's lifetime.
    pool_pre_ping=True,
    future=True,
)


@event.listens_for(engine, "connect")
def _configure_sqlite_connection(dbapi_connection, _connection_record):
    """Apply WAL + concurrency PRAGMAs to every new SQLite connection.

    Runs once per physical connection the pool opens. Non-SQLite backends are
    left untouched so the same code path is portable.
    """
    if not settings.database_url.startswith("sqlite"):
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms};")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
    finally:
        cursor.close()


# Session factory. expire_on_commit=False lets us return ORM objects after a
# commit without triggering a surprise reload (relevant for idempotent replays).
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
    future=True,
)


def get_db():
    """FastAPI dependency yielding a request-scoped session.

    One session per request defines the transaction boundary: the route's work
    either commits as a whole or rolls back as a whole. The session is always
    closed, returning the connection to the pool.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create the schema if it does not yet exist.

    Startup sequence
    ----------------
    1. The engine is already created at import time (above), and the `connect`
       listener has the WAL / busy_timeout / foreign_keys PRAGMAs ready to apply
       to every connection the pool opens.
    2. `init_models()` imports all model modules so their tables register on
       `Base.metadata`.
    3. `create_all(engine)` discovers every registered table, index, and
       constraint from that single metadata object and emits CREATE statements
       for anything missing (it never drops or alters existing objects).

    This is idempotent: running it on an existing database is a no-op.

    How this supports atomic transactions later
    -------------------------------------------
    `create_all` materializes the UNIQUE(request_id) index, the CHECK
    constraints, and the foreign keys. Those storage-layer guarantees are
    exactly what the service layer will lean on so that, inside a single
    `get_db` session/transaction, the ledger insert and the atomic UserStats
    update either both commit or both roll back.
    """
    from app.db.base import Base, init_models

    init_models()
    Base.metadata.create_all(bind=engine)
