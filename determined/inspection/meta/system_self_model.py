# tools/analysis/inspection/meta/system_self_model.py
#
# SystemSelfModel — the assessor's account of its own blind spots.
#
# Purpose: distinguish what the system KNOWS deterministically (from the
# DB-derived graph and contracts) from what it ASSUMES or cannot currently
# answer. This is a Tier 2 component in the Truth Kernel sense — it does
# not invent facts, it only reports on the structural conditions that are
# already measurable, plus a small set of fixed, honestly-labeled
# limitations of the inspection layer itself.
#
# Every list field is either:
#   (a) populated from a real, checkable condition against oracle/graph/shape, or
#   (b) a fixed structural caveat about the inspection layer's own design.
# Nothing here is a placeholder that always fires or never fires.

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field


@dataclass
class SystemSelfModel:
    capabilities: list = field(default_factory=list)
    limitations: list = field(default_factory=list)
    structural_biases: list = field(default_factory=list)
    failure_modes: list = field(default_factory=list)
    inference_gaps: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def _router_module_present() -> bool:
    """
    Check whether the intent-budgeted oracle_router module is importable,
    without importing oracle_router at module-load time (avoids circular
    imports between oracle/, api/, and inspection/).
    """
    return importlib.util.find_spec("determined.api.oracle_router") is not None


class SystemSelfModelBuilder:
    def __init__(self, oracle):
        self.oracle = oracle

    def build(self) -> SystemSelfModel:
        graph = self.oracle.get_snapshot_graph()
        edges = graph.edges

        capabilities: list = []
        limitations: list = []
        biases: list = []
        failure_modes: list = []
        inference_gaps: list = []
        notes: list = []

        # -------------------------
        # Structural reality checks (graph)
        # -------------------------

        if len(edges) == 0:
            failure_modes.append("graph_empty_state")
        elif len(edges) < 10:
            limitations.append("low_observability_graph")

        # -------------------------
        # Routing structure signals
        #
        # The query path runs through determined.api.oracle_router,
        # which applies intent-conditioned traversal budgets (see
        # docs/DESIGN.md, "Symbol classification & routing architecture").
        # Per docs/TRACKER.md, budget enforcement and forward/reverse
        # weighting are still partially heuristic, and implementation-level
        # symbols can leak into expansion results. This is a known, named
        # open problem, not a guess.
        # -------------------------

        if _router_module_present():
            biases.append("router_is_primary_decision_layer")
            biases.append("router_expansion_budgets_not_fully_calibrated")
        else:
            failure_modes.append("router_module_unreachable")

        # -------------------------
        # DB-derived system shape (real signal, not a stub)
        # -------------------------

        shape = None
        try:
            from determined.inspection.system_shape import generate_system_shape
            shape = generate_system_shape(self.oracle.conn)
        except Exception as e:
            inference_gaps.append(f"system_shape_unavailable:{type(e).__name__}")

        if shape:
            tags = shape.get("system_shape_tags", [])

            if "external_dependency_heavy" in tags:
                limitations.append("external_dependency_dominance")

            if "high_coupling_core" in tags:
                failure_modes.append("high_coupling_core_risk")

            if "contract_weak_system" in tags:
                limitations.append("contract_coverage_weak")

            if "hotspot_concentrated" in tags:
                biases.append("analysis_concentrated_in_few_hotspots")

            if "cross_layer_coupling_detected" in tags:
                failure_modes.append("cross_layer_coupling_present")

        # -------------------------
        # Oracle capabilities (verified — these are real methods that
        # execute against DB-derived data, not aspirational claims)
        # -------------------------

        if hasattr(self.oracle, "get_snapshot_graph"):
            capabilities.append("symbol_graph_traversal")
        if _router_module_present():
            capabilities.append("query_expansion_via_router")
        if hasattr(self.oracle, "file_reference_map"):
            capabilities.append("contract_violation_detection")

        # -------------------------
        # Known, fixed inference-layer caveats
        #
        # These are structural properties of how the pipeline classifies
        # and routes symbols (see docs/DESIGN.md, "Symbol classification &
        # routing architecture", and docs/TRACKER.md's current open items
        # on symbol classification stability). They are always true of the
        # current architecture, not conditionally detected — that is why
        # they are listed unconditionally rather than gated on a runtime
        # check.
        # -------------------------

        inference_gaps.append("semantic_identity_is_heuristic_not_ground_truth")
        inference_gaps.append("edge_bucket_assignment_is_best_effort_classification")

        notes.append("system_self_model_is_derivative_not_authoritative")
        notes.append("self_model_reflects_db_snapshot_at_query_time_not_live_state")

        return SystemSelfModel(
            capabilities=capabilities,
            limitations=limitations,
            structural_biases=biases,
            failure_modes=failure_modes,
            inference_gaps=inference_gaps,
            notes=notes,
        )
