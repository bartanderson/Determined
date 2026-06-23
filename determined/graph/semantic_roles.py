# tools/analysis/graph/semantic_roles.py

from __future__ import annotations

# MODULE: classifier
# INCLUDED_IN: snapshot (dependency)
#
# CONTRACT NOTE:
# - provides semantic tagging / role inference
# - used by classification pipeline
# - does NOT own classification decisions

SEMANTIC_ROLES = {
    "print": "runtime_noise",
    "str": "builtin_primitive",
    "sum": "builtin_primitive",
    "len": "builtin_primitive",
    "exec": "runtime_execution",
}


def classify_semantic_role(symbol: str) -> str:
    """
    Lightweight semantic classification layer.

    Deterministic only.
    No inference.
    No AI interpretation.
    """

    if not symbol:
        return "unknown"

    lowered = symbol.lower()

    if lowered in SEMANTIC_ROLES:
        return SEMANTIC_ROLES[lowered]

    if lowered.startswith("test_"):
        return "test_code"

    if symbol.startswith("<"):
        return "runtime_artifact"

    if "." in symbol:
        return "qualified_reference"

    if symbol[0].isupper():
        return "type_or_class"

    return "general_symbol"