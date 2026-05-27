from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import sqlite3
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from rapidfuzz import fuzz
import numpy as np
import re
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB = "db.sqlite"

model = SentenceTransformer("all-MiniLM-L6-v2")

conn = sqlite3.connect(DB, check_same_thread=False)

conn.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    description TEXT,
    merchant TEXT,
    amount REAL
)
""")

conn.commit()


def clean_text(text):
    text = str(text).upper()

    patterns = [
        r"UPI",
        r"NEFT",
        r"IMPS",
        r"TO",
        r"FROM",
        r"[0-9]+",
        r"[/\-]"
    ]

    for p in patterns:
        text = re.sub(p, " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def cluster_merchants(names):
    cleaned = [clean_text(n) for n in names]

    embeddings = model.encode(cleaned)

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1.0
    )

    labels = clustering.fit_predict(embeddings)

    canonical = {}

    for idx, label in enumerate(labels):
        if label not in canonical:
            canonical[label] = cleaned[idx]

    result = {}

    for idx, label in enumerate(labels):
        result[names[idx]] = canonical[label]

    return result


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    df = pd.read_csv(file.file)

    columns = [c.lower() for c in df.columns]

    date_col = None
    desc_col = None
    amount_col = None

    for c in columns:
        if "date" in c:
            date_col = c

        if "desc" in c or "narration" in c or "remark" in c:
            desc_col = c

        if "amount" in c or "withdrawal" in c or "debit" in c:
            amount_col = c

    if not desc_col:
        return {"error": "No description column found"}

    names = df[desc_col].astype(str).tolist()

    clustered = cluster_merchants(names)

    for _, row in df.iterrows():
        desc = str(row[desc_col])

        merchant = clustered[desc]

        amount = 0

        try:
            amount = float(row[amount_col])
        except:
            pass

        conn.execute(
            """
            INSERT INTO transactions
            (date, description, merchant, amount)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(row.get(date_col, "")),
                desc,
                merchant,
                amount
            )
        )

    conn.commit()

    return {"status": "uploaded"}


@app.get("/stats")
def stats():
    cur = conn.cursor()

    cur.execute("""
    SELECT merchant, SUM(amount) as total
    FROM transactions
    GROUP BY merchant
    ORDER BY total DESC
    """)

    rows = cur.fetchall()

    return [
        {
            "merchant": r[0],
            "total": r[1]
        }
        for r in rows
    ]


@app.get("/transactions")
def transactions():
    cur = conn.cursor()

    cur.execute("""
    SELECT date, merchant, amount, description
    FROM transactions
    ORDER BY amount DESC
    """)

    rows = cur.fetchall()

    return [
        {
            "date": r[0],
            "merchant": r[1],
            "amount": r[2],
            "description": r[3]
        }
        for r in rows
    ]
