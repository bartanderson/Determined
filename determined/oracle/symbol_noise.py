# tools/analysis/oracle/symbol_noise.py
#
# Single canonical home for "is this symbol noise" logic.
#
# Why this file exists:
#   Noise filtering used to live in two places that could silently drift
#   apart:
#     - oracle/db_oracle.py::_discover_token() — accessor-chain filtering,
#       inline, seed-discovery time
#     - api/oracle_router.py::_is_valid_symbol() — a hand-maintained
#       word list of "obvious" builtins, expansion time
#   The word list was never guaranteed to match the DB's own bucket
#   classification (symbol_references.bucket == "builtin"), so a builtin
#   like "isinstance" or "enumerate" could leak through expansion even
#   though discovery correctly excluded it. There was exactly one
#   authoritative answer to "is this a builtin" (the ingestion-time
#   bucket classification, exposed via DBOracle.builtin_symbols()) and a
#   second, weaker, hand-maintained answer competing with it.
#
# Rule going forward: builtin-ness is ALWAYS decided by DB-backed bucket
# classification (passed in as a set), never by a hardcoded word list.
# Accessor-chain noise (self/cursor/cls/ctx dotted paths, single-letter
# loop-variable segments) is decided by is_accessor_chain_noise() below,
# used by both seed discovery and graph expansion.

from __future__ import annotations

import builtins as _builtins
from typing import Iterable

_PYTHON_BUILTINS = frozenset(dir(_builtins))


def is_accessor_chain_noise(symbol: str) -> bool:
    """
    True if `symbol` looks like a runtime accessor path recorded by the
    symbol extractor rather than a meaningful query target.

    e.g. "surface.self.oracle", "cursor.self.oracle.conn",
         "split.i.surface" (single-letter loop-variable chain)
    """
    if not symbol:
        return False

    segments = symbol.lower().split(".")

    if any(seg in ("self", "cursor", "cls", "ctx") for seg in segments):
        return True

    if len(segments) >= 3 and any(len(seg) <= 2 for seg in segments[1:-1]):
        return True

    return False


def is_noise_symbol(symbol: str, builtin_symbols: Iterable[str] = ()) -> bool:
    """
    Single entry point for "should this symbol be excluded as noise".

    builtin_symbols: the DB-authoritative set from DBOracle.builtin_symbols()
    (or any iterable of known-builtin names). Pass () only when no DB
    context is available (e.g. isolated unit tests) — expansion will then
    fall back to accessor-chain filtering only.
    """
    if not symbol:
        return True

    if symbol.startswith("<"):
        return True

    if symbol in builtin_symbols:
        return True

    # Python's own builtins module is authoritative for bare builtin names
    # (e.g. 'all', 'len', 'range'). Covers names that appear in mixed buckets
    # in the DB and are therefore excluded from builtin_symbols().
    if symbol in _PYTHON_BUILTINS:
        return True

    if is_accessor_chain_noise(symbol):
        return True

    return False
