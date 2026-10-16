"""
Tests for determined/ingestion/fsm_walker.py.

All tests are offline -- in-memory SQLite only.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from determined.ingestion.fsm_walker import (
    _parse_fsm,
    discover_fsm_files,
    ingest_fsm_file,
    ingest_fsm_pass,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENCOUNTER_FSM = {
    "name": "EncounterFSM",
    "states": [
        {"name": "initiating", "initial": True, "prompt": "{description}"},
        {"name": "awaiting_choice", "prompt": "What do you do?"},
        {"name": "resolving_fight", "prompt": "Combat starts!"},
        {"name": "completed", "final": True, "prompt": "Encounter ended."},
    ],
    "events": {
        "next": {"transitions": [{"from": "initiating", "to": "awaiting_choice"}]},
        "fight": {
            "transitions": [
                {"from": "awaiting_choice", "to": "resolving_fight", "actions": ["start_combat"]}
            ]
        },
        "flee": {
            "transitions": [
                {"from": "awaiting_choice", "to": "completed", "cond": "flee_possible", "actions": ["resolve_flee"]}
            ]
        },
        "parley": {
            "transitions": [{"from": "awaiting_choice", "to": "completed", "actions": ["resolve_parley"]}]
        },
        "combat_ended": {
            "transitions": [{"from": "resolving_fight", "to": "completed"}]
        },
    },
    "guards": {
        "flee_possible": {"parameters": {}, "description": "True if flee attempt succeeds."},
        "parley_possible": {"parameters": {}, "description": "True if parley attempt succeeds."},
    },
    "actions": {
        "start_combat": {"parameters": {}, "description": "Triggers combat system."},
        "resolve_flee": {"parameters": {}, "description": "Resolves flee success."},
        "resolve_parley": {"parameters": {}, "description": "Resolves parley success."},
    },
}


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            name TEXT,
            line_number INTEGER,
            return_type TEXT,
            arguments_json TEXT,
            docstring TEXT,
            is_stub INTEGER DEFAULT 0,
            param_types_json TEXT,
            decorators_json TEXT,
            http_route TEXT,
            is_tool INTEGER DEFAULT 0
        );
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            caller TEXT,
            callee TEXT,
            line_number INTEGER,
            caller_file TEXT,
            resolved INTEGER DEFAULT 0,
            edge_type TEXT DEFAULT 'static'
        );
    """)
    return conn


def _write_fsm(tmp_path: Path, data: dict, subdir: str = "config/fsms") -> Path:
    d = tmp_path / subdir
    d.mkdir(parents=True, exist_ok=True)
    p = d / "encounter.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _parse_fsm
# ---------------------------------------------------------------------------

def test_parse_fsm_symbol_counts(tmp_path):
    path = _write_fsm(tmp_path, ENCOUNTER_FSM)
    _, symbols, transitions = _parse_fsm(path)
    names = [s.canonical for s in symbols]
    assert sum(1 for n in names if "::state::" in n) == 4
    assert sum(1 for n in names if "::event::" in n) == 5
    assert sum(1 for n in names if "::action::" in n) == 3
    assert sum(1 for n in names if "::guard::" in n) == 2


def test_parse_fsm_canonical_names(tmp_path):
    path = _write_fsm(tmp_path, ENCOUNTER_FSM)
    _, symbols, _ = _parse_fsm(path)
    names = {s.canonical for s in symbols}
    assert "EncounterFSM::state::initiating" in names
    assert "EncounterFSM::event::fight" in names
    assert "EncounterFSM::action::start_combat" in names
    assert "EncounterFSM::guard::flee_possible" in names


def test_parse_fsm_stub_flags(tmp_path):
    path = _write_fsm(tmp_path, ENCOUNTER_FSM)
    _, symbols, _ = _parse_fsm(path)
    for sym in symbols:
        if "::action::" in sym.canonical or "::guard::" in sym.canonical:
            assert sym.is_stub == 1, f"{sym.canonical} should be stub"
        else:
            assert sym.is_stub == 0, f"{sym.canonical} should not be stub"


def test_parse_fsm_transitions(tmp_path):
    path = _write_fsm(tmp_path, ENCOUNTER_FSM)
    _, _, transitions = _parse_fsm(path)
    assert len(transitions) == 5
    assert ("EncounterFSM::event::fight", "EncounterFSM::state::resolving_fight") in transitions
    assert ("EncounterFSM::event::flee", "EncounterFSM::state::completed") in transitions


def test_parse_fsm_missing_name_raises(tmp_path):
    bad = {k: v for k, v in ENCOUNTER_FSM.items() if k != "name"}
    path = _write_fsm(tmp_path, bad)
    with pytest.raises(ValueError, match="name"):
        _parse_fsm(path)


