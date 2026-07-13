"""Raw table rows -> canonical transactions, driven by a BankConfig.

Canonical transaction:
    {account, date (ISO), description, amount (signed: - = money out), balance}

The pipeline is deliberately forgiving: it locates the header row by looking
for a date-ish and a description-ish column, then maps the rest by keyword.
Rows that don't parse are skipped rather than crashing the run.
"""

import re
from datetime import datetime

from banks.base import BankConfig


def _match_col(headers: list[str], keywords: list[str]) -> int | None:
    """Index of the first header containing any keyword (case-insensitive)."""
    for kw in keywords:
        for i, h in enumerate(headers):
            if kw in h.lower():
                return i
    return None


def _looks_like_header(row: list[str], config: BankConfig) -> bool:
    joined = " ".join(row).lower()
    has_date = any(kw in joined for kw in config.date_headers)
    has_desc = any(kw in joined for kw in config.description_headers)
    return has_date and has_desc


def _parse_amount(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")")  # (1,234.00) style
    s = s.strip("()")
    s = s.replace(",", "").replace("₹", "").replace("INR", "")
    s = re.sub(r"(?i)\b(dr|cr)\b", "", s).strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    val = float(m.group())
    return -val if negative else val


def _try_date(s: str, formats: list[str]) -> str | None:
    """ISO date if `s` matches one of the formats, else None."""
    s = (s or "").strip()
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


# A real statement wraps the transaction table in other tables (account details,
# a totals/summary block, linked accounts, digital products...). These phrases
# mark the end of the transactions — once we see one, we stop, so those other
# tables can never leak in as bogus rows.
_END_MARKERS = (
    "summary", "total debit", "total credit", "opening balance", "closing balance",
    "linked casa", "linked deposit", "linked loan", "linked locker",
    "other digital", "scheme type",
)


def to_canonical(rows: list[list[str]], config: BankConfig) -> list[dict]:
    # Column indices are re-derived from EVERY header row we meet, not just the
    # first. Statements repeat the header on each page, and pdfplumber can shift
    # column positions from one page to the next; re-mapping per header keeps
    # the debit/credit/balance columns aligned instead of drifting.
    di = ni = dbi = cri = bi = None
    mapped = False

    out: list[dict] = []
    for row in rows:
        if not any(cell.strip() for cell in row):
            continue

        if _looks_like_header(row, config):
            di = _match_col(row, config.date_headers)
            ni = _match_col(row, config.description_headers)
            dbi = _match_col(row, config.debit_headers)
            cri = _match_col(row, config.credit_headers)
            bi = _match_col(row, config.balance_headers)
            mapped = True
            continue

        if not mapped:
            continue  # skip any preamble before the first header

        joined = " ".join(row).lower()
        if any(marker in joined for marker in _END_MARKERS):
            break  # reached the summary / linked-accounts section — transactions done

        def cell(idx: int | None) -> str:
            # collapse in-cell line wraps (pdfplumber keeps them as "\n")
            if idx is None or idx >= len(row):
                return ""
            return re.sub(r"\s+", " ", row[idx].replace("\n", " ")).strip()

        iso = _try_date(cell(di), config.date_formats)
        desc = cell(ni)
        debit_raw, credit_raw = cell(dbi), cell(cri)
        has_amount = bool(debit_raw) or bool(credit_raw)
        balance_raw = cell(bi)

        # A genuine transaction must have a parseable DATE. Without one, the row
        # is either the wrapped overflow of the previous transaction's
        # description (fold it back in) or a stray line from another table
        # (drop it) — never recorded as its own transaction.
        if iso is None:
            is_continuation = desc and not has_amount and not balance_raw
            if is_continuation and out:
                out[-1]["description"] = f"{out[-1]['description']} {desc}".strip()
            continue

        debit = _parse_amount(debit_raw) or 0.0
        credit = _parse_amount(credit_raw) or 0.0
        out.append({
            "account": config.name,
            "date": iso,
            "description": desc,
            "amount": round(credit - debit, 2),  # money out is negative
            "balance": _parse_amount(balance_raw),
        })
    return out
