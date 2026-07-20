# tests/regression/test_shape_normalizer.py

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from determined.ingestion.shape_normalizer import (
    normalize_file,
    normalize_findings,
    summarize_normalization,
    NormalizationResult,
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
    conn.execute("""
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            caller TEXT,
            callee TEXT,
            line_number INTEGER,
            caller_file TEXT,
            resolved INTEGER DEFAULT 0,
            edge_type TEXT DEFAULT 'static'
        )
    """)
    return conn


def _fsm(name="TestFSM", states=None, events=None, actions=None, guards=None):
    states = states or [{"name": "a"}, {"name": "b", "final": True}]
    events = events or {"go": {"transitions": [{"from": "a", "to": "b", "actions": ["do_thing"]}]}}
    obj = {"name": name, "states": states, "events": events}
    if actions:
        obj["actions"] = actions
    if guards:
        obj["guards"] = guards
    return obj


# ---------------------------------------------------------------------------
# normalize_file
# ---------------------------------------------------------------------------

def test_writes_edges_for_transitions(tmp_path):
    fsm = _fsm()
    _write(tmp_path, "fsm.json", json.dumps(fsm))
    conn = _db()
    r = normalize_file(tmp_path / "fsm.json", conn, tmp_path)
    assert r.edges_written == 1
    assert r.error == ""
    rows = conn.execute("SELECT caller, callee, edge_type FROM graph_edges").fetchall()
    assert len(rows) == 1
    assert rows[0] == ("a", "b", "config_edge")


def test_writes_nodes_as_knowledge_artifacts(tmp_path):
    fsm = _fsm()
    _write(tmp_path, "fsm.json", json.dumps(fsm))
    conn = _db()
    r = normalize_file(tmp_path / "fsm.json", conn, tmp_path)
    assert r.nodes_written == 2
    kinds = conn.execute(
        "SELECT kind FROM knowledge_artifacts WHERE kind='fsm_state'"
    ).fetchall()
    assert len(kinds) == 2


def test_writes_actions_from_transition(tmp_path):
    fsm = _fsm()
    _write(tmp_path, "fsm.json", json.dumps(fsm))
    conn = _db()
    normalize_file(tmp_path / "fsm.json", conn, tmp_path)
    row = conn.execute(
        "SELECT subject, kind FROM knowledge_artifacts WHERE kind='fsm_action'"
    ).fetchone()
    assert row is not None
    assert "do_thing" in row[0]


def test_writes_named_actions_with_descriptions(tmp_path):
    fsm = _fsm(actions={"do_thing": {"description": "Performs the thing."}})
    _write(tmp_path, "fsm.json", json.dumps(fsm))
    conn = _db()
    normalize_file(tmp_path / "fsm.json", conn, tmp_path)
    row = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE subject LIKE '%do_thing' AND kind='fsm_action'"
    ).fetchone()
    assert row is not None
    assert "Performs the thing" in row[0]


def test_writes_guards(tmp_path):
    fsm = _fsm(guards={"check_ok": {"description": "True if ok."}})
    _write(tmp_path, "fsm.json", json.dumps(fsm))
    conn = _db()
    normalize_file(tmp_path / "fsm.json", conn, tmp_path)
    row = conn.execute(
        "SELECT subject FROM knowledge_artifacts WHERE kind='fsm_guard'"
    ).fetchone()
    assert row is not None
    assert "check_ok" in row[0]


def test_idempotent_skips_on_second_run(tmp_path):
    fsm = _fsm()
    _write(tmp_path, "fsm.json", json.dumps(fsm))
    conn = _db()
    r1 = normalize_file(tmp_path / "fsm.json", conn, tmp_path)
    r2 = normalize_file(tmp_path / "fsm.json", conn, tmp_path)
    assert r1.skipped is False
    assert r2.skipped is True
    # Only one edge in DB
    count = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
    assert count == 1


def test_source_id_and_target_id_use_fsm_name(tmp_path):
    fsm = {"name": "EncounterFSM", "states": [{"name": "idle"}, {"name": "active"}],
           "events": {"start": {"transitions": [{"from": "idle", "to": "active"}]}}}
    _write(tmp_path, "encounter.json", json.dumps(fsm))
    conn = _db()
    normalize_file(tmp_path / "encounter.json", conn, tmp_path)
    row = conn.execute("SELECT source_id, target_id FROM graph_edges").fetchone()
    assert row == ("EncounterFSM.idle", "EncounterFSM.active")


def test_missing_file_returns_error(tmp_path):
    conn = _db()
    r = normalize_file(tmp_path / "nonexistent.json", conn, tmp_path)
    assert r.error != ""


# ---------------------------------------------------------------------------
# normalize_findings (driven by shape_finding artifacts)
# ---------------------------------------------------------------------------

def test_normalize_findings_processes_high_confidence(tmp_path):
    fsm = _fsm()
    _write(tmp_path, "fsm.json", json.dumps(fsm))
    conn = _db()
    conn.execute(
        "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at, needs_review) "
        "VALUES (?, 'shape_finding', ?, 'shape_scanner', '2026-01-01', 0)",
        ("fsm.json", json.dumps({"kind": "directed_graph", "confidence": 0.9})),
    )
    results = normalize_findings(tmp_path, conn, min_confidence=0.7)
    assert len(results) == 1
    assert results[0].edges_written == 1


def test_normalize_findings_skips_low_confidence(tmp_path):
    fsm = _fsm()
    _write(tmp_path, "fsm.json", json.dumps(fsm))
    conn = _db()
    conn.execute(
        "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at, needs_review) "
        "VALUES (?, 'shape_finding', ?, 'shape_scanner', '2026-01-01', 0)",
        ("fsm.json", json.dumps({"kind": "directed_graph", "confidence": 0.4})),
    )
    results = normalize_findings(tmp_path, conn, min_confidence=0.7)
    assert results == []


def test_normalize_findings_skips_non_graph_kinds(tmp_path):
    conn = _db()
    conn.execute(
        "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at, needs_review) "
        "VALUES (?, 'shape_finding', ?, 'shape_scanner', '2026-01-01', 0)",
        ("data.json", json.dumps({"kind": "tree", "confidence": 0.9})),
    )
    results = normalize_findings(tmp_path, conn, min_confidence=0.7)
    assert results == []


# ---------------------------------------------------------------------------
# summarize_normalization
# ---------------------------------------------------------------------------

def test_summarize_empty():
    s = summarize_normalization([])
    assert "no directed_graph" in s


def test_summarize_counts_edges():
    results = [NormalizationResult(file="a.json", edges_written=5, nodes_written=3)]
    s = summarize_normalization(results)
    assert "5 edge" in s
    assert "3 node" in s


def test_summarize_counts_skipped():
    results = [
        NormalizationResult(file="a.json", edges_written=2),
        NormalizationResult(file="b.json", skipped=True),
    ]
    s = summarize_normalization(results)
    assert "skipped" in s
