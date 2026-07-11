# tools/analysis/agent/graph_utils.py
#
# Graph traversal utilities for the discovery agent.
# Pure DB operations - no AI calls. All functions take an oracle and
# return plain Python data structures.

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle


# ------------------------------------------------------------------
# Entry points
# ------------------------------------------------------------------

def find_entry_points(oracle: "DBOracle", exclude_tests: bool = True) -> list[dict]:
    """
    Symbols that nothing calls (in-degree 0 in graph_edges).
    These are system roots - either public API, top-level scripts,
    or dead code. Returns list of {name, file_path, symbol_type, out_degree},
    sorted by out_degree descending so real entry points (high fan-out) rank first.
    Excludes test files and __init__ by default.
    """
    # All symbols that appear as a callee somewhere — also check dotted form
    # (e.g. "from_dict" is called as "ClassName.from_dict" in graph_edges)
    raw_callees = {
        r[0] for r in
        oracle.conn.execute("SELECT DISTINCT callee FROM graph_edges").fetchall()
    }
    # Include bare names that appear as the suffix of a dotted callee
    called = raw_callees | {c.rsplit(".", 1)[-1] for c in raw_callees if "." in c}

    # Out-degree per (name, file_path) using caller_file when available
    out_deg_file: dict[tuple, int] = {}
    try:
        for r in oracle.conn.execute(
            "SELECT caller, caller_file, COUNT(*) FROM graph_edges "
            "WHERE caller_file IS NOT NULL GROUP BY caller, caller_file"
        ).fetchall():
            out_deg_file[(r[0], r[1])] = r[2]
    except Exception:
        pass  # older DBs without caller_file column
    # Fallback: name-only out_degree for edges without caller_file
    out_deg_name: dict[str, int] = {}
    for r in oracle.conn.execute(
        "SELECT caller, COUNT(*) FROM graph_edges GROUP BY caller"
    ).fetchall():
        out_deg_name[r[0]] = r[1]

    rows = oracle.conn.execute(
        "SELECT name, file_path, 'function' AS symbol_type FROM functions "
        "UNION ALL "
        "SELECT name, file_path, 'class' AS symbol_type FROM classes"
    ).fetchall()

    results = []
    seen_names: set[str] = set()
    for r in rows:
        name, fp, stype = r[0], r[1], r[2]
        if name in called:
            continue
        if name.startswith("__"):
            continue
        if exclude_tests and ("test" in fp.lower() or name.startswith("test_")):
            continue
        # Deduplicate: when same bare name appears in multiple files, keep first
        # (edges are name-keyed so all copies share the same out_degree anyway)
        if name in seen_names:
            continue
        seen_names.add(name)
        odeg = out_deg_file.get((name, fp), out_deg_name.get(name, 0))
        results.append({
            "name": name,
            "file_path": fp,
            "symbol_type": stype,
            "out_degree": odeg,
        })

    results.sort(key=lambda r: r["out_degree"], reverse=True)
    return results


# ------------------------------------------------------------------
# BFS callees (forward walk)
# ------------------------------------------------------------------

def bfs_callees(
    oracle: "DBOracle",
    root: str,
    max_depth: int = 4,
    max_nodes: int = 50,
) -> list[dict]:
    """
    BFS down the call graph from root.
    Returns list of {symbol, depth, callers} in visit order.
    Stops at max_depth or max_nodes, whichever comes first.
    """
    visited: set[str] = {root}
    queue: deque[tuple[str, int]] = deque([(root, 0)])
    results = []

    while queue and len(results) < max_nodes:
        node, depth = queue.popleft()
        if depth > 0:
            placeholders = ",".join("?" * len(visited))
            callers = [
                r[0] for r in oracle.conn.execute(
                    f"SELECT DISTINCT caller FROM graph_edges WHERE callee = ? AND caller IN ({placeholders})",
                    (node, *visited),
                ).fetchall()
            ]
            results.append({"symbol": node, "depth": depth, "callers": callers})

        if depth >= max_depth:
            continue

        callees = oracle.conn.execute(
            "SELECT DISTINCT callee FROM graph_edges WHERE caller = ?", (node,)
        ).fetchall()
        for row in callees:
            callee = row[0]
            if callee not in visited:
                visited.add(callee)
                queue.append((callee, depth + 1))

    return results


# ------------------------------------------------------------------
# Shortest path between two symbols
# ------------------------------------------------------------------

def _resolve_to_canonical(oracle: "DBOracle", name: str) -> str:
    """Resolve a name (any form) to its canonical_id via symbol_names, or normalize directly."""
    try:
        row = oracle.conn.execute(
            "SELECT canonical_id FROM symbol_names WHERE name = ? LIMIT 1", (name,)
        ).fetchone()
        if row:
            return row[0]
    except Exception:
        pass
    from determined.identity.symbol_identity import normalize_symbol
    return normalize_symbol(name)


def shortest_path(oracle: "DBOracle", src: str, dst: str) -> list[str] | None:
    """
    Shortest call path from src to dst through graph_edges.
    Traverses by source_id/target_id (canonical bare names) so module-qualified
    callee names don't break BFS. Returns [src, ..., dst] as bare names, or None.
    """
    src_id = _resolve_to_canonical(oracle, src)
    dst_id = _resolve_to_canonical(oracle, dst)

    if src_id == dst_id:
        return [src_id]

    visited: set[str] = {src_id}
    queue: deque[list[str]] = deque([[src_id]])

    while queue:
        path = queue.popleft()
        node_id = path[-1]

        rows = oracle.conn.execute(
            "SELECT DISTINCT target_id FROM graph_edges WHERE source_id = ?", (node_id,)
        ).fetchall()
        for (target_id,) in rows:
            if target_id == dst_id:
                return path + [dst_id]
            if target_id not in visited:
                visited.add(target_id)
                queue.append(path + [target_id])

    return None


# ------------------------------------------------------------------
# Most connected symbols (by call degree)
# ------------------------------------------------------------------

def most_connected(oracle: "DBOracle", n: int = 20, filter_substr: str = "") -> list[dict]:
    """
    Top N symbols by total call degree (in + out edges).
    Optional filter_substr limits to symbols whose name or file contains the string.
    Returns list of {symbol, file_path, in_degree, out_degree, total}.
    """
    in_deg: dict[str, int] = defaultdict(int)
    out_deg: dict[str, int] = defaultdict(int)

    for row in oracle.conn.execute("SELECT caller, callee FROM graph_edges").fetchall():
        out_deg[row[0]] += 1
        in_deg[row[1]] += 1

    # Build file lookup
    file_map: dict[str, str] = {}
    for row in oracle.conn.execute(
        "SELECT name, file_path FROM functions UNION ALL SELECT name, file_path FROM classes"
    ).fetchall():
        file_map[row[0]] = row[1]

    all_syms = set(in_deg) | set(out_deg)
    results = []
    for sym in all_syms:
        fp = file_map.get(sym, "")
        # Skip builtins and external library symbols (no project file known)
        if not fp:
            continue
        # Skip Python protocol methods (dunders): their call count is language-
        # invoked, not a developer architectural choice, so it is not a signal
        # of centrality. Same rationale as builtin filtering above.
        if sym.startswith("__") and sym.endswith("__"):
            continue
        if filter_substr and filter_substr.lower() not in sym.lower() and filter_substr.lower() not in fp.lower():
            continue
        total = in_deg[sym] + out_deg[sym]
        results.append({
            "symbol": sym,
            "file_path": fp,
            "in_degree": in_deg[sym],
            "out_degree": out_deg[sym],
            "total": total,
        })

    results.sort(key=lambda r: r["total"], reverse=True)
    return results[:n]


# ------------------------------------------------------------------
# Cluster detection (files with heavy mutual call density)
# ------------------------------------------------------------------

def find_clusters(oracle: "DBOracle", min_edges: int = 2) -> list[dict]:
    """
    Find clusters of files that call each other heavily.
    A cluster is a set of files with >= min_edges between them in either direction.
    Returns list of {files: [str], edge_count: int} sorted by edge_count desc.
    """
    # Build file-to-file edge counts
    file_map: dict[str, str] = {}
    for row in oracle.conn.execute(
        "SELECT name, file_path FROM functions UNION ALL SELECT name, file_path FROM classes"
    ).fetchall():
        file_map[row[0]] = row[1]

    edge_counts: dict[frozenset, int] = defaultdict(int)
    for row in oracle.conn.execute("SELECT caller, callee FROM graph_edges").fetchall():
        src_file = file_map.get(row[0], "")
        dst_file = file_map.get(row[1], "")
        if src_file and dst_file and src_file != dst_file:
            pair = frozenset([src_file, dst_file])
            edge_counts[pair] += 1

    clusters = []
    for pair, count in edge_counts.items():
        if count >= min_edges:
            clusters.append({"files": sorted(pair), "edge_count": count})

    clusters.sort(key=lambda c: c["edge_count"], reverse=True)
    return clusters


# ------------------------------------------------------------------
# Subgraph around a symbol (for visualization)
# ------------------------------------------------------------------

def subgraph_around(oracle: "DBOracle", symbol: str, radius: int = 2) -> dict:
    """
    Pull all nodes and edges within `radius` hops of `symbol` in either direction.
    Returns {nodes: [str], edges: [(caller, callee)],
             reasons: {node: reason_string}}.
    """
    reasons: dict[str, str] = {symbol: "root (queried symbol)"}
    visited: set[str] = {symbol}
    frontier = {symbol}

    for hop in range(1, radius + 1):
        next_frontier: set[str] = set()
        for node in frontier:
            for row in oracle.conn.execute(
                "SELECT callee FROM graph_edges WHERE caller = ?", (node,)
            ).fetchall():
                callee = row[0]
                if callee not in visited:
                    visited.add(callee)
                    next_frontier.add(callee)
                    reasons[callee] = f"called by {node} (hop {hop}, outbound)"
            for row in oracle.conn.execute(
                "SELECT caller FROM graph_edges WHERE callee = ?", (node,)
            ).fetchall():
                caller = row[0]
                if caller not in visited:
                    visited.add(caller)
                    next_frontier.add(caller)
                    reasons[caller] = f"calls {node} (hop {hop}, inbound)"
        frontier = next_frontier

    edges = oracle.conn.execute(
        "SELECT DISTINCT caller, callee FROM graph_edges"
    ).fetchall()
    edges = [(r[0], r[1]) for r in edges if r[0] in visited and r[1] in visited]

    return {"nodes": sorted(visited), "edges": edges, "reasons": reasons}
