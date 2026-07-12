"""Regression tests for scaffold_from_pattern tool (RM46)."""
import sqlite3
import textwrap
import pytest
from determined.agent.agent_tools import scaffold_from_pattern
from determined.agent.stub_projector import _extract_structural_skeleton


# ---------------------------------------------------------------------------
# Minimal oracle/assessor stubs
# ---------------------------------------------------------------------------

class _Oracle:
    def __init__(self, conn):
        self.conn = conn


class _Assessor:
    def __init__(self, conn):
        self.oracle = _Oracle(conn)


def _make_db(rows=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE functions (
            name TEXT PRIMARY KEY,
            file_path TEXT,
            line_number INTEGER DEFAULT 1,
            is_stub INTEGER DEFAULT 0,
            return_type TEXT DEFAULT '',
            docstring TEXT DEFAULT '',
            param_types_json TEXT DEFAULT '{}'
        )
    """)
    conn.execute("""
        CREATE TABLE graph_edges (
            caller TEXT,
            callee TEXT,
            line_number INTEGER DEFAULT 0,
            resolved INTEGER DEFAULT 0
        )
    """)
    if rows:
        for r in rows:
            conn.execute(
                "INSERT INTO functions (name, file_path, line_number, is_stub, return_type, docstring, param_types_json) VALUES (?,?,?,?,?,?,?)",
                r,
            )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# _extract_structural_skeleton tests (pure AST, no DB)
# ---------------------------------------------------------------------------

def test_skeleton_guard_clause():
    src = textwrap.dedent("""\
        def process(data):
            if not data:
                return None
            return data
    """)
    skel = _extract_structural_skeleton(src, "process")
    assert skel["first_stmt_type"] == "if_guard"
    assert skel["has_guard"] is True


def test_skeleton_try_except():
    src = textwrap.dedent("""\
        def fetch(url):
            try:
                result = call(url)
            except Exception as e:
                raise
            return result
    """)
    skel = _extract_structural_skeleton(src, "fetch")
    assert skel["error_handling"] == "try_except"
    assert skel["first_stmt_type"] == "try_block"


def test_skeleton_return_dict():
    src = textwrap.dedent("""\
        def build():
            x = 1
            return {"key": x}
    """)
    skel = _extract_structural_skeleton(src, "build")
    assert "dict" in skel["return_shape"]


def test_skeleton_return_none():
    src = textwrap.dedent("""\
        def do_thing():
            pass
    """)
    skel = _extract_structural_skeleton(src, "do_thing")
    assert skel["return_shape"] == "none"


def test_skeleton_unknown_fn():
    src = "def foo(): pass"
    skel = _extract_structural_skeleton(src, "bar")  # fn_name not found
    assert skel["first_stmt_type"] == "unknown"


def test_skeleton_syntax_error():
    skel = _extract_structural_skeleton("def foo(: pass", "foo")
    assert skel["first_stmt_type"] == "unknown"


# ---------------------------------------------------------------------------
# scaffold_from_pattern integration tests (DB-backed, no LLM/embedding)
# ---------------------------------------------------------------------------

FP = "/project/module.py"


def _base_rows():
    return [
        # target stub
        ("my_stub", FP, 10, 1, "dict", "Do the thing.", '{"x": "int"}'),
        # complete sibling — same file, same return_type
        ("do_similar", FP, 20, 0, "dict", "Similar complete impl.", '{}'),
        ("do_another", FP, 30, 0, "dict", "Another complete impl.", '{}'),
    ]


def test_missing_symbol_returns_error():
    conn = _make_db()
    assessor = _Assessor(conn)
    result = scaffold_from_pattern(assessor, {"symbol": "nonexistent"})
    assert result.startswith("ERROR")


def test_missing_symbol_arg_returns_error():
    conn = _make_db()
    assessor = _Assessor(conn)
    result = scaffold_from_pattern(assessor, {})
    assert result.startswith("ERROR")


def test_finds_same_file_siblings():
    conn = _make_db(_base_rows())
    assessor = _Assessor(conn)
    result = scaffold_from_pattern(assessor, {"symbol": "my_stub"})
    assert "STRUCTURAL SIBLINGS" in result
    # At least one sibling from the same file should appear
    assert "do_similar" in result or "do_another" in result


def test_output_contains_scaffold_template():
    conn = _make_db(_base_rows())
    assessor = _Assessor(conn)
    result = scaffold_from_pattern(assessor, {"symbol": "my_stub"})
    assert "SCAFFOLD TEMPLATE" in result
    assert "```python" in result
    assert "my_stub" in result


def test_output_contains_structural_analysis():
    conn = _make_db(_base_rows())
    assessor = _Assessor(conn)
    result = scaffold_from_pattern(assessor, {"symbol": "my_stub"})
    assert "STRUCTURAL ANALYSIS" in result


def test_output_contains_reference_implementations():
    conn = _make_db(_base_rows())
    assessor = _Assessor(conn)
    result = scaffold_from_pattern(assessor, {"symbol": "my_stub"})
    assert "REFERENCE IMPLEMENTATIONS" in result


def test_no_siblings_graceful():
    # Only the stub itself, no complete siblings
    conn = _make_db([("lonely_stub", FP, 1, 1, "dict", "A stub.", "{}")])
    assessor = _Assessor(conn)
    result = scaffold_from_pattern(assessor, {"symbol": "lonely_stub"})
    assert "No structural siblings found" in result


def test_limit_respected():
    rows = [("target", FP, 1, 1, "dict", "stub.", "{}")]
    for i in range(10):
        rows.append((f"sibling_{i}", FP, i + 10, 0, "dict", f"sibling {i}.", "{}"))
    conn = _make_db(rows)
    assessor = _Assessor(conn)
    result = scaffold_from_pattern(assessor, {"symbol": "target", "limit": "3"})
    # Count sibling lines in the STRUCTURAL SIBLINGS block
    sibling_lines = [l for l in result.splitlines() if l.strip().startswith("- sibling_")]
    assert len(sibling_lines) <= 3


def test_header_shows_symbol_and_file():
    conn = _make_db(_base_rows())
    assessor = _Assessor(conn)
    result = scaffold_from_pattern(assessor, {"symbol": "my_stub"})
    assert "my_stub" in result
    assert "module.py" in result


def test_stubs_not_included_as_siblings():
    rows = [
        ("target_stub", FP, 1, 1, "dict", "stub.", "{}"),
        ("other_stub", FP, 5, 1, "dict", "another stub.", "{}"),  # is_stub=1 -- should be excluded
        ("real_impl", FP, 10, 0, "dict", "real impl.", "{}"),
    ]
    conn = _make_db(rows)
    assessor = _Assessor(conn)
    result = scaffold_from_pattern(assessor, {"symbol": "target_stub"})
    # other_stub must not appear as a sibling
    assert "other_stub" not in result
    assert "real_impl" in result
