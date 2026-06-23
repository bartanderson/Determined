# tools/analysis/graph/route_trace.py   (new file)

from dataclasses import dataclass, field
from typing import Optional, Any
from determined.graph.semantic_observation import (
    SemanticObservation,
    SemanticCandidate,
)

@dataclass
class RouteTrace:
    input_raw: str

    cp0_raw: str = ""
    cp1_canonical: str = ""
    cp1_normalized: str = ""

    cp2_classification_input: str = ""

    cp3_project_match: bool = False
    cp3_runtime_match: bool = False
    cp3_builtin_match: bool = False
    cp3_stdlib_match: bool = False

    cp4_result: str = ""

    project_symbols_sample: list[str] = field(default_factory=list)
    normalized_project_symbols_sample: list[str] = field(default_factory=list)

    alias_map_snapshot: dict = field(default_factory=dict)
    runtime_bindings_snapshot: dict = field(default_factory=dict)


@dataclass
class SemanticRouteTrace(RouteTrace):
    semantic_observation: SemanticObservation | None = None
    resolved_candidates: list[SemanticCandidate] = field(default_factory=list)
    comparison_attempts: list[dict] = field(default_factory=list)

class TraceCollector:
    def __init__(self, name: str):
        self.trace = SemanticRouteTrace(input_raw=name)

    def record(self, key: str, value):
        setattr(self.trace, key, value)

    def snapshot(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self.trace, k, v)

    def snapshot_semantic_identity(self, **kwargs):

        if not hasattr(self.trace, "semantic_observation"):
            return

        observation = self.trace.semantic_observation

        if observation is None:
            return

        for k, v in kwargs.items():
            observation.metadata[k] = v

    def record_semantic(
        self,
        surface: str,
        fqdn: str | None = None,
        confidence: float | None = None,
        evidence: list[str] | None = None,
        module: str | None = None,
        binding_type: str | None = None,
    ):
        candidate = SemanticCandidate(
            surface=surface,
            fqdn=fqdn,
            module=module,
            binding_type=binding_type,
            confidence=confidence or 1.0,
            evidence=evidence or [],
        )

        self.trace.resolved_candidates.append(candidate)

    def get(self):
        return self.trace