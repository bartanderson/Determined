# tests/regression/test_discovery_agent.py - minimal smoke tests

import sys, os, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _make_env(edges=None, functions=None, files=None):
    class _Oracle:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            for t in ["graph_edges (caller TEXT, callee TEXT, line_number INTEGER)",
                       "functions (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)",
                       "classes (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)",
                       "files (file_path TEXT, line_count INTEGER)"]:
                self.conn.execute(f"CREATE TABLE {t}")
            for c, e in (edges or []):
                self.conn.execute("INSERT INTO graph_edges VALUES (?,?,0)", (c, e))
            for n, fp, doc in (functions or []):
                self.conn.execute("INSERT INTO functions VALUES (?,?,0,?)", (n, fp, doc))
            for fp in (files or []):
                self.conn.execute("INSERT INTO files VALUES (?,100)", (fp,))
        def get_project_root(self): return "/project"
        def find_symbols(self, *a, **kw): return []
        def find_files(self, pattern=""):
            rows = self.conn.execute("SELECT file_path, 100 as line_count FROM files").fetchall()
            return [{"file_path": r[0], "line_count": r[1]} for r in rows]

    class _Assessor:
        def __init__(self):
            self._knowledge_conn = sqlite3.connect(":memory:")
            self._knowledge_conn.execute(
                "CREATE TABLE knowledge_artifacts "
                "(id INTEGER PRIMARY KEY, subject TEXT, kind TEXT, content TEXT, "
                "provenance TEXT, created_at TEXT, file_hash TEXT, needs_review INTEGER DEFAULT 0)"
            )
        def semantic_summary(self, fp, kind="file"):
            return {"content": f"Summary of {fp}", "cache_hit": False}
        def add_artifact(self, subject, kind, content, provenance):
            self._knowledge_conn.execute(
                "INSERT INTO knowledge_artifacts (subject,kind,content,provenance,created_at) VALUES (?,?,?,?,datetime('now'))",
                (subject, kind, content, provenance)
            )
        def get_artifacts(self, subject): return []

    return _Oracle(), _Assessor()


def test_survey_files_stores_findings():
    from determined.agent.discovery_agent import survey_files
    oracle, assessor = _make_env(files=["/project/world/encounter_generator.py"])
    n = survey_files(oracle, assessor, limit=5)
    assert n == 1
    row = assessor._knowledge_conn.execute(
        "SELECT kind, content FROM knowledge_artifacts WHERE subject = 'encounter_generator.py'"
    ).fetchone()
    assert row is not None
    assert row[0] == "file_purpose"


def test_survey_files_skips_already_stored():
    from determined.agent.discovery_agent import survey_files
    oracle, assessor = _make_env(files=["/project/world/encounter_generator.py"])
    survey_files(oracle, assessor, limit=5)
    n = survey_files(oracle, assessor, limit=5)  # second run
    assert n == 0  # already stored, nothing new


def test_survey_entry_points_stores_design_notes():
    from determined.agent.discovery_agent import survey_entry_points
    oracle, assessor = _make_env(
        edges=[("run_game", "start_encounter")],
        functions=[("run_game", "/project/main.py", "Main entry point."),
                   ("start_encounter", "/project/engine.py", None)],
    )
    n = survey_entry_points(oracle, assessor, limit=5)
    assert n >= 1
    row = assessor._knowledge_conn.execute(
        "SELECT kind FROM knowledge_artifacts WHERE subject = 'run_game'"
    ).fetchone()
    assert row and row[0] == "design_note"


def test_survey_call_chains_stores_strategy():
    from determined.agent.discovery_agent import survey_call_chains
    oracle, assessor = _make_env(
        edges=[("run_game", "start_encounter"), ("start_encounter", "generate_encounter")],
        functions=[("run_game", "/p/main.py", None),
                   ("start_encounter", "/p/eng.py", None),
                   ("generate_encounter", "/p/enc.py", None)],
    )
    n = survey_call_chains(oracle, assessor, limit=3)
    assert n >= 1
    row = assessor._knowledge_conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE kind = 'strategy_decision'"
    ).fetchone()
    assert row and "run_game" in row[0]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
