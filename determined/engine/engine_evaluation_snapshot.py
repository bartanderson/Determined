# tools/analysis/engine/engine_evaluation_snapshot.py

from collections import defaultdict


class EngineEvaluationSnapshotBuilder:

    def build(self, file_analyses, graph):

        bucket_summary = {
            "project": 0,
            "builtin": 0,
            "classification_gap": 0,
        }

        node_degree = defaultdict(int)

        # ---------------------------------------
        # EDGE WALK (must match pipeline semantics)
        # ---------------------------------------
        for edge in graph.edges:

            bucket = getattr(edge, "bucket", None)

            if bucket not in bucket_summary:
                bucket = "classification_gap"

            bucket_summary[bucket] += 1

            node_degree[edge.caller] += 1
            node_degree[edge.callee] += 1

        # ---------------------------------------
        # TOP NODES (mirror exact pipeline logic)
        # ---------------------------------------
        ranked_nodes = [
            (node, degree)
            for node, degree in node_degree.items()
        ]

        top_nodes_by_degree = sorted(
            ranked_nodes,
            key=lambda x: -x[1]
        )[:10]

        high_fanout_nodes = [
            (n, d)
            for n, d in top_nodes_by_degree
            if d > 3
        ]

        # ---------------------------------------
        # SNAPSHOT (STRICT CONTRACT)
        # ---------------------------------------
        return {
            "file_count": len(file_analyses),
            "edge_count": len(graph.edges),
            "bucket_summary": bucket_summary,
            "graph_insights": {
                "top_nodes_by_degree": top_nodes_by_degree,
            },
            "structural_signals": {
                "high_fanout_nodes": high_fanout_nodes,
            },
        }