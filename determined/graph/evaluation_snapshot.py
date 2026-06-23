# tools/analysis/graph/evaluation_snapshot.py

# MODULE: snapshot
# OWNED: TRUE
#
# CONTRACT (LOCKED v2 - SymbolIdentity aligned snapshot layer)
#
# - Consumes classified edges (post-routing stage)
# - Aggregates bucket results across file-level snapshots
# - Produces deterministic per-file structural summary
#
# DOES NOT OWN
# - classification (moved to classify_references)
# - identity reconstruction (SymbolIdentity responsibility)

from collections import defaultdict
from determined.graph.semantic_roles import classify_semantic_role
from determined.graph.symbol_classifier import classify_symbol
from determined.representation.semantic_identity import SemanticIdentity
from determined.representation.symbol_environment import SymbolEnvironment

BUCKET_NORMALIZER = {
    "unresolved_qualified_reference": "classification_gap",
}


def structural_score(node_name: str) -> int:
    return 0


def node_semantic_tag(node_name: str) -> str:
    if not node_name:
        return "unknown"

    lowered = node_name.lower()

    if lowered.startswith("test_"):
        return "test_code"
    if lowered == "print":
        return "runtime_noise"
    if lowered == "<module>":
        return "module_root"
    if lowered == "main":
        return "entry_point"

    if node_name[0].isupper():
        return "type_or_class"

    if "." in node_name:
        return "qualified_reference"

    return "general_symbol"


def build_evaluation_snapshot(
    analysis,
    graph,
):
    env = getattr(analysis, "env", None)

    if env is None:
        env = SymbolEnvironment(
            alias_map=getattr(analysis, "alias_map", {}),
            runtime_bindings=getattr(analysis, "runtime_bindings", {}),
            project_symbols=getattr(analysis, "project_symbols", set()),
        )

    # ----------------------------
    # INITIALIZE BUCKETS (ONLY ONCE)
    # ----------------------------
    bucket_summary = {
        "project": 0,
        "builtin": 0,
        "classification_gap": 0,
    }

    node_degree = defaultdict(int)

    # ----------------------------
    # SINGLE PASS TRUTH BUILD
    # ----------------------------

    for edge in graph.edges:

        identity = SemanticIdentity(
            surface=edge.callee,
            leaf=edge.callee.split(".")[-1],
        )

        # reuse analysis-level environment (DO NOT RESET PER EDGE)
        pass

        bucket = classify_symbol(identity, env)

        bucket = BUCKET_NORMALIZER.get(bucket, bucket)

        # safety: ignore unknowns instead of crashing
        if bucket not in bucket_summary:
            bucket = "classification_gap"

        bucket_summary[bucket] += 1

        node_degree[edge.caller] += 1
        node_degree[edge.callee] += 1

    # ----------------------------
    # HARD INVARIANT
    # ----------------------------
    assert sum(bucket_summary.values()) == len(graph.edges)

    # ----------------------------
    # NODE RANKING
    # ----------------------------
    ranked_nodes = []
    for node, degree in node_degree.items():
        role = node_semantic_tag(node)
        ranked_nodes.append((node, degree, degree, role))

    top_nodes = sorted(ranked_nodes, key=lambda x: -x[2])[:10]

    high_fanout = [
        (n, d, s, r)
        for n, d, s, r in top_nodes
        if s > 3
    ]

    # ----------------------------
    # SNAPSHOT OUTPUT (FINAL CONTRACT)
    # ----------------------------
    return {
        "file_count": getattr(analysis, "file_count", None),
        "edge_count": len(graph.edges),
        "bucket_summary": bucket_summary,
        "graph_insights": {
            "top_nodes_by_degree": top_nodes,
        },
        "structural_signals": {
            "high_fanout_nodes": high_fanout,
        },
    }