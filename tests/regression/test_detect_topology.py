# tests/regression/test_detect_topology.py
#
# Guards detect_topology() shape-counting logic against a minimal in-memory corpus.

import sqlite3
import pytest
from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.agent.agent_tools import detect_topology


def _make_oracle(tmp_path):
    db = tmp_path / "topo.db"
    conn = sqlite3.connect(str(db))
    ensure_schema(conn)
    return DBOracle(str(db)), conn


def _add_fn(conn, name, file_path, is_stub):
    conn.execute(
        "INSERT OR IGNORE INTO functions (name, file_path, is_stub, line_number) VALUES (?,?,?,1)",
        (name, file_path, int(is_stub)),
    )


def _add_edge(conn, caller, callee):
    conn.execute(
        "INSERT OR IGNORE INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number) VALUES (?,?,?,?,?,1)",
        (caller, callee, caller, callee, "x.py"),
    )


# ── T1: direct-call shape ──────────────────────────────────────────────


def test_direct_call_count(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "stub_a", "a.py", True)
    _add_fn(conn, "stub_b", "b.py", True)
    _add_fn(conn, "caller", "c.py", False)
    _add_edge(conn, "caller", "stub_a")  # direct-call: caller -> stub_a
    conn.commit()

    result = detect_topology(oracle, {})
    assert "Direct-call" in result
    # stub_a has a functional caller; stub_b is disconnected
    lines = {l.strip() for l in result.splitlines()}
    dc_line = next(l for l in result.splitlines() if "Direct-call" in l)
    assert "1" in dc_line


# ── T2: disconnected shape ─────────────────────────────────────────��───


def test_disconnected_count(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "island_stub", "d.py", True)
    conn.commit()

    result = detect_topology(oracle, {})
    disc_line = next(l for l in result.splitlines() if "Disconnected" in l)
    assert "1" in disc_line


# ── T3: chain shape ────────────────────────────────────────────────────


def test_chain_count(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "stub_caller", "e.py", True)
    _add_fn(conn, "stub_callee", "f.py", True)
    _add_edge(conn, "stub_caller", "stub_callee")
    conn.commit()

    result = detect_topology(oracle, {})
    chain_line = next(l for l in result.splitlines() if "Chain" in l)
    assert "1" in chain_line


# ── T4: empty corpus ───────────────────────────────────────────────────


def test_empty_corpus(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    conn.commit()

    result = detect_topology(oracle, {})
    assert "CORPUS TOPOLOGY" in result
    assert "Total stubs: 0" in result
    assert "none" in result.lower()


# ── T5: orphaned-impl count ────────────────────────────────────────────


def test_orphaned_impl_count(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "impl_fn", "g.py", False)   # implemented, no callers
    _add_fn(conn, "other_impl", "h.py", False) # has a functional caller
    _add_fn(conn, "fn_caller", "i.py", False)
    _add_edge(conn, "fn_caller", "other_impl")
    conn.commit()

    result = detect_topology(oracle, {})
    orphan_line = next(l for l in result.splitlines() if "Orphaned" in l)
    # impl_fn has no callers -> orphaned; other_impl has fn_caller -> not orphaned
    count = int(orphan_line.strip().split()[1])
    assert count >= 1
