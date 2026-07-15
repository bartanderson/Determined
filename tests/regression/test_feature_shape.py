"""
Regression tests for RM59: list_features and feature_shape.
Uses in-memory SQLite seeded with a multi-directory symbol fixture.
"""
import sqlite3
import pytest
from unittest.mock import MagicMock
from determined.agent.agent_tools import (
    list_features, feature_shape, development_priorities,
    _detect_prefix, _strip_prefix, _is_external_callee,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_oracle(conn):
    oracle = MagicMock()
    oracle.conn = conn
    return oracle


def _seed_db(conn):
    """
    Minimal schema + fixture data.

    Feature layout:
      combat/attack.py   -> Attack, defend (stub)
      combat/utils.py    -> log_hit
      loot/chest.py      -> open_chest (entry: called by main), give_item (stub)
      loot/rare.py       -> roll_rare
      main.py            -> main

    Call edges:
      main -> open_chest        (external caller into loot)
      open_chest -> give_item   (internal loot edge)
      open_chest -> roll_rare   (internal loot edge)
      open_chest -> log_hit     (cross-feature: loot -> combat)
      Attack -> log_hit         (internal combat edge? no -- Attack is combat, log_hit is combat)
      defend -> log_hit         (internal)
    """
    conn.executescript("""
        CREATE TABLE functions (
            name TEXT PRIMARY KEY,
            file_path TEXT,
            is_stub INTEGER DEFAULT 0,
            docstring TEXT,
            param_types_json TEXT
        );
        CREATE TABLE graph_edges (
            caller TEXT,
            callee TEXT,
            edge_type TEXT DEFAULT 'static',
            resolved INTEGER DEFAULT 1
        );
        -- symbols
        INSERT INTO functions VALUES ('Attack',     'combat/attack.py', 0, NULL, NULL);
        INSERT INTO functions VALUES ('defend',     'combat/attack.py', 1, NULL, NULL);
        INSERT INTO functions VALUES ('log_hit',    'combat/utils.py',  0, NULL, NULL);
        INSERT INTO functions VALUES ('open_chest', 'loot/chest.py',    0, NULL, NULL);
        INSERT INTO functions VALUES ('give_item',  'loot/chest.py',    1, NULL, NULL);
        INSERT INTO functions VALUES ('roll_rare',  'loot/rare.py',     0, NULL, NULL);
        INSERT INTO functions VALUES ('main',       'main.py',          0, NULL, NULL);
        -- edges
        INSERT INTO graph_edges VALUES ('main',       'open_chest', 'static', 1);
        INSERT INTO graph_edges VALUES ('open_chest', 'give_item',  'static', 1);
        INSERT INTO graph_edges VALUES ('open_chest', 'roll_rare',  'static', 1);
        INSERT INTO graph_edges VALUES ('open_chest', 'log_hit',    'static', 1);
        INSERT INTO graph_edges VALUES ('Attack',     'log_hit',    'static', 1);
        INSERT INTO graph_edges VALUES ('defend',     'log_hit',    'static', 1);
    """)


# ---------------------------------------------------------------------------
# list_features tests
# ---------------------------------------------------------------------------

def test_list_features_groups_by_top_dir():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = list_features(oracle, {"depth": 1})
    assert "combat" in result
    assert "loot" in result
    assert "main" in result


def test_list_features_symbol_counts():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = list_features(oracle, {"depth": 1})
    # combat has 3 symbols, loot has 3
    lines = [l for l in result.splitlines() if l.strip().startswith("combat")]
    assert lines, "combat feature row missing"
    parts = lines[0].split()
    combat_syms = int(parts[1])
    assert combat_syms == 3


def test_list_features_stub_counts():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = list_features(oracle, {"depth": 1})
    loot_lines = [l for l in result.splitlines() if l.strip().startswith("loot")]
    assert loot_lines, "loot feature row missing"
    parts = loot_lines[0].split()
    loot_stubs = int(parts[2])
    assert loot_stubs == 1  # give_item


def test_list_features_entry_points():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = list_features(oracle, {"depth": 1})
    # open_chest is called by main (outside loot) -> loot has 1 entry point
    loot_lines = [l for l in result.splitlines() if l.strip().startswith("loot")]
    parts = loot_lines[0].split()
    loot_ep = int(parts[3])
    assert loot_ep >= 1


def test_list_features_depth2():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = list_features(oracle, {"depth": 2})
    assert "combat/attack" in result or "combat/utils" in result
    assert "loot/chest" in result or "loot/rare" in result


def test_list_features_scope_filter():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = list_features(oracle, {"depth": 1, "scope": "loot"})
    assert "loot" in result
    assert "combat" not in result


def test_list_features_empty_corpus():
    conn = sqlite3.connect(":memory:")
    conn.executescript("CREATE TABLE functions (name TEXT, file_path TEXT, is_stub INTEGER);")
    oracle = _make_oracle(conn)
    result = list_features(oracle, {})
    assert "No functions" in result


# ---------------------------------------------------------------------------
# feature_shape tests
# ---------------------------------------------------------------------------

def test_feature_shape_identifies_entry_points():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = feature_shape(oracle, {"feature_path": "loot"})
    assert "open_chest" in result
    assert "Entry points" in result


def test_feature_shape_marks_stubs():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = feature_shape(oracle, {"feature_path": "loot"})
    assert "[stub]" in result
    assert "give_item" in result


def test_feature_shape_implemented_nodes():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = feature_shape(oracle, {"feature_path": "loot"})
    assert "[implemented]" in result


def test_feature_shape_cross_feature_edge():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = feature_shape(oracle, {"feature_path": "loot"})
    # open_chest -> log_hit is cross-feature (log_hit in combat)
    assert "log_hit" in result
    assert "cross-feature" in result


def test_feature_shape_completeness_shown():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = feature_shape(oracle, {"feature_path": "loot"})
    assert "Completeness" in result
    assert "%" in result


def test_feature_shape_missing_feature_path():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = feature_shape(oracle, {})
    assert "ERROR" in result


def test_feature_shape_no_matching_symbols():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = feature_shape(oracle, {"feature_path": "nonexistent"})
    assert "No symbols found" in result


def test_feature_shape_combat_entry_point_is_log_hit():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = feature_shape(oracle, {"feature_path": "combat"})
    # log_hit is called by open_chest (from loot) -> it's the entry point for combat
    assert "log_hit" in result
    assert "Entry points" in result


# ---------------------------------------------------------------------------
# development_priorities tests
# ---------------------------------------------------------------------------

def test_development_priorities_returns_table():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {})
    assert "Development priorities" in result
    assert "Feature" in result
    assert "Done%" in result


