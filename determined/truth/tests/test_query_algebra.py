# tools/analysis/truth/tests/test_query_algebra.py

import pytest

from determined.truth.query_ast import Select, Combine, Filter
from determined.truth.query_plan import QueryPlanner, QuerySemanticsRegistry, QueryPlan
from determined.truth.query_executor import QueryExecutor, QueryResult, CombineResult


registry = QuerySemanticsRegistry()
planner = QueryPlanner(registry)


def plan(q):
    return planner.plan(q).root


# =========================================================
# FIXTURES — minimal view stubs for executor tests
# =========================================================

class _StructureViewStub:
    edges = [("a", "b"), ("b", "c")]
    adjacency = {"a": {"b"}, "b": {"c"}}
    hotspots = [("b", 2), ("a", 1), ("c", 1)]


class _StabilityViewStub:
    stable_contracts = ["file_a.py", "file_b.py"]
    unstable_contracts = []
    drift_signals = []


class _IntegrityViewStub:
    errors = ["missing caller at line 10"]
    warnings = []
    db_mismatches = []


VIEWS = {
    "STRUCTURE": _StructureViewStub(),
    "STABILITY": _StabilityViewStub(),
    "INTEGRITY": _IntegrityViewStub(),
    "SUMMARY": {"edge_count": 2, "file_count": 3, "metrics": {}},
    "SUBSYSTEM": {"subsystems": ["api", "oracle"]},
}

executor = QueryExecutor(views=VIEWS)


def execute(q):
    plan_ = planner.plan(q)
    return executor.execute(plan_.root)


# =========================================================
# VALID COMBINES — planner
# =========================================================

def test_valid_structure_stability():
    plan(Combine(Select("STRUCTURE"), Select("STABILITY")))


def test_valid_structure_integrity():
    plan(Combine(Select("STRUCTURE"), Select("INTEGRITY")))


def test_valid_summary_stability():
    plan(Combine(Select("SUMMARY"), Select("STABILITY")))


def test_valid_subsystem_structure():
    plan(Combine(Select("SUBSYSTEM"), Select("STRUCTURE")))


def test_valid_stability_integrity():
    # added as valid combine — both are diagnostic views
    plan(Combine(Select("STABILITY"), Select("INTEGRITY")))


# =========================================================
# INVALID COMBINES — planner
# =========================================================

def test_invalid_same_view():
    with pytest.raises(ValueError):
        plan(Combine(Select("STRUCTURE"), Select("STRUCTURE")))


def test_invalid_unregistered_combine():
    # SUMMARY + INTEGRITY is not a registered combine pair
    with pytest.raises(ValueError):
        plan(Combine(Select("SUMMARY"), Select("INTEGRITY")))


def test_nested_combine_rejected():
    with pytest.raises(ValueError):
        plan(Combine(
            Combine(Select("STRUCTURE"), Select("STABILITY")),
            Select("INTEGRITY"),
        ))


def test_filter_as_root_rejected():
    with pytest.raises(ValueError):
        plan(Filter(key="edges", op=">", value=10))


# =========================================================
# VALID METRICS — planner
# =========================================================

def test_valid_metric_hotspots():
    plan(Select("STRUCTURE", metric="hotspots"))


def test_valid_metric_stable_contracts():
    plan(Select("STABILITY", metric="stable_contracts"))


def test_valid_metric_errors():
    plan(Select("INTEGRITY", metric="errors"))


def test_valid_metric_edge_count():
    plan(Select("SUMMARY", metric="edge_count"))


# =========================================================
# INVALID METRICS — planner
# =========================================================

def test_invalid_metric_for_view():
    with pytest.raises(ValueError):
        plan(Select("STRUCTURE", metric="errors"))


def test_unknown_view():
    with pytest.raises(ValueError):
        plan(Select("NONEXISTENT"))


# =========================================================
# VALID FILTERS — planner
# =========================================================

def test_filter_caller_allowed():
    plan(Select("STRUCTURE", filter=Filter("caller", "==", "foo")))


def test_filter_hotspots_allowed():
    plan(Select("STRUCTURE", filter=Filter("hotspots", ">", 5)))


def test_filter_stable_contracts_allowed():
    plan(Select("STABILITY", filter=Filter("stable_contracts", "==", "file_a.py")))


# =========================================================
# INVALID FILTERS — planner
# =========================================================

def test_invalid_filter_key_for_view():
    with pytest.raises(ValueError):
        plan(Select("STRUCTURE", filter=Filter("errors", "==", "x")))


def test_filter_not_allowed_on_integrity():
    # INTEGRITY has no VALID_FILTER_KEYS entry
    with pytest.raises(ValueError):
        plan(Select("INTEGRITY", filter=Filter("errors", ">", 0)))


# =========================================================
# EXECUTOR — SELECT
# =========================================================

def test_executor_select_structure_full():
    r = execute(Select("STRUCTURE"))
    assert isinstance(r, QueryResult)
    assert r.view == "STRUCTURE"
    assert r.metric is None
    assert r.data is VIEWS["STRUCTURE"]


def test_executor_select_hotspots():
    r = execute(Select("STRUCTURE", metric="hotspots"))
    assert isinstance(r, QueryResult)
    assert r.metric == "hotspots"
    assert isinstance(r.data, list)
    assert len(r.data) > 0


def test_executor_select_stability_full():
    r = execute(Select("STABILITY"))
    assert isinstance(r, QueryResult)
    assert r.view == "STABILITY"


def test_executor_select_stability_metric():
    r = execute(Select("STABILITY", metric="stable_contracts"))
    assert isinstance(r, QueryResult)
    assert r.data == ["file_a.py", "file_b.py"]


def test_executor_select_integrity_full():
    r = execute(Select("INTEGRITY"))
    assert isinstance(r, QueryResult)
    assert r.view == "INTEGRITY"


def test_executor_select_integrity_errors():
    r = execute(Select("INTEGRITY", metric="errors"))
    assert isinstance(r, QueryResult)
    assert "missing caller at line 10" in r.data


def test_executor_select_summary_edge_count():
    r = execute(Select("SUMMARY", metric="edge_count"))
    assert r.data == 2


# =========================================================
# EXECUTOR — COMBINE
# =========================================================

def test_executor_combine_structure_stability():
    r = execute(Combine(Select("STRUCTURE"), Select("STABILITY")))
    assert isinstance(r, CombineResult)
    assert isinstance(r.left, QueryResult)
    assert isinstance(r.right, QueryResult)
    assert r.left.view == "STRUCTURE"
    assert r.right.view == "STABILITY"


def test_executor_combine_stability_integrity():
    r = execute(Combine(Select("STABILITY"), Select("INTEGRITY")))
    assert isinstance(r, CombineResult)
    assert r.left.view == "STABILITY"
    assert r.right.view == "INTEGRITY"


def test_executor_combine_is_structural_join_only():
    # Combine must NOT merge or interpret — it returns two independent results
    r = execute(Combine(Select("STRUCTURE"), Select("INTEGRITY")))
    assert isinstance(r, CombineResult)
    assert r.left.data is not r.right.data


# =========================================================
# EXECUTOR — DETERMINISM
# =========================================================

def test_executor_same_query_same_result():
    q = Select("STRUCTURE", metric="hotspots")
    r1 = execute(q)
    r2 = execute(q)
    assert r1.data == r2.data


def test_executor_combine_deterministic():
    q = Combine(Select("STRUCTURE"), Select("STABILITY"))
    r1 = execute(q)
    r2 = execute(q)
    assert r1.left.data == r2.left.data
    assert r1.right.data == r2.right.data