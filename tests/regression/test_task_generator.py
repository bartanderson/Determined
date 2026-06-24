# tools/analysis/tests/regression/test_task_generator.py
#
# Locks in task.md generator (TRACKER item 10, step 1, 2026-06-19).
# Two-tier model: direct callers (graph_edges WHERE callee=?) and impact zone
# (route_query with seeds override). See TRACKER item 6 audit for rationale.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema

os.environ.setdefault("PYTHONPATH", ".")


# =========================================================
# MINIMAL ORACLE STUB
# =========================================================

class FakeOracle:
    """Duck-type oracle for testing: holds a real sqlite conn + edge list."""
    def __init__(self, conn, edges=()):
        self.conn = conn
        self._edges = list(edges)  # list of (caller, callee) tuples

    def get_edge_maps(self):
        forward, reverse = {}, {}
        for caller, callee in self._edges:
            forward.setdefault(caller, set()).add(callee)
            reverse.setdefault(callee, set()).add(caller)
        return forward, reverse

    def discover_seed_symbols(self, text, limit=20):
        return []

    def builtin_symbols(self):
        return frozenset()


# =========================================================
# FIXTURE
# =========================================================

def _make_oracle():
    """
    Real in-memory DB with schema.
    Graph: dispatcher -> handler -> helper
    We'll generate task.md for 'handler'.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=MEMORY")
    ensure_schema(conn)

    rows = [
        # (file_path, caller, callee, line_number, bucket)
        ("dispatch.py", "dispatcher", "handler", 10, "project"),
        ("handle.py",   "handler",   "helper",   20, "project"),
    ]
    for fp, caller, callee, line, bucket in rows:
        conn.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES (?, ?, ?, ?, ?)",
            (fp, caller, callee, line, bucket),
        )
        conn.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (caller, callee, caller, callee, line),
        )
    conn.commit()
    return FakeOracle(conn, edges=[("dispatcher", "handler"), ("handler", "helper")])


# =========================================================
# TESTS
# =========================================================

def test_direct_callers_found():
    from determined.agent.task_generator import _direct_callers
    oracle = _make_oracle()
    callers = _direct_callers(oracle.conn, "handler")
    assert len(callers) == 1
    assert callers[0]["caller"] == "dispatcher"
    assert "dispatch.py" in callers[0]["file_path"]


def test_direct_callers_found_via_qualified_name():
    """Callee stored as 'module.symbol' must still match a bare-name query."""
    import sqlite3
    from determined.persistence.persistence_engine import ensure_schema
    from determined.agent.task_generator import _direct_callers
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=MEMORY")
    ensure_schema(conn)
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
        "VALUES ('caller_fn', 'mod.handler', 'caller_fn', 'mod.handler', 7)"
    )
    conn.commit()
    callers = _direct_callers(conn, "handler")
    assert len(callers) == 1
    assert callers[0]["caller"] == "caller_fn"


def test_direct_callers_empty_for_unknown_symbol():
    from determined.agent.task_generator import _direct_callers
    oracle = _make_oracle()
    callers = _direct_callers(oracle.conn, "nonexistent_symbol")
    assert callers == []


def test_impact_zone_excludes_seed():
    from determined.agent.task_generator import _impact_zone
    oracle = _make_oracle()
    zone = _impact_zone("handler", oracle)
    assert "handler" not in zone


def test_generate_returns_markdown_string():
    from determined.agent.task_generator import generate_task_md
    oracle = _make_oracle()
    md = generate_task_md(symbol="handler", oracle=oracle)
    assert isinstance(md, str)
    assert "handler" in md
    assert "Direct callers (confirmed)" in md
    assert "Impact zone" in md


def test_direct_callers_appear_in_output():
    from determined.agent.task_generator import generate_task_md
    oracle = _make_oracle()
    md = generate_task_md("handler", oracle)
    assert "dispatcher" in md
    assert "dispatch.py" in md


def test_generate_writes_file():
    from determined.agent.task_generator import generate_task_md
    oracle = _make_oracle()
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
        path = f.name
    try:
        generate_task_md("handler", oracle, out_path=path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "handler" in content
        assert "Direct callers (confirmed)" in content
    finally:
        os.remove(path)


def test_assessor_generate_task_md_wired():
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor

    tmp = tempfile.mktemp(suffix=".db")
    try:
        oracle = DBOracle(tmp)
        ensure_schema(oracle.conn)
        oracle.conn.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES ('a.py', 'caller_fn', 'target_fn', 5, 'project')"
        )
        oracle.conn.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
            "VALUES ('caller_fn', 'target_fn', 'caller_fn', 'target_fn', 5)"
        )
        oracle.conn.commit()

        assessor = Assessor(oracle)
        md = assessor.generate_task_md("target_fn")
        assert "target_fn" in md
        assert "Direct callers (confirmed)" in md
        assert "caller_fn" in md
    finally:
        import os
        oracle.conn.close()
        if os.path.exists(tmp):
            os.remove(tmp)


def _make_knowledge_conn():
    from determined.intent.knowledge_artifact import ensure_knowledge_artifacts_table
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    ensure_knowledge_artifacts_table(cursor)
    conn.commit()
    return conn


def test_known_findings_appear_in_output():
    from determined.agent.task_generator import generate_task_md
    from determined.intent.knowledge_artifact import add_artifact
    oracle = _make_oracle()
    kconn = _make_knowledge_conn()
    add_artifact(kconn, "handler", "known_issue", "Handler silently drops errors.", "human-confirmed")
    md = generate_task_md("handler", oracle, knowledge_conn=kconn)
    assert "Known findings" in md
    assert "Handler silently drops errors." in md
    assert "human-confirmed" in md


def test_no_findings_section_when_no_artifacts():
    from determined.agent.task_generator import generate_task_md
    oracle = _make_oracle()
    kconn = _make_knowledge_conn()
    md = generate_task_md("handler", oracle, knowledge_conn=kconn)
    assert "Known findings" not in md


if __name__ == "__main__":
    tests = [
        test_direct_callers_found,
        test_direct_callers_empty_for_unknown_symbol,
        test_impact_zone_excludes_seed,
        test_generate_returns_markdown_string,
        test_direct_callers_appear_in_output,
        test_generate_writes_file,
        test_assessor_generate_task_md_wired,
        test_known_findings_appear_in_output,
        test_no_findings_section_when_no_artifacts,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
