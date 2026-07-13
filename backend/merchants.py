"""Extract the counterparty name from a bank transaction description.

Indian UPI descriptions are *structured*, so we read the name out directly
instead of guessing with a fuzzy model (the old approach wrongly merged
different people — e.g. it relabelled "SUMITHRA M" as "SHRUTHI J").

Layouts seen so far::

    SBI : UPI/DR/427520652621/MAHESH B G/YESB/q588161991/UPI
    UBI : UPIAR/653686128112/DR/VISHAL_M/YESB/paytmqr65v0vb@

The parts are slash-separated: a channel (UPI/UPIAR), a type (DR/CR/DRC...),
a long numeric reference, then the NAME, then a bank code and handle. The
NAME is the first non-type token after the numeric reference. Reversals
(DRC/CRC) carry no name and are labelled "REVERSAL".
"""

import re

# transaction-type codes that sit around the name but are not the name
_TYPE_CODES = {"DR", "CR", "DRC", "CRC", "DRR", "REV", "DEBIT", "CREDIT"}
# payment channels (used only by the fallback path)
_CHANNELS = {"UPI", "UPIAR", "IMPS", "NEFT", "RTGS", "POS", "ATM", "ACH", "MMT", "INF"}


def _is_ref(tok: str) -> bool:
    """A long run of digits = the UPI transaction reference."""
    return tok.isdigit() and len(tok) >= 6


def _clean_name(name: str) -> str:
    name = name.replace("_", " ")
    name = re.sub(r"\s+", " ", name).strip(" .-")
    return name.upper()


def extract_merchant(description: str) -> str:
    """Return the payee name for one transaction description."""
    desc = (description or "").strip()
    if not desc:
        return "UNKNOWN"

    tokens = [t.strip() for t in desc.split("/")]

    ref_idx = next((i for i, t in enumerate(tokens) if _is_ref(t)), None)
    if ref_idx is not None:
        for tok in tokens[ref_idx + 1:]:
            if not tok:
                continue
            if tok.upper() in _TYPE_CODES:   # skip a DR/CR sitting after the ref (UBI)
                continue
            if tok.isdigit():                # numeric where a name should be -> none here
                break
            name = _clean_name(tok)
            if name:
                return name
        # no name after the reference -> reversal / refund
        if {t.upper() for t in tokens} & {"DRC", "CRC"}:
            return "REVERSAL"

    # fallback for non-UPI / unstructured descriptions: first meaningful token
    kept = [t for t in tokens
            if t and not t.isdigit() and t.upper() not in (_CHANNELS | _TYPE_CODES)]
    return _clean_name(kept[0]) if kept else "UNKNOWN"
