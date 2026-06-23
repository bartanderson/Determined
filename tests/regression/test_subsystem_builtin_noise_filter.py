# tools/analysis/tests/regression/test_subsystem_builtin_noise_filter.py
#
# Locks in the 2026-06-18 fix for TRACKER.md open item 18: SUBSYSTEM
# dependency lists had no equivalent of the builtin filtering hotspot
# ranking (truth/views.py's build_structure_view()) already applies.
# A builtin like len/str/RuntimeError/print has no `symbols` table
# declaration, so truth/subsystem_view.py's _module() fell through to
# the dotted-name fallback and returned the bare builtin name as its own
# "module" - which then polluted whichever real subsystem called it with
# a fake architectural dependency (and, if a builtin happened to be a
# caller too, could show up as its own bogus top-level subsystem entry).
#
# Fix: build_subsystem_view() now takes an optional builtin_symbols set
# (DBOracle.builtin_symbols(), the same DB-authoritative set
# build_structure_view() already uses) and skips any edge where the
# caller or callee is a confirmed builtin, before module resolution -
# same "exclude from the signal, never mutate edges/graph truth" pattern
# the hotspot fix already established.
#
# Same fixture pattern as test_discovery_api_and_subsystem_fix.py: real
# temp sqlite DB, real schema via ensure_schema, no mocking of the DB
# layer.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.truth.subsystem_view import build_subsystem_view


def _oracle_with_builtin_noise():
    """
    Real temp DB seeded with:
      - two real project files/symbols in different directories
        (moduleA/core.py:do_thing, moduleB/utils.py:helper_function)
      - a real project->project edge between them
      - a project->builtin edge (do_thing -> len) and a builtin->project
        edge (print -> helper_function), both recorded with
        bucket='builtin' in symbol_references so DBOracle.builtin_symbols()
        confirms them as builtins, exactly like a real engine run would.
    """
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)

    cur = oracle.conn.cursor()

    file_rows = [
        ("moduleA/core.py", 120, "logic", 0),
        ("moduleB/utils.py", 80, "utility", 0),
    ]
    for file_path, line_count, role, is_hot in file_rows:
        cur.execute(
            "INSERT INTO files (file_path, line_count, role, is_hot) VALUES (?, ?, ?, ?)",
            (file_path, line_count, role, is_hot),
        )

    symbol_rows = [
        ("moduleA/core.py", "function", "do_thing", 10, "def do_thing()", "moduleA/core.py:do_thing:10"),
        ("moduleB/utils.py", "function", "helper_function", 5, "def helper_function()", "moduleB/utils.py:helper_function:5"),
    ]
    for file_path, symbol_type, name, line_number, signature, canonical_id in symbol_rows:
        cur.execute(
            "INSERT INTO symbols (file_path, symbol_type, name, line_number, signature, canonical_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (file_path, symbol_type, name, line_number, signature, canonical_id),
        )

    # symbol_references: one real project edge, plus builtin noise on
    # both sides (callee-is-builtin and caller-is-builtin).
    reference_rows = [
        # (file_path, caller, callee, line_number, bucket)
        ("moduleA/core.py", "do_thing", "helper_function", 10, "project"),
        ("moduleA/core.py", "do_thing", "len", 11, "builtin"),
        ("moduleB/utils.py", "print", "helper_function", 6, "builtin"),
    ]
    for file_path, caller, callee, line_number, bucket in reference_rows:
        cur.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, caller, callee, line_number, bucket),
        )

    # graph_edges mirrors symbol_references - this is what
    # get_snapshot_graph()/build_subsystem_view() actually iterate.
    edge_rows = [
        ("do_thing", "helper_function", 10),
        ("do_thing", "len", 11),
        ("print", "helper_function", 6),
    ]
    for caller, callee, line_number in edge_rows:
        cur.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (caller, callee, caller, callee, line_number),
        )

    oracle.conn.commit()

    return oracle, tmp_path


