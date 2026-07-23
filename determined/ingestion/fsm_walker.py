"""
FSM ingestor: parse FSM JSON files and write symbols + edges into corpus DB.

States and events  -> functions (is_stub=0)
Actions and guards -> functions (is_stub=1)
Transitions        -> graph_edges (edge_type='fsm_transition')
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from determined.core.pathing import normalize_file_path
from determined.identity.symbol_identity import normalize_symbol


def discover_fsm_files(root: Path) -> list[Path]:
    """Return all *.json files under any path component named 'fsms'."""
    return [p for p in Path(root).rglob("*.json") if "fsms" in p.parts]


@dataclass
class _FsmSymbol:
    canonical: str  # e.g. "EncounterFSM::state::initiating"
    is_stub: int
    docstring: str


def _parse_fsm(path: Path) -> tuple[str, list[_FsmSymbol], list[tuple[str, str]]]:
    """
    Parse one FSM JSON file.
    Returns (fsm_name, symbols, transitions).
    transitions: (event_canonical, target_state_canonical) pairs.
    Raises ValueError for structurally invalid input.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error: {exc}") from exc

    if not isinstance(data.get("name"), str):
        raise ValueError("missing or non-string 'name'")
    if not isinstance(data.get("states"), list):
        raise ValueError("missing or non-list 'states'")

    fsm = data["name"]
    symbols: list[_FsmSymbol] = []
    transitions: list[tuple[str, str]] = []

    for state in data["states"]:
        if isinstance(state.get("name"), str):
            symbols.append(_FsmSymbol(
                canonical=f"{fsm}::state::{state['name']}",
                is_stub=0,
                docstring=state.get("prompt", "") or "",
            ))

    for event_name, event_data in (data.get("events") or {}).items():
        symbols.append(_FsmSymbol(
            canonical=f"{fsm}::event::{event_name}",
            is_stub=0,
            docstring="",
        ))
        for t in (event_data or {}).get("transitions") or []:
            if isinstance(t.get("to"), str):
                transitions.append((
                    f"{fsm}::event::{event_name}",
                    f"{fsm}::state::{t['to']}",
                ))

    for action_name, action_data in (data.get("actions") or {}).items():
        symbols.append(_FsmSymbol(
            canonical=f"{fsm}::action::{action_name}",
            is_stub=1,
            docstring=(action_data or {}).get("description", "") or "",
        ))

    for guard_name, guard_data in (data.get("guards") or {}).items():
        symbols.append(_FsmSymbol(
            canonical=f"{fsm}::guard::{guard_name}",
            is_stub=1,
            docstring=(guard_data or {}).get("description", "") or "",
        ))

    return fsm, symbols, transitions


def ingest_fsm_file(path: Path, conn, project_root: Path) -> int:
    """
    Ingest one FSM JSON file into the corpus DB. Idempotent.
    Returns count of symbols inserted.
    """
    _, symbols, transitions = _parse_fsm(path)
    file_path = normalize_file_path(path)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM functions WHERE file_path = ?", (file_path,))
    cursor.execute(
        "DELETE FROM graph_edges WHERE caller_file = ? AND edge_type = 'fsm_transition'",
        (file_path,),
    )

    for sym in symbols:
        cursor.execute(
            "INSERT INTO functions (file_path, name, line_number, is_stub, docstring) "
            "VALUES (?, ?, 0, ?, ?)",
            (file_path, sym.canonical, sym.is_stub, sym.docstring or None),
        )

    for event_canonical, state_canonical in transitions:
        src_id = normalize_symbol(event_canonical)
        tgt_id = normalize_symbol(state_canonical)
        cursor.execute(
            "INSERT INTO graph_edges "
            "(source_id, target_id, caller, callee, caller_file, resolved, edge_type) "
            "VALUES (?, ?, ?, ?, ?, 1, 'fsm_transition')",
            (src_id, tgt_id, event_canonical, state_canonical, file_path),
        )

    conn.commit()
    return len(symbols)


def ingest_fsm_pass(conn, root: Path) -> int:
    """Discover and ingest all FSM files under root. Returns total symbols ingested."""
    root = Path(root)
    total = 0
    for path in discover_fsm_files(root):
        try:
            total += ingest_fsm_file(path, conn, root)
        except (ValueError, KeyError) as exc:
            print(f"[fsm_walker] skipped {path.name}: {exc}")
    return total
