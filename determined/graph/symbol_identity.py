# tools/analysis/graph/symbol_identity.py

from __future__ import annotations

def normalize_symbol(name: str) -> str:
    """
    Canonical symbol identity normalization.

    This is the single contract used across ingestion, classification,
    routing, and persistence.
    """

    if not name:
        return name

    # 1. strip whitespace
    name = name.strip()

    # 2. collapse accidental surrounding noise
    name = name.strip("()`[]{}")

    # 3. DO NOT over-normalize yet (important)
    return name
    
def project_key(name: str) -> str:
    if not name:
        return name
    return name.split(".")[-1]


def module_key(name: str) -> str:
    if not name:
        return ""
    return ".".join(name.split(".")[:-1]) if "." in name else ""