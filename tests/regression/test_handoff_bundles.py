"""handoff_bundles: which open items a verified bundle covers, and the primer split.

Pure functions over small synthetic patches, plus one check against the real
handoffs/dj2 bundles so a regenerated bundle that stops covering its handlers shows up.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from determined.agent import handoff_bundles as hb

REPO = Path(__file__).resolve().parent.parent.parent

PATCH = """\
diff --git a/world/fsm/builtins.py b/world/fsm/builtins.py
index 1..2 100644
--- a/world/fsm/builtins.py
+++ b/world/fsm/builtins.py
@@ -10,9 +10,12 @@ def other(instance, event_data):
     return instance.context

-def start_combat(instance, event_data):
-    return None
+def start_combat(instance, event_data):
+    emit('combat.started')
+    return instance.context

 def untouched(instance, event_data):
     return False
+
+def resolve_flee(instance, event_data):
+    return instance.context
diff --git a/world/engine.py b/world/engine.py
--- a/world/engine.py
+++ b/world/engine.py
@@ -1,4 +1,5 @@ class Engine:
     reg = {
+        'update_price': builtins.update_price,
         'keep': builtins.keep,
     }
diff --git a/tests/unit/test_x.py b/tests/unit/test_x.py
--- a/tests/unit/test_x.py
+++ b/tests/unit/test_x.py
@@ -0,0 +1,3 @@
+def only_in_tests():
+    helper_only_in_tests()
+    return 1
"""


def _bundle(tmp_path, bid="002", slug="encounter-fsm", verified="2026-10-14T01:00:00+00:00",
            patch=PATCH):
    d = tmp_path / "dj2" / f"{bid}-{slug}"
    d.mkdir(parents=True)
    (d / "MANIFEST.json").write_text(json.dumps({
        "id": bid, "base_sha": "abc", "files_touched": [], "tests_run": [],
        "finding_ids": [], "openspec_task": "3.2", "verified_at": verified}), encoding="utf-8")
    (d / "change.patch").write_text(patch, encoding="utf-8")
    return d


def test_parse_patch_tracks_defs_and_added_words():
    files = {f.path: f for f in hb.parse_patch(PATCH)}
    b = files["world/fsm/builtins.py"]
    assert {"start_combat", "resolve_flee"} <= b.touched_defs
    assert "untouched" not in b.touched_defs          # only a context def, no change in it
    assert "other" not in b.touched_defs
    assert "emit" in b.added_words
    assert files["tests/unit/test_x.py"].is_test
    assert not b.is_test


def test_removed_def_is_not_an_implementation():
    patch = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
        "@@ -1,3 +1,3 @@\n-def old_name(x):\n-    return 1\n+def new_name(x):\n+    return 2\n"
    )
    f = hb.parse_patch(patch)[0]
    assert f.touched_defs == {"new_name"}


def test_load_bundles_only_verified(tmp_path):
    _bundle(tmp_path, "001", "events", verified="")
    _bundle(tmp_path, "002", "encounter-fsm")
    got = hb.load_bundles("dj2", root=tmp_path)
    assert [b.id for b in got] == ["002"]
    assert got[0].label == "002-encounter-fsm"


def test_load_bundles_missing_dir_is_empty(tmp_path):
    assert hb.load_bundles("nope", root=tmp_path) == []


def _fsm_item(actions, guards=()):
    return {"is_fsm": True, "name": "EncounterFSM", "file_path": "x/encounter.json",
            "actions": list(actions), "guards": list(guards)}


def _stub_item(name, file_path):
    return {"is_fsm": False, "name": name, "file_path": file_path}


def test_fsm_full_coverage_is_handed_off(tmp_path):
    _bundle(tmp_path)
    bundles = hb.load_bundles("dj2", root=tmp_path)
    actionable, handed = hb.annotate_items(
        [_fsm_item(["start_combat", "resolve_flee"])], bundles)
    assert actionable == []
    assert handed[0]["handoff"]["full"] is True


def test_fsm_partial_coverage_stays_actionable_with_remaining(tmp_path):
    _bundle(tmp_path)
    bundles = hb.load_bundles("dj2", root=tmp_path)
    actionable, handed = hb.annotate_items(
        [_fsm_item(["start_combat", "update_price"], ["never_mentioned"])], bundles)
    assert handed == []
    h = actionable[0]["handoff"]
    assert h["full"] is False
    assert h["remaining"] == ["never_mentioned"]
    assert set(h["bundles"][0]["covered"]) == {"start_combat", "update_price"}


def test_names_only_in_test_files_do_not_count(tmp_path):
    _bundle(tmp_path)
    bundles = hb.load_bundles("dj2", root=tmp_path)
    actionable, handed = hb.annotate_items([_fsm_item(["helper_only_in_tests"])], bundles)
    assert handed == [] and "handoff" not in actionable[0]


def test_python_stub_must_match_file(tmp_path):
    _bundle(tmp_path)
    bundles = hb.load_bundles("dj2", root=tmp_path)
    right = _stub_item("start_combat", "C:/Users/me/dj2/world/fsm/builtins.py")
    wrong = _stub_item("start_combat", "C:/Users/me/dj2/other/builtins.py")
    actionable, handed = hb.annotate_items([right, wrong], bundles)
    assert [i["file_path"] for i in handed] == [right["file_path"]]
    assert [i["file_path"] for i in actionable] == [wrong["file_path"]]


def test_input_items_not_mutated_and_no_bundles_is_identity(tmp_path):
    item = _fsm_item(["start_combat"])
    a, h = hb.annotate_items([item], [])
    assert a == [item] and h == []
    _bundle(tmp_path)
    hb.annotate_items([item], hb.load_bundles("dj2", root=tmp_path))
    assert "handoff" not in item


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def test_bundle_state_applied_vs_pending(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-qm", "base")
    patch = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
        "@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 2\n"
    )
    _bundle(tmp_path, patch=patch)
    b = hb.load_bundles("dj2", root=tmp_path)[0]
    assert hb.bundle_state(b, repo) == "pending"
    (repo / "a.py").write_text("def f():\n    return 2\n", encoding="utf-8")
    assert hb.bundle_state(b, repo) == "applied"
    assert hb.bundle_state(b, tmp_path / "no-such-repo") == "unknown"
    assert hb.bundle_state(b, None) == "unknown"


def test_describe_says_what_patch_says():
    handoff = {
        "total": 5, "full": False, "remaining": ["parley_possible"],
        "bundles": [{"id": "002", "label": "002-encounter-fsm", "verified_at": "2026-10-14",
                     "state": "pending", "covered": ["a", "b", "c", "d"]}],
    }
    text = "\n".join(hb.describe(handoff))
    assert "changes 4/5" in text and "do not reimplement" in text
    assert "not changed by the bundle: parley_possible" in text


@pytest.mark.skipif(not (REPO / "handoffs" / "dj2").is_dir(), reason="no dj2 handoffs")
def test_real_bundles_cover_their_named_handlers():
    bundles = {b.id: b for b in hb.load_bundles("dj2")}
    assert {"001", "002", "003", "004", "005"} <= set(bundles)
    enc = bundles["002"]
    for name in ("start_combat", "resolve_flee", "resolve_parley", "flee_possible"):
        assert hb._covers_handler(enc, name), name
    ctx = bundles["005"]
    assert hb._covers_stub(ctx, "_get_encounter_context", "C:/x/dj2/world/context_builder.py")
    assert hb._covers_stub(ctx, "_get_combat_context", "C:/x/dj2/world/context_builder.py")


def test_corpus_handoff_context_reads_project_root(tmp_path):
    import sqlite3
    conn = sqlite3.connect(":memory:")
    assert hb.corpus_handoff_context(conn) == ([], None)      # no project_meta table
    conn.execute("CREATE TABLE project_meta (key TEXT, value TEXT)")
    assert hb.corpus_handoff_context(conn) == ([], None)      # no row
    conn.execute("INSERT INTO project_meta VALUES ('project_root', 'C:/Users/me/dj2')")
    bundles, root = hb.corpus_handoff_context(conn)
    assert root == "C:/Users/me/dj2"
    assert all(isinstance(b, hb.Bundle) for b in bundles)
