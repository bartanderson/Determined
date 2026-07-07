"""Regression tests for structured layer-rule violation detection (RM18 Gap 1)."""
import json
import sqlite3
import tempfile
import os
import pytest


# ---------------------------------------------------------------------------
# _extract_layer_rules
# ---------------------------------------------------------------------------

from determined.agent.doc_extractor import _extract_layer_rules, write_seed_layer_rules_doc


def test_extract_layer_rules_must_not_import():
    text = "`ui` must not import `storage`"
    rules = _extract_layer_rules(text, "DESIGN.md")
    assert len(rules) == 1
    assert rules[0]["from_layer"] == "ui"
    assert rules[0]["to_layer"] == "storage"
    assert rules[0]["direction"] == "forbidden"
    assert rules[0]["source"] == "DESIGN.md"


def test_extract_layer_rules_cannot_depend_on():
    text = "`api` cannot depend on `ui`"
    rules = _extract_layer_rules(text, "arch.md")
    assert len(rules) == 1
    assert rules[0]["from_layer"] == "api"
    assert rules[0]["to_layer"] == "ui"


def test_extract_layer_rules_should_not():
    text = "`cli` should not import from `web`"
    rules = _extract_layer_rules(text, "rules.md")
    assert len(rules) == 1
    assert rules[0]["from_layer"] == "cli"
    assert rules[0]["to_layer"] == "web"


def test_extract_layer_rules_no_match():
    text = "This is a general design note with no layer constraints."
    rules = _extract_layer_rules(text, "README.md")
    assert rules == []


def test_extract_layer_rules_deduplicates():
    text = "`ui` must not import `storage`\n`ui` must not import `storage`"
    rules = _extract_layer_rules(text, "doc.md")
    assert len(rules) == 1


def test_extract_layer_rules_multiple():
    text = "`ui` must not import `storage`\n`api` cannot depend on `ui`"
    rules = _extract_layer_rules(text, "doc.md")
    assert len(rules) == 2


def test_extract_layer_rules_normalises_slashes():
    text = "`ui/` must not import `storage/`"
    rules = _extract_layer_rules(text, "doc.md")
    assert rules[0]["from_layer"] == "ui"
    assert rules[0]["to_layer"] == "storage"


# ---------------------------------------------------------------------------
# write_seed_layer_rules_doc
# ---------------------------------------------------------------------------

def test_write_seed_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        dest = write_seed_layer_rules_doc(tmp)
        assert dest != ""
        assert os.path.exists(os.path.join(tmp, "LAYER_RULES.md"))


def test_write_seed_does_not_overwrite():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "LAYER_RULES.md")
        with open(path, "w") as f:
            f.write("custom content")
        dest = write_seed_layer_rules_doc(tmp)
        assert dest == ""
        assert open(path).read() == "custom content"


def test_write_seed_content_has_example():
    with tempfile.TemporaryDirectory() as tmp:
        write_seed_layer_rules_doc(tmp)
        content = open(os.path.join(tmp, "LAYER_RULES.md")).read()
        assert "must not import" in content
        assert "ingest_design_docs" in content


# ---------------------------------------------------------------------------
# _check_import_layer_violations
# ---------------------------------------------------------------------------

from determined.agent.agent_tools import _check_import_layer_violations


def _make_db_with_layer_rule(from_layer, to_layer):
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE knowledge_artifacts
        (id INTEGER PRIMARY KEY, subject TEXT, kind TEXT, content TEXT,
         provenance TEXT, created_at TEXT, file_hash TEXT, needs_review INTEGER, corpus TEXT)""")
    conn.execute("""CREATE TABLE imports
        (id INTEGER PRIMARY KEY, file_path TEXT, module TEXT,
         import_type TEXT, line_number INTEGER)""")
    rule = json.dumps({"from_layer": from_layer, "to_layer": to_layer,
                       "direction": "forbidden", "source": "test.md"})
    conn.execute(
        "INSERT INTO knowledge_artifacts (subject,kind,content,provenance,created_at,needs_review) VALUES (?,?,?,?,?,?)",
        ("test.md", "layer_rule", rule, "human-confirmed", "2026-01-01", 0)
    )
    return conn


def test_violation_detected():
    conn = _make_db_with_layer_rule("ui", "storage")
    conn.execute(
        "INSERT INTO imports (file_path,module,import_type,line_number) VALUES (?,?,?,?)",
        ("ui/views.py", "storage.models", "import", 5)
    )
    violations = _check_import_layer_violations(conn, "ui/views.py")
    real = [v for v in violations if "_hint" not in v]
    assert len(real) == 1
    assert real[0]["forbidden_import"] == "storage.models"
    assert real[0]["line_number"] == 5


def test_no_violation_when_import_allowed():
    conn = _make_db_with_layer_rule("ui", "storage")
    conn.execute(
        "INSERT INTO imports (file_path,module,import_type,line_number) VALUES (?,?,?,?)",
        ("ui/views.py", "flask", "import", 1)
    )
    violations = _check_import_layer_violations(conn, "ui/views.py")
    real = [v for v in violations if "_hint" not in v]
    assert real == []


def test_hint_returned_when_no_rules():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE knowledge_artifacts
        (id INTEGER PRIMARY KEY, subject TEXT, kind TEXT, content TEXT,
         provenance TEXT, created_at TEXT, file_hash TEXT, needs_review INTEGER, corpus TEXT)""")
    conn.execute("""CREATE TABLE imports
        (id INTEGER PRIMARY KEY, file_path TEXT, module TEXT,
         import_type TEXT, line_number INTEGER)""")
    result = _check_import_layer_violations(conn, "ui/views.py")
    assert len(result) == 1
    assert "_hint" in result[0]
    assert "LAYER_RULES.md" in result[0]["_hint"]


def test_empty_file_path_returns_empty():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE knowledge_artifacts
        (id INTEGER PRIMARY KEY, subject TEXT, kind TEXT, content TEXT,
         provenance TEXT, created_at TEXT, file_hash TEXT, needs_review INTEGER, corpus TEXT)""")
    assert _check_import_layer_violations(conn, "") == []


def test_wrong_layer_file_not_flagged():
    conn = _make_db_with_layer_rule("ui", "storage")
    conn.execute(
        "INSERT INTO imports (file_path,module,import_type,line_number) VALUES (?,?,?,?)",
        ("api/views.py", "storage.models", "import", 3)
    )
    # api/ is not subject to the ui->storage rule
    violations = _check_import_layer_violations(conn, "api/views.py")
    real = [v for v in violations if "_hint" not in v]
    assert real == []
