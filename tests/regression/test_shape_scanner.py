# tests/regression/test_shape_scanner.py

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from determined.ingestion.shape_scanner import (
    scan_file,
    scan_corpus,
    summarize,
    ShapeFinding,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp: Path, rel: str, content: str) -> Path:
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE knowledge_artifacts (
            id INTEGER PRIMARY KEY,
            subject TEXT NOT NULL,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            provenance TEXT NOT NULL,
            created_at TEXT NOT NULL,
            needs_review INTEGER NOT NULL DEFAULT 0,
            corpus TEXT
        )
    """)
    return conn


# ---------------------------------------------------------------------------
# scan_file — structured
# ---------------------------------------------------------------------------

def test_fsm_json_detected_as_directed_graph(tmp_path):
    fsm = {
        "name": "EncounterFSM",
        "states": [
            {"name": "idle"},
            {"name": "active"},
            {"name": "done", "final": True},
        ],
        "events": {
            "start": {"transitions": [{"from": "idle", "to": "active"}]},
            "end":   {"transitions": [{"from": "active", "to": "done"}]},
        },
    }
    p = _write(tmp_path, "config/fsms/encounter.json", json.dumps(fsm))
    finding = scan_file(p)
    assert finding is not None
    assert finding.kind == "directed_graph"
    assert finding.confidence >= 0.5
    assert finding.edge_count == 2
    assert finding.node_count == 3


def test_missing_refs_detected(tmp_path):
    # Need at least 2 named states so node_collection_pass builds a node_id set,
    # then the undefined target becomes a detectable missing reference.
    fsm = {
        "name": "BrokenFSM",
        "states": [{"name": "start"}, {"name": "middle"}],
        "events": {
            "go": {"transitions": [{"from": "start", "to": "undefined_state"}]},
        },
    }
    p = _write(tmp_path, "config/broken.json", json.dumps(fsm))
    finding = scan_file(p)
    assert finding is not None
    assert "undefined_state" in finding.missing


def test_flat_json_not_reported(tmp_path):
    p = _write(tmp_path, "config/settings.json", json.dumps({"debug": True, "port": 8080}))
    finding = scan_file(p)
    assert finding is None


def test_manifest_json_detected(tmp_path):
    pkg = {
        "name": "myapp",
        "dependencies": {
            "flask": ">=2.0",
            "sqlalchemy": ">=1.4",
            "click": ">=8.0",
        },
    }
    p = _write(tmp_path, "package.json", json.dumps(pkg))
    # Flat manifest — may or may not fire depending on depth/ref signals
    # Just ensure it doesn't crash and returns None or a low-confidence finding
    finding = scan_file(p)
    if finding is not None:
        assert finding.confidence <= 0.6


# ---------------------------------------------------------------------------
# scan_file — prose
# ---------------------------------------------------------------------------

def test_markdown_with_arrows_detected(tmp_path):
    md = """
# State Machine

The encounter flows like this:

- idle -> active when the player engages
- active -> resolving when combat starts
- resolving -> done when combat ends
"""
    p = _write(tmp_path, "docs/design.md", md)
    finding = scan_file(p)
    assert finding is not None
    assert finding.kind == "directed_graph"
    assert finding.edge_count >= 3


def test_markdown_with_table_detected(tmp_path):
    md = """
# API

| Endpoint | Method | Response |
|---|---|---|
| /users | GET | list |
| /users/:id | GET | object |
| /users | POST | created |
| /users/:id | DELETE | ok |
"""
    p = _write(tmp_path, "docs/api.md", md)
    finding = scan_file(p)
    assert finding is not None
    assert finding.kind == "tabular"


def test_plain_markdown_not_reported(tmp_path):
    md = "# Hello\n\nThis is a simple readme with no structure.\n"
    p = _write(tmp_path, "README.md", md)
    finding = scan_file(p)
    assert finding is None


def test_code_files_skipped(tmp_path):
    p = _write(tmp_path, "main.py", "def foo(): pass\n")
    finding = scan_file(p)
    assert finding is None


# ---------------------------------------------------------------------------
# scan_corpus
# ---------------------------------------------------------------------------

def test_scan_corpus_stores_findings(tmp_path):
    fsm = {
        "name": "TestFSM",
        "states": [{"name": "a"}, {"name": "b"}],
        "events": {"go": {"transitions": [{"from": "a", "to": "b"}]}},
    }
    _write(tmp_path, "config/fsms/test.json", json.dumps(fsm))
    _write(tmp_path, "src/main.py", "def foo(): pass\n")

    conn = _db()
    findings = scan_corpus(tmp_path, conn)

    assert len(findings) >= 1
    rows = conn.execute(
        "SELECT subject, kind FROM knowledge_artifacts WHERE kind = 'shape_finding'"
    ).fetchall()
    assert len(rows) >= 1


def test_scan_corpus_skips_code(tmp_path):
    _write(tmp_path, "main.py", "def foo(): pass\n")
    conn = _db()
    findings = scan_corpus(tmp_path, conn)
    assert findings == []


def test_scan_corpus_sorted_by_confidence(tmp_path):
    fsm = {
        "name": "F",
        "states": [{"name": "x"}, {"name": "y"}, {"name": "z"}],
        "events": {
            "a": {"transitions": [{"from": "x", "to": "y"}]},
            "b": {"transitions": [{"from": "y", "to": "z"}]},
        },
    }
    _write(tmp_path, "fsm.json", json.dumps(fsm))
    _write(tmp_path, "docs/a.md", "- idle -> active\n- active -> done\n- done -> end\n")

    conn = _db()
    findings = scan_corpus(tmp_path, conn)
    confs = [f.confidence for f in findings]
    assert confs == sorted(confs, reverse=True)


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------

def test_summarize_empty():
    s = summarize([])
    assert "no structure" in s


def test_summarize_reports_top_file():
    findings = [
        ShapeFinding(file="config/encounter.json", kind="directed_graph", confidence=0.9, edge_count=4),
        ShapeFinding(file="docs/design.md", kind="prose_structure", confidence=0.4),
    ]
    s = summarize(findings)
    assert "encounter.json" in s
    assert "directed_graph" in s
