# tools/analysis/truth/query_executor.py

from dataclasses import dataclass
from typing import Any, Optional

from determined.truth.query_ast import Select, Filter, Combine


# -------------------------
# RESULT TYPES (grounded)
# -------------------------

@dataclass
class ViewResult:
    view: str
    data: Any


@dataclass
class FilterResult:
    key: str
    op: str
    value: Any


@dataclass
class CombineResult:
    left: Any
    right: Any


@dataclass
class QueryResult:
    view: str
    metric: Optional[str]
    data: Any


# -------------------------
# SHAPE-SAFE ACCESSOR
# -------------------------
# CLAUDE-EDIT 2026-06-17: added while root-causing the Windows-only
# test_ask_purpose_question_routes_to_role_view AttributeError (full
# incident in REFACTOR OPS BOARD.md 2026-06-17 "algebra shape contract"
# entry). The root issue wasn't a bug in the AI compiler - Select(ROLE,
# metric="files") for a question naming one specific file is a legitimate,
# arguably more precise choice than the full view, and the registry
# validates it as such. The bug was that a consumer assumed only one
# shape (the full view object) could ever come back.
#
# QueryResult.data's shape is fully determined by QueryResult.metric:
#   metric is None    -> data is the full view (a views.py dataclass,
#                         or a dict for any future dict-shaped view)
#   metric == "X"      -> data IS the projected value of field X already
#                         (a list, dict, int, str - whatever that field's
#                         type is), not an object containing field X.
#
# Any code reading a QueryResult's payload - tests, Assessor.ask()
# callers, a future narration layer - should go through get_field()
# instead of assuming a fixed shape derived from intent/view labels.
# Works uniformly across dataclass-shaped views (attribute access) and
# any dict-shaped view (key access).
def get_field(result: "QueryResult", name: str, default: Any = None) -> Any:
    """
    Read field `name` out of a QueryResult regardless of whether the
    algebra returned the full view (metric=None) or that exact field
    already projected out (metric=name, where .data IS the value).

    Returns `default` if a *different* metric was selected (the
    requested field genuinely isn't part of this result) or if the
    field isn't present on whatever came back.
    """
    data = result.data
    metric = result.metric

    if metric == name:
        return data

    if metric is not None:
        # A different metric was explicitly selected - `name` was never
        # going to be in `data`, so don't guess.
        return default

    if data is None:
        return default

    if isinstance(data, dict):
        return data.get(name, default)

    return getattr(data, name, default)


# -------------------------
# EXECUTOR
# -------------------------

class QueryExecutor:

    def __init__(self, views: dict, registry=None):
        self.views = views
        self.registry = registry

    def execute(self, query):

        if isinstance(query, Select):
            return self._select(query)

        if isinstance(query, Combine):
            return self._combine(
                self.execute(query.left),
                self.execute(query.right),
            )

        # Filter is not a root node in deterministic-model.
        # It only exists inside Select.

        raise ValueError(f"Invalid query node: {type(query)}")

    # -------------------------
    # SELECT (deterministic projection)
    # -------------------------

    def _select(self, q: Select):

        view = self.views[q.view]

        # CLAUDE-EDIT 2026-06-17: filter now applies AFTER projection, not
        # before. It used to run against the bare view object first - but
        # every real view (StructureView/StabilityView/.../RoleView) is a
        # dataclass, not a dict or list, so _apply_filter's isinstance
        # checks always fell through to "return data unchanged" and the
        # filter was silently a no-op no matter what key/op/value it had.
        # Filtering only makes sense against the addressable list/dict a
        # metric actually projects out (e.g. ROLE's "files" list) - so
        # project first, then filter the result. Found while wiring
        # single-named-file scoping (query_compiler.py's
        # _maybe_scope_to_named_file) and discovering the filter it builds
        # would have been validated by the planner but done nothing here.

        # full view
        if q.metric is None:
            data = view

        # attribute projection
        elif hasattr(view, q.metric):
            data = getattr(view, q.metric)

        # dict projection
        elif isinstance(view, dict):
            data = view.get(q.metric)

        else:
            raise ValueError(
                f"Metric '{q.metric}' not resolvable for view '{q.view}'"
            )

        if q.filter:
            data = self._apply_filter(data, q.filter)

        return QueryResult(
            view=q.view,
            metric=q.metric,
            data=data,
        )

    # -------------------------
    # COMBINE (pure structural join)
    # -------------------------

    def _combine(self, a, b):

        # deterministic wrapper only
        return CombineResult(
            left=a,
            right=b,
        )

    # -------------------------
    # FILTER (pure descriptor node)
    # -------------------------

    def _apply_filter(self, data, f: Filter):

        key, op, value = f.key, f.op, f.value

        if isinstance(data, dict):
            if op == "==":
                return data if data.get(key) == value else None
            # CLAUDE-EDIT 2026-06-17: "endswith" - for matching a bare
            # filename (what a question names) against a full stored path
            # (what DBOracle stores), where "==" would never match.
            if op == "endswith":
                v = data.get(key)
                return data if isinstance(v, str) and v.endswith(value) else None
            return data

        if isinstance(data, list):
            if op == "==":
                return [x for x in data if x.get(key) == value]
            if op == ">":
                return [x for x in data if x.get(key, 0) > value]
            if op == "<":
                return [x for x in data if x.get(key, 0) < value]
            if op == "endswith":
                return [
                    x for x in data
                    if isinstance(x.get(key), str) and x.get(key).endswith(value)
                ]

        return data
