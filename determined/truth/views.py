# tools/analysis/truth/views.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StructureView:
    edges: list[tuple[str, str]]
    adjacency: dict[str, set[str]]
    hotspots: list[tuple[str, int]]  # (module, degree)


def build_structure_view(graph: Any, builtin_symbols: set = None) -> StructureView:
    edges = [(e.caller, e.callee) for e in graph.edges]

    adjacency = {}
    degree_count = {}

    for caller, callee in edges:
        adjacency.setdefault(caller, set()).add(callee)

        degree_count[caller] = degree_count.get(caller, 0) + 1
        degree_count[callee] = degree_count.get(callee, 0) + 1

    # Exclude builtin symbols from hotspot ranking.
    # Builtins (print, len, getattr, etc.) dominate degree counts by volume
    # but carry no semantic signal about project structure.
    # edges/adjacency are left intact - structural truth is not modified.
    if builtin_symbols:
        ranked = {k: v for k, v in degree_count.items() if k not in builtin_symbols}
    else:
        ranked = degree_count

    hotspots = sorted(
        ranked.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return StructureView(
        edges=edges,
        adjacency=adjacency,
        hotspots=hotspots,
    )

@dataclass
class StabilityView:
    stable_contracts: list[str]
    unstable_contracts: list[str]
    drift_signals: list[dict]
    lifecycle: list[dict] = None  # per-contract health/lifecycle state, populated after first ingest


def build_stability_view(contract_reports, drift_signals, lifecycle=None) -> StabilityView:
    stable = []
    unstable = []

    for r in contract_reports:
        if r.violations:
            unstable.append(r.file_path)
        else:
            stable.append(r.file_path)

    lifecycle_dicts = [
        {
            "contract": lc.contract_name,
            "state": lc.state,
            "score": lc.stability_score,
            "trend": lc.trend,
            "recommendation": lc.recommendation,
        }
        for lc in (lifecycle or [])
    ]

    return StabilityView(
        stable_contracts=stable,
        unstable_contracts=unstable,
        drift_signals=[
            {
                "contract": s.contract_name,
                "class": s.classification,
                "count": s.count,
                "layer": s.layer,
            }
            for s in drift_signals
        ],
        lifecycle=lifecycle_dicts or None,
    )

@dataclass
class IntegrityView:
    errors: list[str]
    warnings: list[str]
    db_mismatches: list[str]


# CLAUDE-EDIT 2026-06-18 (TRACKER.md section 3 item 17): db_mismatches
# used to be unconditionally [] with the comment "no DB comparison
# anymore." Investigated whether engine/structural_parity_diff.py's
# run_structural_diff() (the historical engine-vs-DB parity check this
# name likely meant) could be revived - it can't: it requires an
# in-memory file_analyses object Assessor's DB-only architecture never
# produces, and it has zero callers anywhere (confirmed via grep), so
# wiring it would mean inventing fake engine-side data just to fill the
# field - exactly what "never invent information" rules out. What's real
# instead: Assessor.run_integrity_check() already compares two
# independently-persisted tables that are supposed to agree
# (graph_edges vs symbol_references) and flags edge_count_mismatch when
# they don't - a genuine DB-internal mismatch, just never wired into the
# Truth Layer. See Assessor.db_mismatches() for the extraction. Default
# kept as [] so existing callers that don't pass anything keep exactly
# the prior behavior.
def build_integrity_view(validation_result, graph, db_mismatches=None) -> IntegrityView:
    return IntegrityView(
        errors=validation_result.errors,
        warnings=validation_result.warnings,
        db_mismatches=db_mismatches or [],
    )

@dataclass
class SystemSummaryView:
    edge_count: int
    file_count: int
    metrics: dict


def build_system_summary_view(reduced, metrics, file_count: int) -> SystemSummaryView:
    return SystemSummaryView(
        edge_count=reduced.get("edge_activity_total", 0),
        file_count=file_count,
        metrics=metrics,
    )

@dataclass
class SubsystemView:
    subsystems: dict[str, dict]


@dataclass
class RoleView:
    files: list[dict]
    totals: dict


@dataclass
class IntentView:
    """
    Answers "what is X for" using author-stated intent (docstrings) rather
    than call-graph heuristics. Populated from the functions/classes tables'
    docstring columns, which are captured at ingestion time from ast.get_docstring().
    This is Truth.md Phase 1 Row 1 remainder + Row 5: the first deterministic,
    grounded answer to intent questions that does not invent information.
    """
    functions: list[dict]   # {file, name, line, docstring}
    classes: list[dict]     # {file, name, line, docstring}
    mutations: list[dict]   # {file, line, target, operation, intent}
    coverage: dict          # {functions_with_docstring, functions_total, ...}


def build_intent_view(conn) -> "IntentView":
    import sqlite3
    cur = conn.cursor()

    cur.execute("SELECT file_path, name, line_number, docstring FROM functions WHERE docstring IS NOT NULL AND docstring != ''")
    functions = [{"file": r[0], "name": r[1], "line": r[2], "docstring": r[3]} for r in cur.fetchall()]

    cur.execute("SELECT file_path, name, line_number, docstring FROM classes WHERE docstring IS NOT NULL AND docstring != ''")
    classes = [{"file": r[0], "name": r[1], "line": r[2], "docstring": r[3]} for r in cur.fetchall()]

    cur.execute("SELECT file_path, line_number, target, operation, intent FROM mutations WHERE intent IS NOT NULL AND intent != ''")
    mutations = [{"file": r[0], "line": r[1], "target": r[2], "operation": r[3], "intent": r[4]} for r in cur.fetchall()]

    cur.execute("SELECT COUNT(*) FROM functions")
    fn_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM functions WHERE docstring IS NOT NULL AND docstring != ''")
    fn_with_doc = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM classes")
    cls_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM classes WHERE docstring IS NOT NULL AND docstring != ''")
    cls_with_doc = cur.fetchone()[0]

    return IntentView(
        functions=functions,
        classes=classes,
        mutations=mutations,
        coverage={
            "functions_with_docstring": fn_with_doc,
            "functions_total": fn_total,
            "classes_with_docstring": cls_with_doc,
            "classes_total": cls_total,
        },
    )


def build_role_view(responsibility_map: dict) -> RoleView:
    """
    Pure transform - wraps Assessor.responsibility_map()'s already
    DB-backed, already-computed role classification (ingestion/
    classification/graph/persistence/reporting per file) into the view
    shape the query algebra expects. No new heuristics, no new DB
    queries: same principle as build_system_summary_view/
    build_subsystem_view, just exposing data that already existed under
    a name Select()/Combine() can address.

    See tools/analysis/docs/Truth.md, Phase 3 findings Row 2: this is
    the fix for the "responsibility/role classification exists, but is
    not reachable" gap.
    """
    return RoleView(
        files=responsibility_map.get("files", []),
        totals=responsibility_map.get("totals", {}),
    )
