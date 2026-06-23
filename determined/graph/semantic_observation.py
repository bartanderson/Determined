# tools/analysis/graph/semantic_observation.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class SemanticCandidate:
    fqdn: str
    confidence: float
    source: str
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SemanticObservation:
    surface: str

    normalized: Optional[str] = None

    root: Optional[str] = None
    leaf: Optional[str] = None

    has_dots: bool = False
    depth: int = 0

    runtime_root_hit: bool = False
    project_leaf_hit: bool = False

    runtime_bound: bool = False
    builtin_match: bool = False
    stdlib_match: bool = False
    project_match: bool = False

    routing_result: Optional[str] = None

    provenance_stage: str = "cp25"

    candidates: list[SemanticCandidate] = field(default_factory=list)

    metadata: dict = field(default_factory=dict)