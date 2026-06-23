# tools/analysis/truth/query_plan.py

from dataclasses import dataclass
from typing import Any

from determined.truth.query_ast import Select, Filter, Combine


@dataclass
class QueryPlan:
    root: Any

    VALID_METRICS = {
        "STRUCTURE": {"edges", "adjacency", "hotspots"},
        "STABILITY": {"stable_contracts", "unstable_contracts", "drift_signals"},
        "INTEGRITY": {"errors", "warnings", "db_mismatches"},
        "SUMMARY": {"edge_count", "file_count", "metrics"},
        "SUBSYSTEM": {"subsystems"},
        "ROLE": {"files", "totals"},
        "INTENT": {"functions", "classes", "mutations", "coverage"},
    }

class QuerySemanticsRegistry:

    VALID_COMBINES = {
        ("STRUCTURE", "STABILITY"),
        ("STRUCTURE", "INTEGRITY"),
        ("SUMMARY", "STABILITY"),
        ("SUBSYSTEM", "STRUCTURE"),
        ("STABILITY", "INTEGRITY"),
    }

    VALID_FILTER_KEYS = {
        "STRUCTURE": {"edges", "callee", "caller", "hotspots"},
        "STABILITY": {"stable_contracts", "unstable_contracts"},
        "SUBSYSTEM": {"modules", "edge_count"},
        # CLAUDE-EDIT 2026-06-17: added so a single-named-file question
        # ("what is the purpose of X.py") can be scoped to just that file's
        # entry in ROLE's files list instead of returning all files - see
        # query_compiler.py's _maybe_scope_to_named_file().
        "ROLE": {"file_path"},
        "INTENT": {"file_path", "name"},
    }

    def validate_combine(self, left, right):
        return (
            (left, right) in self.VALID_COMBINES
            or (right, left) in self.VALID_COMBINES
        )

    def validate_filter_key(self, view: str, key: str):
        allowed = self.VALID_FILTER_KEYS.get(view, set())
        return key in allowed

    # CLAUDE-EDIT 2026-06-17: removed validate_metric() - dead code (zero
    # callers anywhere in the codebase, confirmed via grep) that was also
    # silently wrong: it checked VALID_FILTER_KEYS instead of
    # QueryPlan.VALID_METRICS, so it would have rejected every legitimate
    # metric for every view had anything ever called it. The real,
    # actually-enforced metric check lives in QueryPlanner._validate_select
    # below. Same "looks like a feature, isn't" shape as the deleted
    # two_hop key / _apply_intent_weights stub - found while doing the
    # full algebra shape-contract audit (REFACTOR OPS BOARD.md 2026-06-17).

class QueryPlanner:

    def __init__(self, registry: QuerySemanticsRegistry):
        self.registry = registry

    def plan(self, query):
        query = self._validate(query)
        return QueryPlan(root=query)

    def _extract_view(self, q):
        if isinstance(q, Select):
            return q.view

        if isinstance(q, Combine):
            raise ValueError("Cannot extract view from Combine during validation")

        if isinstance(q, Filter):
            raise ValueError("Cannot extract view from Filter during validation")

        raise ValueError(f"Unknown AST node type: {type(q)}")

    def _validate(self, query):

        if isinstance(query, Filter):
            raise ValueError("Filter cannot be a root query node in deterministic-model")

        if isinstance(query, Combine):

            if isinstance(query.left, Combine) or isinstance(query.right, Combine):
                raise ValueError("Nested Combine not supported (flat-only AST)")

            # STEP 1: validate children first (same as before)
            left = self._validate(query.left)
            right = self._validate(query.right)

            # STEP 2: extract views for combine validation
            left_view = self._extract_view(left)
            right_view = self._extract_view(right)

            if not self.registry.validate_combine(left_view, right_view):
                raise ValueError(f"Invalid combine: ({left_view}, {right_view})")

            # STEP 3: NEW - enforce filter scoping rule
            # Filters are NOT allowed to exist at top-level inside Combine branches
            if isinstance(left, Filter) or isinstance(right, Filter):
                raise ValueError("Filter must be attached to a Select node")

            return Combine(left=left, right=right)

        if isinstance(query, Select):
            return self._validate_select(query)

        # pass-through for Select (unchanged behavior assumed elsewhere)
        return query

    def _validate_select(self, q: Select):

        if q.view not in QueryPlan.VALID_METRICS:
            raise ValueError(f"Unknown view: {q.view}")

        if q.metric is not None:
            allowed = QueryPlan.VALID_METRICS[q.view]
            if q.metric not in allowed:
                raise ValueError(
                    f"Invalid metric '{q.metric}' for view '{q.view}'"
                )

        # FILTER VALIDATION (NOW INLINE, DETERMINISTIC)

        if q.filter is not None:
            allowed = self.registry.VALID_FILTER_KEYS.get(q.view, set())

            if q.filter.key not in allowed:
                raise ValueError(
                    f"Invalid filter key '{q.filter.key}' for view '{q.view}'"
                )

        return q
