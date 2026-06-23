# tools/analysis/contracts/contract_map.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Contract:
    """
    Pure declarative contract definition.

    This file is intentionally OBSERVATIONAL:
    - No validation logic
    - No runtime enforcement
    - No pipeline coupling

    It is a structured representation of system intent.
    """

    name: str

    # architectural layer this contract belongs to
    layer: str  # ingestion | classification | persistence | graph | reducer | architecture

    # human readable invariant description
    rule: str

    # enforcement intent (NOT executed here)
    enforcement: str  # "observe" | "strict" (future use only)

    # severity if violated
    violation_type: str  # error | warning | info

    # related system components
    dependencies: List[str]


def build_contract_map() -> Dict[str, Contract]:
    """
    Central registry of system boundaries and invariants.

    This is a READ MODEL ONLY.
    """

    return {

        # =========================================================
        # INGESTION LAYER
        # =========================================================

        "ingestion_emits_file_analyses": Contract(
            name="ingestion_emits_file_analyses",
            layer="ingestion",
            rule="scan_project_files must emit exactly one FileAnalysis per discovered file",
            enforcement="observe",
            violation_type="error",
            dependencies=["scan_project_files"],
        ),

        "ingestion_preserves_symbol_density": Contract(
            name="ingestion_preserves_symbol_density",
            layer="ingestion",
            rule="symbol_references must be fully extracted and never reduced during ingestion",
            enforcement="observe",
            violation_type="error",
            dependencies=["parse_ast", "extract_symbols"],
        ),

        # =========================================================
        # CLASSIFICATION LAYER
        # =========================================================

        "classification_is_non_destructive": Contract(
            name="classification_is_non_destructive",
            layer="classification",
            rule="classification may annotate symbol references but must not remove or mutate structural data",
            enforcement="observe",
            violation_type="error",
            dependencies=["classify_references"],
        ),

        # =========================================================
        # PERSISTENCE LAYER
        # =========================================================

        "persistence_is_side_effect_only": Contract(
            name="persistence_is_side_effect_only",
            layer="persistence",
            rule="persist_file_analysis must not mutate FileAnalysis objects or upstream structures",
            enforcement="observe",
            violation_type="error",
            dependencies=["persist_file_analysis"],
        ),

        "persistence_row_count_matches_memory": Contract(
            name="persistence_row_count_matches_memory",
            layer="persistence",
            rule="symbol_references in DB must equal in-memory symbol_references per file",
            enforcement="observe",
            violation_type="error",
            dependencies=["symbol_references", "sqlite"],
        ),

        # =========================================================
        # GRAPH LAYER
        # =========================================================

        "graph_builder_deterministic_output": Contract(
            name="graph_builder_deterministic_output",
            layer="graph",
            rule="GraphBuilder must produce identical edge sets for identical symbol inputs",
            enforcement="observe",
            violation_type="error",
            dependencies=["GraphBuilder"],
        ),

        # =========================================================
        # REDUCER LAYER
        # =========================================================

        "reducer_preserves_edge_semantics": Contract(
            name="reducer_preserves_edge_semantics",
            layer="reducer",
            rule="reduce must preserve semantic edge meaning unless explicitly aggregating",
            enforcement="observe",
            violation_type="error",
            dependencies=["reduce"],
        ),

        # =========================================================
        # ARCHITECTURE / CROSS-LAYER BOUNDARIES
        # =========================================================

        "no_ingestion_cross_layer_imports": Contract(
            name="no_ingestion_cross_layer_imports",
            layer="architecture",
            rule="ingestion layer must not import persistence or reducer logic",
            enforcement="observe",
            violation_type="error",
            dependencies=["scan_project_files"],
        ),

        "clean_layer_separation": Contract(
            name="clean_layer_separation",
            layer="architecture",
            rule="each pipeline stage must only consume previous stage outputs and not reach across layers",
            enforcement="observe",
            violation_type="warning",
            dependencies=["pipeline_stages"],
        ),
    }


def list_contracts() -> List[Contract]:
    return list(build_contract_map().values())


def get_contract(name: str) -> Optional[Contract]:
    return build_contract_map().get(name)