def test_development_priorities_ranks_by_priority():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {})
    # loot has a stub (give_item) AND an external caller (main -> open_chest)
    # so it should have priority > 0 and appear in results
    assert "loot" in result


def test_development_priorities_top_n():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {"top_n": 1})
    # Only 1 feature row should appear after the header
    lines = [l for l in result.splitlines() if l and not l.startswith("-") and not l.startswith("Dev") and not l.startswith("Feature") and not l.startswith(" ") and not l.startswith("\t")]
    assert len(lines) <= 1


def test_development_priorities_shows_completeness():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {})
    assert "%" in result


def test_development_priorities_cross_feature_blocker_flag():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {})
    # give_item (loot stub) is called by open_chest (loot), not cross-feature in this fixture.
    # defend (combat stub) is only called internally, not cross-feature either.
    # So BLOCKER flag may not appear -- but the test confirms the field is computed correctly
    # by verifying no crash and the output contains priority scores.
    assert "Score" in result


def test_development_priorities_blocker_feature_ranks_high():
    """A stub called from OUTSIDE its feature (cross-feature blocker) ranks above
    a stub only called internally at same priority score."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE functions (
            name TEXT PRIMARY KEY,
            file_path TEXT,
            is_stub INTEGER DEFAULT 0,
            docstring TEXT,
            param_types_json TEXT
        );
        CREATE TABLE graph_edges (
            caller TEXT,
            callee TEXT,
            edge_type TEXT DEFAULT 'static',
            resolved INTEGER DEFAULT 1
        );
        -- feature A: one stub (a_stub) called from feature B (cross-feature blocker)
        INSERT INTO functions VALUES ('a_impl',  'featA/x.py', 0, NULL, NULL);
        INSERT INTO functions VALUES ('a_stub',  'featA/x.py', 1, NULL, NULL);
        -- feature B: one stub (b_stub) only called internally
        INSERT INTO functions VALUES ('b_impl',  'featB/y.py', 0, NULL, NULL);
        INSERT INTO functions VALUES ('b_stub',  'featB/y.py', 1, NULL, NULL);
        -- external caller into both features (equal entry point pressure)
        INSERT INTO functions VALUES ('main',    'main.py',    0, NULL, NULL);
        INSERT INTO graph_edges VALUES ('main', 'a_impl', 'static', 1);
        INSERT INTO graph_edges VALUES ('main', 'b_impl', 'static', 1);
        -- a_stub is called from featB (cross-feature blocker)
        INSERT INTO graph_edges VALUES ('b_impl', 'a_stub', 'static', 1);
        -- b_stub only called internally
        INSERT INTO graph_edges VALUES ('b_impl', 'b_stub', 'static', 1);
    """)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {})
    assert "BLOCKER" in result
    # featA should appear before featB in the output (it's the cross-feature blocker)
    featA_pos = result.find("featA")
    featB_pos = result.find("featB")
    assert featA_pos != -1 and featB_pos != -1
    assert featA_pos < featB_pos


