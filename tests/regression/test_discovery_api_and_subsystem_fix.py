# tools/analysis/tests/regression/test_discovery_api_and_subsystem_fix.py
#
# Locks in the 2026-06-17 Track A + Track B-item-2 work:
#   1. The 5 new DBReader-only discovery methods on DBOracle
#      (list_symbols, find_symbols, find_files, find_modules,
#      symbol_module_map - oracle/db_oracle.py) actually read what's
#      really in the `symbols`/`files` tables, with no engine/in-memory
#      fallback.
#   2. truth/subsystem_view.py's _module() fix: SUBSYSTEM grouping for a
#      symbol with a real DB-backed declaration (a `symbols` table row)
#      now resolves to that symbol's true containing directory instead
#      of fragmenting into a singleton group, which is what the old
#      dotted-name-split heuristic did for this codebase's mostly-bare
#      (non-dotted) real symbol names. See REFACTOR OPS BOARD.md /
#      Truth Kernel Board.md 2026-06-17 entries and subsystem_view.py's
#      CLAUDE-EDIT comments for the full root-cause writeup.
#
# Same fixture pattern as test_oracle_router_persistence_lock.py /
# test_run_algebra_end_to_end.py: real temp sqlite DB, real schema via
# ensure_schema, no mocking of the DB layer.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.truth.subsystem_view import build_subsystem_view, _module


def _oracle_with_symbols_and_files():
    """
    Real temp DB seeded with:
      - `files` rows across two distinct directories (two real modules)
      - `symbols` rows: real function/class declarations with BARE names
        (no dots) - matching this project's actual real-world shape,
        the exact case that fragmented SUBSYSTEM before this fix
      - one ambiguous bare name declared in two different files, to
        exercise symbol_module_map()'s deterministic tie-break
    """
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)

    cur = oracle.conn.cursor()

    file_rows = [
        # (file_path, line_count, role, is_hot)
        ("moduleA/core.py", 120, "logic", 0),
        ("moduleA/helpers.py", 40, "logic", 0),
        ("moduleB/utils.py", 80, "utility", 1),
    ]
    for file_path, line_count, role, is_hot in file_rows:
        cur.execute(
            "INSERT INTO files (file_path, line_count, role, is_hot) VALUES (?, ?, ?, ?)",
            (file_path, line_count, role, is_hot),
        )

    symbol_rows = [
        # (file_path, symbol_type, name, line_number, signature, canonical_id)
        ("moduleA/core.py", "function", "do_thing", 10, "def do_thing()", "moduleA/core.py:do_thing:10"),
        ("moduleB/utils.py", "function", "helper_function", 5, "def helper_function()", "moduleB/utils.py:helper_function:5"),
        # ambiguous bare name, declared in two files - alphabetically
        # first file_path (moduleA/core.py) should win deterministically
        ("moduleB/utils.py", "function", "shared_name", 1, "def shared_name()", "moduleB/utils.py:shared_name:1"),
        ("moduleA/core.py", "function", "shared_name", 99, "def shared_name()", "moduleA/core.py:shared_name:99"),
    ]
    for file_path, symbol_type, name, line_number, signature, canonical_id in symbol_rows:
        cur.execute(
            "INSERT INTO symbols (file_path, symbol_type, name, line_number, signature, canonical_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (file_path, symbol_type, name, line_number, signature, canonical_id),
        )

    # caller/callee symbol_references + graph_edges using the SAME bare
    # names as the symbols rows above, so subsystem_view has real edges
    # to resolve through symbol_module_map().
    cur.execute(
        "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
        "VALUES (?, ?, ?, ?, ?)",
        ("moduleA/core.py", "do_thing", "helper_function", 10, "project"),
    )
    cur.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
        "VALUES (?, ?, ?, ?, ?)",
        ("do_thing", "helper_function", "do_thing", "helper_function", 10),
    )

    oracle.conn.commit()

    return oracle, tmp_path


# =========================================================
# 1. list_symbols
# =========================================================

def test_list_symbols_reads_real_rows():
    oracle, tmp_path = _oracle_with_symbols_and_files()
    try:
        all_symbols = oracle.list_symbols()
        names = {s["name"] for s in all_symbols}
        assert {"do_thing", "helper_function", "shared_name"} <= names

        functions_only = oracle.list_symbols(symbol_type="function")
        assert all(s["symbol_type"] == "function" for s in functions_only)

        limited = oracle.list_symbols(limit=1)
        assert len(limited) == 1
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 2. find_symbols
# =========================================================

def test_find_symbols_substring_and_exact():
    oracle, tmp_path = _oracle_with_symbols_and_files()
    try:
        substring_hits = oracle.find_symbols("helper")
        assert any(s["name"] == "helper_function" for s in substring_hits)

        exact_hits = oracle.find_symbols("do_thing", exact=True)
        assert len(exact_hits) == 1
        assert exact_hits[0]["name"] == "do_thing"

        exact_miss = oracle.find_symbols("do_th", exact=True)
        assert exact_miss == []

        typed_hits = oracle.find_symbols("shared_name", symbol_type="function")
        assert len(typed_hits) == 2  # both declarations
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 3. find_files
# =========================================================

