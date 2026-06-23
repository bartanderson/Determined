# tools/analysis/utilities/reachable_print_trace.py
from collections import deque


def explore_call_routes(oracle, start_symbol: str, max_depth=10):

    graph = oracle.get_snapshot_graph()
    edges = graph.edges

    forward = {}

    for e in edges:
        forward.setdefault(e.caller, set()).add(e.callee)

    visited = set()

    queue = deque([(start_symbol, 0, [start_symbol])])

    paths = []

    while queue:
        node, depth, path = queue.popleft()

        if node in visited:
            continue
        visited.add(node)

        # record every path expansion
        paths.append({
            "node": node,
            "depth": depth,
            "path": path,
            "fanout": len(forward.get(node, [])),
        })

        if depth >= max_depth:
            continue

        for nxt in forward.get(node, []):
            queue.append((nxt, depth + 1, path + [nxt]))

    return paths


def main():

    from determined.oracle.db_oracle import DBOracle

    db_path = "corpus.db"
    oracle = DBOracle(db_path)

    start = "EngineRunner.run"

    paths = explore_call_routes(oracle, start)

    print("\n=== CALL ROUTE EXPLORATION ===\n")

    for p in paths[:50]:  # keep output sane
        print("NODE:", p["node"])
        print("DEPTH:", p["depth"])
        print("FANOUT:", p["fanout"])
        print("PATH:")
        print("  " + " -> ".join(p["path"]))
        print()

    print("TOTAL NODES VISITED:", len(paths))


if __name__ == "__main__":
    main()