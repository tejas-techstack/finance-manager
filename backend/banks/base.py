"""Per-bank configuration.

Each bank statement has its own column names, date format and debit/credit
convention. A BankConfig captures just enough to (a) recognise which file
belongs to which bank (by filename prefix) and (b) map that bank's columns
onto our single canonical schema.

Header matching is by case-insensitive substring: e.g. the keyword
"narration" matches a column titled "Narration" or "Transaction Narration".
List the more specific keywords first.
"""

from dataclasses import dataclass, field


@dataclass
class BankConfig:
    name: str                                    # canonical account label, e.g. "HDFC"
    prefixes: list[str]                          # filename prefixes (lowercase), e.g. ["hdfc"]
    date_headers: list[str] = field(default_factory=list)
    description_headers: list[str] = field(default_factory=list)
    debit_headers: list[str] = field(default_factory=list)      # money OUT columns
    credit_headers: list[str] = field(default_factory=list)     # money IN columns
    balance_headers: list[str] = field(default_factory=list)
    date_formats: list[str] = field(default_factory=list)       # strptime formats to try
