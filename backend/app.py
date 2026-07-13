"""Read-only viewer API over the SQLite DB.

No upload endpoint — ingestion happens in the offline pipeline (ingest.py).
This process also enforces the offline rule on its own, so it is safe even if
launched independently of run.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import store
from offline_guard import arm, assert_offline

app = FastAPI(title="Finance Manager (offline)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    assert_offline()
    arm()


@app.get("/health")
def health():
    """Liveness probe the frontend polls. When the offline guard trips, this
    whole process exits, so the probe starts failing and the UI locks itself."""
    return {"ok": True}


def _rows(query: str, params: tuple = ()) -> list[dict]:
    conn = store.connect()
    conn.row_factory = lambda c, r: {d[0]: r[i] for i, d in enumerate(c.description)}
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


@app.get("/summary")
def summary():
    """Per-account totals: money in, money out, net, transaction count."""
    return _rows(
        """
        SELECT account,
               COUNT(*)                                        AS count,
               ROUND(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 2) AS spent,
               ROUND(SUM(CASE WHEN amount > 0 THEN  amount ELSE 0 END), 2) AS received,
               ROUND(SUM(amount), 2)                          AS net
        FROM transactions
        GROUP BY account
        ORDER BY spent DESC
        """
    )


@app.get("/merchants")
def merchants(limit: int = 30):
    """Top merchants by total spend."""
    return _rows(
        """
        SELECT merchant,
               COUNT(*)                    AS count,
               ROUND(SUM(-amount), 2)      AS spent
        FROM transactions
        WHERE amount < 0
        GROUP BY merchant
        ORDER BY spent DESC
        LIMIT ?
        """,
        (limit,),
    )


@app.get("/monthly")
def monthly():
    """Spend and income grouped by YYYY-MM."""
    return _rows(
        """
        SELECT substr(date, 1, 7) AS month,
               ROUND(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 2) AS spent,
               ROUND(SUM(CASE WHEN amount > 0 THEN  amount ELSE 0 END), 2) AS received
        FROM transactions
        WHERE length(date) >= 7
        GROUP BY month
        ORDER BY month
        """
    )


@app.get("/transactions")
def transactions(account: str | None = None, merchant: str | None = None,
                 q: str | None = None, limit: int = 500):
    where, params = [], []
    if account:
        where.append("account = ?")
        params.append(account)
    if merchant:
        where.append("merchant = ?")
        params.append(merchant)
    if q:
        where.append("(description LIKE ? OR merchant LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    return _rows(
        f"""
        SELECT date, account, merchant, description, amount, balance
        FROM transactions
        {clause}
        ORDER BY date DESC, id DESC
        LIMIT ?
        """,
        tuple(params),
    )