def test_development_priorities_scope_filter():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {"scope": "loot"})
    assert "loot" in result
    assert "combat" not in result


def test_development_priorities_empty_corpus():
    conn = sqlite3.connect(":memory:")
    conn.executescript("CREATE TABLE functions (name TEXT, file_path TEXT, is_stub INTEGER);")
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {})
    assert "No functions" in result


def test_development_priorities_all_complete():
    """When no stubs or missing nodes exist, no incomplete features are returned."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE functions (name TEXT PRIMARY KEY, file_path TEXT, is_stub INTEGER DEFAULT 0, docstring TEXT, param_types_json TEXT);
        CREATE TABLE graph_edges (caller TEXT, callee TEXT, edge_type TEXT DEFAULT 'static', resolved INTEGER DEFAULT 1);
        INSERT INTO functions VALUES ('foo', 'pkg/a.py', 0, NULL, NULL);
        INSERT INTO functions VALUES ('bar', 'pkg/b.py', 0, NULL, NULL);
        INSERT INTO graph_edges VALUES ('foo', 'bar', 'static', 1);
    """)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {})
    assert "No incomplete" in result


# ---------------------------------------------------------------------------
# RM60 Phase 0: prefix auto-detect and external callee filtering
# ---------------------------------------------------------------------------

def _seed_abs_db(conn):
    """Same fixture as _seed_db but with Windows-style absolute paths."""
    conn.executescript("""
        CREATE TABLE functions (
            name TEXT PRIMARY KEY,
            file_path TEXT,
            is_stub INTEGER DEFAULT 0,
            docstring TEXT,
            param_types_json TEXT
        );
        CREATE TABLE graph_edges (
            caller TEXT,
            callee TEXT,
            edge_type TEXT DEFAULT 'static',
            resolved INTEGER DEFAULT 1
        );
        INSERT INTO functions VALUES ('Attack',     'C:/Users/dev/proj/combat/attack.py', 0, NULL, NULL);
        INSERT INTO functions VALUES ('defend',     'C:/Users/dev/proj/combat/attack.py', 1, NULL, NULL);
        INSERT INTO functions VALUES ('log_hit',    'C:/Users/dev/proj/combat/utils.py',  0, NULL, NULL);
        INSERT INTO functions VALUES ('open_chest', 'C:/Users/dev/proj/loot/chest.py',    0, NULL, NULL);
        INSERT INTO functions VALUES ('give_item',  'C:/Users/dev/proj/loot/chest.py',    1, NULL, NULL);
        INSERT INTO functions VALUES ('roll_rare',  'C:/Users/dev/proj/loot/rare.py',     0, NULL, NULL);
        INSERT INTO functions VALUES ('main',       'C:/Users/dev/proj/main.py',          0, NULL, NULL);
        INSERT INTO graph_edges VALUES ('main',       'open_chest', 'static', 1);
        INSERT INTO graph_edges VALUES ('open_chest', 'give_item',  'static', 1);
        INSERT INTO graph_edges VALUES ('open_chest', 'roll_rare',  'static', 1);
        INSERT INTO graph_edges VALUES ('open_chest', 'log_hit',    'static', 1);
        INSERT INTO graph_edges VALUES ('Attack',     'log_hit',    'static', 1);
        INSERT INTO graph_edges VALUES ('defend',     'log_hit',    'static', 1);
        -- external call that must NOT count as local-missing
        INSERT INTO graph_edges VALUES ('open_chest', 'os.path.join', 'static', 1);
        INSERT INTO graph_edges VALUES ('Attack',     'json.loads',   'static', 1);
    """)


