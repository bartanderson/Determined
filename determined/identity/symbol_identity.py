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
    """Return canonical bare name: strip module/attribute prefix, keep last segment.

    Handles both dot-separated (Python/Go: 'pkg.Fn') and double-colon-separated
    (Rust: 'Module::Fn') paths. Only the final segment is kept.
    """
    if not name:
        return name
    name = name.strip()
    # Strip Rust-style :: paths first, then dot paths
    if '::' in name:
        name = name.rsplit('::', 1)[-1]
    if '.' in name:
        name = name.rsplit('.', 1)[-1]
    return name


def all_name_forms(name: str) -> list[tuple[str, str]]:
    """Return (name, name_type) pairs for all known forms of a symbol name."""
    if not name:
        return []
    name = name.strip()
    forms = [('surface', name)]
    if '.' in name:
        bare = name.rsplit('.', 1)[-1]
        forms.append(('bare', bare))
    return forms


def resolve_symbol_identity(name: str, alias_map: dict[str, str]) -> str:
    return alias_map.get(name, name)


def project_key(name: str):
    return "default"