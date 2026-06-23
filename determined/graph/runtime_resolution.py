# tools/analysis/graph/runtime_resolution.py

from typing import Optional


def resolve_runtime_symbol(name: str, runtime_bindings: dict[str, str] | None):
    if not name or not runtime_bindings:
        return None

    parts = name.split(".")
    root = parts[0]

    # 1. direct root binding (THIS is the real contract)
    if root in runtime_bindings:
        return runtime_bindings[root]

    # 2. full match fallback (rare)
    if name in runtime_bindings:
        return runtime_bindings[name]

    return None