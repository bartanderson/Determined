# tests/regression/test_call_graph_accuracy.py
#
# Tests for item 20: call graph accuracy via type annotation exploitation
# and __init__ attribute tracking.

import sqlite3
import textwrap
from pathlib import Path

import pytest

from determined.ingestion.parse_ast import parse_ast, _extract_class_attributes, _extract_functions
from determined.ingestion.scan_project_files import scan_project_files
from determined.persistence.persistence_engine import create_database, persist_all
from determined.classification.classify_references import classify_references
from determined.graph.graph_builder import GraphBuilder


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_project(root: Path, files: dict[str, str]) -> None:
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(src), encoding="utf-8")


def _ingest(root: Path, db_path: str) -> sqlite3.Connection:
    conn = create_database(db_path)
    file_analyses = list(scan_project_files(str(root), [], str(root)))
    file_analyses = [classify_references(a, []) for a in file_analyses]
    builder = GraphBuilder()
    for analysis in file_analyses:
        for ref in analysis.symbol_references:
            builder.add_reference(
                caller=ref.caller,
                callee=ref.callee,
                line_number=ref.line_number,
                bucket=getattr(ref, "bucket", "unknown"),
                caller_file=analysis.file_path,
                resolved=getattr(ref, "resolved", False),
            )
    graph = builder.build()
    persist_all(connection=conn, file_analyses=file_analyses, graph=graph,
                project_prefixes=[], project_root=str(root))
    return conn


# ------------------------------------------------------------------
# Phase 1a: param type capture
# ------------------------------------------------------------------

def test_extract_functions_captures_param_types():
    """_extract_functions captures type annotations for function parameters."""
    import ast
    src = textwrap.dedent("""
        def process(item: MyClass, count: int) -> None:
            pass

        def no_annotations(x, y):
            pass
    """)
    tree = ast.parse(src)
    fns = _extract_functions(tree)
    fn_map = {f.name: f for f in fns}

    assert fn_map["process"].param_types == {"item": "MyClass", "count": "int"}
    assert fn_map["no_annotations"].param_types == {}


def test_extract_functions_skips_self():
    """self is excluded from param_types."""
    import ast
    src = textwrap.dedent("""
        class Foo:
            def method(self, x: Bar) -> None:
                pass
    """)
    tree = ast.parse(src)
    fns = _extract_functions(tree)
    method = next(f for f in fns if f.name == "method")
    assert "self" not in method.param_types
    assert method.param_types == {"x": "Bar"}


# ------------------------------------------------------------------
# Phase 1b: class attribute extraction
# ------------------------------------------------------------------

def test_extract_class_attributes_from_annotation():
    """Extracts self.x: Foo style annotations."""
    import ast
    src = textwrap.dedent("""
        class MyClass:
            def __init__(self):
                self.engine: Engine = None
                self.name: str = ""
    """)
    tree = ast.parse(src)
    attrs = _extract_class_attributes(tree)
    attr_map = {(a.class_name, a.attribute): a.inferred_type for a in attrs}

    assert attr_map[("MyClass", "engine")] == "Engine"
    assert attr_map[("MyClass", "name")] == "str"


def test_extract_class_attributes_from_constructor_call():
    """Extracts self.x = Foo() style constructor assignments."""
    import ast
    src = textwrap.dedent("""
        class Manager:
            def __init__(self):
                self.db = Database()
                self.cache = CacheStore()
    """)
    tree = ast.parse(src)
    attrs = _extract_class_attributes(tree)
    attr_map = {(a.class_name, a.attribute): a.inferred_type for a in attrs}

    assert attr_map[("Manager", "db")] == "Database"
    assert attr_map[("Manager", "cache")] == "CacheStore"


def test_extract_class_attributes_no_init():
    """Classes without __init__ produce no attributes."""
    import ast
    src = textwrap.dedent("""
        class Empty:
            x = 1
    """)
    tree = ast.parse(src)
    attrs = _extract_class_attributes(tree)
    assert attrs == []


# ------------------------------------------------------------------
# Phase 2: annotation-resolved call edges
# ------------------------------------------------------------------

def test_param_annotation_resolves_method_call(tmp_path):
    """obj.method() where obj: Foo is annotated emits Foo.method with resolved=True."""
    import ast as _ast
    from determined.core.pathing import normalize_file_path

    src = textwrap.dedent("""
        class Engine:
            def run(self):
                pass

        def process(eng: Engine):
            eng.run()
    """)
    fp = tmp_path / "pkg.py"
    fp.write_text(src, encoding="utf-8")
    normalized = normalize_file_path(str(fp))
    analysis = parse_ast(normalized, global_known_symbols={"Engine", "process"})

    resolved_refs = [r for r in analysis.symbol_references if r.resolved]
    callee_names = [r.callee for r in resolved_refs]

    assert any("Engine.run" in c for c in callee_names), \
        f"Expected annotation-resolved Engine.run in {callee_names}"


