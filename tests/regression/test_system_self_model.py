# tools/analysis/tests/regression/test_system_self_model.py
#
# Coverage for SystemSelfModelBuilder (inspection/meta/system_self_model.py)
# - TRACKER.md open item 19. This capability was found, during the
# 2026-06-18 from-the-beginning codebase review, to be real and live
# (wired into both Assessor.ask() and QuerySession results) but with zero
# direct test coverage anywhere in the suite. These tests lock in its
# actual behavior so future changes to it, or to generate_system_shape()/
# the router module it inspects, can't silently break it unnoticed.
#
# Same fixture pattern as the rest of tests/regression: real temp sqlite
# DB via DBOracle + ensure_schema, no mocking of the DB layer. The one
# exception is test_system_shape_unavailable_records_inference_gap, which
# deliberately uses an INCOMPLETE schema (real missing table, not a mock)
# to exercise the except-and-record-gap branch.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.inspection.meta.system_self_model import SystemSelfModelBuilder


def _oracle(files=None, imports=None, symbols=None, symbol_references=None,
            graph_edges=None, contract_violations=None):
    """
    Real temp sqlite DB, full schema, seeded only with whatever rows a
    given test needs. Every argument defaults to "no rows" so each test
    only has to specify the part of the fixture it actually cares about.
    """
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)

    cur = oracle.conn.cursor()

    for file_path, line_count, role, is_hot in (files or []):
        cur.execute(
            "INSERT INTO files (file_path, line_count, role, is_hot) VALUES (?, ?, ?, ?)",
            (file_path, line_count, role, is_hot),
        )

    for file_path, module, import_type in (imports or []):
        cur.execute(
            "INSERT INTO imports (file_path, module, import_type) VALUES (?, ?, ?)",
            (file_path, module, import_type),
        )

    for file_path, symbol_type, name, canonical_id in (symbols or []):
        cur.execute(
            "INSERT INTO symbols (file_path, symbol_type, name, canonical_id) VALUES (?, ?, ?, ?)",
            (file_path, symbol_type, name, canonical_id),
        )

    for file_path, caller, callee, line_number, bucket in (symbol_references or []):
        cur.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, caller, callee, line_number, bucket),
        )

    for caller, callee, line_number in (graph_edges or []):
        cur.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (caller, callee, caller, callee, line_number),
        )

    for file_path, contract_name, severity, message in (contract_violations or []):
        cur.execute(
            "INSERT INTO contract_violations (file_path, contract_name, severity, message) "
            "VALUES (?, ?, ?, ?)",
            (file_path, contract_name, severity, message),
        )

    oracle.conn.commit()

    return oracle, tmp_path


