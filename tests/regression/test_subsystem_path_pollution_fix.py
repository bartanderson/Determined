# tools/analysis/tests/regression/test_subsystem_path_pollution_fix.py
#
# Locks in the 2026-06-17 fix for TRACKER.md open item 16: SUBSYSTEM /
# find_modules() identity strings were carrying the full absolute
# filesystem path (e.g. "sessions.<id>.mnt.myproject.determined.oracle"
# in this session's sandbox, or a drive-letter-polluted equivalent on
# Bart's Windows checkout) instead of a clean project-relative module
# name ("determined.oracle"), because oracle/db_oracle.py's
# _file_path_to_module() dotted every raw stored file_path segment
# with no project-root trimming.
#
# The real fix needed more than "reuse the existing
# module_name_from_file_path() utility" (the original item-16 framing)
# - that utility requires an explicit project_root argument, and
# nothing in the schema persisted one anywhere. So this also covers
# the supporting pieces: persistence_engine.set_project_root() /
# the new project_meta table (written from EngineRunner.run()'s
# repo_root), and DBOracle.get_project_root()'s fallback inference
# (longest common directory prefix across `files.file_path`) for any
# DB that predates this fix and has no persisted row.
#
# Same fixture pattern as test_discovery_api_and_subsystem_fix.py: real
# temp sqlite DB, real schema via ensure_schema, no mocking of the DB
# layer. The end-to-end test additionally runs a real EngineRunner over
# a tiny temp project, since the bug only reproduces with real absolute
# file_path values - the existing discovery-API fixture uses bare
# relative paths ("moduleA/core.py") that never exhibited it.

import os
import shutil
import sqlite3
import sys
import tempfile

from determined.persistence.persistence_engine import (
    ensure_schema,
    set_project_root,
    create_database,
)
from determined.oracle.db_oracle import DBOracle, _file_path_to_module
from determined.core.pathing import normalize_file_path
from determined.engine.run_engine import EngineRunner


def _make_db():
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)
    return oracle, tmp_path


def _seed_files(oracle, file_paths):
    cur = oracle.conn.cursor()
    for fp in file_paths:
        cur.execute(
            "INSERT INTO files (file_path, line_count, role, is_hot) VALUES (?, 10, 'logic', 0)",
            (fp,),
        )
    oracle.conn.commit()


def _seed_symbol(oracle, file_path, name):
    cur = oracle.conn.cursor()
    cur.execute(
        "INSERT INTO symbols (file_path, symbol_type, name, line_number, signature, canonical_id) "
        "VALUES (?, 'function', ?, 1, '', ?)",
        (file_path, name, f"{file_path}:{name}:1"),
    )
    oracle.conn.commit()


# =========================================================
# 1. _file_path_to_module trims when project_root is supplied,
#    and is unchanged (back-compat) when it isn't
# =========================================================

def test_file_path_to_module_trims_with_project_root():
    abs_path = "/sessions/eloquent-magical-bohr/mnt/myproject/tools/analysis/oracle/db_oracle.py"
    root = "/sessions/eloquent-magical-bohr/mnt/myproject"

    assert _file_path_to_module(abs_path, root) == "determined.oracle"

    # no project_root supplied -> exact prior (polluted) behavior,
    # nothing silently changes for a caller that hasn't opted in
    assert _file_path_to_module(abs_path) == (
        "sessions.eloquent-magical-bohr.mnt.myproject.determined.oracle"
    )

    # file IS the project root itself -> top-level module, no leading dot
    assert _file_path_to_module(root + "/setup.py", root) == "setup"

    # file outside the given root -> root doesn't match as a prefix,
    # falls back to the untrimmed (old) behavior rather than guessing
    other = _file_path_to_module("/elsewhere/foo.py", root)
    assert other == "elsewhere"


# =========================================================
# 2. get_project_root() reads the persisted row when present
# =========================================================

def test_get_project_root_reads_persisted_value():
    # Compare against the *normalized* form, not the raw literal string.
    # set_project_root() normalizes via normalize_file_path(), which
    # resolves to a platform-specific absolute path - on Windows that
    # means gaining a drive letter (Path("/sessions/x/mnt/myproject").resolve()
    # != "/sessions/x/mnt/myproject" there). A bare hardcoded POSIX-style
    # string broke this test on a real Windows run (2026-06-18); fixed
    # by running the same normalization on both sides of the assertion.
    oracle, tmp_path = _make_db()
    try:
        raw_root = "/sessions/x/mnt/myproject"
        set_project_root(oracle.conn, raw_root)
        expected = normalize_file_path(raw_root)
        assert oracle.get_project_root() == expected
        # cached - second call doesn't need to re-query
        assert oracle.get_project_root() == expected
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 3. get_project_root() falls back to common-prefix inference
#    when no row was ever persisted (legacy DB)
# =========================================================

