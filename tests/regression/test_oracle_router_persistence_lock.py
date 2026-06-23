# tools/analysis/tests/regression/test_oracle_router_persistence_lock.py
#
# Locks in the "close the small holes" fixes (2026-06-16):
#   1. Builtin exclusion during graph expansion is decided by the DB's
#      own bucket classification (DBOracle.builtin_symbols()), not a
#      hardcoded word list in api/oracle_router.py.
#   2. Accessor-chain noise filtering (oracle/symbol_noise.py) still
#      works after being extracted out of db_oracle.py.
#   3. The dead _apply_intent_weights() stub does not exist.
#   4. QuerySession.run_query() durably persists every result to the
#      query_sessions table, not just the in-memory _history list.
#   5. A persistence failure never breaks the query contract — run_query()
#      still returns a valid result even if the DB write fails.
#
# Uses a real temp sqlite DB built through the real schema (ensure_schema),
# no mocking of the DB layer — only test 6 mocks the persistence call
# itself, since that's the one thing we WANT to fail on purpose.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.api import oracle_router
from determined.api.oracle_router import _is_valid_symbol
from determined.assessor.query_session import QuerySession


def _seeded_oracle():
    """
    Real temp DB, real schema, hand-seeded symbol_references / graph_edges
    rows covering: a true builtin NOT in the old hardcoded word list, a
    project symbol, and an accessor-chain noise symbol.

    Uses DBOracle's own connection for everything (rather than opening a
    second sqlite3 connection to the same file) — Windows holds file
    handles for the lifetime of an open sqlite3.Connection, so a second,
    separate connection to the same temp file caused os.remove() to fail
    with WinError 32 in CI/local runs even after the "active" connection
    var was closed.
    """
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)

    cur = oracle.conn.cursor()

    symbol_reference_rows = [
        # (file_path, caller, callee, line_number, bucket)
        ("file.py", "ConnectionManager.connect", "do_thing", 10, "project"),
        # "enumerate" was NEVER in oracle_router's old hardcoded noise set
        # (run/len/print/getattr/set/int/str/any/all/dict/list) — if this
        # test passes, the filter is reading the DB, not a leftover list.
        ("file.py", "do_thing", "enumerate", 11, "builtin"),
        ("file.py", "cursor.self.oracle.conn", "do_thing", 13, "project"),
        ("file.py", "do_thing", "helper_function", 14, "project"),
    ]
    for file_path, caller, callee, line, bucket in symbol_reference_rows:
        cur.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, caller, callee, line, bucket),
        )

    graph_edge_rows = [
        # (source_id, target_id, caller, callee, line_number)
        ("do_thing", "enumerate", "do_thing", "enumerate", 11),
        ("do_thing", "helper_function", "do_thing", "helper_function", 14),
        ("helper_function", "ConnectionManager.connect",
         "helper_function", "ConnectionManager.connect", 20),
    ]
    for source_id, target_id, caller, callee, line in graph_edge_rows:
        cur.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_id, target_id, caller, callee, line),
        )

    oracle.conn.commit()

    return oracle, tmp_path


def test_builtin_filtering_uses_db_not_wordlist():
    oracle, tmp_path = _seeded_oracle()
    try:
        builtins = oracle.builtin_symbols()
        assert "enumerate" in builtins, (
            "DBOracle.builtin_symbols() should classify 'enumerate' as "
            "builtin from bucket='builtin' rows"
        )
        assert _is_valid_symbol("enumerate", builtins) is False, (
            "_is_valid_symbol must reject builtins via the DB-backed set "
            "— 'enumerate' was never in the old hardcoded word list, so "
            "this only passes if the DB classification is actually used"
        )
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_non_builtin_symbol_not_falsely_excluded():
    oracle, tmp_path = _seeded_oracle()
    try:
        builtins = oracle.builtin_symbols()
        assert _is_valid_symbol("helper_function", builtins) is True, (
            "a real project symbol must not be excluded as noise"
        )
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_accessor_chain_noise_still_filtered():
    oracle, tmp_path = _seeded_oracle()
    try:
        builtins = oracle.builtin_symbols()
        assert _is_valid_symbol("cursor.self.oracle.conn", builtins) is False, (
            "accessor-chain noise filtering must survive the extraction "
            "into oracle/symbol_noise.py"
        )
        assert _is_valid_symbol("split.i.surface", builtins) is False, (
            "single-letter loop-variable chains must still be filtered"
        )
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_apply_intent_weights_removed():
    assert not hasattr(oracle_router, "_apply_intent_weights"), (
        "_apply_intent_weights was deleted as dead code (never called, "
        "returned input unchanged) — it must not silently come back"
    )


def test_query_session_persists_to_db():
    oracle, tmp_path = _seeded_oracle()
    try:
        session = QuerySession(oracle)
        result = session.run_query("what does do_thing call")

        row = oracle.conn.execute(
            "SELECT session_id, raw_query, intent FROM query_sessions "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()

        assert row is not None, "run_query() must write a row to query_sessions"
        assert row["session_id"] == result.session_id
        assert row["raw_query"] == "what does do_thing call"
        assert row["intent"] == result.intent
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_persist_failure_does_not_break_query():
    """
    If persist_query_session() raises (disk full, locked file, whatever),
    run_query() must still return a valid result rather than propagating
    the exception. Persistence is best-effort logging, not part of the
    query contract.
    """
    oracle, tmp_path = _seeded_oracle()
    try:
        session = QuerySession(oracle)

        import determined.assessor.query_session as qs_module

        original = qs_module.persist_query_session

        def _boom(connection, result):
            raise sqlite3.OperationalError("simulated disk full")

        qs_module.persist_query_session = _boom
        try:
            result = session.run_query("what does do_thing call")
        finally:
            qs_module.persist_query_session = original

        assert result is not None
        assert result.raw_query == "what does do_thing call"
        assert result.intent is not None
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


if __name__ == "__main__":
    tests = [
        test_builtin_filtering_uses_db_not_wordlist,
        test_non_builtin_symbol_not_falsely_excluded,
        test_accessor_chain_noise_still_filtered,
        test_apply_intent_weights_removed,
        test_query_session_persists_to_db,
        test_persist_failure_does_not_break_query,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
