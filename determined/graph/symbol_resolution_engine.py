# tools/analysis/graph/symbol_resolution_engine.py

from __future__ import annotations

import builtins
import sys

from typing import Literal

from determined.identity.symbol_identity import normalize_symbol


RouteType = Literal[
    "project",
    "runtime",
    "builtin",
    "stdlib",
    "external",
    "unknown",
]


BUILTINS = set(dir(builtins))
STDLIB_PREFIXES = set(sys.stdlib_module_names)


def terminal_symbol(name: str) -> str:
    return name.split(".")[-1]


def canonical_symbol(
    name: str,
    project_prefixes: list[str] | None = None,
) -> str:
    """
    Reserved canonicalization stage.

    IMPORTANT:
    This function must remain deterministic.
    """
    if not name:
        return name

    return name


# ============================================================
# BUILTIN
# ============================================================

def is_builtin_symbol(name: str) -> bool:
    if not name:
        return False

    root = name.split(".")[0]

    return root in BUILTINS


# ============================================================
# STDLIB
# ============================================================

def is_stdlib_symbol(name: str) -> bool:
    if not name:
        return False

    root = name.split(".")[0]

    return root in STDLIB_PREFIXES


# ============================================================
# RUNTIME
# ============================================================

def resolve_runtime_binding(name: str, runtime_bindings: dict[str, str] | None = None) -> str | None:
    if not name:
        return None

    runtime_bindings = runtime_bindings or {}

    # 1. direct key match (request = request.args case)
    if name in runtime_bindings:
        return runtime_bindings[name]

    # 2. reverse lookup (request.args -> request)
    for k, v in runtime_bindings.items():
        if v == name:
            return v

    # 3. prefix walk fallback
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in runtime_bindings:
            return runtime_bindings[prefix]

    return None


def is_runtime_symbol(
    name: str,
    runtime_bindings: dict[str, str] | None = None,
) -> bool:
    return resolve_runtime_binding(name, runtime_bindings) is not None


# ============================================================
# PROJECT
# ============================================================

def is_project_symbol(
    name: str,
    project_symbols: set[str] | None,
) -> bool:

    if not project_symbols:
        return False

    normalized_name = normalize_symbol(name)

    # ----------------------------------------
    # exact fqdn
    # ----------------------------------------
    if normalized_name in project_symbols:
        return True

    # ----------------------------------------
    # semantic leaf match
    # ----------------------------------------
    leaf = terminal_symbol(normalized_name)

    for symbol in project_symbols:
        if terminal_symbol(normalize_symbol(symbol)) == leaf:
            return True

    # ----------------------------------------
    # normalized fallback
    # ----------------------------------------
    normalized_project_symbols = {
        normalize_symbol(s)
        for s in project_symbols
    }

    if normalized_name in normalized_project_symbols:
        return True

    return False


# ============================================================
# PRIMARY AUTHORITY
# ============================================================

def resolve_symbol_type(
    name: str,
    runtime_bindings: dict[str, str] | None = None,
    project_symbols: set[str] | None = None,
    project_prefixes: list[str] | None = None,
) -> RouteType:
    assert runtime_bindings is not None
    
    if not name:
        return "unknown"

    # ----------------------------------------
    # canonicalization
    # ----------------------------------------
    name = canonical_symbol(
        name,
        project_prefixes=project_prefixes,
    )

    # ----------------------------------------
    # builtin
    # ----------------------------------------
    if is_builtin_symbol(name):
        return "builtin"

    # ----------------------------------------
    # runtime
    # ----------------------------------------
    if is_runtime_symbol(name, runtime_bindings):
        return "runtime"

    # ----------------------------------------
    # stdlib
    # ----------------------------------------
    if is_stdlib_symbol(name):
        return "stdlib"

    # ----------------------------------------
    # project
    # ----------------------------------------
    if is_project_symbol(name, project_symbols):
        return "project"

    # ----------------------------------------
    # external
    # ----------------------------------------
    normalized_name = normalize_symbol(name)

    if "." in normalized_name:
        return "external"

    # ----------------------------------------
    # fallback
    # ----------------------------------------
    return "unknown"