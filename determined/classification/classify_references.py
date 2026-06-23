# tools/analysis/classification/classify_references.py

# MODULE: classification
# OWNED: TRUE
#
# CONTRACT (LOCKED v3 - SymbolIdentity-aware classification boundary)
#
# PURPOSE
# - Assign bucket labels to SymbolReference edges after SymbolIdentity reconstruction exists
#
# RESPONSIBILITY
# - Consume SymbolIdentity or resolved symbol strings
# - Apply deterministic routing via symbol_router.route_symbol
# - Emit bucket classification:
#     project | runtime | builtin | stdlib | external | unknown
#
# STRICT BOUNDARIES
# - Does NOT perform semantic reconstruction (SymbolIdentity owns this)
# - Does NOT compute identity resolution
# - Does NOT use SemanticCandidateBuilder or identity inference logic
# - Does NOT mutate SymbolIdentity objects
#
# PIPELINE POSITION
# FileAnalysis ingestion pipeline:
#
#   SymbolIdentity semantic reconstruction
#       → produces SemanticIdentity (single resolved representation)
#
#   classify_references (THIS MODULE)
#       → assigns deterministic routing buckets only
#       → does NOT perform identity reconstruction
#       → consumes SymbolIdentity + runtime context only
#
#   GraphBuilder
#       → builds structural call/reference graph
#
#   build_evaluation_snapshot
#       → aggregates final analytical view (read-only)
#
# IMPORTANT ARCHITECTURAL NOTE
# - SymbolIdentity is authoritative identity source
# - CP2.5 remains observational only
# - routing is deterministic decision layer only
#
# GLOBAL INVARIANTS
# - Classification must remain deterministic
# - No identity reconstruction allowed here
# - No cross-symbol inference
# - Every edge must resolve to exactly one bucket

from determined.graph.project_graph_context import ProjectGraphContext
from determined.graph.symbol_router import route_symbol
from determined.graph.symbol_router import route_symbol_shadow
from determined.engine.engine_logger import EngineLogger


def classify_references(analysis, project_prefixes, logger=None):
    ctx = ProjectGraphContext(
        project_prefixes=project_prefixes,
        project_symbols=getattr(analysis, "project_symbols", None) or set(),
        runtime_bindings=getattr(analysis, "runtime_bindings", {}) or {},
    )

    for ref in analysis.symbol_references:

        # ---------------------------------------
        # 1. PRODUCTION ROUTING (UNCHANGED)
        # ---------------------------------------
        route = route_symbol(
            name=ref.callee,
            runtime_bindings=analysis.runtime_bindings,
            project_symbols=analysis.project_symbols,
        )

        ref.bucket = route

        # ---------------------------------------
        # 2. SHADOW ROUTING (OBSERVABILITY ONLY)
        # ---------------------------------------
        shadow_route, trace = route_symbol_shadow(
            name=ref.callee,
            runtime_bindings=analysis.runtime_bindings,
            project_symbols=analysis.project_symbols,
        )

        # attach trace if your analysis supports it
        if hasattr(ref, "trace"):
            ref.trace = trace

        # ---------------------------------------
        # 3. OPTIONAL DIVERGENCE LOG (SAFE)
        # ---------------------------------------
        if shadow_route != route and logger:
            logger.write("\n[ROUTE DIVERGENCE]")
            logger.write("  symbol:", ref.callee)
            logger.write("  prod:", route)
            logger.write("  shadow:", shadow_route)

    return analysis