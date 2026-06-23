# tools/analysis/api/oracle_router.py
#
# Thin compatibility re-export. Routing logic moved to assessor/query_router.py
# (Phase 3 boundary completion - Assessor owns query execution).
# Tests that import internal helpers (_route_expand, _is_valid_symbol,
# _detect_intent) from this module still work via these re-exports.

from determined.assessor.query_router import (
    RouteResult,
    route_query,
    _route_expand,
    _is_valid_symbol,
    _detect_intent,
    _select_primitives,
    _build_plan,
    _prune,
    _score_symbol,
)

__all__ = [
    "RouteResult", "route_query",
    "_route_expand", "_is_valid_symbol", "_detect_intent",
    "_select_primitives", "_build_plan", "_prune", "_score_symbol",
]
