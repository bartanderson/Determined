# tests/regression/test_artifact_layer.py
#
# Tests for RM28 Stage 1: artifact persistence, staleness, and cascade.

import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from determined.persistence.persistence_engine import ensure_schema
from determined.intent.workflow_store import (
    ensure_workflow_items_table,
    ensure_artifact_columns,
    store_artifact,
    get_artifact_by_name,
    list_artifacts,
    mark_stale_by_files,
    VALID_KINDS,
    VALID_ARTIFACT_STATUSES,
)


def _db():
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    cur = conn.cursor()
    ensure_workflow_items_table(cur)
    ensure_artifact_columns(cur)
    conn.commit()
    return conn


# -- constants --

def test_artifact_in_valid_kinds():
    assert "artifact" in VALID_KINDS


def test_valid_artifact_statuses():
    assert VALID_ARTIFACT_STATUSES == {"fresh", "stale", "superseded"}


# -- ensure_artifact_columns idempotent --

def test_ensure_artifact_columns_idempotent():
    conn = _db()
    cur = conn.cursor()
    ensure_artifact_columns(cur)  # second call must not raise
    conn.commit()


# -- store_artifact --

def test_store_artifact_returns_id():
    conn = _db()
    row_id = store_artifact(conn, "orient-result", "orient_to_codebase", "some output")
    assert isinstance(row_id, int) and row_id > 0


def test_store_artifact_fresh_by_default():
    conn = _db()
    store_artifact(conn, "topo", "detect_topology", "topology output")
    art = get_artifact_by_name(conn, "topo")
    assert art is not None
    assert art["artifact_status"] == "fresh"


def test_store_artifact_supersedes_prior():
    conn = _db()
    store_artifact(conn, "orient", "orient_to_codebase", "first run")
    store_artifact(conn, "orient", "orient_to_codebase", "second run")
    # only the latest non-superseded should be returned
    art = get_artifact_by_name(conn, "orient")
    assert art["content"] == "second run"
    # old one should be superseded
    rows = conn.execute(
        "SELECT artifact_status FROM workflow_items WHERE kind='artifact' AND subject='orient'"
    ).fetchall()
    statuses = [r[0] for r in rows]
    assert "superseded" in statuses
    assert statuses.count("fresh") == 1


def test_store_artifact_feeds_into():
    conn = _db()
    store_artifact(conn, "frontier", "find_frontier", "frontier output", feeds_into=["orient"])
    art = get_artifact_by_name(conn, "frontier")
    assert "orient" in art["feeds_into"]


# -- list_artifacts --

def test_list_artifacts_excludes_superseded():
    conn = _db()
    store_artifact(conn, "a", "tool_a", "v1")
    store_artifact(conn, "a", "tool_a", "v2")
    arts = list_artifacts(conn)
    names = [a["name"] for a in arts]
    assert names.count("a") == 1  # only the live one


def test_list_artifacts_filter_by_status():
    conn = _db()
    store_artifact(conn, "b", "tool_b", "content")
    # manually stale one
    conn.execute("UPDATE workflow_items SET artifact_status='stale' WHERE subject='b'")
    conn.commit()
    fresh = list_artifacts(conn, artifact_status="fresh")
    stale = list_artifacts(conn, artifact_status="stale")
    assert all(a["artifact_status"] == "fresh" for a in fresh)
    assert any(a["artifact_status"] == "stale" for a in stale)


# -- staleness --

def _past(seconds=10):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _future(seconds=10):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def test_mark_stale_by_files_marks_old_artifacts():
    conn = _db()
    # insert artifact with old created_at
    conn.execute(
        "INSERT INTO workflow_items (kind, subject, content, status, provenance, "
        "created_at, updated_at, tool_name, artifact_status, feeds_into) "
        "VALUES ('artifact','old-art','content','active','tool',?,?,'t','fresh','[]')",
        (_past(20), _past(20)),
    )
    # file reingested more recently
    conn.execute("INSERT INTO files(file_path, ingested_at) VALUES ('foo.py', ?)", (_past(5),))
    conn.commit()
    count = mark_stale_by_files(conn)
    assert count >= 1
    art = get_artifact_by_name(conn, "old-art")
    assert art["artifact_status"] == "stale"


def test_mark_stale_no_files_reingested():
    conn = _db()
    store_artifact(conn, "fresh-art", "tool", "content")
    conn.execute("INSERT INTO files(file_path) VALUES ('foo.py')")  # no ingested_at
    conn.commit()
    count = mark_stale_by_files(conn)
    assert count == 0
    art = get_artifact_by_name(conn, "fresh-art")
    assert art["artifact_status"] == "fresh"


def test_cascade_staleness():
    import json
    conn = _db()
    # orient artifact created before reingest
    conn.execute(
        "INSERT INTO workflow_items (kind, subject, content, status, provenance, "
        "created_at, updated_at, tool_name, artifact_status, feeds_into) "
        "VALUES ('artifact','orient','o','active','tool',?,?,'t','fresh','[]')",
        (_past(20), _past(20)),
    )
    # frontier depends on orient
    conn.execute(
        "INSERT INTO workflow_items (kind, subject, content, status, provenance, "
        "created_at, updated_at, tool_name, artifact_status, feeds_into) "
        "VALUES ('artifact','frontier','f','active','tool',?,?,'t','fresh',?)",
        (_past(20), _past(20), json.dumps(["orient"])),
    )
    conn.execute("INSERT INTO files(file_path, ingested_at) VALUES ('foo.py', ?)", (_past(5),))
    conn.commit()
    mark_stale_by_files(conn)
    orient = get_artifact_by_name(conn, "orient")
    frontier = get_artifact_by_name(conn, "frontier")
    assert orient["artifact_status"] == "stale"
    assert frontier["artifact_status"] == "stale"


# -- ingested_at column --

def test_files_table_has_ingested_at():
    conn = _db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(files)").fetchall()}
    assert "ingested_at" in cols
