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


def _key(name: str) -> str:
    """Space/punctuation-stripped key so 'ZOMAT O' and 'ZOMATO' collapse."""
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def canonicalize(names: list[str]) -> dict[str, str]:
    """Group merchant-name variants onto one label.

    Banks truncate counterparty names to a fixed width and sometimes insert
    stray spaces, so the same merchant shows up as e.g. 'ZOMAT O', 'ZOMATO' and
    'ZOMATO L'. We (1) strip spaces/punctuation so spacing variants become
    identical, then (2) union any two whose keys are a prefix of each other
    (that's what truncation produces). The most common original wins as the
    display label. Fully deterministic — no model, works offline.
    """
    from collections import Counter

    uniq = list(dict.fromkeys(names))
    key = {n: _key(n) for n in uniq}

    parent = {n: n for n in uniq}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    MIN = 4  # don't group on ultra-short keys (avoids merging unrelated names)
    for i, a in enumerate(uniq):
        ka = key[a]
        if len(ka) < MIN:
            continue
        for b in uniq[i + 1:]:
            kb = key[b]
            if len(kb) < MIN:
                continue
            if ka == kb or ka.startswith(kb) or kb.startswith(ka):
                union(a, b)

    groups: dict[str, list[str]] = {}
    for n in uniq:
        groups.setdefault(find(n), []).append(n)

    freq = Counter(names)
    mapping: dict[str, str] = {}
    for members in groups.values():
        # label = most frequent variant, ties broken by the longest (most info)
        label = max(members, key=lambda m: (freq[m], len(m)))
        for m in members:
            mapping[m] = label
    return mapping
