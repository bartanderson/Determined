# tools/analysis/tests/regression/test_task_rereferencer.py
#
# Locks in task.md re-reference path (TRACKER item 10 step 2, 2026-06-19).
# Workflow: read task.md -> extract symbol -> re-run query -> diff -> report.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema

os.environ.setdefault("PYTHONPATH", ".")


class FakeOracle:
    """Duck-type oracle for testing: holds a real sqlite conn + edge list."""
    def __init__(self, conn, edges=()):
        self.conn = conn
        self._edges = list(edges)

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


SAMPLE_TASK_MD = """\
# task: review impact of changes to `handler`
Generated 2026-06-01 by tools/analysis task_generator.

---

## Direct callers (confirmed)

_These call `handler` directly._

- [ ] `dispatcher` at `dispatch.py:10`

## Impact zone (may need review)

_These symbols are in the reverse-closure neighborhood of `handler`._

- [ ] `middleware`

---

## Notes

- Direct callers list is exact.
"""


# =========================================================
# EXTRACT SYMBOL
# =========================================================

def test_extract_symbol_from_header():
    from determined.agent.task_rereferencer import extract_symbol
    assert extract_symbol(SAMPLE_TASK_MD) == "handler"


def test_extract_symbol_returns_none_for_bad_header():
    from determined.agent.task_rereferencer import extract_symbol
    assert extract_symbol("# some other header\nno match here") is None


# =========================================================
# PARSE EXISTING TASK.MD SECTIONS
# =========================================================

def test_parse_direct_callers_from_content():
    from determined.agent.task_rereferencer import _parse_direct_callers
    callers = _parse_direct_callers(SAMPLE_TASK_MD)
    assert "dispatcher" in callers


def test_parse_impact_zone_from_content():
    from determined.agent.task_rereferencer import _parse_impact_zone
    zone = _parse_impact_zone(SAMPLE_TASK_MD)
    assert "middleware" in zone


# =========================================================
# DIFF: NO CHANGE
# =========================================================

def _make_oracle_with_dispatcher():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=MEMORY")
    ensure_schema(conn)
    conn.execute(
        "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
        "VALUES ('dispatch.py', 'dispatcher', 'handler', 10, 'project')"
    )
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
        "VALUES ('dispatcher', 'handler', 'dispatcher', 'handler', 10)"
    )
    conn.commit()
    return FakeOracle(conn, edges=[("dispatcher", "handler")])


def test_diff_unchanged_when_db_matches():
    from determined.agent.task_rereferencer import diff_task_md
    oracle = _make_oracle_with_dispatcher()
    # Impact zone from route_query with seeds=[handler] - dispatcher calls handler,
    # route_query reverse-expands: dispatcher is the reverse neighbor.
    # middleware was in old task.md but NOT in the graph -> shows as removed.
    diff = diff_task_md(SAMPLE_TASK_MD, "handler", oracle)
    # Direct callers: dispatcher is in both old and new -> no change
    assert "dispatcher" not in diff["direct_callers"]["added"]
    assert "dispatcher" not in diff["direct_callers"]["removed"]


def test_diff_detects_new_caller():
    from determined.agent.task_rereferencer import diff_task_md
    oracle = _make_oracle_with_dispatcher()
    # Add a second caller not in the sample task.md
    oracle.conn.execute(
        "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
        "VALUES ('router.py', 'router_fn', 'handler', 30, 'project')"
    )
    oracle.conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
        "VALUES ('router_fn', 'handler', 'router_fn', 'handler', 30)"
    )
    oracle.conn.commit()
    oracle._edges.append(("router_fn", "handler"))
    diff = diff_task_md(SAMPLE_TASK_MD, "handler", oracle)
    assert "router_fn" in diff["direct_callers"]["added"]
    assert diff["unchanged"] is False


def test_diff_detects_removed_caller():
    from determined.agent.task_rereferencer import diff_task_md
    # Empty DB - dispatcher no longer calls handler
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=MEMORY")
    ensure_schema(conn)
    conn.commit()
    oracle = FakeOracle(conn, edges=[])
    diff = diff_task_md(SAMPLE_TASK_MD, "handler", oracle)
    assert "dispatcher" in diff["direct_callers"]["removed"]
    assert diff["unchanged"] is False


# =========================================================
# RENDER DIFF MARKDOWN
# =========================================================

def test_render_diff_md_unchanged():
    from determined.agent.task_rereferencer import render_diff_md
    diff = {
        "symbol": "handler",
        "direct_callers": {"added": [], "removed": []},
        "impact_zone": {"added": [], "removed": []},
        "unchanged": True,
    }
    md = render_diff_md(diff)
    assert "No changes" in md
    assert "handler" in md


def test_render_diff_md_with_changes():
    from determined.agent.task_rereferencer import render_diff_md
    diff = {
        "symbol": "handler",
        "direct_callers": {"added": ["new_caller"], "removed": ["old_caller"]},
        "impact_zone": {"added": [], "removed": []},
        "unchanged": False,
    }
    md = render_diff_md(diff)
    assert "new_caller" in md
    assert "old_caller" in md


# =========================================================
# END-TO-END: FILE-BASED
# =========================================================

def test_rereference_reads_file_and_diffs():
    from determined.agent.task_rereferencer import rereference_task_md
    oracle = _make_oracle_with_dispatcher()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_TASK_MD)
        path = f.name
    try:
        result = rereference_task_md(path, oracle)
        assert result["symbol"] == "handler"
        assert "diff_md" in result
        assert "handler" in result["diff_md"]
    finally:
        os.remove(path)


def test_rereference_raises_on_bad_header():
    from determined.agent.task_rereferencer import rereference_task_md
    oracle = FakeOracle(sqlite3.connect(":memory:"), edges=[])
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# not a valid task header\nsome content\n")
        path = f.name
    try:
        try:
            rereference_task_md(path, oracle)
            assert False, "expected ValueError"
        except ValueError as e:
            assert "symbol" in str(e).lower() or "header" in str(e).lower()
    finally:
        os.remove(path)


# =========================================================
# ASSESSOR WIRING
# =========================================================

def test_assessor_rereference_task_md_wired():
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor

    tmp_db = tempfile.mktemp(suffix=".db")
    tmp_task = tempfile.mktemp(suffix=".md")
    try:
        oracle = DBOracle(tmp_db)
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
        # Generate a real task.md first
        assessor.generate_task_md("target_fn", out_path=tmp_task)
        # Re-reference it - DB unchanged so direct callers tier should match
        result = assessor.rereference_task_md(tmp_task)
        assert result["symbol"] == "target_fn"
        assert "diff_md" in result
    finally:
        oracle.conn.close()
        for p in (tmp_db, tmp_task):
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    tests = [
        test_extract_symbol_from_header,
        test_extract_symbol_returns_none_for_bad_header,
        test_parse_direct_callers_from_content,
        test_parse_impact_zone_from_content,
        test_diff_unchanged_when_db_matches,
        test_diff_detects_new_caller,
        test_diff_detects_removed_caller,
        test_render_diff_md_unchanged,
        test_render_diff_md_with_changes,
        test_rereference_reads_file_and_diffs,
        test_rereference_raises_on_bad_header,
        test_assessor_rereference_task_md_wired,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
