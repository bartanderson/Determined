"""
Regression tests for Rust trait dispatch:
  - LanguageWalker.trait_types() extracts trait method signatures
  - LanguageWalker.impl_trait_map() extracts {concrete_type: trait_name}
  - persist_all inserts trait_dispatch edges after ingestion
"""

import sqlite3
import textwrap
from pathlib import Path

import pytest

from determined.ingestion.language_walker import LanguageWalker
from determined.persistence.persistence_engine import persist_all, ensure_schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rust_walker(src: str, filename: str = "mymod") -> LanguageWalker:
    return LanguageWalker(src, f"/fake/{filename}.rs", "rust")


# ---------------------------------------------------------------------------
# trait_types() tests
# ---------------------------------------------------------------------------

TRAIT_SRC = textwrap.dedent("""\
    pub trait Shape {
        fn area(&self) -> f64;
        fn perimeter(&self) -> f64;
    }

    pub trait Drawable {
        fn draw(&self);
    }
""")


def test_trait_types_returns_methods():
    w = rust_walker(TRAIT_SRC)
    traits = w.trait_types()
    assert "Shape" in traits
    assert set(traits["Shape"]) == {"area", "perimeter"}


def test_trait_types_multiple_traits():
    w = rust_walker(TRAIT_SRC)
    traits = w.trait_types()
    assert "Drawable" in traits
    assert traits["Drawable"] == ["draw"]


def test_trait_types_empty_for_go():
    src = "package main\nfunc Foo() {}\n"
    w = LanguageWalker(src, "/fake/main.go", "go")
    assert w.trait_types() == {}


# ---------------------------------------------------------------------------
# impl_trait_map() tests
# ---------------------------------------------------------------------------

IMPL_SRC = textwrap.dedent("""\
    struct Circle { radius: f64 }
    struct Square { side: f64 }

    impl Shape for Circle {
        fn area(&self) -> f64 { 3.14 * self.radius * self.radius }
        fn perimeter(&self) -> f64 { 2.0 * 3.14 * self.radius }
    }

    impl Shape for Square {
        fn area(&self) -> f64 { self.side * self.side }
        fn perimeter(&self) -> f64 { 4.0 * self.side }
    }

    impl Circle {
        fn new(r: f64) -> Self { Circle { radius: r } }
    }
""")


def test_impl_trait_map_detects_trait_impls():
    w = rust_walker(IMPL_SRC)
    m = w.impl_trait_map()
    assert "Shape" in m.get("Circle", [])
    assert "Shape" in m.get("Square", [])


def test_impl_trait_map_ignores_plain_impl():
    w = rust_walker(IMPL_SRC)
    m = w.impl_trait_map()
    # plain "impl Circle" has no trait; Circle should appear via "impl Shape for Circle"
    assert "Circle" in m


def test_impl_trait_map_empty_for_no_trait_impls():
    src = textwrap.dedent("""\
        struct Foo {}
        impl Foo { fn bar(&self) {} }
    """)
    w = rust_walker(src)
    assert w.impl_trait_map() == {}


# ---------------------------------------------------------------------------
# End-to-end: persist_all inserts trait_dispatch edges
# ---------------------------------------------------------------------------

TRAIT_FILE = textwrap.dedent("""\
    pub trait Greet {
        fn hello(&self) -> String;
        fn goodbye(&self) -> String;
    }
""")

IMPL_FILE = textwrap.dedent("""\
    struct English;
    struct French;

    impl Greet for English {
        fn hello(&self) -> String { String::from("Hello") }
        fn goodbye(&self) -> String { String::from("Goodbye") }
    }

    impl Greet for French {
        fn hello(&self) -> String { String::from("Bonjour") }
        fn goodbye(&self) -> String { String::from("Au revoir") }
    }
""")


@pytest.fixture()
def rust_project(tmp_path):
    (tmp_path / "greet.rs").write_text(TRAIT_FILE, encoding="utf-8")
    (tmp_path / "impls.rs").write_text(IMPL_FILE, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def db_with_rust(rust_project):
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)

    class _EmptyGraph:
        edges = []

    persist_all(
        connection=conn,
        file_analyses=[],
        graph=_EmptyGraph(),
        project_prefixes=[],
        project_root=str(rust_project),
    )
    conn.commit()
    return conn


def test_rust_concrete_methods_in_functions(db_with_rust):
    names = {r[0] for r in db_with_rust.execute("SELECT name FROM functions").fetchall()}
    assert "English::hello" in names
    assert "French::goodbye" in names


def test_rust_trait_dispatch_edges_inserted(db_with_rust):
    rows = db_with_rust.execute(
        "SELECT caller, callee FROM graph_edges WHERE edge_type = 'trait_dispatch'"
    ).fetchall()
    pairs = {(r[0], r[1]) for r in rows}
    assert ("Greet::hello", "English::hello") in pairs
    assert ("Greet::goodbye", "English::goodbye") in pairs
    assert ("Greet::hello", "French::hello") in pairs
    assert ("Greet::goodbye", "French::goodbye") in pairs


def test_rust_trait_dispatch_edge_count(db_with_rust):
    count = db_with_rust.execute(
        "SELECT COUNT(*) FROM graph_edges WHERE edge_type = 'trait_dispatch'"
    ).fetchone()[0]
    # 2 implementors × 2 methods = 4
    assert count == 4


def test_rust_trait_dispatch_reingest_idempotent(db_with_rust, rust_project):
    class _EmptyGraph:
        edges = []

    persist_all(
        connection=db_with_rust,
        file_analyses=[],
        graph=_EmptyGraph(),
        project_prefixes=[],
        project_root=str(rust_project),
    )
    db_with_rust.commit()
    count = db_with_rust.execute(
        "SELECT COUNT(*) FROM graph_edges WHERE edge_type = 'trait_dispatch'"
    ).fetchone()[0]
    assert count == 4  # still 4, not 8
