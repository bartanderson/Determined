# tools/analysis/identity/edge_identity.py

from typing import Any
from determined.identity.symbol_identity import (
    normalize_symbol,
    resolve_symbol_identity,
)

def edge_identity(source: Any, target: Any) -> tuple[str, str]:
    def resolve(x: Any) -> str:
        if hasattr(x, "normalized") or hasattr(x, "fqdn"):
            return resolve_symbol_identity(x)
        if isinstance(x, str):
            return normalize_symbol(x)
        return str(x)

    return resolve(source), resolve(target)