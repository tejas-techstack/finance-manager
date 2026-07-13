"""PDF (and CSV passthrough) -> raw table rows.

We target *digital* bank-statement PDFs (selectable text), so pdfplumber's
table extraction is enough — no OCR, no model, low RAM. Encrypted PDFs are
opened with the password supplied at runtime.

Output is a flat list of rows, each row a list of cell strings, in reading
order across all pages. normalize.py turns that into canonical transactions.
"""

import csv as _csv


def extract_tables(path: str, password: str | None = None) -> list[list[str]]:
    """Extract every table row from a PDF as list-of-cells."""
    import pdfplumber  # imported lazily so the viewer never pulls it in

    rows: list[list[str]] = []
    # pdfplumber accepts password="" for unencrypted files.
    with pdfplumber.open(path, password=password or "") as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                for raw in table:
                    rows.append([("" if c is None else str(c)).strip() for c in raw])
    return rows


def extract_csv(path: str) -> list[list[str]]:
    """Read a CSV as list-of-cells (lets you test the pipeline without a PDF)."""
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return [row for row in _csv.reader(f)]
