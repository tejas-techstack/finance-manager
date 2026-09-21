# Finance Manager (fully offline)

Parses messy, possibly password-protected bank-statement PDFs from more than one
bank into a single deduplicated ledger, then shows it in a local dashboard.
**After a one-time setup, nothing ever touches the network** — the app refuses
to run if it detects an internet connection. There is no ML model; the payee
name is read straight out of the (structured) UPI transaction description.

## ⚡ Just want to use it?

Follow these five steps. Your statements never leave your machine.

1. **One-time setup (needs internet, only this once):**
   ```bash
   python -m venv backend/.venv && source backend/.venv/bin/activate
   pip install -r backend/requirements.txt
   python setup.py
   ```
2. **Download your statement PDFs into `data/inbox/`**, and name each file with
   its bank as a prefix so the app knows how to read it:
   - SBI statements → `sbi_anything.pdf` (e.g. `sbi_jan2026.pdf`)
   - Union Bank statements → `ubi_anything.pdf` (e.g. `ubi_q1.pdf`)

   Only the `sbi_` / `ubi_` prefix matters; the rest of the name is up to you.
3. **Go offline** — turn off Wi-Fi / unplug ethernet. (If you forget, step 4
   refuses to run.)
4. **Run everything with one command:**
   ```bash
   python run.py
   ```
   It asks each bank's PDF password (typed once, never written to disk), builds
   the ledger, and opens the dashboard at <http://localhost:5173>. `Ctrl+C` stops it.
5. **Your data stays private in git.** The folder is kept by `data/inbox/.gitkeep`,
   but your **PDFs, the generated CSVs, and the database are all git-ignored** — so
   you can safely `git commit` / `git push` and only the *code* is shared, never a
   single transaction of yours. Nothing you push ties the project to your details.

Everything below is the detailed reference.

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

## The dashboard

Everything is interactive and filters/sorts client-side:

- **KPI cards + stat tiles** — spent, received, net, count, largest expense, avg
  expense, largest credit, date range — all recomputed live as you filter.
- **Filters** — full-text search, account, debit/credit, date range, and min/max
  amount, with one-click reset.
- **Sortable transactions** — click any column header (Date, Account, Merchant,
  Description, Debit, Credit, Balance) to sort; click again to flip direction. A
  footer shows the filtered debit/credit totals.
- **Merchants panel** — each payee shows **Debit, Credit and Net** as separate
  columns (so a two-way counterparty — e.g. transfers between your own SBI and
  UBI — isn't collapsed into one net figure). Sort by any column; click a row to
  filter the whole view to that merchant. Name variants are grouped (see below).
- **By-account** split and a **monthly** spent-vs-received chart.

Merchant names are grouped so variants of the same payee collapse into one:
bank statements truncate names and sometimes add stray spaces, so `ZOMAT O`,
`ZOMATO`, `ZOMATO L`, `ZOMATO LTD` all roll up to a single merchant. This is
deterministic (space/punctuation-stripped + shared-prefix union) — no model.

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
