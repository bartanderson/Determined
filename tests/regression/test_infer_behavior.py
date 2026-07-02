# tests/regression/test_infer_behavior.py
#
# Tests for infer_behavior tool and the role pattern library.
# Phase 1: no LLM required - pattern seeding, context assembly, dispatch.
# Phase 2: live LLM - only runs when llama-server is available (pytest -m live_llm).

import sqlite3

import pytest

from determined.agent.agent_tools import (
    _ROLE_PATTERNS,
    _ensure_pattern_library,
    infer_behavior,
)
from determined.persistence.persistence_engine import ensure_schema
from determined.intent.semantic_summary import ensure_semantic_summaries_table
from determined.intent.knowledge_artifact import ensure_knowledge_artifacts_table


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

PROJECT_ROOT = "C:/project"


class FakeOracle:
    def __init__(self, conn):
        self.conn = conn
        self.db_path = ":memory:"

    def get_project_root(self):
        return PROJECT_ROOT

    def find_symbols(self, pattern, symbol_type=None, exact=False, limit=50):
        cond = "name = ?" if exact else "name LIKE ?"
        params = [pattern if exact else f"%{pattern}%"]
        if symbol_type:
            cond += " AND symbol_type = ?"
            params.append(symbol_type)
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT name, file_path, symbol_type, line_number, signature, canonical_id "
            f"FROM symbols WHERE {cond} LIMIT ?", params,
        ).fetchall()
        return [dict(r) for r in rows]

    def find_files(self, pattern=None, role=None, limit=None):
        conditions, params = [], []
        if pattern:
            conditions.append("file_path LIKE ?")
            params.append(f"%{pattern}%")
        q = "SELECT file_path, line_count, role, is_hot FROM files"
        if conditions:
            q += " WHERE " + " AND ".join(conditions)
        if limit:
            q += " LIMIT ?"
            params.append(limit)
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]

    def get_edge_maps(self):
        rows = self.conn.execute(
            "SELECT caller, callee FROM graph_edges"
        ).fetchall()
        forward, reverse = {}, {}
        for r in rows:
            forward.setdefault(r[0], set()).add(r[1])
            reverse.setdefault(r[1], set()).add(r[0])
        return forward, reverse

    def builtin_symbols(self):
        return frozenset()

    def discover_seed_symbols(self, text, limit=20):
        return []


class FakeAssessor:
    def __init__(self, oracle):
        self.oracle = oracle
        self._knowledge_conn = oracle.conn

    def get_artifacts(self, subject):
        rows = self._knowledge_conn.execute(
            "SELECT id, subject, kind, content, provenance, created_at, file_hash, needs_review "
            "FROM knowledge_artifacts WHERE subject = ? ORDER BY created_at DESC",
            (subject,),
        ).fetchall()
        keys = ["id", "subject", "kind", "content", "provenance", "created_at", "file_hash", "needs_review"]
        return [dict(zip(keys, r)) for r in rows]

    def add_artifact(self, subject, kind, content, provenance):
        from determined.intent.knowledge_artifact import VALID_KINDS, VALID_PROVENANCES
        if kind not in VALID_KINDS:
            raise ValueError(f"invalid kind: {kind}")
        if provenance not in VALID_PROVENANCES:
            raise ValueError(f"invalid provenance: {provenance}")
        self._knowledge_conn.execute(
            "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (subject, kind, content, provenance),
        )
        self._knowledge_conn.commit()

    def list_artifacts(self, kind=None):
        return []

    def list_semantic_summaries(self, kind=None):
        return []


def _make_oracle():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=MEMORY")
    ensure_schema(conn)
    cur = conn.cursor()
    ensure_semantic_summaries_table(cur)
    ensure_knowledge_artifacts_table(cur)
    conn.commit()
    return FakeOracle(conn)


# ---------------------------------------------------------------------------
# Pattern library — no LLM
# ---------------------------------------------------------------------------

class TestPatternLibrary:
    def test_patterns_defined(self):
        assert len(_ROLE_PATTERNS) >= 6
        roles = {p["subject"] for p in _ROLE_PATTERNS}
        # Wirfs-Brock Responsibility-Driven Design roles
        assert "pattern::information-holder" in roles
        assert "pattern::structurer" in roles
        assert "pattern::service-provider" in roles
        assert "pattern::coordinator" in roles
        assert "pattern::controller" in roles
        assert "pattern::interfacer" in roles

    def test_patterns_have_subject_and_content(self):
        for p in _ROLE_PATTERNS:
            assert p["subject"].startswith("pattern::")
            assert len(p["content"]) > 50

    def test_ensure_pattern_library_seeds(self):
        oracle = _make_oracle()
        inserted = _ensure_pattern_library(oracle.conn)
        assert inserted == len(_ROLE_PATTERNS)
        rows = oracle.conn.execute(
            "SELECT subject FROM knowledge_artifacts WHERE kind='pattern'"
        ).fetchall()
        assert len(rows) == len(_ROLE_PATTERNS)

    def test_ensure_pattern_library_idempotent(self):
        oracle = _make_oracle()
        _ensure_pattern_library(oracle.conn)
        inserted2 = _ensure_pattern_library(oracle.conn)
        assert inserted2 == 0
        count = oracle.conn.execute(
            "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='pattern'"
        ).fetchone()[0]
        assert count == len(_ROLE_PATTERNS)

    def test_patterns_stored_as_human_confirmed(self):
        oracle = _make_oracle()
        _ensure_pattern_library(oracle.conn)
        rows = oracle.conn.execute(
            "SELECT provenance FROM knowledge_artifacts WHERE kind='pattern'"
        ).fetchall()
        for row in rows:
            assert row[0] == "human-confirmed"


