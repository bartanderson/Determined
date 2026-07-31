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


def _shortest_path_by_name(oracle: "DBOracle", src: str, dst: str) -> list[str] | None:
    """
    Fallback BFS over graph_edges.caller/callee columns (not source_id/target_id).
    Used when source_id-based shortest_path fails, e.g. for JS/TS FQN pairs where
    source_id is not populated or uses a different normalization.
    Returns [src, ..., dst] as stored names, or None.
    """
    from collections import deque as _deque

    def _bare(name: str) -> str:
        return name.rsplit(".", 1)[-1] if "." in name else name

    src_bare = _bare(src)
    dst_bare = _bare(dst)

    # Build candidate src callers: any caller whose bare name matches src
    src_candidates = set()
    for (c,) in oracle.conn.execute(
        "SELECT DISTINCT caller FROM graph_edges WHERE caller = ? OR caller LIKE '%.' || ?",
        (src, src_bare),
    ).fetchall():
        src_candidates.add(c)
    if not src_candidates:
        return None

    visited: set[str] = set(src_candidates)
    queue: _deque[list[str]] = _deque([[c] for c in src_candidates])

    while queue:
        path = queue.popleft()
        node = path[-1]
        for (callee,) in oracle.conn.execute(
            "SELECT DISTINCT callee FROM graph_edges WHERE caller = ?", (node,)
        ).fetchall():
            if _bare(callee) == dst_bare or callee == dst:
                return path + [callee]
            if callee not in visited:
                visited.add(callee)
                queue.append(path + [callee])
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


# ------------------------------------------------------------------
# Implementation frontier (stubs and their callers)
# ------------------------------------------------------------------

def frontier_rows(conn, mode: str = "direct"):
    """
    Authoritative frontier query, shared by the UI frontier graph and the
    corpus verdict. Moved from ui_server.py so "actionable stub" has one
    definition.

    Modes:
      direct — functional callers of stubs  (the actionable frontier)
      chain  — stubs that call other stubs
      all    — both combined
    Returns rows of (caller_name, caller_file, caller_line,
                     callee_name, callee_file, callee_line).
    """
    def _run(caller_stub: int, callee_stub: int):
        return conn.execute("""
            SELECT DISTINCT f_caller.name, f_caller.file_path, f_caller.line_number,
                            f_callee.name, f_callee.file_path, f_callee.line_number
            FROM graph_edges ge
            JOIN functions f_caller ON ge.source_id = f_caller.name
            JOIN functions f_callee ON (
                ge.target_id = f_callee.name
                OR ge.target_id LIKE '%.' || f_callee.name
            )
            WHERE f_caller.is_stub = ? AND f_callee.is_stub = 1
        """, (caller_stub,)).fetchall()

    if mode == "chain":
        return _run(caller_stub=1, callee_stub=1)
    if mode == "all":
        return _run(0, 1) + _run(1, 1)
    return _run(caller_stub=0, callee_stub=1)  # default: direct


# ------------------------------------------------------------------
# Stub islands: stubs with no live callers anywhere in transitive closure
# ------------------------------------------------------------------

def find_stub_islands(oracle: "DBOracle", subsystem: str = "") -> list[dict]:
    """
    Return stubs where no non-stub caller exists anywhere in the transitive
    closure of callers. These are design-complete but entirely unwired — nothing
    in live code touches them, even indirectly.

    Different from the frontier (which shows stubs that DO have callers).
    Different from orphaned (which are non-stub symbols with no callers).

    Returns list of {name, file_path, transitive_caller_count} sorted by name.
    Optional subsystem: filter by file_path or name substring.
    """
    conn = oracle.conn
    use_ids = _has_id_columns(conn)

    # Get all stubs (optionally filtered)
    if subsystem:
        sub = subsystem.lower()
        stubs = conn.execute(
            "SELECT name, file_path FROM functions "
            "WHERE is_stub = 1 AND (LOWER(file_path) LIKE ? OR LOWER(name) LIKE ?)",
            (f"%{sub}%", f"%{sub}%"),
        ).fetchall()
    else:
        stubs = conn.execute(
            "SELECT name, file_path FROM functions WHERE is_stub = 1"
        ).fetchall()

    if not stubs:
        return []

    # Build a reverse adjacency map: callee -> set of callers
    if use_ids:
        edge_rows = conn.execute("SELECT caller, target_id FROM graph_edges").fetchall()
    else:
        edge_rows = conn.execute("SELECT caller, callee FROM graph_edges").fetchall()

    callers_of: dict[str, set[str]] = {}
    for caller, callee in edge_rows:
        bare = callee.rsplit(".", 1)[-1] if "." in callee else callee
        callers_of.setdefault(callee, set()).add(caller)
        if bare != callee:
            callers_of.setdefault(bare, set()).add(caller)

    # Non-stub symbol names (live code)
    live_names: set[str] = set()
    for (name,) in conn.execute("SELECT name FROM functions WHERE is_stub = 0").fetchall():
        live_names.add(name)
        live_names.add(name.rsplit(".", 1)[-1])

    islands = []
    for (stub_name, stub_file) in stubs:
        # BFS upward through caller chain; stop if any live (non-stub) caller found
        visited: set[str] = set()
        queue = [stub_name, stub_name.rsplit(".", 1)[-1]]
        has_live_caller = False
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            for caller in callers_of.get(node, set()):
                if caller in live_names:
                    has_live_caller = True
                    break
                if caller not in visited:
                    queue.append(caller)
            if has_live_caller:
                break

        if not has_live_caller:
            islands.append({
                "name": stub_name,
                "file_path": stub_file,
                "transitive_caller_count": 0,
            })

    islands.sort(key=lambda x: x["name"])
    return islands