def test_get_project_root_infers_from_files_when_unset():
    oracle, tmp_path = _make_db()
    try:
        # os.path.commonpath() of just these two converges no higher than
        # their shared parent, "/sessions/x/mnt/myproject/tools/analysis" - that
        # IS the correct inferred root for this fixture (it's a directory
        # common to every seeded file, exactly what _infer_project_root()
        # promises). A third file under a different top-level dir pulls
        # the common ancestor up to "/sessions/x/mnt/myproject", which is the
        # case this test wants to demonstrate.
        _seed_files(oracle, [
            "/sessions/x/mnt/myproject/tools/analysis/oracle/db_oracle.py",
            "/sessions/x/mnt/myproject/tools/analysis/truth/views.py",
            "/sessions/x/mnt/myproject/README.md",
        ])
        assert oracle.get_project_root() == "/sessions/x/mnt/myproject"
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_get_project_root_empty_when_insufficient_signal():
    oracle, tmp_path = _make_db()
    try:
        # no project_meta row, and only one distinct file - can't infer
        # a directory without risking the filename itself being treated
        # as a path segment, so this must stay "" (no trimming) rather
        # than guess.
        _seed_files(oracle, ["/sessions/x/mnt/myproject/tools/analysis/only_file.py"])
        assert oracle.get_project_root() == ""
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_get_project_root_empty_on_totally_empty_db():
    oracle, tmp_path = _make_db()
    try:
        assert oracle.get_project_root() == ""
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 4. find_modules() / symbol_module_map() produce
#    project-relative identities end to end, given a persisted root
# =========================================================

def test_find_modules_and_symbol_module_map_use_persisted_root():
    # Uses a real tempdir (rather than a hardcoded POSIX-style string)
    # so the seeded file_path values and the persisted project_root
    # normalize the same way set_project_root()/normalize_file_path()
    # do in production, on any platform. The previous hardcoded
    # "/sessions/x/mnt/myproject" root broke this test on a real Windows run
    # (2026-06-18): set_project_root() normalizes via Path.resolve(),
    # which adds a drive letter there, so the persisted root no longer
    # matched as a literal prefix of the (un-normalized) seeded
    # file_path strings, and _file_path_to_module() silently fell back
    # to its untrimmed behavior instead of producing "determined.*".
    oracle, tmp_path = _make_db()
    tmp_dir = tempfile.mkdtemp()
    try:
        root = normalize_file_path(tmp_dir)
        oracle_file = root + "/tools/analysis/oracle/db_oracle.py"
        truth_file = root + "/tools/analysis/truth/views.py"

        set_project_root(oracle.conn, root)
        _seed_files(oracle, [oracle_file, truth_file])
        _seed_symbol(oracle, oracle_file, "do_thing")

        modules = {m["module"] for m in oracle.find_modules()}
        assert "determined.oracle" in modules
        assert "determined.truth" in modules

        # no module identity should still carry any segment of the
        # temp dir's own path once trimmed
        leaked_segment = [p for p in root.split("/") if p][-1]
        assert not any(leaked_segment in m for m in modules)

        mapping = oracle.symbol_module_map()
        assert mapping["do_thing"] == "determined.oracle"
    finally:
        oracle.conn.close()
        os.remove(tmp_path)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# =========================================================
# 5. End to end: a real EngineRunner run persists project_root,
#    and the discovery API comes out project-relative because of it
# =========================================================

def test_engine_run_persists_project_root_and_trims_module_identity():
    tmp_dir = tempfile.mkdtemp()
    db_path = tempfile.mktemp(suffix=".db")
    try:
        pkg_dir = os.path.join(tmp_dir, "pkg")
        os.makedirs(pkg_dir)
        with open(os.path.join(pkg_dir, "mod.py"), "w", encoding="utf-8") as f:
            f.write("def do_thing():\n    return 1\n")

        db = create_database(db_path)

        corpus = type("Corpus", (), {"root_path": tmp_dir})()
        EngineRunner().run(
            corpus=corpus,
            project_prefixes=["pkg"],
            repo_root=tmp_dir,
            connection=db,
        )
        db.close()

        oracle = DBOracle(db_path)
        oracle.conn.row_factory = sqlite3.Row

        assert oracle.get_project_root() == normalize_file_path(tmp_dir)

        modules = {m["module"] for m in oracle.find_modules()}
        assert "pkg" in modules

        # the bug this closes: no module identity should still carry
        # any segment of the absolute temp-dir path once trimmed
        tmp_dir_norm = normalize_file_path(tmp_dir)
        leaked_segment = [p for p in tmp_dir_norm.split("/") if p][-1]
        assert not any(leaked_segment in m for m in modules)

        oracle.conn.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == "__main__":
    tests = [
        test_file_path_to_module_trims_with_project_root,
        test_get_project_root_reads_persisted_value,
        test_get_project_root_infers_from_files_when_unset,
        test_get_project_root_empty_when_insufficient_signal,
        test_get_project_root_empty_on_totally_empty_db,
        test_find_modules_and_symbol_module_map_use_persisted_root,
        test_engine_run_persists_project_root_and_trims_module_identity,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
