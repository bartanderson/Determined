# determined/assessor/epistemic_policy.py
#
# Pure risk measurement layer. No decisions, no routing influence.
# Reads the real Truth Layer view shapes and produces a risk decomposition.
#
# All thresholds are named constants at the top -- tune them as you observe
# the tool running on real corpora. Do not bury magic numbers in logic.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# ------------------------------------------------------------------
# TUNABLE CONSTANTS  (adjust after observing real corpus outputs)
# ------------------------------------------------------------------

# Structure
CYCLE_RISK        = 0.35   # added when module-level cycles are detected
HOTSPOT_THRESHOLD = 50     # node degree count that signals high complexity
HOTSPOT_RISK      = 0.10   # added when the top hotspot exceeds threshold

# Integrity
ERROR_RISK_PER    = 0.08   # risk added per integrity error
ERROR_RISK_CAP    = 0.40   # maximum integrity contribution

# Stability
DRIFT_RISK_SCALE  = 0.40   # stability risk = unstable_ratio * this
DRIFT_THRESHOLD   = 0.30   # ratio above which STABILITY surface is required

# Summary -- density-based so absolute project size doesn't inflate risk.
# Any real project exceeds a raw edge count of 10; use avg edges per file.
EDGE_DENSITY_THRESHOLD = 20   # avg edges/file above which scale risk applies
SCALE_RISK             = 0.10

# Completeness
COMPLETENESS_RISK = 0.05   # added when role view is empty

# Query-level grounding signals
SEED_ZERO_RISK           = 0.25   # no seeds = router blind = high uncertainty
SEED_SPARSE_RISK         = 0.10   # 1-3 seeds = weak grounding
SEED_SPARSE_MAX          = 3      # threshold between sparse and adequate
EXPANSION_SPARSE_RISK    = 0.10   # expanded/seed_count < EXPANSION_RATIO_MIN
EXPANSION_RATIO_MIN      = 2.0    # minimum expansion ratio for adequate coverage
INTENT_INTERPRETIVE_RISK = 0.10   # debug_query/general_query = needs synthesis
INTERPRETIVE_INTENTS     = {"debug_query", "general_query"}

# Decision gate (used by Assessor.ask() -- live here so tests can import them)
LLM_SEVERITY_THRESHOLD = 0.15  # minimum severity to consider LLM at all
HARD_BLOCK_INTEGRITY   = 0.35  # integrity risk at or above this blocks LLM
HARD_BLOCK_STRUCTURE   = 0.30  # structure risk at or above this blocks LLM


# ------------------------------------------------------------------
# OUTPUT SHAPE
# ------------------------------------------------------------------

@dataclass
class EpistemicDirective:
    """
    Pure measurement output. No thresholds. No decisions. No routing influence.
    Severity is the sum of the risk vector, clamped to [0, 1].
    """
    severity: float
    risk_vector: Dict[str, float] = field(default_factory=dict)
    required_surfaces: List[str] = field(default_factory=list)
    reason: str = ""


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def _has_cycles(structure_view) -> bool:
    """DFS cycle detection on the adjacency dict from StructureView."""
    adjacency = structure_view.adjacency  # dict[str, set[str]]
    visited: set = set()
    stack: set = set()

    def dfs(node: str) -> bool:
        if node in stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        stack.add(node)
        for neighbour in adjacency.get(node, set()):
            if dfs(neighbour):
                return True
        stack.discard(node)
        return False

    return any(dfs(n) for n in adjacency if n not in visited)


def _top_hotspot_degree(structure_view) -> int:
    """Degree of the single most-connected node (0 if no hotspots)."""
    if not structure_view.hotspots:
        return 0
    return structure_view.hotspots[0][1]


def _unstable_ratio(stability_view) -> float:
    """Fraction of contracts that are unstable."""
    total = len(stability_view.stable_contracts) + len(stability_view.unstable_contracts)
    if total == 0:
        return 0.0
    return len(stability_view.unstable_contracts) / total


# ------------------------------------------------------------------
# POLICY
# ------------------------------------------------------------------

class EpistemicPolicy:
    """
    Deterministic view projection -> risk decomposition.
    Stateless. No decision authority.
    """

    def analyze(
        self,
        structure_view,
        integrity_view,
        stability_view,
        summary_view,
        role_view,
        query_context: dict = None,
    ) -> EpistemicDirective:

        cycles        = _has_cycles(structure_view)
        unstable_ratio = _unstable_ratio(stability_view)
        error_count   = len(integrity_view.errors)
        top_degree    = _top_hotspot_degree(structure_view)
        edge_count    = summary_view.edge_count
        role_empty    = not role_view.files

        file_count    = summary_view.file_count
        edge_density  = edge_count / max(file_count, 1)

        risk_vector = {
            "structure":    CYCLE_RISK if cycles else 0.0,
            "integrity":    min(error_count * ERROR_RISK_PER, ERROR_RISK_CAP),
            "stability":    unstable_ratio * DRIFT_RISK_SCALE,
            "scale":        SCALE_RISK if edge_density > EDGE_DENSITY_THRESHOLD else 0.0,
            "complexity":   HOTSPOT_RISK if top_degree > HOTSPOT_THRESHOLD else 0.0,
            "completeness": COMPLETENESS_RISK if role_empty else 0.0,
        }

        if query_context:
            seed_count     = query_context.get("seed_count", 0)
            expanded_count = query_context.get("expanded_count", 0)
            intent         = query_context.get("intent", "general_query")
            expansion_ratio = expanded_count / max(seed_count, 1)

            risk_vector["query_grounding"] = (
                SEED_ZERO_RISK   if seed_count == 0
                else SEED_SPARSE_RISK if seed_count <= SEED_SPARSE_MAX
                else 0.0
            )
            risk_vector["query_coverage"] = (
                EXPANSION_SPARSE_RISK if expansion_ratio < EXPANSION_RATIO_MIN else 0.0
            )
            risk_vector["query_intent"] = (
                INTENT_INTERPRETIVE_RISK if intent in INTERPRETIVE_INTENTS else 0.0
            )

        severity = max(0.0, min(1.0, sum(risk_vector.values())))

        required_surfaces = ["INTEGRITY"]
        if cycles:
            required_surfaces.append("STRUCTURE")
        if unstable_ratio > DRIFT_THRESHOLD:
            required_surfaces.append("STABILITY")
        if top_degree > HOTSPOT_THRESHOLD:
            required_surfaces.append("SUMMARY")

        return EpistemicDirective(
            severity=severity,
            risk_vector=risk_vector,
            required_surfaces=required_surfaces,
            reason="projection risk decomposition complete",
        )