# ---------------------------------------------------------------------------
# infer_behavior dispatch — no LLM
# ---------------------------------------------------------------------------

class TestInferBehaviorDispatch:
    def test_missing_symbol_arg_returns_error(self):
        oracle = _make_oracle()
        assessor = FakeAssessor(oracle)
        result = infer_behavior(assessor, {})
        assert "ERROR" in result
        assert isinstance(result, str)

    def test_seeds_pattern_library_on_first_call(self):
        oracle = _make_oracle()
        assessor = FakeAssessor(oracle)
        before = oracle.conn.execute(
            "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='pattern'"
        ).fetchone()[0]
        assert before == 0
        # Call with unknown symbol — patterns still get seeded before evidence lookup
        infer_behavior(assessor, {"symbol": "__probe__"})
        after = oracle.conn.execute(
            "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='pattern'"
        ).fetchone()[0]
        assert after == len(_ROLE_PATTERNS)

    def test_unknown_symbol_returns_string_not_exception(self):
        oracle = _make_oracle()
        assessor = FakeAssessor(oracle)
        result = infer_behavior(assessor, {"symbol": "__no_such_symbol__"})
        assert isinstance(result, str)
        # Either "no evidence found" message or an LLM result — never a crash
        assert "INFER BEHAVIOR" in result or "no match" in result.lower() or "evidence" in result.lower()

    def test_result_contains_symbol_name(self):
        oracle = _make_oracle()
        assessor = FakeAssessor(oracle)
        # Insert a symbol so context assembly has something to find
        oracle.conn.execute(
            "INSERT INTO symbols (name, file_path, symbol_type, line_number) "
            "VALUES ('my_func', 'world/engine.py', 'function', 5)"
        )
        oracle.conn.commit()
        result = infer_behavior(assessor, {"symbol": "my_func"})
        assert "my_func" in result


# ---------------------------------------------------------------------------
# Live LLM test — skipped without llama-server
# ---------------------------------------------------------------------------

@pytest.mark.live_llm
class TestInferBehaviorLive:
    def test_controller_role_detected(self):
        """
        A controller-shaped calling profile (evaluate_action in adjudication_engine)
        should yield MATCHES_PATTERN or UNCERTAIN (not crash), with a Wirfs-Brock
        role name in the output.
        """
        from determined.agent.llm_client import is_available
        if not is_available(timeout=5):
            pytest.skip("llama-server not reachable")

        oracle = _make_oracle()
        assessor = FakeAssessor(oracle)
        conn = oracle.conn

        conn.executescript("""
            INSERT INTO symbols (name, file_path, symbol_type, line_number)
                VALUES ('evaluate_action', 'world/adjudication_engine.py', 'function', 10);
            INSERT INTO functions (name, file_path, line_number, param_types_json)
                VALUES ('evaluate_action', 'world/adjudication_engine.py', 10,
                        '{"action": "dict", "context": "dict"}');
            INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number)
                VALUES ('session_manager', 'evaluate_action',
                        'session_manager', 'evaluate_action', 'world/session.py', 42);
            INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number)
                VALUES ('evaluate_action', 'score_outcome',
                        'evaluate_action', 'score_outcome', 'world/adjudication_engine.py', 15);
            INSERT INTO graph_edges (source_id, target_id, caller, callee, caller_file, line_number)
                VALUES ('evaluate_action', 'check_constraints',
                        'evaluate_action', 'check_constraints', 'world/adjudication_engine.py', 20);
        """)
        conn.commit()

        result = infer_behavior(assessor, {"symbol": "evaluate_action"})
        assert isinstance(result, str)
        assert "INFER BEHAVIOR" in result
        lower = result.lower()
        wirfs_brock_roles = {"controller", "coordinator", "interfacer", "service-provider",
                             "information-holder", "structurer"}
        assert any(r in lower for r in wirfs_brock_roles) or "matches_pattern" in lower or "uncertain" in lower
