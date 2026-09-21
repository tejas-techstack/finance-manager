"""Ingestion pipeline: data/inbox/*.{pdf,csv} -> data/csv + SQLite.

Runs one file at a time (kind to limited RAM), routes each file to a bank by
its filename prefix, extracts + normalises rows, clusters merchants once across
the whole batch, then writes CSVs and loads the DB with dedupe.

Usually launched by run.py, but also runnable on its own:
    python backend/ingest.py
"""

import glob
import os
import sys

# make the sibling modules importable whether run as a script or imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import banks
import extract
import normalize
import store

INBOX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "inbox")


def _inbox_files(inbox: str) -> list[str]:
    files = glob.glob(os.path.join(inbox, "*"))
    return sorted(f for f in files if f.lower().endswith((".pdf", ".csv")))


def banks_needing_password(inbox: str) -> list[str]:
    """Distinct bank names among the PDF files in the inbox (CSV needs none)."""
    names: list[str] = []
    for path in _inbox_files(inbox):
        if not path.lower().endswith(".pdf"):
            continue
        cfg = banks.route(os.path.basename(path))
        if cfg and cfg.name not in names:
            names.append(cfg.name)
    return names


def run_ingest(inbox: str, passwords: dict[str, str | None] | None = None,
               only: set[str] | None = None) -> None:
    """Ingest inbox files.

    `passwords` maps a bank name (e.g. "SBI") to that bank's PDF password.
    `only` optionally restricts processing to a set of bank names; files from
    other banks are left in the inbox and skipped.
    """
    passwords = passwords or {}
    files = _inbox_files(inbox)
    if not files:
        print("[ingest] inbox is empty — nothing to import.")
        return

    conn = store.connect()
    parsed: list[tuple[str, list[dict]]] = []  # (path, rows)
    all_rows: list[dict] = []

    for i, path in enumerate(files, 1):
        fname = os.path.basename(path)
        cfg = banks.route(fname)
        if cfg is None:
            print(f"[{i}/{len(files)}] {fname} — no bank matched the filename prefix, SKIPPED")
            continue
        if only is not None and cfg.name not in only:
            print(f"[{i}/{len(files)}] {fname} → bank={cfg.name}  not selected, skipped")
            continue
        try:
            if path.lower().endswith(".pdf"):
                raw = extract.extract_tables(path, password=passwords.get(cfg.name))
                # persist the untouched scan FIRST, before any parsing
                store.write_raw_csv(raw, path)
            else:
                raw = extract.extract_csv(path)
            rows = normalize.to_canonical(raw, cfg)
        except Exception as e:  # a bad file shouldn't kill the whole batch
            print(f"[{i}/{len(files)}] {fname} — ERROR: {e}")
            continue
        print(f"[{i}/{len(files)}] {fname} → bank={cfg.name}  {len(rows)} rows")
        parsed.append((path, rows))
        all_rows.extend(rows)

    # derive each merchant name from its description, then group variants of the
    # same merchant (ZOMAT O / ZOMATO / ZOMATO L) onto one label
    if all_rows:
        import merchants
        raw_names = [merchants.extract_merchant(r["description"]) for r in all_rows]
        label = merchants.canonicalize(raw_names)
        for r, name in zip(all_rows, raw_names):
            r["merchant"] = label.get(name, name)

    inserted = 0
    for path, rows in parsed:
        store.write_csv(rows, path)
        inserted += store.store(conn, rows, path)
    print(f"[store] {inserted} new, {len(all_rows) - inserted} duplicates skipped "
          f"→ {os.path.relpath(store.DB_PATH)}")
    conn.close()


if __name__ == "__main__":
    import getpass

    from offline_guard import arm, assert_offline

    assert_offline()
    print("[guard] OFFLINE ✓  arming kill-switch")
    arm()
    pwds = {name: (getpass.getpass(f"{name} PDF password (blank if none): ") or None)
            for name in banks_needing_password(INBOX)}
    run_ingest(INBOX, pwds)