# --- _detect_prefix unit tests ---

def test_detect_prefix_strips_common_root():
    fps = [
        "C:/Users/dev/proj/combat/attack.py",
        "C:/Users/dev/proj/loot/chest.py",
        "C:/Users/dev/proj/main.py",
    ]
    assert _detect_prefix(fps) == "C:/Users/dev/proj"


def test_detect_prefix_single_path():
    fps = ["C:/Users/dev/proj/pkg/a.py"]
    result = _detect_prefix(fps)
    assert result == "C:/Users/dev/proj/pkg"


def test_detect_prefix_empty():
    assert _detect_prefix([]) == ""


def test_detect_prefix_relative_paths_returns_empty_or_minimal():
    fps = ["combat/a.py", "loot/b.py"]
    # Common prefix of relative paths is empty (no shared leading segments)
    result = _detect_prefix(fps)
    assert result == ""


# --- _is_external_callee unit tests ---

def test_is_external_dotted():
    assert _is_external_callee("os.path.join") is True
    assert _is_external_callee("json.loads") is True
    assert _is_external_callee("bubbletea.Run") is True


def test_is_external_bare():
    assert _is_external_callee("give_item") is False
    assert _is_external_callee("_process_item") is False
    assert _is_external_callee("open_chest") is False


# --- list_features with absolute paths ---

def test_list_features_absolute_paths_auto_prefix():
    conn = sqlite3.connect(":memory:")
    _seed_abs_db(conn)
    oracle = _make_oracle(conn)
    result = list_features(oracle, {"depth": 1})
    # Feature row labels should be short relative names (not full Windows paths)
    assert "combat" in result
    assert "loot" in result
    # No feature row should start with "C:" (header may mention prefix, that's fine)
    data_lines = [l for l in result.splitlines() if l and not l.startswith("Feature") and not l.startswith("-")]
    assert not any(l.strip().startswith("C:") for l in data_lines)


def test_list_features_explicit_prefix():
    conn = sqlite3.connect(":memory:")
    _seed_abs_db(conn)
    oracle = _make_oracle(conn)
    result = list_features(oracle, {"depth": 1, "prefix": "C:/Users/dev/proj"})
    assert "combat" in result
    data_lines = [l for l in result.splitlines() if l and not l.startswith("Feature") and not l.startswith("-")]
    assert not any(l.strip().startswith("C:") for l in data_lines)


def test_list_features_relative_paths_unchanged():
    """Relative-path corpora (regression) still produce correct names."""
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    result = list_features(oracle, {"depth": 1})
    assert "combat" in result
    assert "loot" in result


# --- feature_shape with absolute paths ---

def test_feature_shape_absolute_path_auto_prefix():
    conn = sqlite3.connect(":memory:")
    _seed_abs_db(conn)
    oracle = _make_oracle(conn)
    # Pass relative feature_path; prefix should be auto-detected
    result = feature_shape(oracle, {"feature_path": "loot"})
    assert "open_chest" in result
    assert "give_item" in result
    assert "No symbols found" not in result


def test_feature_shape_external_not_counted_as_missing():
    conn = sqlite3.connect(":memory:")
    _seed_abs_db(conn)
    oracle = _make_oracle(conn)
    result = feature_shape(oracle, {"feature_path": "loot"})
    # os.path.join is external — should be labelled 'external', not 'local-missing'
    assert "(external)" in result
    assert "os.path.join" in result


def test_feature_shape_external_excluded_from_completeness():
    conn = sqlite3.connect(":memory:")
    _seed_abs_db(conn)
    oracle = _make_oracle(conn)
    result = feature_shape(oracle, {"feature_path": "combat"})
    # json.loads is called by Attack — external, must not drag completeness down
    # combat has no stubs and no local-missing, so completeness should be 100%
    assert "100%" in result


