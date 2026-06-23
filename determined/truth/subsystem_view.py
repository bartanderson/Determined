# tools/analysis/truth/subsystem_view.py
# CLAUDE-EDIT 2026-06-17: returns SubsystemView (views.py) instead of a
# bare dict. Before this, SUBSYSTEM was the only one of the 6 Truth Layer
# views where Select(view) with no metric returned a raw dict (bracket
# access) while every other view returned a dataclass instance (attribute
# access) - a real shape inconsistency in the algebra contract, found
# while root-causing the Windows-only ROLE-view AttributeError (see
# REFACTOR OPS BOARD.md 2026-06-17 "algebra shape contract" entry).
# Same data, same "subsystems" key - just exposed as .subsystems instead
# of ["subsystems"], for parity with STRUCTURE/STABILITY/INTEGRITY/
# SUMMARY/ROLE.
#
# CLAUDE-EDIT 2026-06-17 (later): _module() now takes an optional
# module_map (DBOracle.symbol_module_map() - see oracle/db_oracle.py
# Phase 2 discovery API) and prefers it over the old dotted-name-split
# heuristic. Root cause being fixed (Truth.md Phase 3 Row 4 / REFACTOR
# OPS BOARD.md NEXT STEPS Track B item 2): this codebase's real symbols
# are mostly bare function names with no dots, so the old heuristic
# ("first two dotted segments, else the whole name") returned the bare
# name itself for almost everything, fragmenting SUBSYSTEM into ~355
# singleton groups instead of real architectural groupings. module_map
# is built from real `symbols` table declarations (true file_path, not
# guessed), so any symbol with a captured function/class declaration now
# groups by its actual file's directory. The dotted-name heuristic is
# kept as a fallback ONLY for symbols absent from module_map (builtins,
# external-library calls, accessor-chain noise) - it is no longer the
# only source of truth, just the honest answer when the DB has nothing
# better. Passing no module_map (default None) preserves the exact prior
# behavior, so existing callers/tests that seed only symbol_references/
# graph_edges (no `symbols` table rows) are unaffected - see
# tests/regression/test_run_algebra_end_to_end.py's seeded-DB test.
#
# CLAUDE-EDIT 2026-06-18 (TRACKER.md section 3 item 18): build_subsystem_view()
# now takes an optional builtin_symbols set (DBOracle.builtin_symbols(), the
# same DB-authoritative set truth/views.py's build_structure_view() already
# uses to exclude builtins from hotspot ranking). Before this, a builtin like
# len/str/RuntimeError/print had no `symbols` table declaration, so it fell
# through to the dotted-name fallback in _module() and came back as its own
# bare-name "module" - which then polluted whichever real subsystem called it
# with a fake architectural dependency. Edges where either endpoint is a
# DB-confirmed builtin are now skipped entirely before module resolution, the
# same "exclude from this signal but never mutate edges/graph truth itself"
# treatment build_structure_view() already applies. Passing no
# builtin_symbols (default None) preserves exact prior behavior.

from __future__ import annotations

from collections import defaultdict

from determined.truth.views import SubsystemView


def build_subsystem_view(
    graph,
    module_map: dict | None = None,
    builtin_symbols: set | None = None,
) -> SubsystemView:
    """
    Deterministic subsystem extraction.

    Input:
        graph.edges
        module_map: optional symbol -> module map (DBOracle.
            symbol_module_map()), real DB-backed module resolution.
            Falls back to dotted-name splitting for any symbol not in
            the map (or when module_map is omitted entirely).
        builtin_symbols: optional DB-authoritative builtin set (DBOracle.
            builtin_symbols()). Edges where the caller or callee is a
            confirmed builtin are excluded from grouping, so dependency
            lists reflect real architectural dependencies rather than
            calls to len/str/RuntimeError/print etc. Omit (default None)
            to preserve exact prior (unfiltered) behavior.

    Output:
        SubsystemView wrapping subsystem grouping based on module projection
    """

    subsystems = defaultdict(set)
    edge_counts = defaultdict(int)
    builtin_symbols = builtin_symbols or set()

    for e in graph.edges:
        if e.caller in builtin_symbols or e.callee in builtin_symbols:
            continue

        caller = _module(e.caller, module_map)
        callee = _module(e.callee, module_map)

        if caller == callee:
            continue

        subsystems[caller].add(callee)
        edge_counts[caller] += 1

    return SubsystemView(
        subsystems={
            k: {
                "modules": sorted(v),
                "edge_count": edge_counts[k],
            }
            for k, v in subsystems.items()
        }
    )


def _module(symbol: str, module_map: dict | None = None) -> str:
    if module_map:
        if symbol in module_map:
            return module_map[symbol]
        tail = symbol.split(".")[-1]
        if tail in module_map:
            return module_map[tail]

    # Fallback: original dotted-name heuristic, for symbols with no
    # DB-backed declaration (builtins, external libs, unresolved
    # accessor chains) or when no module_map was supplied at all.
    parts = symbol.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else parts[0]