def test_builtin_symbols_confirms_len_and_print():
    """Sanity check on the fixture: DBOracle.builtin_symbols() must agree
    that 'len' and 'print' are builtins, and 'do_thing'/'helper_function'
    are not - otherwise the rest of this test proves nothing."""
    oracle, tmp_path = _oracle_with_builtin_noise()
    try:
        builtins = oracle.builtin_symbols()
        assert "len" in builtins
        assert "print" in builtins
        assert "do_thing" not in builtins
        assert "helper_function" not in builtins
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_subsystem_view_without_builtin_filter_shows_the_bug():
    """Without builtin_symbols (the old/default-omitted behavior),
    builtin noise pollutes the dependency list and can appear as its own
    bogus top-level subsystem - this is the bug item 18 describes."""
    oracle, tmp_path = _oracle_with_builtin_noise()
    try:
        assessor = Assessor(oracle)
        snapshot = assessor.snapshot()
        module_map = oracle.symbol_module_map()

        view = build_subsystem_view(snapshot, module_map=module_map)

        # do_thing -> len pollutes moduleA's dependency list with "len"
        assert "len" in view.subsystems["moduleA"]["modules"]
        # print -> helper_function: "print" has no declaration, so it
        # falls to the dotted-name fallback and becomes its own bogus
        # top-level subsystem entry.
        assert "print" in view.subsystems
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_subsystem_view_with_builtin_filter_excludes_noise():
    """With builtin_symbols supplied (the fix, wired via
    Assessor.subsystem_view()), len/print are excluded entirely - the
    real do_thing -> helper_function edge (moduleA -> moduleB) is the
    only thing left."""
    oracle, tmp_path = _oracle_with_builtin_noise()
    try:
        assessor = Assessor(oracle)
        snapshot = assessor.snapshot()
        module_map = oracle.symbol_module_map()
        builtin_symbols = oracle.builtin_symbols()

        view = build_subsystem_view(
            snapshot,
            module_map=module_map,
            builtin_symbols=builtin_symbols,
        )

        assert "moduleA" in view.subsystems
        assert view.subsystems["moduleA"]["modules"] == ["moduleB"]
        assert "len" not in view.subsystems["moduleA"]["modules"]
        assert "print" not in view.subsystems
        # only the one real edge should have been counted
        assert view.subsystems["moduleA"]["edge_count"] == 1
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_assessor_subsystem_view_is_wired_to_the_fix():
    """Assessor.subsystem_view() (the real production path, what ask()/
    all_views() actually call) must pass builtin_symbols too, not just
    module_map - confirms the fix is live, not just available."""
    oracle, tmp_path = _oracle_with_builtin_noise()
    try:
        assessor = Assessor(oracle)
        wired = assessor.subsystem_view()

        assert "moduleA" in wired.subsystems
        assert wired.subsystems["moduleA"]["modules"] == ["moduleB"]
        assert "len" not in wired.subsystems["moduleA"]["modules"]
        assert "print" not in wired.subsystems
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_no_builtin_symbols_argument_preserves_prior_behavior():
    """Omitting builtin_symbols entirely (default None) must behave
    identically to before this fix - existing callers/tests that don't
    pass it are unaffected."""
    oracle, tmp_path = _oracle_with_builtin_noise()
    try:
        snapshot = Assessor(oracle).snapshot()
        module_map = oracle.symbol_module_map()

        view_default = build_subsystem_view(snapshot, module_map=module_map)
        view_explicit_none = build_subsystem_view(
            snapshot, module_map=module_map, builtin_symbols=None
        )

        assert view_default.subsystems == view_explicit_none.subsystems
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


if __name__ == "__main__":
    tests = [
        test_builtin_symbols_confirms_len_and_print,
        test_subsystem_view_without_builtin_filter_shows_the_bug,
        test_subsystem_view_with_builtin_filter_excludes_noise,
        test_assessor_subsystem_view_is_wired_to_the_fix,
        test_no_builtin_symbols_argument_preserves_prior_behavior,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
