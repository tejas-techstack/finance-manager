"""Persistence: canonical transactions -> per-statement CSV + SQLite.

The CSV in data/csv/ is the human-readable intermediate you asked for; the DB
is what the viewer reads. Every row carries a dedupe_hash with a UNIQUE index,
so re-ingesting an overlapping statement never double-counts.
"""

import csv
import hashlib
import os
import sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "..", "data")
DB_PATH = os.path.join(DATA_DIR, "db.sqlite")
CSV_DIR = os.path.join(DATA_DIR, "csv")
RAW_DIR = os.path.join(CSV_DIR, "raw")

_FIELDS = ["account", "date", "description", "merchant", "amount", "balance"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account     TEXT,
    date        TEXT,
    description TEXT,
    merchant    TEXT,
    amount      REAL,
    balance     REAL,
    source_file TEXT,
    dedupe_hash TEXT UNIQUE
);
"""


def connect() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def _hash(t: dict) -> str:
    key = f"{t['account']}|{t['date']}|{t['description']}|{t['amount']}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def write_raw_csv(rows: list[list[str]], source_file: str) -> str:
    """Dump the exact rows pulled from the PDF, BEFORE any parsing/mapping.

    This is your ground truth for debugging: if a column looks wrong in the
    final ledger, open the matching file in data/csv/raw/ to see precisely what
    the PDF scan produced (variable column counts and all).
    """
    os.makedirs(RAW_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(source_file))[0]
    path = os.path.join(RAW_DIR, base + ".raw.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return path


def write_csv(rows: list[dict], source_file: str) -> str:
    """Write one CSV per source statement into data/csv/."""
    os.makedirs(CSV_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(source_file))[0]
    path = os.path.join(CSV_DIR, base + ".csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in _FIELDS})
    return path


def store(conn: sqlite3.Connection, rows: list[dict], source_file: str) -> int:
    """Insert rows, skipping duplicates. Returns count actually inserted."""
    src = os.path.basename(source_file)
    inserted = 0
    for t in rows:
        cur = conn.execute(
            "INSERT OR IGNORE INTO transactions "
            "(account, date, description, merchant, amount, balance, source_file, dedupe_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (t["account"], t["date"], t["description"], t.get("merchant", ""),
             t["amount"], t.get("balance"), src, _hash(t)),
        )
        inserted += cur.rowcount
    conn.commit()
    return inserted