def test_parse_fsm_missing_states_raises(tmp_path):
    bad = {k: v for k, v in ENCOUNTER_FSM.items() if k != "states"}
    path = _write_fsm(tmp_path, bad)
    with pytest.raises(ValueError, match="states"):
        _parse_fsm(path)


def test_parse_fsm_invalid_json_raises(tmp_path):
    d = tmp_path / "config/fsms"
    d.mkdir(parents=True)
    p = d / "bad.json"
    p.write_text("{not json}", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        _parse_fsm(p)


# ---------------------------------------------------------------------------
# ingest_fsm_file
# ---------------------------------------------------------------------------

def test_ingest_inserts_correct_symbol_count(tmp_path):
    conn = _make_db()
    path = _write_fsm(tmp_path, ENCOUNTER_FSM)
    count = ingest_fsm_file(path, conn, tmp_path)
    assert count == 14  # 4 states + 5 events + 3 actions + 2 guards


def test_ingest_functions_rows(tmp_path):
    conn = _make_db()
    path = _write_fsm(tmp_path, ENCOUNTER_FSM)
    ingest_fsm_file(path, conn, tmp_path)
    rows = conn.execute("SELECT name, is_stub FROM functions").fetchall()
    names = {r[0] for r in rows}
    assert "EncounterFSM::state::initiating" in names
    assert "EncounterFSM::action::start_combat" in names
    stubs = {r[0] for r in rows if r[1] == 1}
    assert "EncounterFSM::action::start_combat" in stubs
    assert "EncounterFSM::state::initiating" not in stubs


def test_ingest_graph_edges(tmp_path):
    conn = _make_db()
    path = _write_fsm(tmp_path, ENCOUNTER_FSM)
    ingest_fsm_file(path, conn, tmp_path)
    rows = conn.execute(
        "SELECT source_id, target_id, edge_type FROM graph_edges"
    ).fetchall()
    assert len(rows) == 5
    assert all(r[2] == "fsm_transition" for r in rows)
    # normalize_symbol strips the :: prefix segments, leaving bare name
    src_ids = {r[0] for r in rows}
    tgt_ids = {r[1] for r in rows}
    assert "fight" in src_ids
    assert "resolving_fight" in tgt_ids


def test_ingest_idempotent(tmp_path):
    conn = _make_db()
    path = _write_fsm(tmp_path, ENCOUNTER_FSM)
    ingest_fsm_file(path, conn, tmp_path)
    ingest_fsm_file(path, conn, tmp_path)
    count = conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]
    assert count == 14  # no duplicates


def test_ingest_edge_caller_callee_display(tmp_path):
    conn = _make_db()
    path = _write_fsm(tmp_path, ENCOUNTER_FSM)
    ingest_fsm_file(path, conn, tmp_path)
    row = conn.execute(
        "SELECT caller, callee FROM graph_edges WHERE source_id = 'fight'"
    ).fetchone()
    assert row is not None
    assert row[0] == "EncounterFSM::event::fight"
    assert row[1] == "EncounterFSM::state::resolving_fight"


# ---------------------------------------------------------------------------
# discover_fsm_files
# ---------------------------------------------------------------------------

def test_discover_finds_fsm_json(tmp_path):
    _write_fsm(tmp_path, ENCOUNTER_FSM, subdir="config/fsms")
    found = discover_fsm_files(tmp_path)
    assert len(found) == 1
    assert found[0].name == "encounter.json"


def test_discover_ignores_non_fsm_json(tmp_path):
    other = tmp_path / "config"
    other.mkdir(parents=True)
    (other / "settings.json").write_text("{}", encoding="utf-8")
    _write_fsm(tmp_path, ENCOUNTER_FSM)
    found = discover_fsm_files(tmp_path)
    assert all("fsms" in str(p) for p in found)


# ---------------------------------------------------------------------------
# ingest_fsm_pass
# ---------------------------------------------------------------------------

def test_ingest_pass_multiple_files(tmp_path):
    conn = _make_db()
    _write_fsm(tmp_path, ENCOUNTER_FSM, subdir="config/fsms")
    # write a second minimal FSM
    second = {"name": "TradeFSM", "states": [{"name": "open"}, {"name": "closed"}], "events": {}}
    _write_fsm(tmp_path, second, subdir="world/fsms")
    total = ingest_fsm_pass(conn, tmp_path)
    assert total == 16  # 14 encounter + 2 trade states


def test_ingest_pass_skips_bad_file(tmp_path, capsys):
    conn = _make_db()
    fsms_dir = tmp_path / "config/fsms"
    fsms_dir.mkdir(parents=True)
    (fsms_dir / "bad.json").write_text("{not json}", encoding="utf-8")
    _write_fsm(tmp_path, ENCOUNTER_FSM)
    total = ingest_fsm_pass(conn, tmp_path)
    captured = capsys.readouterr()
    assert "skipped" in captured.out
    assert total == 14  # bad file skipped, encounter ingested