# ------------------------------------------------------------------
# Chain synthesis: entry-point-to-stub path with missing-link labels
# ------------------------------------------------------------------

def chain_synthesis(oracle: "DBOracle", name: str, max_depth: int = 8) -> dict:
    """
    Given a stub or domain name, assemble the call chain from the nearest
    entry point down to (and through) that stub, annotating each hop as
    implemented, stub, or missing.

    Returns a dict with:
      name       — the resolved bare name queried
      upstream   — list of {name, is_stub, is_ep, file_path} from EP → stub
                   (shortest path; empty if stub is an island)
      downstream — list of {name, is_stub, file_path} immediately called by stub
      missing    — list of stub/unresolved names blocking the chain
      is_island  — True if no caller chain reaches an entry point
    """
    conn = oracle.conn
    use_ids = _has_id_columns(conn)

    # Resolve name to canonical form
    bare = name.rsplit(".", 1)[-1]
    if use_ids:
        try:
            row = conn.execute(
                "SELECT canonical_id FROM symbol_names WHERE name = ? LIMIT 1", (bare,)
            ).fetchone()
            canonical = row[0] if row else bare
        except Exception:
            canonical = bare
    else:
        canonical = bare

    # Build is_stub + file_path lookup from functions table
    def _node_info(sym: str) -> dict:
        try:
            row = conn.execute(
                "SELECT is_stub, file_path FROM functions WHERE name = ? LIMIT 1", (sym,)
            ).fetchone()
            if row:
                return {"is_stub": bool(row[0]), "file_path": row[1] or ""}
        except Exception:
            pass
        return {"is_stub": False, "file_path": ""}

    # Identify entry points (nodes with no callers in the corpus)
    if use_ids:
        all_targets: set[str] = {
            r[0] for r in conn.execute("SELECT DISTINCT target_id FROM graph_edges").fetchall()
        }
        all_sources: set[str] = {
            r[0] for r in conn.execute("SELECT DISTINCT source_id FROM graph_edges").fetchall()
        }
    else:
        all_targets = {r[0] for r in conn.execute("SELECT DISTINCT callee FROM graph_edges").fetchall()}
        all_sources = {r[0] for r in conn.execute("SELECT DISTINCT caller FROM graph_edges").fetchall()}
    entry_point_ids = all_sources - all_targets

    # BFS upward from `canonical` to find the shortest path reaching an EP
    # Each queue item is a path (list) from canonical upward: [canonical, caller1, caller2, ...]
    visited_up: set[str] = {canonical}
    queue: deque[list[str]] = deque([[canonical]])
    best_upstream_reversed: list[str] | None = None  # path from stub up to EP

    while queue:
        path = queue.popleft()
        tip = path[-1]

        if len(path) > max_depth:
            continue

        # Get callers of tip
        if use_ids:
            rows = conn.execute(
                "SELECT DISTINCT source_id FROM graph_edges WHERE target_id = ?", (tip,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT caller FROM graph_edges WHERE callee = ? OR callee LIKE ?",
                (tip, f"%.{tip}"),
            ).fetchall()

        has_any_caller = bool(rows)
        if not has_any_caller or tip in entry_point_ids:
            # tip has no callers — it's a root
            if len(path) > 1:  # don't count the stub itself as its own EP
                best_upstream_reversed = path
                break

        for (caller,) in rows:
            if caller not in visited_up:
                visited_up.add(caller)
                new_path = path + [caller]
                if caller in entry_point_ids:
                    best_upstream_reversed = new_path
                    queue.clear()  # found an EP — take shortest path
                    break
                queue.append(new_path)

        if best_upstream_reversed:
            break

    # Reverse so it reads EP → stub
    if best_upstream_reversed:
        upstream_names = list(reversed(best_upstream_reversed))
    else:
        upstream_names = [canonical]  # just the stub itself (island)

    upstream = []
    for sym in upstream_names:
        info = _node_info(sym)
        upstream.append({
            "name": sym,
            "is_stub": info["is_stub"],
            "is_ep": sym in entry_point_ids or sym == upstream_names[0],
            "file_path": info["file_path"],
        })

    # BFS downward from stub — one hop (immediate callees)
    if use_ids:
        callee_rows = conn.execute(
            "SELECT DISTINCT target_id FROM graph_edges WHERE source_id = ?", (canonical,)
        ).fetchall()
    else:
        callee_rows = conn.execute(
            "SELECT DISTINCT callee FROM graph_edges WHERE caller = ?", (canonical,)
        ).fetchall()

    downstream = []
    for (callee,) in callee_rows:
        info = _node_info(callee)
        downstream.append({
            "name": callee,
            "is_stub": info["is_stub"],
            "file_path": info["file_path"],
        })

    # Collect missing links: stubs in the chain
    missing = [n["name"] for n in upstream if n["is_stub"]]
    missing += [n["name"] for n in downstream if n["is_stub"] and n["name"] not in missing]

    is_island = len(upstream) == 1 and upstream[0]["name"] == canonical

    return {
        "name": canonical,
        "upstream": upstream,
        "downstream": downstream,
        "missing": missing,
        "is_island": is_island,
    }