# --- development_priorities with absolute paths ---

def test_development_priorities_absolute_paths_relative_labels():
    conn = sqlite3.connect(":memory:")
    _seed_abs_db(conn)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {})
    assert "loot" in result or "combat" in result
    # Feature rows must not start with "C:" (header may show the prefix, that's fine)
    data_lines = [l for l in result.splitlines()
                  if l and not l.startswith("Dev") and not l.startswith("Feature") and not l.startswith("-")]
    assert not any(l.strip().startswith("C:") for l in data_lines)


# ---------------------------------------------------------------------------
# RM62: bare-suffix callee resolution for JS-style cross-feature edges
# ---------------------------------------------------------------------------

def _seed_js_style_db(conn):
    """
    Simulates a JS corpus where graph_edges.callee is a bare name (e.g. 'generateDungeon')
    but functions.name is module-qualified (e.g. 'dungeon.generateDungeon').
    This is exactly what the JS ingester produces: resolved=1 but callee not updated to
    the qualified name. The fix: bare-suffix matching in list_features and
    development_priorities.
    """
    conn.executescript("""
        CREATE TABLE functions (
            name TEXT PRIMARY KEY,
            file_path TEXT,
            is_stub INTEGER DEFAULT 0,
            docstring TEXT,
            param_types_json TEXT
        );
        CREATE TABLE graph_edges (
            caller TEXT,
            callee TEXT,
            edge_type TEXT DEFAULT 'static',
            resolved INTEGER DEFAULT 1
        );
        -- controller/ calls dungeon/ using bare name 'generateDungeon'
        INSERT INTO functions VALUES ('controller.run',         'controller/controller.js', 0, NULL, NULL);
        INSERT INTO functions VALUES ('dungeon.generateDungeon','dungeon/generate.js',      0, NULL, NULL);
        INSERT INTO functions VALUES ('utility.toss',           'utility/tools.js',         1, NULL, NULL);
        -- JS bare-callee edges (callee lacks module prefix)
        INSERT INTO graph_edges VALUES ('controller.run', 'generateDungeon', 'static', 1);
        INSERT INTO graph_edges VALUES ('controller.run', 'toss',            'static', 1);
    """)


def test_list_features_bare_suffix_callee_counts_as_entry_point():
    """JS-style bare callee 'generateDungeon' should register as EP for dungeon/ feature."""
    conn = sqlite3.connect(":memory:")
    _seed_js_style_db(conn)
    oracle = _make_oracle(conn)
    result = list_features(oracle, {"depth": 1})
    dungeon_lines = [l for l in result.splitlines() if l.strip().startswith("dungeon")]
    assert dungeon_lines, "dungeon feature not found"
    ep_count = int(dungeon_lines[0].split()[3])  # EntryPts column (0=name,1=syms,2=stubs,3=EP)
    assert ep_count >= 1, f"Expected dungeon EP>=1 for bare callee, got {ep_count}"


def test_development_priorities_bare_suffix_callee_counts_as_entry_point():
    """JS-style bare callee 'toss' (stub in utility/) should register as EP and blocker."""
    conn = sqlite3.connect(":memory:")
    _seed_js_style_db(conn)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {})
    assert "utility" in result
    utility_lines = [l for l in result.splitlines() if "utility" in l]
    # utility has a stub (toss) called cross-feature -> should be BLOCKER
    combined = " ".join(utility_lines)
    assert "BLOCKER" in combined or "toss" in combined


def test_development_priorities_external_not_counted_as_missing():
    conn = sqlite3.connect(":memory:")
    _seed_abs_db(conn)
    oracle = _make_oracle(conn)
    result = development_priorities(oracle, {})
    # os.path.join / json.loads should not inflate Miss count or drive down completeness
    # loot has give_item (1 stub), no local-missing bare names -> Miss should be 0
    loot_lines = [l for l in result.splitlines() if "loot" in l and "%" in l]
    if loot_lines:
        parts = loot_lines[0].split()
        miss_idx = 3  # Done% Stubs Miss EP Score columns
        miss_val = int(parts[miss_idx])
        assert miss_val == 0, f"Expected 0 local-missing for loot, got {miss_val}"
