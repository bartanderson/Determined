# tools/analysis/identity/symbol_identity.py

from dataclasses import dataclass
from typing import Optional, Literal, List

@dataclass(frozen=True)
class SymbolIdentity:
    """
    Canonical symbol identity contract used throughout analysis.
    """

    surface: str
    normalized: str
    fqdn: Optional[str]
    module: Optional[str]

    kind: Literal[
        "local",
        "imported",
        "attribute",
        "runtime",
        "builtin",
        "unknown",
    ]

    provenance: List[str]
    confidence: float
    
def normalize_symbol(name: str) -> str:
    if not name:
        return name
    return name.strip()

def resolve_symbol_identity(name: str, alias_map: dict[str, str]) -> str:
    # keep minimal behavior for now
    return alias_map.get(name, name)

def project_key(name: str):
    return "default"