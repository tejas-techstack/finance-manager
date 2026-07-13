"""Bank registry + filename routing.

To add another bank: create banks/<name>.py exposing a CONFIG, then add it to
CONFIGS below. Nothing else in the pipeline needs to change.
"""

from . import sbi, ubi
from .base import BankConfig

CONFIGS = [sbi.CONFIG, ubi.CONFIG]


def route(filename: str) -> BankConfig | None:
    """Pick a bank config from a filename prefix, e.g. sbi_jan2026.pdf -> SBI."""
    name = filename.lower()
    for cfg in CONFIGS:
        for prefix in cfg.prefixes:
            if name.startswith(prefix):
                return cfg
    return None


def resolve(token: str) -> BankConfig | None:
    """Look up a bank by its name or a prefix, e.g. "sbi" or "SBI" -> SBI config.
    Used to turn user selections (--banks / the picker) into concrete banks."""
    t = token.strip().lower()
    for cfg in CONFIGS:
        if t == cfg.name.lower() or t in [p.lower() for p in cfg.prefixes]:
            return cfg
    return None


def names() -> list[str]:
    """All registered bank names, e.g. ["SBI", "UBI"]."""
    return [cfg.name for cfg in CONFIGS]
