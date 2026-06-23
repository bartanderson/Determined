# tools/analysis/resolution/symbol_origin_resolver.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Protocol
import sys
import importlib.util


OriginType = Literal["project", "external", "builtin", "unknown"]


@dataclass(frozen=True)
class SymbolOrigin:
    type: OriginType
    module: Optional[str]
    confidence: float
    source: Literal["lite", "pyright"]


class SymbolOriginResolver(Protocol):
    def resolve(
        self,
        symbol: str,
        file_path: str,
        context: dict
    ) -> SymbolOrigin:
        ...


class PyrightLiteResolver:
    """
    Deterministic heuristic resolver (current production default).
    """

    def resolve(self, symbol: str, file_path: str, context: dict) -> SymbolOrigin:

        # --------------------------
        # BUILTIN DETECTION
        # --------------------------
        if symbol in sys.stdlib_module_names:
            return SymbolOrigin(
                type="builtin",
                module=None,
                confidence=0.95,
                source="lite",
            )

        # --------------------------
        # EXTERNAL PACKAGE CHECK
        # --------------------------
        try:
            spec = importlib.util.find_spec(symbol)
            if spec and spec.origin:
                if "site-packages" in spec.origin:
                    return SymbolOrigin(
                        type="external",
                        module=spec.origin,
                        confidence=0.8,
                        source="lite",
                    )
        except Exception:
            pass

        # --------------------------
        # PROJECT HEURISTIC
        # --------------------------
        repo_root = context.get("repo_root")
        if repo_root and repo_root in file_path:
            return SymbolOrigin(
                type="project",
                module=file_path,
                confidence=0.9,
                source="lite",
            )

        # --------------------------
        # FALLBACK
        # --------------------------
        return SymbolOrigin(
            type="unknown",
            module=None,
            confidence=0.3,
            source="lite",
        )