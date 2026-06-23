# tools/analysis/oracle/edge_semantics.py

from dataclasses import dataclass
from typing import Any


# =========================================================
# SEMANTIC EDGE VIEW (ORACLE LAYER ONLY)
# =========================================================

@dataclass
class SemanticEdge:
    caller: str
    callee: str

    # semantic roles (IMPORTANT ADDITION)
    outgoing: str = "dependency_source"
    incoming: str = "dependency_target"


def interpret_edge(edge: Any) -> SemanticEdge:
    """
    Converts raw DB graph edge into semantic oracle form.
    No logic change — only labeling.
    """

    return SemanticEdge(
        caller=edge.caller,
        callee=edge.callee,
    )