# ---------------------------------------------------------------------------
# Handler wiring: a declared handler is only "unimplemented" if code lacks it
# ---------------------------------------------------------------------------

from determined.ingestion.fsm_walker import classify_handlers, python_registry_keys  # noqa: E402

TRADE_FSM = {
    "name": "TradeFSM",
    "states": [{"name": "awaiting", "initial": True}, {"name": "completed", "final": True}],
    "events": {"offer": {"transitions": [
        {"from": "awaiting", "to": "completed", "cond": "price_too_low", "actions": ["update_price"]}]}},
    "guards": {"price_too_low": {"description": "offer < price"}},
    "actions": {"update_price": {"description": "store the counter"},
                "execute_buy": {"description": "complete the purchase"}},
}


def _write_py(tmp_path: Path, rel: str, text: str) -> str:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return str(p).replace("\\", "/")


def _add_function(conn, file_path: str, name: str, is_stub: int = 0) -> None:
    conn.execute(
        "INSERT INTO functions (file_path, name, line_number, is_stub) VALUES (?,?,1,?)",
        (file_path, name, is_stub),
    )


def _wiring_corpus(tmp_path: Path):
    """builtins defines price_lt and update_price; the engine registry maps the guard
    name price_too_low to price_lt but has no 'update_price' key; execute_buy is nowhere."""
    conn = _make_db()
    b = _write_py(tmp_path, "world/fsm/builtins.py",
                  "def price_lt(i, e):\n    return True\n\ndef update_price(i, e):\n    return i\n")
    g = _write_py(tmp_path, "world/engine.py",
                  "import builtins_mod as builtins\n"
                  "REG = {'price_too_low': builtins.price_lt, 'noise': 3}\n")
    _add_function(conn, b, "price_lt")
    _add_function(conn, b, "update_price")
    _add_function(conn, g, "build")
    conn.commit()
    return conn


def test_registry_keys_found_with_value_names(tmp_path):
    p = _write_py(tmp_path, "e.py", "R = {'a': mod.f, 'b': g, 'c': 1, 'd': mod.sub.h}\n")
    keys = python_registry_keys([p])
    assert keys["a"][0][0] == "f" and keys["b"][0][0] == "g" and keys["d"][0][0] == "h"
    assert "c" not in keys


def test_registry_scan_skips_tests_and_bad_files(tmp_path):
    t = _write_py(tmp_path, "tests/test_x.py", "R = {'k': f}\n")
    t2 = _write_py(tmp_path, "pkg/test_y.py", "R = {'k2': f}\n")
    bad = _write_py(tmp_path, "pkg/bad.py", "def (:\n")
    assert python_registry_keys([t, t2, bad, str(tmp_path / "missing.py")]) == {}


def test_classify_wired_defined_and_missing(tmp_path):
    conn = _wiring_corpus(tmp_path)
    w = classify_handlers(conn)
    assert w["price_too_low"][0] == "wired"
    assert "engine.py" in w["price_too_low"][1] and "price_lt" in w["price_too_low"][1]
    assert w["update_price"][0] == "defined"          # function exists, no registry key
    assert "execute_buy" not in w                     # missing


def test_wired_value_must_be_a_real_function(tmp_path):
    conn = _make_db()
    g = _write_py(tmp_path, "e.py", "R = {'ghost': builtins.not_defined_anywhere}\n")
    _add_function(conn, g, "build")
    assert "ghost" not in classify_handlers(conn)


def test_ingest_marks_wired_defined_missing(tmp_path):
    conn = _wiring_corpus(tmp_path)
    path = _write_fsm(tmp_path, TRADE_FSM)
    ingest_fsm_pass(conn, tmp_path)
    rows = {r[0]: (r[1], r[2] or "") for r in conn.execute(
        "SELECT name, is_stub, docstring FROM functions WHERE file_path LIKE '%.json'")}
    guard = rows["TradeFSM::guard::price_too_low"]
    assert guard[0] == 0 and guard[1].startswith("[wired:")
    defined = rows["TradeFSM::action::update_price"]
    assert defined[0] == 1 and defined[1].startswith("[defined, not registered]")
    missing = rows["TradeFSM::action::execute_buy"]
    assert missing[0] == 1 and not missing[1].startswith("[")


def test_ingest_without_python_files_keeps_everything_stub(tmp_path):
    conn = _make_db()
    path = _write_fsm(tmp_path, TRADE_FSM)
    ingest_fsm_file(path, conn, tmp_path)
    stubs = conn.execute(
        "SELECT COUNT(*) FROM functions WHERE is_stub=1 AND file_path LIKE '%.json'").fetchone()[0]
    assert stubs == 3          # 1 guard + 2 actions, nothing resolved
