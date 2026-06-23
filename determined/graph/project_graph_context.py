# tools\analysis\graph\project_graph_context.py

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProjectGraphContext:

    project_prefixes: list[str] = field(default_factory=list)

    project_symbols: set[str] = field(default_factory=set)

    runtime_bindings: dict[str, str] = field(default_factory=dict)

    def resolve_runtime(self, name: str) -> str | None:
        return self.runtime_bindings.get(name)


    def resolve_alias(self, name: str) -> str | None:
        # if alias_map exists on ctx, support it safely
        alias_map = getattr(self, "alias_map", None) or {}
        return alias_map.get(name)