def test_self_method_call_resolved(tmp_path):
    """self.method() inside a class emits ClassName.method with resolved=True."""
    import ast as _ast
    from determined.core.pathing import normalize_file_path

    src = textwrap.dedent("""
        class Worker:
            def start(self):
                pass

            def run(self):
                self.start()
    """)
    fp = tmp_path / "worker.py"
    fp.write_text(src, encoding="utf-8")
    normalized = normalize_file_path(str(fp))
    analysis = parse_ast(normalized, global_known_symbols={"Worker"})

    resolved_refs = [r for r in analysis.symbol_references if r.resolved]
    callee_names = [r.callee for r in resolved_refs]

    assert any("Worker.start" in c for c in callee_names), \
        f"Expected annotation-resolved Worker.start in {callee_names}"


def test_unresolved_call_not_flagged(tmp_path):
    """obj.method() without annotation is NOT marked resolved."""
    import ast as _ast
    from determined.core.pathing import normalize_file_path

    src = textwrap.dedent("""
        def process(obj):
            obj.run()
    """)
    fp = tmp_path / "plain.py"
    fp.write_text(src, encoding="utf-8")
    normalized = normalize_file_path(str(fp))
    analysis = parse_ast(normalized, global_known_symbols=set())

    resolved_refs = [r for r in analysis.symbol_references if r.resolved]
    assert resolved_refs == [], f"Expected no resolved refs, got: {resolved_refs}"


# ------------------------------------------------------------------
# Phase 3: DB persistence
# ------------------------------------------------------------------

def test_class_attributes_persisted(tmp_path):
    """class_attributes are stored in the corpus DB after ingestion."""
    _make_project(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/foo.py": """
            class Engine:
                def __init__(self):
                    self.db: Database = None
                    self.cache = CacheStore()
        """,
    })
    conn = _ingest(tmp_path, str(tmp_path / "corpus.db"))
    rows = conn.execute(
        "SELECT class_name, attribute, inferred_type FROM class_attributes ORDER BY attribute"
    ).fetchall()
    conn.close()

    attr_map = {r[1]: (r[0], r[2]) for r in rows}
    assert "db" in attr_map
    assert attr_map["db"] == ("Engine", "Database")
    assert "cache" in attr_map
    assert attr_map["cache"] == ("Engine", "CacheStore")


def test_param_types_json_persisted(tmp_path):
    """param_types_json is stored in the functions table after ingestion."""
    _make_project(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/foo.py": """
            def process(item: MyClass, count: int) -> None:
                pass
        """,
    })
    conn = _ingest(tmp_path, str(tmp_path / "corpus.db"))
    row = conn.execute(
        "SELECT param_types_json FROM functions WHERE name = 'process'"
    ).fetchone()
    conn.close()

    import json
    assert row is not None
    types = json.loads(row[0])
    assert types.get("item") == "MyClass"
    assert types.get("count") == "int"


def test_resolved_edges_persisted(tmp_path):
    """graph_edges.resolved=1 for annotation-derived edges after ingestion."""
    _make_project(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/foo.py": """
            class Engine:
                def run(self):
                    pass

            def process(eng: Engine):
                eng.run()
        """,
    })
    conn = _ingest(tmp_path, str(tmp_path / "corpus.db"))
    resolved = conn.execute(
        "SELECT COUNT(*) FROM graph_edges WHERE resolved = 1"
    ).fetchone()[0]
    conn.close()

    assert resolved > 0, "Expected at least one annotation-resolved edge in graph_edges"


def test_db_oracle_get_class_attribute_type(tmp_path):
    """DBOracle.get_class_attribute_type returns the inferred type."""
    _make_project(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/foo.py": """
            class Manager:
                def __init__(self):
                    self.engine: Engine = None
        """,
    })
    db_path = str(tmp_path / "corpus.db")
    conn = _ingest(tmp_path, db_path)
    conn.close()

    from determined.oracle.db_oracle import DBOracle
    oracle = DBOracle(db_path)
    result = oracle.get_class_attribute_type("Manager", "engine")
    oracle.conn.close()

    assert result == "Engine"


def test_db_oracle_get_class_attribute_type_missing(tmp_path):
    """get_class_attribute_type returns None for unknown class/attr."""
    _make_project(tmp_path, {"pkg/__init__.py": ""})
    db_path = str(tmp_path / "corpus.db")
    conn = _ingest(tmp_path, db_path)
    conn.close()

    from determined.oracle.db_oracle import DBOracle
    oracle = DBOracle(db_path)
    result = oracle.get_class_attribute_type("NoSuchClass", "attr")
    oracle.conn.close()

    assert result is None
