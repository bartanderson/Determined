"""
Edge types for the Determined analysis agent.

EdgeRef is the atomic unit — a typed, weighted, annotatable connection
between two named things in the corpus. Everything else (symbols, files,
subsystems) is composed from edges.

Edge types:
  call        — function A calls function B (from graph_edges)
  import      — file A imports from module/file B (from file_edges/imports)
  inherit     — class A inherits from class B (not yet extracted)
  co_change   — files A and B change together in git (not yet computed)
  manual      — user-asserted connection with a note
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EdgeRef:
    """A typed, annotatable connection between two named things."""

    src: str                        # symbol name or file path
    src_type: str                   # "symbol" | "file" | "module"
    dst: str                        # symbol name or file path
    dst_type: str                   # "symbol" | "file" | "module"
    edge_type: str                  # "call" | "import" | "inherit" | "co_change" | "manual"
    weight: float = 1.0             # call count, import count, co-change score
    line: Optional[int] = None      # line number where edge appears
    note: Optional[str] = None      # annotation (especially for manual edges)
    provenance: str = "ingestion"   # "ingestion" | "computed" | "manual" | "git"
    is_internal: bool = True        # False if dst is stdlib/external

    def key(self) -> str:
        """Stable dedup key for bags."""
        return f"{self.edge_type}::{self.src}::{self.dst}"

    def to_dict(self) -> dict:
        return {
            "src": self.src, "src_type": self.src_type,
            "dst": self.dst, "dst_type": self.dst_type,
            "edge_type": self.edge_type, "weight": self.weight,
            "line": self.line, "note": self.note,
            "provenance": self.provenance, "is_internal": self.is_internal,
        }

    def label(self) -> str:
        arrow = {"call": "calls", "import": "imports", "inherit": "inherits",
                 "co_change": "co-changes-with", "manual": "→"}.get(self.edge_type, "→")
        return f"{self.src} {arrow} {self.dst}"
