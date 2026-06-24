"""Seed demo users so the API and frontend have data to work with.

There is no user-creation endpoint (out of scope); users are pre-seeded. Each
user gets a paired user_stats row in the SAME transaction, preserving the
invariant "every user has exactly one stats row".

Run:  python -m app.db.seed
Idempotent: re-running does not duplicate users.
"""

from __future__ import annotations

from app.db.database import SessionLocal, init_db
from app.models.user import User
from app.models.user_stats import UserStats

# (id, username) — a mix that makes the ranking story visible in the demo.
SEED_USERS = [
    ("u_1", "alice"),
    ("u_2", "bob"),
    ("u_3", "carol"),
    ("u_4", "dave"),
    ("u_5", "erin"),
]


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        created = 0
        for uid, uname in SEED_USERS:
            if db.get(User, uid) is None:
                db.add(User(id=uid, username=uname))
                db.add(UserStats(user_id=uid))
                created += 1
        db.commit()
        print(f"Seed complete. Users created this run: {created}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
