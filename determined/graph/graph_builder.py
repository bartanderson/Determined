# tools/analysis/graph/graph_builder.py

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from determined.identity.symbol_identity import project_key

@dataclass
class GraphEdge:
    caller: str
    callee: str
    line_number: int
    caller_file: str = ""


@dataclass
class GraphBundle:
    edges: list[GraphEdge] = field(default_factory=list)
    bucket_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))


class GraphBuilder:
    """
    Pure transformation layer:
    - no DB access
    - no classification logic
    - no side effects
    """

    def __init__(self):
        self.seen = set()
        self.edges = []
        self.bucket_counts = defaultdict(int)

    def add_reference(self, caller: str, callee: str, line_number: int, bucket: str, caller_file: str = ""):
        self.edges.append(
            GraphEdge(
                caller=caller,
                callee=callee,
                line_number=line_number,
                caller_file=caller_file,
            )
        )

        if isinstance(bucket, dict):
            key = bucket.get("bucket", "unknown_event")
        else:
            key = bucket

        self.bucket_counts[key] += 1
        

    def build(self) -> GraphBundle:
        return GraphBundle(
            edges=self.edges,
            bucket_counts=dict(self.bucket_counts),
        )

    def edges_for(self, callee: str):
        return [e for e in self.edges if e.callee == callee]

    def callers_of(self, callee: str):
        return {e.caller for e in self.edges if e.callee == callee}

    def callees_of(self, caller: str):
        return {
            e.callee
            for e in self.edges
            if e.caller == caller
        }

    def adjacency(self):
        graph = {}
        for e in self.edges:
            graph.setdefault(e.caller, set()).add(e.callee)
        return graph

    def critical_modules(self, top_n: int = 10):
        """
        Returns most important modules in the system.
        """
        ranked = self.rank_modules()
        return ranked[:top_n]

    def impacted_modules(self, target_module: str):
        """
        Returns all modules transitively impacted
        by changes to target_module.
        """

        from collections import defaultdict, deque

        reverse_graph = defaultdict(set)

        for caller, callee in self.module_projection():
            reverse_graph[callee].add(caller)

        impacted = set()
        queue = deque([target_module])

        while queue:
            current = queue.popleft()

            for dep in reverse_graph[current]:
                if dep not in impacted:
                    impacted.add(dep)
                    queue.append(dep)

        return impacted

    def risk_scores(self):
        """
        Computes architectural risk scores for modules.
        """

        stats = self.module_stats()
        cycles = self.find_module_cycles()

        cycle_nodes = set()
        for c in cycles:
            cycle_nodes.update(c)

        scores = {}

        for module, s in stats.items():

            impact = len(self.impacted_modules(module))

            score = (
                s["fan_in"] * 3
                + s["fan_out"] * 2
                + impact * 2
                + (10 if module in cycle_nodes else 0)
            )

            scores[module] = {
                "score": score,
                "fan_in": s["fan_in"],
                "fan_out": s["fan_out"],
                "impact_radius": impact,
                "in_cycle": module in cycle_nodes,
            }

        return dict(
            sorted(
                scores.items(),
                key=lambda kv: kv[1]["score"],
                reverse=True,
            )
        )

    def top_callees(self, limit: int = 10):
        counts = {}

        seen = set()

        for e in self.edges:
            key = (e.caller, e.callee)

            if key in seen:
                continue
            seen.add(key)

            counts[e.callee] = counts.get(e.callee, 0) + 1

        return sorted(
            counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

    def top_callers(self, limit: int = 10):
        counts = {}

        seen = set()

        for e in self.edges:
            key = (e.caller, e.callee)

            if key in seen:
                continue
            seen.add(key)

            counts[e.caller] = counts.get(e.caller, 0) + 1

        return sorted(
            counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

    def connectivity_score(self):
        score = {}

        for e in self.edges:
            score[e.caller] = score.get(e.caller, 0) + 1
            score[e.callee] = score.get(e.callee, 0) + 1

        return score

    def module_projection(self):
        """
        Converts symbol-level edges → module-level dependency edges.
        """

        edges = set()

        for e in self.edges:
            caller_parts = e.caller.split(".")
            callee_parts = e.callee.split(".")

            caller_module = ".".join(caller_parts[:2]) if len(caller_parts) >= 2 else caller_parts[0]
            callee_module = ".".join(callee_parts[:2]) if len(callee_parts) >= 2 else callee_parts[0]

            if caller_module == callee_module:
                continue

            edges.add((caller_module, callee_module))

        return sorted(edges)

    def module_stats(self):
        """
        Computes module-level dependency statistics.
        """

        fan_in = {}
        fan_out = {}

        for caller, callee in self.module_projection():
            fan_out[caller] = fan_out.get(caller, 0) + 1
            fan_in[callee] = fan_in.get(callee, 0) + 1

        modules = set(fan_in.keys()) | set(fan_out.keys())

        stats = {}

        for m in modules:
            stats[m] = {
                "fan_in": fan_in.get(m, 0),
                "fan_out": fan_out.get(m, 0),
                "total": fan_in.get(m, 0) + fan_out.get(m, 0),
            }

        return stats

    def find_module_cycles(self):
        """
        Detect cycles in module dependency graph using DFS.
        """

        from collections import defaultdict

        graph = defaultdict(list)

        for caller, callee in self.module_projection():
            graph[caller].append(callee)

        visited = set()
        stack = set()
        cycles = []

        def dfs(node, path):
            if node in stack:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return

            if node in visited:
                return

            visited.add(node)
            stack.add(node)

            for neigh in graph[node]:
                dfs(neigh, path + [neigh])

            stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node, [node])

        return cycles

    def rank_modules(self):
        """
        Ranks modules by structural importance.

        Heuristic:
        - high fan-in = important dependency target
        - high fan-out = coupling risk
        - cycles increase importance weight
        """

        stats = self.module_stats()
        cycles = self.find_module_cycles()

        cycle_nodes = set()
        for c in cycles:
            cycle_nodes.update(c)

        ranked = []

        for module, s in stats.items():
            score = (
                s["fan_in"] * 2
                + s["fan_out"] * 1
                + (5 if module in cycle_nodes else 0)
            )

            ranked.append((module, score, s))

        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked