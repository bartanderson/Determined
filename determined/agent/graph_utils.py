# tools/analysis/agent/graph_utils.py
#
# Graph traversal utilities for the discovery agent.
# Pure DB operations - no AI calls. All functions take an oracle and
# return plain Python data structures.
#
# TWO-TIER NAMING CONTRACT (mirrors graph_edges schema in persistence_engine.py)
# -------------------------------------------------------------------------------
# graph_edges has two distinct name columns:
#
#   source_id / target_id  — canonical bare name (last segment after last dot).
#       Always a simple identifier like "ground_question".
#       Computed at store time by edge_identity() → normalize_symbol().
#       USE THESE for all graph traversal, degree counting, and connectivity
#       queries. They are stable keys regardless of how the caller imported
#       the symbol.
#
#   caller / callee  — raw surface name as emitted by parse_ast.
#       May be bare ("ground_question"), fully-qualified
#       ("determined.agent.agent_resolver.ground_question"), or dotted-attr
#       ("obj.method"). The form depends on how the call was written in source:
#       same-file calls get bare names; `from X import fn` calls get FQ names.
#       USE THESE for display, debugging, and blame — not for traversal.
#
# symbol_names table  — multi-form index: canonical_id → (surface, bare).
#       Used by _resolve_to_canonical() to go from any name form to canonical.
#
# RULE: traverse via source_id/target_id; display via caller/callee.
# Functions that query callee= by raw string will silently miss cross-module
# edges stored as FQ names. shortest_path() is the reference implementation
# of the correct pattern.

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle


# ------------------------------------------------------------------
# Schema compatibility helper
# ------------------------------------------------------------------

def _has_id_columns(conn) -> bool:
    """
    Return True if graph_edges has source_id/target_id traversal columns.

    Real corpus DBs always have them (added by ensure_schema / _persist_graph_edges).
    Some test fixtures create a minimal graph_edges without these columns because they
    predate the two-tier naming system. This check lets traversal functions degrade
    gracefully for those fixtures rather than raising OperationalError.

    Callers: use source_id/target_id when this returns True; caller/callee otherwise.
    The RULE remains: prefer source_id/target_id for traversal in production code.
    """
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(graph_edges)").fetchall()}
        return "source_id" in cols and "target_id" in cols
    except Exception:
        return False


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
    resolved_only: bool = False,
) -> list[dict]:
    """
    BFS down the call graph from root.
    Returns list of {symbol, depth, callers} in visit order.
    Stops at max_depth or max_nodes, whichever comes first.

    Uses source_id/target_id (canonical bare names) for traversal so that
    cross-module calls stored as FQ callees are reachable. root is normalized
    to its canonical id before the walk begins.
    """
    from determined.identity.symbol_identity import normalize_symbol
    use_ids = _has_id_columns(oracle.conn)
    root_id = normalize_symbol(root) if use_ids else root
    visited: set[str] = {root_id}
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])
    results = []

    res_filter = " AND resolved = 1" if resolved_only else ""
    if use_ids:
        callers_q = "SELECT DISTINCT source_id FROM graph_edges WHERE target_id = ? AND source_id IN ({ph})" + res_filter
        callees_q = "SELECT DISTINCT target_id FROM graph_edges WHERE source_id = ?" + res_filter
    else:
        # Compatibility: test fixtures that predate source_id/target_id columns.
        callers_q = "SELECT DISTINCT caller FROM graph_edges WHERE callee = ? AND caller IN ({ph})" + res_filter
        callees_q = "SELECT DISTINCT callee FROM graph_edges WHERE caller = ?" + res_filter

    while queue and len(results) < max_nodes:
        node, depth = queue.popleft()
        if depth > 0:
            placeholders = ",".join("?" * len(visited))
            callers = [
                r[0] for r in oracle.conn.execute(
                    callers_q.format(ph=placeholders),
                    (node, *visited),
                ).fetchall()
            ]
            results.append({"symbol": node, "depth": depth, "callers": callers})

        if depth >= max_depth:
            continue

        for (callee_id,) in oracle.conn.execute(callees_q, (node,)).fetchall():
            if callee_id not in visited:
                visited.add(callee_id)
                queue.append((callee_id, depth + 1))

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

    # Only traverse through symbols registered in the functions table.
    # Restricting to registered functions prevents false paths through method-call
    # noise: e.g. `results.append(dispatch(...))` is ingested as an edge
    # append -> dispatch (receiver stripped), making unrelated .append() calls
    # look like a path hop into dispatch.  Functions in the corpus have a real
    # source file; stdlib/builtin method names do not.
    corpus_names: set[str] = {
        r[0] for r in oracle.conn.execute(
            "SELECT DISTINCT name FROM functions WHERE name IS NOT NULL"
        ).fetchall()
    }
    # Always allow the destination even if it has no outgoing edges
    corpus_names.add(dst_id)

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
            if target_id not in visited and target_id in corpus_names:
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

    Uses source_id/target_id (canonical bare names) for degree counting so that
    cross-module edges stored as FQ callees contribute to the correct symbol's
    in-degree. The caller/callee surface columns are not used here.
    """
    in_deg: dict[str, int] = defaultdict(int)
    out_deg: dict[str, int] = defaultdict(int)

    use_ids = _has_id_columns(oracle.conn)
    edge_q = "SELECT source_id, target_id FROM graph_edges" if use_ids else "SELECT caller, callee FROM graph_edges"
    for row in oracle.conn.execute(edge_q).fetchall():
        out_deg[row[0]] += 1
        in_deg[row[1]] += 1

    # Build file lookup and a bare-name → full FQDN display map.
    # source_id/target_id in graph_edges are normalized bare names (e.g. "SessionAdapter")
    # but functions.name stores the full FQDN ("game.SessionAdapter"). Index both so
    # the degree lookup succeeds, and record the full name for display.
    file_map: dict[str, str] = {}
    display_name: dict[str, str] = {}  # bare/source_id key -> full FQDN for display
    for row in oracle.conn.execute(
        "SELECT name, file_path FROM functions UNION ALL SELECT name, file_path FROM classes"
    ).fetchall():
        name, fp = row[0], row[1]
        file_map[name] = fp
        bare = name.rsplit("::", 1)[-1].rsplit(".", 1)[-1]
        if bare != name:
            file_map.setdefault(bare, fp)
            display_name.setdefault(bare, name)

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
            "symbol": display_name.get(sym, sym),
            "file_path": fp,
            "in_degree": in_deg[sym],
            "out_degree": out_deg[sym],
            "total": total,
        })

    # Merge duplicate entries that arose from bare-name aliasing (e.g. both "run"
    # and "run::run" resolve to the same display symbol in the same file).
    merged: dict[tuple, dict] = {}
    for r in results:
        key = (r["symbol"], r["file_path"])
        if key in merged:
            merged[key]["in_degree"] += r["in_degree"]
            merged[key]["out_degree"] += r["out_degree"]
            merged[key]["total"] += r["total"]
        else:
            merged[key] = dict(r)
    results = list(merged.values())

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
    # Build file_map indexed by FQDN and bare name so both Python (FQDN caller column)
    # and Go/Rust (bare target_id) resolve correctly.
    file_map: dict[str, str] = {}
    for row in oracle.conn.execute(
        "SELECT name, file_path FROM functions UNION ALL SELECT name, file_path FROM classes"
    ).fetchall():
        name, fp = row[0], row[1]
        file_map[name] = fp
        bare = name.rsplit("::", 1)[-1].rsplit(".", 1)[-1]
        if bare != name:
            file_map.setdefault(bare, fp)

    # Use caller (FQDN, always matches functions.name) for source file.
    # Use target_id (canonical bare name) for dest file — resolved via bare-name
    # entries added above. This handles all languages: Python, Go, Rust, JS/TS.
    use_ids = _has_id_columns(oracle.conn)
    if use_ids:
        edge_rows = oracle.conn.execute("SELECT caller, target_id FROM graph_edges").fetchall()
    else:
        edge_rows = oracle.conn.execute("SELECT caller, callee FROM graph_edges").fetchall()

    edge_counts: dict[frozenset, int] = defaultdict(int)
    for caller, target in edge_rows:
        src_file = file_map.get(caller, "")
        dst_file = file_map.get(target, "")
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

def subgraph_around(oracle: "DBOracle", symbol: str, radius: int = 2, resolved_only: bool = False) -> dict:
    """
    Pull all nodes and edges within `radius` hops of `symbol` in either direction.
    Returns {nodes: [str], edges: [(source_id, target_id)],
             reasons: {node: reason_string}}.

    Uses source_id/target_id (canonical bare names) for traversal so that
    cross-module edges stored as FQ callees are included. The returned edge
    tuples are canonical ids, not surface names.
    """
    from determined.identity.symbol_identity import normalize_symbol
    use_ids = _has_id_columns(oracle.conn)
    root_id = normalize_symbol(symbol) if use_ids else symbol
    reasons: dict[str, str] = {root_id: "root (queried symbol)"}
    visited: set[str] = {root_id}
    frontier = {root_id}

    res_filter = " AND resolved = 1" if resolved_only else ""
    res_where  = " WHERE resolved = 1" if resolved_only else ""
    if use_ids:
        out_q  = "SELECT target_id FROM graph_edges WHERE source_id = ?" + res_filter
        in_q   = "SELECT source_id FROM graph_edges WHERE target_id = ?" + res_filter
        edge_q = "SELECT DISTINCT source_id, target_id FROM graph_edges" + res_where
    else:
        out_q  = "SELECT callee FROM graph_edges WHERE caller = ?" + res_filter
        in_q   = "SELECT caller FROM graph_edges WHERE callee = ?" + res_filter
        edge_q = "SELECT DISTINCT caller, callee FROM graph_edges" + res_where

    for hop in range(1, radius + 1):
        next_frontier: set[str] = set()
        for node in frontier:
            for (tgt,) in oracle.conn.execute(out_q, (node,)).fetchall():
                if tgt not in visited:
                    visited.add(tgt)
                    next_frontier.add(tgt)
                    reasons[tgt] = f"called by {node} (hop {hop}, outbound)"
            for (src,) in oracle.conn.execute(in_q, (node,)).fetchall():
                if src not in visited:
                    visited.add(src)
                    next_frontier.add(src)
                    reasons[src] = f"calls {node} (hop {hop}, inbound)"
        frontier = next_frontier

    edges = oracle.conn.execute(edge_q).fetchall()
    edges = [(r[0], r[1]) for r in edges if r[0] in visited and r[1] in visited]

    return {"nodes": sorted(visited), "edges": edges, "reasons": reasons}
