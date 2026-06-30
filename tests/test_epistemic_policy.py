# tests/test_epistemic_policy.py
#
# Unit tests for EpistemicPolicy risk math.
# Uses real view dataclass shapes from determined/truth/views.py.
# No mocks, no LLM, deterministic synthetic inputs only.

from types import SimpleNamespace
from determined.assessor.epistemic_policy import (
    EpistemicPolicy,
    CYCLE_RISK,
    ERROR_RISK_PER,
    ERROR_RISK_CAP,
    DRIFT_RISK_SCALE,
    HOTSPOT_THRESHOLD,
    HOTSPOT_RISK,
)
from determined.truth.views import (
    StructureView,
    StabilityView,
    IntegrityView,
    SystemSummaryView,
    RoleView,
)


def _make_views(
    adjacency=None,
    hotspots=None,
    errors=None,
    warnings=None,
    db_mismatches=None,
    stable=None,
    unstable=None,
    drift_signals=None,
    edge_count=0,
    file_count=0,
    metrics=None,
    role_files=None,
):
    structure = StructureView(
        edges=[],
        adjacency=adjacency or {},
        hotspots=hotspots or [],
    )
    integrity = IntegrityView(
        errors=errors or [],
        warnings=warnings or [],
        db_mismatches=db_mismatches or [],
    )
    stability = StabilityView(
        stable_contracts=stable or [],
        unstable_contracts=unstable or [],
        drift_signals=drift_signals or [],
    )
    summary = SystemSummaryView(
        edge_count=edge_count,
        file_count=file_count,
        metrics=metrics or {},
    )
    role = RoleView(files=role_files or [], totals={})
    return structure, integrity, stability, summary, role


def _analyze(**kwargs):
    policy = EpistemicPolicy()
    s, i, st, su, r = _make_views(**kwargs)
    return policy.analyze(s, i, st, su, r)


# ------------------------------------------------------------------
# Structure
# ------------------------------------------------------------------

def test_no_cycles_zero_structure_risk():
    # A -> B, no cycle
    result = _analyze(adjacency={"A": {"B"}})
    assert result.risk_vector["structure"] == 0.0


def test_cycle_adds_structure_risk():
    # A -> B -> A
    result = _analyze(adjacency={"A": {"B"}, "B": {"A"}})
    assert result.risk_vector["structure"] == CYCLE_RISK
    assert result.severity >= CYCLE_RISK
    assert "STRUCTURE" in result.required_surfaces


def test_self_loop_is_a_cycle():
    result = _analyze(adjacency={"A": {"A"}})
    assert result.risk_vector["structure"] == CYCLE_RISK


# ------------------------------------------------------------------
# Integrity
# ------------------------------------------------------------------

def test_zero_errors_zero_integrity_risk():
    result = _analyze()
    assert result.risk_vector["integrity"] == 0.0


def test_single_error_adds_risk():
    result = _analyze(errors=["e1"])
    assert result.risk_vector["integrity"] == ERROR_RISK_PER


def test_integrity_risk_caps_at_error_cap():
    # 100 errors should not exceed ERROR_RISK_CAP
    result = _analyze(errors=[f"e{i}" for i in range(100)])
    assert result.risk_vector["integrity"] == ERROR_RISK_CAP


# ------------------------------------------------------------------
# Stability
# ------------------------------------------------------------------

def test_all_stable_zero_stability_risk():
    result = _analyze(stable=["a", "b", "c"])
    assert result.risk_vector["stability"] == 0.0


def test_all_unstable_max_stability_risk():
    result = _analyze(unstable=["a", "b"])
    assert abs(result.risk_vector["stability"] - DRIFT_RISK_SCALE) < 1e-9


def test_partial_instability_scales_correctly():
    # 1 of 4 unstable -> ratio = 0.25
    result = _analyze(stable=["a", "b", "c"], unstable=["d"])
    expected = 0.25 * DRIFT_RISK_SCALE
    assert abs(result.risk_vector["stability"] - expected) < 1e-9


# ------------------------------------------------------------------
# Severity clamping
# ------------------------------------------------------------------

def test_severity_never_exceeds_1():
    result = _analyze(
        adjacency={"A": {"B"}, "B": {"A"}},
        errors=[f"e{i}" for i in range(100)],
        unstable=[f"u{i}" for i in range(100)],
        edge_count=1000,
        hotspots=[("X", HOTSPOT_THRESHOLD + 1)],
    )
    assert result.severity <= 1.0


def test_severity_never_below_0():
    result = _analyze()
    assert result.severity >= 0.0


# ------------------------------------------------------------------
# Required surfaces
# ------------------------------------------------------------------

def test_integrity_always_in_required_surfaces():
    result = _analyze()
    assert "INTEGRITY" in result.required_surfaces


def test_stability_surface_required_when_mostly_unstable():
    # 2 of 3 unstable -> ratio ~0.67, above DRIFT_THRESHOLD
    result = _analyze(stable=["a"], unstable=["b", "c"])
    assert "STABILITY" in result.required_surfaces
