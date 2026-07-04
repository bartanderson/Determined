# tests/regression/test_pattern_executor.py
#
# Regression tests for pattern_executor.py.
# Tests detect_pattern and run_no_llm (no LLM needed).

import os
import sqlite3

os.environ.setdefault("PYTHONPATH", ".")

from determined.agent.pattern_executor import detect_pattern, PatternExecutor, _fill_args
from determined.agent.tool_registry import TASK_PATTERNS


# ------------------------------------------------------------------
# detect_pattern
# ------------------------------------------------------------------

def test_detect_understand_symbol():
    name, subject = detect_pattern("understand process_message")
    assert name == "understand_symbol"
    assert subject == "process_message"

def test_detect_understand_symbol_variants():
    for phrase in ["explain adjudication_engine", "tell me about WorldController", "describe run_query"]:
        name, subject = detect_pattern(phrase)
        assert name == "understand_symbol", f"failed for: {phrase}"
        assert subject is not None

def test_detect_assess_change_risk():
    name, subject = detect_pattern("risk of changing process_message")
    assert name == "assess_change_risk"
    assert subject == "process_message"

def test_detect_assess_risk_variants():
    name, subject = detect_pattern("is it safe to change route_query")
    assert name == "assess_change_risk"
    assert subject is not None

def test_detect_explore_file():
    name, subject = detect_pattern("explore world_controller.py")
    assert name == "explore_file"
    assert "world_controller" in subject

def test_detect_orient():
    for phrase in ["orient me to this codebase", "where do I start", "give me an overview"]:
        name, subject = detect_pattern(phrase)
        assert name == "orient_to_codebase", f"failed for: {phrase}"
        assert subject is None

def test_detect_dead_code():
    name, subject = detect_pattern("find dead code")
    assert name == "find_dead_code"
    assert subject is None

def test_detect_session_startup():
    name, subject = detect_pattern("session startup")
    assert name == "session_startup"
    assert subject is None

def test_detect_trace_data_flow():
    name, subject = detect_pattern("trace process_message to store_finding")
    assert name == "trace_data_flow"
    assert isinstance(subject, tuple)
    assert subject[0] == "process_message"
    assert subject[1] == "store_finding"

def test_detect_no_match():
    name, subject = detect_pattern("what is the weather today")
    assert name is None
    assert subject is None


# ------------------------------------------------------------------
# _fill_args
# ------------------------------------------------------------------

def test_fill_args_simple():
    result = _fill_args({"symbol": "<name>"}, "process_message")
    assert result == {"symbol": "process_message"}

def test_fill_args_no_subject():
    result = _fill_args({}, None)
    assert result == {}

def test_fill_args_tuple_subject():
    result = _fill_args({"src": "<source>", "dst": "<sink>"}, ("A", "B"))
    assert result["src"] == "A"
    assert result["dst"] == "B"

def test_fill_args_literal_value():
    result = _fill_args({"kind": "hot"}, "anything")
    assert result["kind"] == "hot"


# ------------------------------------------------------------------
# PatternExecutor.run_no_llm - validates tool dispatch without LLM
# Uses a minimal fake oracle/assessor duck-type
# ------------------------------------------------------------------

class _FakeOracle:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE files (file_path TEXT, line_count INTEGER, role TEXT)"
        )
        self.conn.execute(
            "CREATE TABLE functions (name TEXT, file_path TEXT, line_number INTEGER, "
            "docstring TEXT, is_stub INTEGER DEFAULT 0)"
        )
        self.conn.execute(
            "CREATE TABLE classes (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
        )
        self.conn.execute(
            "CREATE TABLE graph_edges (caller TEXT, callee TEXT, line_number INTEGER)"
        )
        self.conn.execute(
            "INSERT INTO functions VALUES ('process_message', '/proj/main.py', 10, 'Handles messages.', 0)"
        )
        self.conn.execute(
            "INSERT INTO files VALUES ('/proj/main.py', 50, NULL)"
        )
        self.conn.commit()

    def get_project_root(self):
        return "/proj"

    def find_symbols(self, pattern, **_):
        rows = self.conn.execute(
            "SELECT name, file_path, 'function' AS symbol_type, line_number "
            "FROM functions WHERE name LIKE ?", (f"%{pattern}%",)
        ).fetchall()
        return [dict(r) for r in rows]

    def find_files(self, pattern="", **_):
        rows = self.conn.execute(
            "SELECT file_path, line_count FROM files WHERE file_path LIKE ?",
            (f"%{pattern}%",),
        ).fetchall()
        return [dict(r) for r in rows]


class _FakeAssessor:
    def __init__(self, oracle):
        self.oracle = oracle
        self._knowledge_conn = None

    def semantic_summary(self, *a, **kw):
        return {"content": "(fake summary)", "cache_hit": False}

    def generate_task_md(self, symbol):
        return f"(fake brief for {symbol})"

    def get_artifacts(self, subject):
        return []

    def extract_design_facts(self, **_):
        return {"entry_points": 0, "dead_code": 0, "hot_symbols": 0, "stub_files": 0}

    def workflow_status(self, **_):
        return "No active workflow items."

    def list_workflow_items(self, **_):
        return []

    def prioritize_workflow(self, **_):
        return "No items to prioritize."


def test_run_no_llm_understand_symbol():
    oracle = _FakeOracle()
    assessor = _FakeAssessor(oracle)
    executor = PatternExecutor()
    result = executor.run_no_llm("understand_symbol", "process_message", oracle, assessor)
    assert "understand_symbol" in result
    assert "process_message" in result


def test_run_no_llm_orient_to_codebase():
    oracle = _FakeOracle()
    assessor = _FakeAssessor(oracle)
    executor = PatternExecutor()
    result = executor.run_no_llm("orient_to_codebase", None, oracle, assessor)
    assert "orient_to_codebase" in result


def test_all_patterns_have_valid_tools():
    """Every tool referenced in TASK_PATTERNS must exist in TOOLS."""
    from determined.agent.agent_tools import TOOLS
    for pname, pdata in TASK_PATTERNS.items():
        for step in pdata["steps"]:
            tool = step["tool"]
            assert tool in TOOLS, f"Pattern '{pname}' references unknown tool '{tool}'"


# ------------------------------------------------------------------
# RUN DIRECTLY
# ------------------------------------------------------------------

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
