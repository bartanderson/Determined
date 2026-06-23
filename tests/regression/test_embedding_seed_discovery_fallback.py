# tools/analysis/tests/regression/test_embedding_seed_discovery_fallback.py
#
# TRACKER.md item 22: embedding-fallback crash risk in seed discovery.
#
# discover_seed_symbols_semantic() previously only guarded the top-level
# `import numpy` / `from ...embedding_model import embed_text` statements
# with `except ImportError`. Any failure *after* that point - the actual
# model load inside embedding_model.get_model() (SentenceTransformer(...)),
# which can fail at call time due to a missing model cache, no network
# access, a corrupted download, etc. - propagated uncaught, all the way
# up through _discover_combined() -> discover_seed_symbols() ->
# oracle_router.route_query() -> QuerySession.run_query(), crashing every
# ask.py query whenever the model can't load, even though a perfectly
# good token-based fallback already exists in this same class.
#
# This file locks in the fix: discover_seed_symbols_semantic() must catch
# ANY exception raised while building/using the embedding index (not just
# ImportError) and fall back to _discover_token() - directly, not via
# discover_seed_symbols(), since that path re-enters
# discover_seed_symbols_semantic() through _discover_combined() and would
# recurse forever against a failure that won't go away on retry.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
import determined.oracle.embedding_model as embedding_model


def _oracle_with_symbols():
    """
    Real temp DB seeded with a handful of non-builtin symbols so both
    _discover_token() and the embedding path have something to rank.
    Same fixture pattern as test_discovery_api_and_subsystem_fix.py.
    """
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)

    cur = oracle.conn.cursor()
    rows = [
        # (file_path, caller, callee, line_number, bucket)
        ("core.py", "persist_character_state", "save_to_db", 10, "project"),
        ("core.py", "save_to_db", "open", 11, "builtin"),
        ("core.py", "route_query", "discover_seed_symbols", 20, "project"),
    ]
    for file_path, caller, callee, line_number, bucket in rows:
        cur.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, caller, callee, line_number, bucket),
        )
    oracle.conn.commit()

    return oracle, tmp_path


# =========================================================
# 1. Real-environment case: sentence-transformers genuinely not
#    installed in this sandbox. The ModuleNotFoundError it raises
#    happens lazily inside embedding_model.get_model(), called from
#    deep inside build_embedding_index()/embed_text() - NOT at the
#    top-level `from ...embedding_model import embed_text` line - so
#    the OLD code's `except ImportError` around only the top-level
#    import never had a chance to catch it.
# =========================================================

def test_semantic_discovery_falls_back_when_model_package_missing():
    try:
        import sentence_transformers  # noqa: F401
        import pytest
        pytest.skip("sentence_transformers is installed in this environment")
    except ImportError:
        pass

    oracle, tmp_path = _oracle_with_symbols()
    try:
        token_result = oracle._discover_token("persist character state", limit=10)
        semantic_result = oracle.discover_seed_symbols_semantic(
            "persist character state", limit=10
        )
        # must not raise, and must fall back to the exact token ranking
        assert semantic_result == token_result
        assert "persist_character_state" in semantic_result
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 2. Simulated case: model package importable, but the load/embed call
#    itself raises something that is NOT an ImportError (e.g. an OSError
#    from a missing/corrupted model cache, a network error fetching the
#    weights, etc.) - the exact gap item 22 flagged.
# =========================================================

def test_semantic_discovery_falls_back_on_non_import_error():
    oracle, tmp_path = _oracle_with_symbols()

    call_count = {"n": 0}

    def _broken_embed_text(text):
        call_count["n"] += 1
        raise OSError("simulated model cache failure")

    original_embed_text = embedding_model.embed_text
    embedding_model.embed_text = _broken_embed_text
    try:
        token_result = oracle._discover_token("persist character state", limit=10)
        semantic_result = oracle.discover_seed_symbols_semantic(
            "persist character state", limit=10
        )
        assert semantic_result == token_result
        # exactly one failing call - proves no recursion back into
        # discover_seed_symbols_semantic() via discover_seed_symbols()
        assert call_count["n"] == 1
    finally:
        embedding_model.embed_text = original_embed_text
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 3. End-to-end: the public discover_seed_symbols() entrypoint actually
#    used by oracle_router.route_query() / QuerySession.run_query() must
#    not crash either, with the same simulated failure.
# =========================================================

def test_discover_seed_symbols_public_entrypoint_does_not_crash():
    oracle, tmp_path = _oracle_with_symbols()

    def _broken_embed_text(text):
        raise OSError("simulated model cache failure")

    original_embed_text = embedding_model.embed_text
    embedding_model.embed_text = _broken_embed_text
    try:
        result = oracle.discover_seed_symbols("persist character state", limit=10)
        assert "persist_character_state" in result
    finally:
        embedding_model.embed_text = original_embed_text
        oracle.conn.close()
        os.remove(tmp_path)


if __name__ == "__main__":
    tests = [
        test_semantic_discovery_falls_back_when_model_package_missing,
        test_semantic_discovery_falls_back_on_non_import_error,
        test_discover_seed_symbols_public_entrypoint_does_not_crash,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
