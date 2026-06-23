from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class ReachabilityView:
    forward: dict[str, set[str]]
    reverse: dict[str, set[str]]
    impacted: dict[str, set[str]]  # optional transitive closure


def build_reachability_view(graph, compute_transitive: bool = False) -> ReachabilityView:
    forward = defaultdict(set)
    reverse = defaultdict(set)

    # -------------------------
    # 1-hop structure
    # -------------------------
    for e in graph.edges:
        forward[e.caller].add(e.callee)
        reverse[e.callee].add(e.caller)

    impacted = {}

    # -------------------------
    # optional transitive closure
    # -------------------------
    if compute_transitive:
        for node in forward.keys() | reverse.keys():
            visited = set()
            queue = deque([node])

            while queue:
                current = queue.popleft()

                for nxt in forward.get(current, []):
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)

            visited.discard(node)
            impacted[node] = visited

    return ReachabilityView(
        forward=dict(forward),
        reverse=dict(reverse),
        impacted=impacted,
    )