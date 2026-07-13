# Finance Manager (fully offline)

Parses messy, possibly password-protected bank-statement PDFs from more than one
bank into a single deduplicated ledger, then shows it in a local dashboard.
**After a one-time setup, nothing ever touches the network** — the app refuses
to run if it detects an internet connection. There is no ML model; the payee
name is read straight out of the (structured) UPI transaction description.

## How it works

```
data/inbox/*.pdf ──route by filename──▶ decrypt ─▶ extract tables
      │                                                    │
      │            (sbi_*.pdf  → SBI parser)                ▼
      │            (ubi_*.pdf  → UBI parser)        normalise per bank
      ▼                                                    │
  data/csv/*.csv  ◀── human-readable intermediate ─────────┤
      │                                                    ▼
      └────────────────────────────▶ SQLite (deduped) ─▶ dashboard
```

Two kinds of CSV are written under `data/csv/`:

- `data/csv/raw/<name>.raw.csv` — the **exact** rows pulled from the PDF, written
  *before* any parsing. This is your ground truth: if a column looks wrong in the
  ledger, open this file to see what the scan actually produced.
- `data/csv/<name>.csv` — the cleaned, per-bank normalised transactions.

- **Two banks, two schemas** — each bank is one small config in
  [`backend/banks/`](backend/banks). Filename prefix picks the parser. Add a
  third bank by dropping in one file.
- **Offline enforced** — [`backend/offline_guard.py`](backend/offline_guard.py)
  aborts at startup if you're online and keeps a background kill-switch armed
  that hard-stops everything if the network reappears mid-run.
- **PDF password** — typed once at the prompt, kept only in memory, never
  written to disk (there is no `.env`).
- **Low RAM** — statements are processed one at a time; the only model is a
  small local sentence-transformer used to group merchant names.

## One-time setup (the only step that needs internet)

```bash
python -m venv backend/.venv && source backend/.venv/bin/activate
pip install -r backend/requirements.txt
python setup.py          # runs npm install (no model to download)
```

## Every run (do this OFFLINE)

1. Turn off Wi-Fi / unplug ethernet. (If you forget, step 3 aborts by itself.)
2. Drop statements into `data/inbox/`, named by bank:
   `sbi_jan2026.pdf`, `ubi_q1.pdf`, ... (`.csv` also works, for testing).
3. Run everything with one command:

   ```bash
   python run.py
   ```

   It checks you're offline, wipes the previous run's output, asks which banks
   to process and their PDF passwords, ingests, starts the API + frontend in the
   background, and opens the dashboard at <http://localhost:5173>. Press
   **Ctrl+C** to stop.

### Choosing which banks to process

When more than one bank has files in the inbox you're shown a picker:

```
Banks found in inbox:
  [1] SBI  (2 files)
  [2] UBI  (1 file)
Select banks — numbers/names comma-separated, or Enter for all:
```

Or skip the prompt with a flag:

```bash
python run.py --banks sbi        # just SBI
python run.py --banks sbi,ubi    # both
python run.py --banks all        # everything in the inbox
```

Files from banks you didn't select are left in the inbox and ignored. New banks
appear in the picker automatically once you add their config under
`backend/banks/`.

Note: each run starts from a **clean slate** — the DB and generated CSVs are
wiped and rebuilt from the inbox (your `data/inbox/` PDFs are never touched).

## Tuning a bank parser

If a real statement's columns don't line up, edit the keyword lists in
[`backend/banks/sbi.py`](backend/banks/sbi.py) or
[`backend/banks/ubi.py`](backend/banks/ubi.py). Header matching is
case-insensitive substring, so `"particulars"` matches a `Particulars` column.

### How non-transaction tables are ignored

A statement PDF is full of *other* tables — account details, a totals/summary
block, linked accounts, digital products. Two rules keep them out of your
ledger (see [`backend/normalize.py`](backend/normalize.py)):

1. **A transaction must have a parseable date.** Rows without one are either the
   wrapped overflow of the previous description (folded back in) or stray lines
   (dropped) — never recorded as their own transaction.
2. **Parsing stops at the summary.** Once a row contains a marker like
   `Total Debits`, `Closing Balance`, `Summary` or `Linked ...`, the
   transactions are considered finished. If a new bank uses different wording,
   add it to `_END_MARKERS`.