def test_empty_graph_triggers_failure_mode():
    """Zero graph_edges rows -> get_snapshot_graph().edges == [] ->
    failure_modes must record graph_empty_state, and must NOT also claim
    low_observability_graph (that's the elif branch for a non-empty but
    small graph - the two are mutually exclusive)."""
    oracle, tmp_path = _oracle()
    try:
        model = SystemSelfModelBuilder(oracle).build()
        assert "graph_empty_state" in model.failure_modes
        assert "low_observability_graph" not in model.limitations
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_low_observability_graph_under_ten_edges():
    """1-9 edges -> limitations records low_observability_graph, and
    graph_empty_state must NOT fire (graph isn't empty, just sparse)."""
    edges = [(f"caller_{i}", f"callee_{i}", i) for i in range(3)]
    oracle, tmp_path = _oracle(graph_edges=edges)
    try:
        model = SystemSelfModelBuilder(oracle).build()
        assert "low_observability_graph" in model.limitations
        assert "graph_empty_state" not in model.failure_modes
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_router_present_drives_capabilities_and_biases():
    """tools/analysis/api/oracle_router.py exists in this repo, so
    _router_module_present() must report True, and build() must reflect
    that as both a capability and the two named structural biases - this
    locks in the real, current state rather than a hypothetical one."""
    oracle, tmp_path = _oracle()
    try:
        model = SystemSelfModelBuilder(oracle).build()
        assert "query_expansion_via_router" in model.capabilities
        assert "router_is_primary_decision_layer" in model.structural_biases
        assert "router_expansion_budgets_not_fully_calibrated" in model.structural_biases
        assert "router_module_unreachable" not in model.failure_modes
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_real_oracle_methods_reported_as_capabilities():
    """A real DBOracle always has get_snapshot_graph and
    file_reference_map - build() must report both as capabilities
    (these are verified-real-method checks, not aspirational claims)."""
    oracle, tmp_path = _oracle()
    try:
        model = SystemSelfModelBuilder(oracle).build()
        assert "symbol_graph_traversal" in model.capabilities
        assert "contract_violation_detection" in model.capabilities
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_system_shape_external_contract_and_cross_layer_tags():
    """Seeds data to trigger three system_shape tags at once and confirms
    each maps to the self-model field system_self_model.py says it should:
      - external imports > internal -> external_dependency_dominance (limitation)
      - >20 contract_violations -> contract_coverage_weak (limitation)
      - a builtin-vs-unknown symbol_reference pair -> cross_layer_coupling_present (failure_mode)
    """
    imports = [
        ("a.py", "determined.x", "import"),  # internal: 1
        ("a.py", "numpy", "import"),              # external: 1
        ("a.py", "requests", "import"),           # external: 2 (> internal)
    ]
    violations = [
        ("a.py", "some_contract", "warning", "msg")
        for _ in range(21)  # > 20
    ]
    # "print" classifies as builtin (BUILTIN_HINTS), "mystery_fn" has no
    # module info so classifies as "unknown" - different domains, so this
    # single edge alone produces a cross_bucket_edges entry.
    symbol_references = [("a.py", "print", "mystery_fn", 1, "unknown")]

    oracle, tmp_path = _oracle(
        files=[("a.py", 10, "logic", 0)],
        imports=imports,
        symbol_references=symbol_references,
        contract_violations=violations,
    )
    try:
        model = SystemSelfModelBuilder(oracle).build()
        assert "external_dependency_dominance" in model.limitations
        assert "contract_coverage_weak" in model.limitations
        assert "cross_layer_coupling_present" in model.failure_modes
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_system_shape_hotspot_and_high_coupling_tags():
    """Seeds data to trigger the other two system_shape tags:
      - 1 of 2 files marked hot (> 20% of files) -> analysis_concentrated_in_few_hotspots (bias)
      - one symbol with degree > 50 in symbol_references -> high_coupling_core_risk (failure_mode)
    """
    files = [
        ("hot.py", 50, "logic", 1),
        ("cold.py", 50, "logic", 0),
    ]
    # 51 distinct references from the same caller pushes its node_degree
    # past 50 (each row adds 1 to the caller's degree).
    symbol_references = [
        ("hot.py", "hub_func", f"callee_{i}", i, "project")
        for i in range(51)
    ]

    oracle, tmp_path = _oracle(files=files, symbol_references=symbol_references)
    try:
        model = SystemSelfModelBuilder(oracle).build()
        assert "analysis_concentrated_in_few_hotspots" in model.structural_biases
        assert "high_coupling_core_risk" in model.failure_modes
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_unconditional_inference_gaps_and_notes_always_present():
    """These four are fixed, always-true structural caveats per the
    source comments - they must appear regardless of what data is in the
    DB, not be gated on any runtime check."""
    oracle, tmp_path = _oracle()
    try:
        model = SystemSelfModelBuilder(oracle).build()
        assert "semantic_identity_is_heuristic_not_ground_truth" in model.inference_gaps
        assert "edge_bucket_assignment_is_best_effort_classification" in model.inference_gaps
        assert "system_self_model_is_derivative_not_authoritative" in model.notes
        assert "self_model_reflects_db_snapshot_at_query_time_not_live_state" in model.notes
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_system_shape_unavailable_records_inference_gap():
    """If generate_system_shape() raises (here: a real missing table, not
    a mock - the DB only has graph_edges, nothing else), build() must
    catch it and record system_shape_unavailable:<ExceptionType> in
    inference_gaps rather than propagating the error or silently
    producing an incomplete shape."""
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    cur = oracle.conn.cursor()
    # Deliberately incomplete schema: graph_edges only, so
    # get_snapshot_graph() succeeds but generate_system_shape()'s first
    # query (SELECT ... FROM files) hits a real "no such table" error.
    cur.execute("""
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            caller TEXT,
            callee TEXT,
            line_number INTEGER
        )
    """)
    oracle.conn.commit()

    try:
        model = SystemSelfModelBuilder(oracle).build()
        matching = [g for g in model.inference_gaps if g.startswith("system_shape_unavailable:")]
        assert matching, f"expected a system_shape_unavailable:* entry, got {model.inference_gaps}"
        assert matching[0] == "system_shape_unavailable:OperationalError"
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


if __name__ == "__main__":
    tests = [
        test_empty_graph_triggers_failure_mode,
        test_low_observability_graph_under_ten_edges,
        test_router_present_drives_capabilities_and_biases,
        test_real_oracle_methods_reported_as_capabilities,
        test_system_shape_external_contract_and_cross_layer_tags,
        test_system_shape_hotspot_and_high_coupling_tags,
        test_unconditional_inference_gaps_and_notes_always_present,
        test_system_shape_unavailable_records_inference_gap,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
