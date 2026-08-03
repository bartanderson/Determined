# tests/regression/test_detect_topology.py
#
# Guards detect_topology(), find_orphaned_impls(), find_conditional_stubs(),
# frontier_priority(), find_pure_functions(), find_hot_callers(),
# find_large_files(), find_fetch_calls(), and find_cross_language_calls() tools.

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
    find_pure_functions,
    find_hot_callers,
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


# ── find_pure_functions ───────────────────────────────────────────────


def test_pure_functions_zero_mutation_file_included(tmp_path):
    """Functions in files with no mutations are reported as pure candidates."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "pure_fn", "pure.py", False)
    conn.commit()
    result = find_pure_functions(oracle, {})
    assert "pure_fn" in result
    assert "pure.py" in result


def test_pure_functions_mutation_file_excluded(tmp_path):
    """Functions in files that have mutations are not returned."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "dirty_fn", "dirty.py", False)
    conn.execute(
        "INSERT INTO mutations (file_path, line_number, target, operation) VALUES (?,?,?,?)",
        ("dirty.py", 10, "self", "assign"),
    )
    conn.commit()
    result = find_pure_functions(oracle, {})
    assert "dirty_fn" not in result


def test_pure_functions_memo_flag_on_multi_caller(tmp_path):
    """Functions called from 2+ places are flagged [memo]."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "util_fn", "utils.py", False)
    _add_fn(conn, "caller_a", "a.py", False)
    _add_fn(conn, "caller_b", "b.py", False)
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved) VALUES (1,2,?,?,?,1,1)",
        ("caller_a", "util_fn", "a.py"),
    )
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved) VALUES (2,2,?,?,?,1,1)",
        ("caller_b", "util_fn", "b.py"),
    )
    conn.commit()
    result = find_pure_functions(oracle, {})
    assert "[memo]" in result
    assert "util_fn" in result


def test_pure_functions_stubs_excluded(tmp_path):
    """Stubs are not reported even if their file has no mutations."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "stub_fn", "iface.py", True)
    conn.commit()
    result = find_pure_functions(oracle, {})
    assert "stub_fn" not in result


def test_pure_functions_json_entries_excluded(tmp_path):
    """FSM state/event nodes stored under .json paths are not returned."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "TradeFSM::state::completed", "config/fsms/trade.json", False)
    _add_fn(conn, "real_fn", "utils.py", False)
    conn.commit()
    result = find_pure_functions(oracle, {})
    assert "TradeFSM" not in result
    assert "trade.json" not in result
    assert "real_fn" in result


# ── find_hot_callers ─────────────────────────────────────────────────


def test_hot_callers_ranked_by_caller_count(tmp_path):
    """Functions with more distinct callers appear higher in results."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "hot_fn", "core.py", False)
    _add_fn(conn, "cold_fn", "core.py", False)
    _add_fn(conn, "caller_a", "a.py", False)
    _add_fn(conn, "caller_b", "b.py", False)
    # hot_fn called from 2 places (resolved)
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved) VALUES (1,2,?,?,?,1,1)",
        ("caller_a", "hot_fn", "a.py"),
    )
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved) VALUES (1,2,?,?,?,1,1)",
        ("caller_b", "hot_fn", "b.py"),
    )
    # cold_fn called from 1 place (resolved)
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved) VALUES (1,2,?,?,?,1,1)",
        ("caller_a", "cold_fn", "a.py"),
    )
    conn.commit()
    result = find_hot_callers(oracle, {})
    assert "hot_fn" in result
    assert "cold_fn" in result
    assert result.index("hot_fn") < result.index("cold_fn")


def test_hot_callers_unresolved_edges_excluded(tmp_path):
    """Unresolved edges (external stdlib calls) are not counted."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "project_fn", "core.py", False)
    # unresolved edge pointing at project_fn should not count
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved) VALUES (1,2,?,?,?,1,0)",
        ("caller_x", "project_fn", "x.py"),
    )
    conn.commit()
    result = find_hot_callers(oracle, {})
    # project_fn has no resolved callers — should not appear
    assert "project_fn" not in result


def test_hot_callers_stubs_excluded(tmp_path):
    """Stub functions are not returned even with resolved callers."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "stub_fn", "iface.py", True)
    _add_fn(conn, "caller_x", "x.py", False)
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved) VALUES (1,2,?,?,?,1,1)",
        ("caller_x", "stub_fn", "x.py"),
    )
    conn.commit()
    result = find_hot_callers(oracle, {})
    assert "stub_fn" not in result


def test_hot_callers_empty(tmp_path):
    """No resolved edges returns graceful message."""
    oracle, conn = _make_oracle(tmp_path)
    conn.commit()
    result = find_hot_callers(oracle, {})
    assert "No resolved call edges" in result or result == "" or "0" in result


