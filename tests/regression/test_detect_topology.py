# tests/regression/test_detect_topology.py
#
# Guards detect_topology(), find_orphaned_impls(), find_conditional_stubs(),
# and frontier_priority() topology tools.

import sqlite3
import textwrap
from pathlib import Path
from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.agent.agent_tools import (
    detect_topology,
    find_orphaned_impls,
    find_conditional_stubs,
    frontier_priority,
)


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


# ── detect_topology: direct-call shape ────────────────────────────────


def test_direct_call_count(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "stub_a", "a.py", True)
    _add_fn(conn, "stub_b", "b.py", True)
    _add_fn(conn, "caller", "c.py", False)
    _add_edge(conn, "caller", "stub_a")
    conn.commit()

    result = detect_topology(oracle, {})
    dc_line = next(l for l in result.splitlines() if "Direct-call" in l)
    assert "1" in dc_line


# ── detect_topology: disconnected shape ───────────────────────────────


def test_disconnected_count(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "island_stub", "d.py", True)
    conn.commit()

    result = detect_topology(oracle, {})
    disc_line = next(l for l in result.splitlines() if "Disconnected" in l)
    assert "1" in disc_line


# ── detect_topology: chain-tail / chain-head split ────────────────────


def test_chain_tail_detected(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    # functional -> stub_head -> stub_tail
    _add_fn(conn, "functional", "a.py", False)
    _add_fn(conn, "stub_head", "b.py", True)
    _add_fn(conn, "stub_tail", "c.py", True)
    _add_edge(conn, "functional", "stub_head")
    _add_edge(conn, "stub_head", "stub_tail")
    conn.commit()

    result = detect_topology(oracle, {})
    head_line = next(l for l in result.splitlines() if "Chain-head" in l)
    tail_line = next(l for l in result.splitlines() if "Chain-tail" in l)
    assert "1" in head_line
    assert "1" in tail_line


def test_chain_middle_detected(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    # functional -> stub_a -> stub_b -> stub_c
    _add_fn(conn, "fn", "a.py", False)
    _add_fn(conn, "sa", "b.py", True)
    _add_fn(conn, "sb", "c.py", True)
    _add_fn(conn, "sc", "d.py", True)
    _add_edge(conn, "fn", "sa")
    _add_edge(conn, "sa", "sb")
    _add_edge(conn, "sb", "sc")
    conn.commit()

    result = detect_topology(oracle, {})
    mid_line = next(l for l in result.splitlines() if "Chain-middle" in l)
    tail_line = next(l for l in result.splitlines() if "Chain-tail" in l)
    assert "1" in mid_line   # sb is middle
    assert "1" in tail_line  # sc is tail


# ── detect_topology: empty corpus ─────────────────────────────────────


def test_empty_corpus(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    conn.commit()

    result = detect_topology(oracle, {})
    assert "CORPUS TOPOLOGY" in result
    assert "Total stubs: 0" in result
    assert "Action queues" in result


# ── detect_topology: orphaned-impl count ──────────────────────────────


def test_orphaned_impl_count(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "impl_fn", "g.py", False)    # no callers -> orphaned
    _add_fn(conn, "other_impl", "h.py", False) # has functional caller -> not orphaned
    _add_fn(conn, "fn_caller", "i.py", False)
    _add_edge(conn, "fn_caller", "other_impl")
    conn.commit()

    result = detect_topology(oracle, {})
    orphan_line = next(l for l in result.splitlines() if "Orphaned-impl" in l)
    count = int(orphan_line.strip().split()[1])
    assert count >= 1


# ── detect_topology: entry-point hint ─────────────────────────────────


def test_entry_point_separated_from_disconnected(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "handle_login", "handlers/auth.py", True)   # entry-point hint
    _add_fn(conn, "plain_stub", "utils.py", True)              # truly disconnected
    conn.commit()

    result = detect_topology(oracle, {})
    ep_line   = next(l for l in result.splitlines() if "Entry-point" in l)
    disc_line = next(l for l in result.splitlines() if "Disconnected" in l)
    # handle_login should go to entry-point, plain_stub to disconnected
    assert "1" in ep_line
    assert "1" in disc_line


# ── find_orphaned_impls: labels ────────────────────────────────────────


def test_find_orphaned_impls_anticipatory(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "lonely_impl", "a.py", False)
    conn.commit()

    result = find_orphaned_impls(oracle, {})
    assert "lonely_impl" in result
    assert "anticipatory" in result


def test_find_orphaned_impls_possibly_stranded(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "impl_fn", "a.py", False)
    _add_fn(conn, "stub_caller", "b.py", True)
    _add_edge(conn, "stub_caller", "impl_fn")
    conn.commit()

    result = find_orphaned_impls(oracle, {})
    assert "impl_fn" in result
    assert "possibly-stranded" in result


def test_find_orphaned_impls_excludes_called(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "called_impl", "a.py", False)
    _add_fn(conn, "caller_impl", "b.py", False)
    _add_edge(conn, "caller_impl", "called_impl")
    conn.commit()

    result = find_orphaned_impls(oracle, {})
    assert "called_impl" not in result


def test_find_orphaned_impls_empty(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    conn.commit()

    result = find_orphaned_impls(oracle, {})
    assert "No orphaned" in result


# ── find_conditional_stubs ─────────────────────────────────────────────


def test_find_conditional_stubs_detects_branched_nie(tmp_path):
    src = textwrap.dedent("""\
        def process(mode):
            if mode == 'advanced':
                raise NotImplementedError
            return mode
    """)
    src_file = tmp_path / "proc.py"
    src_file.write_text(src)

    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "process", str(src_file), False)
    conn.commit()

    result = find_conditional_stubs(oracle, {})
    assert "process" in result
    assert "proc.py" in result


def test_find_conditional_stubs_ignores_unconditional_nie(tmp_path):
    src = textwrap.dedent("""\
        def not_done():
            raise NotImplementedError
    """)
    src_file = tmp_path / "nd.py"
    src_file.write_text(src)

    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "not_done", str(src_file), False)
    conn.commit()

    # Unconditional raise at top level — no 'if' before it
    result = find_conditional_stubs(oracle, {})
    assert "not_done" not in result


def test_find_conditional_stubs_empty(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    conn.commit()

    result = find_conditional_stubs(oracle, {})
    assert "No" in result  # either "No implemented functions" or "No conditional stubs"


# ── frontier_priority: chain-tail scores highest ───────────────────────


def test_frontier_priority_tail_beats_direct_call(tmp_path):
    oracle, conn = _make_oracle(tmp_path)
    # direct-call stub: 1 functional caller, no chain involvement
    _add_fn(conn, "direct_stub", "a.py", True)
    _add_fn(conn, "fn_caller", "b.py", False)
    _add_edge(conn, "fn_caller", "direct_stub")

    # chain: functional -> head_stub -> tail_stub (tail has 0 direct functional callers)
    _add_fn(conn, "head_stub", "c.py", True)
    _add_fn(conn, "tail_stub", "d.py", True)
    _add_edge(conn, "fn_caller", "head_stub")
    _add_edge(conn, "head_stub", "tail_stub")
    conn.commit()

    result = frontier_priority(oracle, {})
    lines = [l for l in result.splitlines() if l.strip().startswith(("Score", "─", "  ")) and any(c.isdigit() for c in l)]
    # First data row should be either tail_stub (score=5) or head_stub (score=1+1=2)
    # tail_stub: 0 callers + 5 (tail bonus) = 5
    # direct_stub: 1 caller = 1
    # head_stub: 1 caller + 1 (head bonus) = 2
    assert "tail_stub" in result
    # tail_stub should appear before direct_stub
    tail_pos = result.index("tail_stub")
    direct_pos = result.index("direct_stub")
    assert tail_pos < direct_pos
