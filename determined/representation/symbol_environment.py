from dataclasses import dataclass, field


@dataclass(frozen=True)
class SymbolEnvironment:
    """
    Canonical semantic environment passed through analysis stages.

    PURPOSE:
    - centralize semantic truth inputs
    - eliminate loose dict propagation
    - provide deterministic stage context

    CONTAINS:
    - alias resolution truth
    - runtime binding truth
    - project symbol truth

    IMMUTABLE:
    - stages may read
    - stages may not mutate
    """

    alias_map: dict[str, str] = field(default_factory=dict)

    runtime_bindings: dict[str, str] = field(default_factory=dict)

    project_symbols: set[str] = field(default_factory=set)

    def resolve_alias(self, symbol: str) -> str | None:
        return self.alias_map.get(symbol)

    def resolve_runtime(self, symbol: str) -> str | None:
        return self.runtime_bindings.get(symbol)

    def is_project_symbol(self, fqdn: str) -> bool:
        return fqdn in self.project_symbols
