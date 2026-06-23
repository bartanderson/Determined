# tools/analysis/tests/regression/test_intent_budget_calibration.py
#
# Locks in the 2026-06-17 Track A calibration pass to api/oracle_router.py's
# intent_budget table (see CLAUDE-EDIT 2026-06-17 comment at the call site):
#
#   1. reverse_query ("what uses X" / "used by") is a DIRECT-usage question
#      and must stop at 1 reverse hop - it must NOT reach the same 2-hop
#      transitive node that impact_query ("what depends on X") reaches.
#      Before this fix the two intents had identical reverse_depth=2
#      budgets, making them structurally indistinguishable.
#   2. surface_query ("what does X do" / "surface") must reach a 2-hop
#      forward node, not just direct callees - "structural zones" (plural)
#      requires more than a single hop.
#   3. impact_query and general_query are unchanged (reverse-only depth 2,
#      and balanced depth 1/1 respectively) - tests here also pin those so
#      a future change can't silently drift them.
#   4. The dead "two_hop" key (never read anywhere in _route_expand) is
#      gone from every intent_budget entry.
#
# Uses a fake graph object (plain object with a `.edges` list of objects
# exposing .caller/.callee) rather than a real DB - _route_expand only
# ever reads graph.edges, so this is a faithful, fast unit test of the
# traversal budgets themselves, independent of DB/discovery concerns
# already covered by test_oracle_router_persistence_lock.py.

from determined.api.oracle_router import _route_expand


def _edge_maps(pairs):
    """Build (forward, reverse) dicts from a list of (caller, callee) tuples."""
    forward = {}
    reverse = {}
    for caller, callee in pairs:
        forward.setdefault(caller, set()).add(callee)
        reverse.setdefault(callee, set()).add(caller)
    return forward, reverse


def test_reverse_query_stops_at_one_hop():
    # chain: top -> mid -> seed   (caller -> callee)
    # reverse(seed) = mid (1 hop), reverse(mid) = top (2 hops)
    forward, reverse = _edge_maps([("top", "mid"), ("mid", "seed")])

    result = _route_expand(forward, reverse, ["seed"], "reverse_query")
    nodes = set(result["nodes"])

    assert "mid" in nodes, "reverse_query must still reach the direct caller"
    assert "top" not in nodes, (
        "reverse_query narrowed to reverse_depth=1 must NOT reach a "
        "2-hop transitive caller - that's impact_query's job"
    )


def test_impact_query_reaches_two_hops():
    # same chain as above - impact_query keeps reverse_depth=2
    forward, reverse = _edge_maps([("top", "mid"), ("mid", "seed")])

    result = _route_expand(forward, reverse, ["seed"], "impact_query")
    nodes = set(result["nodes"])

    assert "mid" in nodes
    assert "top" in nodes, (
        "impact_query must still reach 2-hop transitive callers - "
        "this is the behavior reverse_query was differentiated from, "
        "not a regression target"
    )


def test_surface_query_reaches_two_hops_forward():
    # chain: seed -> down1 -> down2   (caller -> callee)
    forward, reverse = _edge_maps([("seed", "down1"), ("down1", "down2")])

    result = _route_expand(forward, reverse, ["seed"], "surface_query")
    nodes = set(result["nodes"])

    assert "down1" in nodes
    assert "down2" in nodes, (
        "surface_query widened to forward_depth=2 must reach a 2-hop "
        "forward node - a single hop isn't a 'structural zone'"
    )


def test_general_query_stays_at_one_hop_each_direction():
    # forward chain: seed -> down1 -> down2
    # reverse chain: top -> mid -> seed
    forward, reverse = _edge_maps([
        ("seed", "down1"), ("down1", "down2"),
        ("top", "mid"), ("mid", "seed"),
    ])

    result = _route_expand(forward, reverse, ["seed"], "general_query")
    nodes = set(result["nodes"])

    assert "down1" in nodes and "mid" in nodes, (
        "general_query must still reach 1-hop nodes in both directions"
    )
    assert "down2" not in nodes and "top" not in nodes, (
        "general_query must stay balanced at depth 1/1 - reaching 2-hop "
        "nodes in either direction would be scope creep past 'balance "
        "both without exploding scope'"
    )


def test_two_hop_key_removed_from_all_budgets():
    # Reach into _route_expand's local intent_budget table the same way
    # the function builds it, by exercising every intent and checking the
    # trace never references a two_hop-shaped decision. Since the dict is
    # local to the function (not a module attribute we can introspect
    # directly), the real assertion is behavioral: every intent must
    # still produce a valid result without the key being present, and the
    # source must not contain the literal key.
    import inspect
    import determined.api.oracle_router as oracle_router_module

    # Check for the literal dict-key form ("two_hop":), not just the bare
    # word - the explanatory comment above intent_budget legitimately
    # mentions "two_hop" by name when describing why it was removed, so
    # a bare substring check would false-positive on its own documentation.
    source = inspect.getsource(oracle_router_module._route_expand)
    assert '"two_hop":' not in source, (
        "two_hop was dead config (never read anywhere) and must stay "
        "removed, not silently come back - same rule as the deleted "
        "_apply_intent_weights stub"
    )

    forward, reverse = _edge_maps([("seed", "down1")])
    for intent in ("surface_query", "impact_query", "reverse_query",
                   "general_query", "role_query", "some_unknown_intent"):
        result = _route_expand(forward, reverse, ["seed"], intent)
        assert "nodes" in result and "trace" in result


if __name__ == "__main__":
    tests = [
        test_reverse_query_stops_at_one_hop,
        test_impact_query_reaches_two_hops,
        test_surface_query_reaches_two_hops_forward,
        test_general_query_stays_at_one_hop_each_direction,
        test_two_hop_key_removed_from_all_budgets,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
