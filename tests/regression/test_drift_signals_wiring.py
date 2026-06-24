# tools/analysis/tests/regression/test_drift_signals_wiring.py
#
# Locks in the 2026-06-17 drift_signals fix (Truth.md Phase 3 Row 3 /
# Truth Kernel Board.md Tier 1): Assessor.stability_view() used to call
# build_stability_view(reports, drift_signals=[]) - hardcoded empty,
# even though ContractDriftClassifier (contracts/contract_drift_classifier.py)
# already existed with the exact output shape build_stability_view() expects.
# It just had zero callers anywhere in the codebase. The fix wires the two
# together - same "orphaned primitive" shape as the SUMMARY/SUBSYSTEM/ROLE
# gaps fixed earlier this week, same fix.
#
# Also locks in the shape-safety fix to ContractDriftClassifier._field():
# the violations Assessor.file_contract_reports() actually produces are
# plain dicts, not the ContractViolation dataclass from the (dead,
# zero-caller) contracts/contract_observer.py path. classify() must work
# against the real dict shape without assuming attribute access.
#
# Same fixture pattern as test_discovery_api_and_subsystem_fix.py /
# test_run_algebra_end_to_end.py: real temp sqlite DB, real schema via
# ensure_schema, no mocking of the DB layer.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.contracts.contract_drift_classifier import (
    ContractDriftClassifier,
    ContractDriftSignal,
    _field,
)


def _oracle_with_broken_references(broken_count, file_path="moduleA/core.py"):
    """
    Real temp DB seeded with `broken_count` symbol_references rows that
    have a null callee - each one trips the symbol_reference_integrity
    contract in Assessor.file_contract_reports(), so the resulting
    ContractReport.violations list has exactly `broken_count` dict-shaped
    violations to feed the classifier.
    """
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)

    cur = oracle.conn.cursor()
    cur.execute(
        "INSERT INTO files (file_path, line_count, role, is_hot) VALUES (?, ?, ?, ?)",
        (file_path, 50, "logic", 0),
    )

    for i in range(broken_count):
        cur.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, "some_caller", None, 10 + i, "project"),
        )

    oracle.conn.commit()
    return oracle, tmp_path


# =========================================================
# 1. Assessor.stability_view() actually populates drift_signals
# =========================================================

def test_stability_view_populates_drift_signals_not_hardcoded_empty():
    oracle, tmp_path = _oracle_with_broken_references(broken_count=2)
    try:
        assessor = Assessor(oracle)
        view = assessor.stability_view()

        assert view.drift_signals != []
        assert len(view.drift_signals) == 1

        signal = view.drift_signals[0]
        assert signal["contract"] == "symbol_reference_integrity"
        assert signal["layer"] == "graph"
        assert signal["count"] == 2
        assert signal["class"] == "recurring"  # 2-3 -> recurring
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 2. Classification thresholds, end-to-end through Assessor
# =========================================================

def test_classification_thresholds_transient_recurring_structural():
    cases = [
        (1, "transient"),
        (3, "recurring"),
        (5, "structural"),
    ]
    for broken_count, expected_class in cases:
        oracle, tmp_path = _oracle_with_broken_references(broken_count=broken_count)
        try:
            assessor = Assessor(oracle)
            view = assessor.stability_view()
            assert len(view.drift_signals) == 1
            assert view.drift_signals[0]["count"] == broken_count
            assert view.drift_signals[0]["class"] == expected_class
        finally:
            oracle.conn.close()
            os.remove(tmp_path)


# =========================================================
# 3. No violations -> no drift signals (not even an empty-but-wrong shape)
# =========================================================

def test_no_violations_yields_no_drift_signals():
    oracle, tmp_path = _oracle_with_broken_references(broken_count=0)
    try:
        assessor = Assessor(oracle)
        view = assessor.stability_view()
        assert view.drift_signals == []
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 4. drift_signals reachable through the query algebra (STABILITY view
#    was already registered in query_plan.py's VALID_METRICS before this
#    fix - this confirms ask()/run_algebra() now return real data for it,
#    not just that the registry entry exists).
# =========================================================

def test_drift_signals_reachable_via_ask():
    oracle, tmp_path = _oracle_with_broken_references(broken_count=4)
    try:
        assessor = Assessor(oracle)
        views = assessor.all_views()
        assert views["STABILITY"].drift_signals != []
        assert views["STABILITY"].drift_signals[0]["class"] == "structural"
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 5. ContractDriftClassifier shape-safety: works on plain dicts (the real
#    production shape) AND on attribute-style objects (the dead
#    contract_observer.py ContractViolation shape) without modification.
# =========================================================

def test_field_helper_handles_dict_and_attribute_shapes():
    dict_violation = {"contract_name": "x", "severity": "error", "layer": "graph"}
    assert _field(dict_violation, "contract_name") == "x"
    assert _field(dict_violation, "missing_key", "default") == "default"

    class FakeAttrViolation:
        contract_name = "y"
        severity = "warning"

    attr_violation = FakeAttrViolation()
    assert _field(attr_violation, "contract_name") == "y"
    assert _field(attr_violation, "layer", "unknown") == "unknown"


def test_classifier_handles_mixed_dict_and_attribute_violations():
    class FakeReport:
        def __init__(self, violations):
            self.violations = violations

    class FakeAttrViolation:
        def __init__(self, contract_name, severity, layer):
            self.contract_name = contract_name
            self.severity = severity
            self.layer = layer

    reports = [
        FakeReport([
            {"contract_name": "dict_contract", "severity": "error", "layer": "graph"},
        ]),
        FakeReport([
            FakeAttrViolation("attr_contract", "error", "persistence"),
        ]),
    ]

    signals = ContractDriftClassifier().classify(reports)
    by_name = {s.contract_name: s for s in signals}

    assert "dict_contract" in by_name
    assert "attr_contract" in by_name
    assert by_name["dict_contract"].layer == "graph"
    assert by_name["attr_contract"].layer == "persistence"
    assert all(isinstance(s, ContractDriftSignal) for s in signals)


if __name__ == "__main__":
    tests = [
        test_stability_view_populates_drift_signals_not_hardcoded_empty,
        test_classification_thresholds_transient_recurring_structural,
        test_no_violations_yields_no_drift_signals,
        test_drift_signals_reachable_via_ask,
        test_field_helper_handles_dict_and_attribute_shapes,
        test_classifier_handles_mixed_dict_and_attribute_violations,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
