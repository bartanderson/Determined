# tools/analysis/tests/regression/test_intent_view_wiring.py
#
# Locks in Truth.md Phase 1 Row 1 remainder + Row 5 (2026-06-19):
# intent/description capture at ingestion time via docstrings.
#
# Proves:
#   1. FunctionRepresentation.docstring is extracted and persisted.
#   2. ClassRepresentation.docstring is extracted and persisted.
#   3. MutationEvent.intent is populated from the containing function's
#      docstring first line.
#   4. Assessor.intent_view() returns real data from the DB (not empty).
#   5. INTENT is a registered 7th Truth Layer view in QueryPlan.VALID_METRICS.
#   6. Select("INTENT") validates cleanly through QueryPlanner.

import os
import sqlite3

os.environ.setdefault("PYTHONPATH", ".")

SOURCE_WITH_DOCSTRINGS = '''
class Widget:
    """Manages widget lifecycle."""

    def activate(self, ctx):
        """Activate the widget and register it with the context."""
        ctx.register(self)
        self.state = "active"

def helper():
    pass
'''


def _parse_and_run(source: str):
    import ast
    from determined.ingestion.parse_ast import (
        _extract_functions,
        _extract_classes,
        _extract_mutations,
    )
    tree = ast.parse(source)
    return (
        _extract_functions(tree),
        _extract_classes(tree),
        _extract_mutations(tree),
    )


def test_function_docstring_extracted():
    functions, _, _ = _parse_and_run(SOURCE_WITH_DOCSTRINGS)
    activate = next((f for f in functions if f.name == "activate"), None)
    assert activate is not None
    assert activate.docstring == "Activate the widget and register it with the context."


def test_class_docstring_extracted():
    _, classes, _ = _parse_and_run(SOURCE_WITH_DOCSTRINGS)
    widget = next((c for c in classes if c.name == "Widget"), None)
    assert widget is not None
    assert widget.docstring == "Manages widget lifecycle."


def test_mutation_intent_from_containing_function():
    _, _, mutations = _parse_and_run(SOURCE_WITH_DOCSTRINGS)
    # ctx.register(self) and self.state = "active" are inside activate()
    ctx_mut = next((m for m in mutations if m.operation == "register"), None)
    assert ctx_mut is not None
    assert ctx_mut.intent == "Activate the widget and register it with the context."


def test_mutation_intent_empty_outside_documented_function():
    _, _, mutations = _parse_and_run(SOURCE_WITH_DOCSTRINGS)
    # helper() has no docstring - any mutations inside it get empty intent
    # (no mutations in helper() here, but confirming no bleed from activate)
    for m in mutations:
        if m.intent:
            assert "Activate" in m.intent or "widget" in m.intent.lower()


def _make_db_with_intent():
    from determined.persistence.persistence_engine import initialize_database
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=MEMORY")
    initialize_database(conn)

    conn.execute("INSERT INTO functions VALUES (NULL, 'f.py', 'activate', 10, NULL, '[]', 'Activate the widget.', 0, NULL, NULL, NULL)")
    conn.execute("INSERT INTO functions VALUES (NULL, 'f.py', 'helper', 20, NULL, '[]', NULL, 0, NULL, NULL, NULL)")
    conn.execute("INSERT INTO classes VALUES (NULL, 'f.py', 'Widget', 1, '[]', '[]', 'Manages widget lifecycle.')")
    conn.execute("INSERT INTO mutations VALUES (NULL, 'f.py', 12, 'ctx', 'register', 'ctx.register(self)', 'Activate the widget.')")
    conn.commit()
    return conn


def test_intent_view_returns_real_data():
    from determined.truth.views import build_intent_view
    conn = _make_db_with_intent()
    view = build_intent_view(conn)

    assert len(view.functions) == 1
    assert view.functions[0]["name"] == "activate"
    assert "Activate" in view.functions[0]["docstring"]

    assert len(view.classes) == 1
    assert view.classes[0]["name"] == "Widget"

    assert len(view.mutations) == 1
    assert view.mutations[0]["intent"] == "Activate the widget."

    assert view.coverage["functions_with_docstring"] == 1
    assert view.coverage["functions_total"] == 2
    assert view.coverage["classes_with_docstring"] == 1
    assert view.coverage["classes_total"] == 1


def test_intent_registered_in_query_plan():
    from determined.truth.query_plan import QueryPlan
    assert "INTENT" in QueryPlan.VALID_METRICS
    assert "functions" in QueryPlan.VALID_METRICS["INTENT"]
    assert "classes" in QueryPlan.VALID_METRICS["INTENT"]
    assert "mutations" in QueryPlan.VALID_METRICS["INTENT"]
    assert "coverage" in QueryPlan.VALID_METRICS["INTENT"]


def test_select_intent_validates():
    from determined.truth.query_ast import Select
    from determined.truth.query_plan import QueryPlanner, QuerySemanticsRegistry
    planner = QueryPlanner(QuerySemanticsRegistry())
    plan = planner.plan(Select("INTENT"))
    assert plan.root.view == "INTENT"


if __name__ == "__main__":
    test_function_docstring_extracted()
    test_class_docstring_extracted()
    test_mutation_intent_from_containing_function()
    test_mutation_intent_empty_outside_documented_function()
    test_intent_view_returns_real_data()
    test_intent_registered_in_query_plan()
    test_select_intent_validates()
    print("All tests passed.")