def test_hot_callers_json_entries_excluded(tmp_path):
    """FSM state nodes in .json paths are not returned even with resolved callers."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fn(conn, "EncounterFSM::state::completed", "config/fsms/encounter.json", False)
    _add_fn(conn, "caller_a", "resolver.py", False)
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved) VALUES (1,2,?,?,?,1,1)",
        ("caller_a", "EncounterFSM::state::completed", "resolver.py"),
    )
    conn.commit()
    result = find_hot_callers(oracle, {})
    assert "EncounterFSM" not in result
    assert "encounter.json" not in result


# ── find_large_files ──────────────────────────────────────────────────


from determined.agent.agent_tools import find_large_files, find_fetch_calls, find_cross_language_calls


def _add_mutation(conn, file_path, line_no=10):
    conn.execute(
        "INSERT INTO mutations (file_path, line_number, target, operation) VALUES (?,?,?,?)",
        (file_path, line_no, "self.x", "assign"),
    )


def test_large_files_basic(tmp_path):
    """Files with 5+ functions appear; smaller files are omitted."""
    oracle, conn = _make_oracle(tmp_path)
    for i in range(6):
        _add_fn(conn, f"fn_{i}", "big.py", False)
    _add_fn(conn, "lone_fn", "tiny.py", False)
    conn.commit()
    result = find_large_files(oracle, {})
    assert "big.py" in result
    assert "tiny.py" not in result


def test_large_files_test_files_excluded(tmp_path):
    """Files with 'test' in their path are excluded."""
    oracle, conn = _make_oracle(tmp_path)
    for i in range(6):
        _add_fn(conn, f"fn_{i}", "tests/test_app.py", False)
    for i in range(6):
        _add_fn(conn, f"real_{i}", "app.py", False)
    conn.commit()
    result = find_large_files(oracle, {})
    assert "test_app.py" not in result
    assert "app.py" in result


def test_large_files_json_excluded(tmp_path):
    """JSON files are not reported even with many functions."""
    oracle, conn = _make_oracle(tmp_path)
    for i in range(8):
        _add_fn(conn, f"FSM::state::{i}", "config.json", False)
    conn.commit()
    result = find_large_files(oracle, {})
    assert "config.json" not in result


def test_large_files_stub_count_correct(tmp_path):
    """Stub count is not inflated by mutation count (CTE aggregation check)."""
    oracle, conn = _make_oracle(tmp_path)
    for i in range(5):
        _add_fn(conn, f"real_{i}", "mixed.py", False)
    _add_fn(conn, "stub_a", "mixed.py", True)
    # Many mutations in same file — must not multiply stub count
    for ln in range(50):
        _add_mutation(conn, "mixed.py", ln)
    conn.commit()
    result = find_large_files(oracle, {})
    # stub count should show 1, not 50
    assert "1 stubs" in result


def test_large_files_sort_by_mutations(tmp_path):
    """sort_by=mutations puts high-mutation file above high-function file."""
    oracle, conn = _make_oracle(tmp_path)
    # many_fns.py: 10 functions, 0 mutations
    for i in range(10):
        _add_fn(conn, f"fn_{i}", "many_fns.py", False)
    # dense.py: 6 functions, 20 mutations
    for i in range(6):
        _add_fn(conn, f"d_{i}", "dense.py", False)
    for ln in range(20):
        _add_mutation(conn, "dense.py", ln)
    conn.commit()
    result = find_large_files(oracle, {"sort_by": "mutations"})
    assert result.index("dense.py") < result.index("many_fns.py")


def test_large_files_scope_filters(tmp_path):
    """scope parameter limits results to matching file paths."""
    oracle, conn = _make_oracle(tmp_path)
    for i in range(6):
        _add_fn(conn, f"a_{i}", "world/world_app.py", False)
    for i in range(6):
        _add_fn(conn, f"b_{i}", "dungeon/dungeon_app.py", False)
    conn.commit()
    result = find_large_files(oracle, {"scope": "world"})
    assert "world_app.py" in result
    assert "dungeon_app.py" not in result


# ── find_fetch_calls ──────────────────────────────────────────────────


def _add_fetch_edge(conn, caller_file, caller, endpoint, method="POST"):
    if method == "GET":
        callee = f"fetch('{endpoint}').then"
    else:
        callee = f"fetch('{endpoint}', {{method: '{method}', headers: {{'Content-Type': 'application/json'}}}}).then"
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved)"
        " VALUES (1,2,?,?,?,1,0)",
        (caller, callee, caller_file),
    )


def test_fetch_calls_basic(tmp_path):
    """JS fetch() calls are found and endpoint/method extracted."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fetch_edge(conn, "app.js", "app.loadData", "/api/data", "GET")
    _add_fetch_edge(conn, "app.js", "app.saveData", "/api/save", "POST")
    conn.commit()
    result = find_fetch_calls(oracle, {})
    assert "/api/data" in result
    assert "GET" in result
    assert "/api/save" in result
    assert "POST" in result
    assert "app.loadData" in result
    assert "app.saveData" in result


def test_fetch_calls_python_files_excluded(tmp_path):
    """Python file edges are not returned even if callee looks like a fetch."""
    oracle, conn = _make_oracle(tmp_path)
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved)"
        " VALUES (1,2,?,?,?,1,0)",
        ("py_fn", "fetch('/api/data')", "server.py"),
    )
    conn.commit()
    result = find_fetch_calls(oracle, {})
    assert "server.py" not in result
    assert "No JS fetch" in result


