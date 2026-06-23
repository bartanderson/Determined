# tools/analysis/tests/regression/test_oracle_cli_smoke.py
#
# Minimal oracle CLI smoke test against the real self-corpus DB.
# Exercises the full route_query path (DBOracle -> route_query ->
# QuerySessionResult) against real data, with no seeded fixtures.
#
# Skips gracefully if the self-corpus DB does not exist (e.g. CI).
# Does NOT require Ollama / sentence-transformers.
#
# Tests:
#   1. DBOracle opens the real DB without error.
#   2. route_query returns a RouteResult with intent/seeds/expanded set.
#   3. A query for a known self-corpus symbol finds it in seeds or expanded.
#   4. QuerySession.run_query returns a QuerySessionResult with populated
#      reasoning primitives (seed_explanation, expansion_explanation,
#      intent_mapping_trace, node_reasons, seed_paths).

import os
import sys

SELF_CORPUS_DB = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..",  # repo root
    "corpus.db",
))

_DB_PRESENT = os.path.exists(SELF_CORPUS_DB)


def _skip_if_no_db(fn):
    """Decorator: skip test with a print if the real DB isn't present."""
    def wrapper():
        if not _DB_PRESENT:
            print(f"  SKIP  {fn.__name__} (self-corpus DB not present)")
            return
        fn()
    wrapper.__name__ = fn.__name__
    return wrapper


def _oracle():
    from determined.oracle.db_oracle import DBOracle
    return DBOracle(SELF_CORPUS_DB)


@_skip_if_no_db
def test_oracle_opens():
    oracle = _oracle()
    builtins = oracle.builtin_symbols()
    assert isinstance(builtins, set)
    assert len(builtins) > 0, "Expected at least some builtins in self-corpus"


@_skip_if_no_db
def test_route_query_returns_valid_result():
    from determined.assessor.query_router import route_query
    oracle = _oracle()
    result = route_query("what calls route_query", oracle)

    assert result.intent is not None
    assert isinstance(result.seed_symbols, list)
    assert isinstance(result.expanded_symbols, list)
    assert result.edge_count > 0, "Expected edges in self-corpus"


@_skip_if_no_db
def test_route_query_finds_known_symbol():
    from determined.assessor.query_router import route_query
    oracle = _oracle()
    result = route_query("route_query", oracle)
    all_symbols = set(result.seed_symbols) | set(result.expanded_symbols)
    assert any("route_query" in s for s in all_symbols), (
        f"Expected 'route_query' in results, seeds={result.seed_symbols[:5]}"
    )


@_skip_if_no_db
def test_query_session_reasoning_primitives():
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.query_session import QuerySession

    oracle = DBOracle(SELF_CORPUS_DB)
    session = QuerySession(oracle)
    result = session.run_query("what calls route_query")

    assert isinstance(result.seed_explanation(), str)
    assert isinstance(result.expansion_explanation(), str)

    trace = result.intent_mapping_trace()
    assert "detected_intent" in trace
    assert "seed_count" in trace

    assert isinstance(result.node_reasons(), dict)
    assert isinstance(result.seed_paths(), dict)
    assert isinstance(result.expansion_edges(), dict)


if __name__ == "__main__":
    tests = [
        test_oracle_opens,
        test_route_query_returns_valid_result,
        test_route_query_finds_known_symbol,
        test_query_session_reasoning_primitives,
    ]
    passed = failed = skipped = 0
    for t in tests:
        try:
            t()
            if not _DB_PRESENT:
                skipped += 1
            else:
                print(f"  PASS  {t.__name__}")
                passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {skipped} skipped, {failed} failed")
    sys.exit(failed)
