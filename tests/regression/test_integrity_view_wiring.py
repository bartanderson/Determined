# tools/analysis/tests/regression/test_integrity_view_wiring.py
#
# Locks in the 2026-06-18 fix for TRACKER.md open item 17: the INTEGRITY
# view was thinner than the codebase's own existing validation logic.
#
# Two distinct things were wrong, fixed together here:
#
# 1. SystemValidator._validate_contracts() read each violation's
#    severity/contract_name/message via bare getattr(v, "severity", None).
#    That's correct for the attribute-style ContractViolation dataclass
#    (contracts/contract_observer.py) but silently wrong for the
#    dict-shaped violations Assessor.file_contract_reports() actually
#    produces in production: getattr(dict, "severity", None) does not
#    raise, it just always returns the default - so an error-severity
#    violation would never escalate, with no visible failure. Fixed via
#    a shape-safe _field() helper (same precedent as
#    contracts/contract_drift_classifier.py's _field()). Assessor.
#    validation_summary() was also changed to call this real
#    SystemValidator method (plus _validate_graph_integrity/
#    _validate_shape_signals) instead of a second, parallel inline
#    reimplementation.
#
# 2. IntegrityView.db_mismatches was permanently hardcoded [] in
#    truth/views.py ("no DB comparison anymore"). Assessor.
#    run_integrity_check() already computes a genuine DB-internal
#    mismatch signal - graph_edges count vs symbol_references count,
#    two persisted tables that are supposed to agree - but had no path
#    into the Truth Layer. Assessor.db_mismatches() extracts exactly
#    that signal; Assessor.integrity_view() now passes it through.
#
# Same fixture pattern as the other regression tests: real temp sqlite
# DB, real schema via ensure_schema, no mocking of the DB layer.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.validation.system_validator import SystemValidator, _field


def _oracle_with(reference_rows, edge_rows, file_rows=None, symbol_rows=None):
    """Minimal seeded DB - just enough for file_contract_reports()/
    run_integrity_check() to have real data to work from."""
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)

    cur = oracle.conn.cursor()

    for file_path, line_count, role, is_hot in (file_rows or []):
        cur.execute(
            "INSERT INTO files (file_path, line_count, role, is_hot) VALUES (?, ?, ?, ?)",
            (file_path, line_count, role, is_hot),
        )

    for file_path, symbol_type, name, line_number, signature, canonical_id in (symbol_rows or []):
        cur.execute(
            "INSERT INTO symbols (file_path, symbol_type, name, line_number, signature, canonical_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (file_path, symbol_type, name, line_number, signature, canonical_id),
        )

    for file_path, caller, callee, line_number, bucket in reference_rows:
        cur.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, caller, callee, line_number, bucket),
        )

    for caller, callee, line_number in edge_rows:
        cur.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (caller, callee, caller, callee, line_number),
        )

    oracle.conn.commit()
    return oracle, tmp_path


# ---------------------------------------------------------------
# 1. Shape-safety fix, at the unit level: _validate_contracts() must
#    escalate a dict-shaped error violation, not silently swallow it.
# ---------------------------------------------------------------

def test_field_reads_dicts_and_attribute_objects():
    class Obj:
        severity = "error"

    assert _field({"severity": "error"}, "severity") == "error"
    assert _field(Obj(), "severity") == "error"
    assert _field({}, "severity", "default") == "default"


def test_validate_contracts_escalates_dict_shaped_error_violation():
    class _Report:
        def __init__(self, violations):
            self.violations = violations

    report = _Report(violations=[
        {"contract_name": "symbol_reference_integrity", "severity": "error",
         "layer": "graph", "message": "Invalid symbol reference at line 10"},
        {"contract_name": "some_other_contract", "severity": "warning",
         "layer": "graph", "message": "not escalated"},
    ])

    errors = SystemValidator()._validate_contracts(report)

    assert any("symbol_reference_integrity" in e for e in errors)
    assert all("not escalated" not in e for e in errors)


# ---------------------------------------------------------------
# 2. Integration: Assessor.validation_summary() escalates a real
#    contract violation produced by file_contract_reports() (a null
#    caller/callee row) end to end through the real SystemValidator path.
# ---------------------------------------------------------------

def test_validation_summary_escalates_real_invalid_reference():
    oracle, tmp_path = _oracle_with(
        reference_rows=[
            ("moduleA/core.py", "do_thing", None, 10, "project"),
        ],
        edge_rows=[("do_thing", "x", 10)] * 10,  # avoid the low-edge-count warning noise
    )
    try:
        summary = Assessor(oracle).validation_summary()
        assert any("symbol_reference_integrity" in e or "Invalid symbol reference" in e
                   for e in summary.errors)
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_validation_summary_low_edge_count_warning_preserved():
    oracle, tmp_path = _oracle_with(
        reference_rows=[("moduleA/core.py", "do_thing", "helper", 10, "project")],
        edge_rows=[("do_thing", "helper", 10)],
    )
    try:
        summary = Assessor(oracle).validation_summary()
        assert any("Low edge count" in w for w in summary.warnings)
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# ---------------------------------------------------------------
# 3. db_mismatches: the genuine new capability. graph_edges and
#    symbol_references are independently seeded here so their counts can
#    disagree, exactly like a real partial/interrupted persistence run.
# ---------------------------------------------------------------

def test_db_mismatches_detects_real_table_count_disagreement():
    oracle, tmp_path = _oracle_with(
        reference_rows=[
            ("moduleA/core.py", "do_thing", "helper", 10, "project"),
            ("moduleA/core.py", "do_thing", "other", 11, "project"),
        ],
        edge_rows=[
            ("do_thing", "helper", 10),
        ],  # only 1 graph_edges row vs 2 symbol_references rows
    )
    try:
        assessor = Assessor(oracle)
        mismatches = assessor.db_mismatches()

        assert len(mismatches) == 1
        assert "edge_count_mismatch" in mismatches[0]
        assert "graph_edges=1" in mismatches[0]
        assert "symbol_references=2" in mismatches[0]

        # production path: integrity_view() must carry it through too
        view = assessor.integrity_view()
        assert view.db_mismatches == mismatches
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_db_mismatches_empty_when_tables_agree():
    oracle, tmp_path = _oracle_with(
        reference_rows=[("moduleA/core.py", "do_thing", "helper", 10, "project")],
        edge_rows=[("do_thing", "helper", 10)],
    )
    try:
        assessor = Assessor(oracle)
        assert assessor.db_mismatches() == []
        assert assessor.integrity_view().db_mismatches == []
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


if __name__ == "__main__":
    tests = [
        test_field_reads_dicts_and_attribute_objects,
        test_validate_contracts_escalates_dict_shaped_error_violation,
        test_validation_summary_escalates_real_invalid_reference,
        test_validation_summary_low_edge_count_warning_preserved,
        test_db_mismatches_detects_real_table_count_disagreement,
        test_db_mismatches_empty_when_tables_agree,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