def test_fetch_calls_deduplication(tmp_path):
    """Same caller+url+method from multiple .then variants counts as one call."""
    oracle, conn = _make_oracle(tmp_path)
    # Walker stores three edge variants for a single fetch: .then, .then(...).then, full chain
    for variant in [
        "fetch('/api/x', {method: 'POST'}).then",
        "fetch('/api/x', {method: 'POST'}).then(r=>r.json()).then",
        "fetch('/api/x', {method: 'POST'}).then(r=>r.json()).then(data=>{})",
    ]:
        conn.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number, resolved)"
            " VALUES (1,2,?,?,?,1,0)",
            ("app.doThing", variant, "app.js"),
        )
    conn.commit()
    result = find_fetch_calls(oracle, {})
    assert result.count("/api/x") == 1


def test_fetch_calls_scope_filters(tmp_path):
    """scope limits results to matching caller files."""
    oracle, conn = _make_oracle(tmp_path)
    _add_fetch_edge(conn, "world.js", "world.load", "/api/world", "GET")
    _add_fetch_edge(conn, "dungeon.js", "dungeon.enter", "/api/enter", "POST")
    conn.commit()
    result = find_fetch_calls(oracle, {"scope": "dungeon"})
    assert "dungeon.js" in result
    assert "world.js" not in result


def test_fetch_calls_empty(tmp_path):
    """No fetch edges returns graceful message."""
    oracle, conn = _make_oracle(tmp_path)
    conn.commit()
    result = find_fetch_calls(oracle, {})
    assert "No JS fetch" in result


# ── find_cross_language_calls ──────────────────────────────────────────────

def _insert_cross_language_edge(conn, caller, callee, edge_type="cross_language"):
    """Insert a graph_edges row for cross-language testing."""
    from determined.identity.edge_identity import edge_identity
    src_id, tgt_id = edge_identity(caller, callee)
    conn.execute(
        "INSERT OR IGNORE INTO graph_edges "
        "(source_id, target_id, caller, callee, edge_type, resolved) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (src_id, tgt_id, caller, callee, edge_type),
    )


def test_find_cross_language_calls_empty(tmp_path):
    """No cross-language edges returns graceful message."""
    oracle, conn = _make_oracle(tmp_path)
    conn.commit()
    result = find_cross_language_calls(oracle, {})
    assert "No cross-language" in result


def test_find_cross_language_calls_fetch(tmp_path):
    """JS fetch→Python handler edges appear under fetch section."""
    oracle, conn = _make_oracle(tmp_path)
    _insert_cross_language_edge(conn, "world.sendWorldCommand", "handle_command")
    _insert_cross_language_edge(conn, "dungeon.enterIntegratedMode", "dungeon_enter")
    conn.commit()
    result = find_cross_language_calls(oracle, {})
    assert "world.sendWorldCommand" in result
    assert "handle_command" in result
    assert "dungeon.enterIntegratedMode" in result
    assert "JS fetch" in result


def test_find_cross_language_calls_htmx(tmp_path):
    """HTMX edges appear under HTMX section."""
    oracle, conn = _make_oracle(tmp_path)
    _insert_cross_language_edge(conn, "__htmx__", "get_game_date")
    _insert_cross_language_edge(conn, "__htmx__", "get_player_name")
    conn.commit()
    result = find_cross_language_calls(oracle, {})
    assert "HTMX" in result
    assert "get_game_date" in result
    assert "get_player_name" in result


def test_find_cross_language_calls_socket(tmp_path):
    """socket.emit edges appear under socket section."""
    oracle, conn = _make_oracle(tmp_path)
    _insert_cross_language_edge(conn, "__js_client__", "handle_player_register")
    conn.commit()
    # Also add a decorator edge so Python @socketio.on handlers appear
    _insert_cross_language_edge(conn, "__js_client__", "handle_player_register", "decorator")
    conn.commit()
    result = find_cross_language_calls(oracle, {})
    assert "socket" in result.lower()
    assert "handle_player_register" in result


def test_find_cross_language_calls_scope(tmp_path):
    """Scope filter narrows results by caller name."""
    oracle, conn = _make_oracle(tmp_path)
    _insert_cross_language_edge(conn, "world.sendWorldCommand", "handle_command")
    _insert_cross_language_edge(conn, "dungeon.enterIntegratedMode", "dungeon_enter")
    conn.commit()
    result = find_cross_language_calls(oracle, {"scope": "world"})
    assert "world.sendWorldCommand" in result
    assert "dungeon" not in result


def test_find_cross_language_calls_http_fetch_type(tmp_path):
    """http_fetch edge_type is also surfaced."""
    oracle, conn = _make_oracle(tmp_path)
    _insert_cross_language_edge(conn, "__htmx__", "inventory_list_html", "http_fetch")
    conn.commit()
    result = find_cross_language_calls(oracle, {})
    assert "inventory_list_html" in result