def test_find_files_pattern_and_role():
    oracle, tmp_path = _oracle_with_symbols_and_files()
    try:
        by_pattern = oracle.find_files(pattern="moduleA")
        assert {f["file_path"] for f in by_pattern} == {
            "moduleA/core.py", "moduleA/helpers.py"
        }

        by_role = oracle.find_files(role="utility")
        assert [f["file_path"] for f in by_role] == ["moduleB/utils.py"]

        unfiltered = oracle.find_files()
        assert len(unfiltered) == 3
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 4. find_modules
# =========================================================

def test_find_modules_groups_by_directory():
    oracle, tmp_path = _oracle_with_symbols_and_files()
    try:
        modules = oracle.find_modules()
        by_name = {m["module"]: m for m in modules}

        assert "moduleA" in by_name
        assert "moduleB" in by_name
        assert by_name["moduleA"]["file_count"] == 2
        assert by_name["moduleB"]["file_count"] == 1
        assert by_name["moduleA"]["files"] == [
            "moduleA/core.py", "moduleA/helpers.py"
        ]
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 5. symbol_module_map
# =========================================================

def test_symbol_module_map_resolves_real_declarations():
    oracle, tmp_path = _oracle_with_symbols_and_files()
    try:
        mapping = oracle.symbol_module_map()

        assert mapping["do_thing"] == "moduleA"
        assert mapping["helper_function"] == "moduleB"

        # ambiguous name -> deterministic alphabetically-first file_path
        # ("moduleA/core.py" < "moduleB/utils.py")
        assert mapping["shared_name"] == "moduleA"

        # symbols with no declaration row at all are simply absent
        assert "nonexistent_symbol" not in mapping
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 6. SUBSYSTEM FIX: bare-name symbols now group by real module,
#    not by fragmenting into singletons
# =========================================================

def test_subsystem_view_uses_module_map_for_bare_names():
    oracle, tmp_path = _oracle_with_symbols_and_files()
    try:
        assessor = Assessor(oracle)
        snapshot = assessor.snapshot()
        module_map = oracle.symbol_module_map()

        # WITHOUT module_map: old behavior. "do_thing" and
        # "helper_function" have no dots, so the old heuristic returns
        # each bare name as its own "module" - caller != callee only
        # when the names actually differ, but neither resolves to a
        # real architectural grouping like "moduleA"/"moduleB".
        view_without_map = build_subsystem_view(snapshot)
        assert "moduleA" not in view_without_map.subsystems
        assert "do_thing" in view_without_map.subsystems  # the bug: bare name as its own group

        # WITH module_map (the fix, wired via Assessor.subsystem_view()):
        # "do_thing" (declared in moduleA/core.py) and "helper_function"
        # (declared in moduleB/utils.py) now resolve to their real
        # containing modules.
        view_with_map = build_subsystem_view(snapshot, module_map=module_map)
        assert "moduleA" in view_with_map.subsystems
        assert "moduleB" in view_with_map.subsystems["moduleA"]["modules"]
        assert "do_thing" not in view_with_map.subsystems

        # Assessor.subsystem_view() is the real wiring - confirm it
        # produces the same fixed result, not just build_subsystem_view
        # called directly with a manually-supplied map.
        wired = assessor.subsystem_view()
        assert "moduleA" in wired.subsystems
        assert "moduleB" in wired.subsystems["moduleA"]["modules"]
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_module_fallback_preserved_for_dotted_unmapped_symbols():
    """
    _module() must still fall back to the dotted-name heuristic for any
    symbol absent from module_map (builtins, external-library calls,
    unresolved accessor chains) - this is what keeps
    test_run_algebra_end_to_end.py's existing dotted-synthetic-name
    fixture (which seeds NO `symbols` table rows at all) passing
    unmodified.
    """
    module_map = {"do_thing": "moduleA"}

    # present in map -> real module
    assert _module("do_thing", module_map) == "moduleA"

    # dotted, and its tail segment IS in the map -> tail-match path
    # (_module checks the bare tail before falling back to the dotted
    # heuristic - this symbol's last segment "do_thing" resolves via
    # module_map, same as if it had been looked up bare)
    assert _module("some.external.do_thing", module_map) == "moduleA"

    # dotted, and genuinely absent from map (tail not in map either)
    # -> old heuristic (first two segments)
    assert _module("moduleA.core.do_other_thing", module_map) == "moduleA.core"

    # absent from map, bare -> old heuristic (whole name, unchanged)
    assert _module("untracked_builtin", module_map) == "untracked_builtin"

    # no map at all -> exact prior behavior
    assert _module("moduleA.core.do_thing", None) == "moduleA.core"


if __name__ == "__main__":
    tests = [
        test_list_symbols_reads_real_rows,
        test_find_symbols_substring_and_exact,
        test_find_files_pattern_and_role,
        test_find_modules_groups_by_directory,
        test_symbol_module_map_resolves_real_declarations,
        test_subsystem_view_uses_module_map_for_bare_names,
        test_module_fallback_preserved_for_dotted_unmapped_symbols,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
