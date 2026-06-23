from collections import Counter
from dataclasses import dataclass, field

@dataclass
class SymbolAudit:
    total: int = 0
    project: int = 0
    external: int = 0
    builtin: int = 0
    stdlib: int = 0
    runtime: int = 0

    symbol_counts: Counter = field(default_factory=Counter)
    unresolved: list[str] = field(default_factory=list)
    noisy_chains: list[str] = field(default_factory=list)