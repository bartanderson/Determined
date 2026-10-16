"""
FSM ingestor: parse FSM JSON files and write symbols + edges into corpus DB.

States and events  -> functions (is_stub=0)
Actions and guards -> functions (is_stub=1 unless the code already wires them)
Transitions        -> graph_edges (edge_type='fsm_transition')

A handler declared in an FSM JSON is only "unimplemented" if the code does not
provide it. Three states, decided from the corpus and the Python source:
  wired    a registry dict literal maps the handler's name to a function that
           exists (e.g. {'price_too_low': builtins.price_lt}); is_stub=0
  defined  a function of that name exists but no registry key names it; stays
           is_stub=1 and the docstring says "[defined, not registered]"
  missing  neither; stays is_stub=1
"""
from __future__ import annotations

import ast
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


def _bare_name(node: ast.AST) -> str | None:
    """Bare callable name of a Name / Attribute value (builtins.price_lt -> price_lt)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def python_registry_keys(paths: list[str]) -> dict[str, list[tuple[str, str]]]:
    """Scan Python files for dict literals with string keys and callable-reference values.

    Returns {key: [(value_bare_name, file_path), ...]}. Registries such as
    guard_registry={'price_too_low': builtins.price_lt} are how FSM names reach code
    (string dispatch), so they are invisible to a call graph. Test files are skipped;
    unreadable or unparseable files are ignored."""
    out: dict[str, list[tuple[str, str]]] = {}
    for p in paths:
        low = p.replace("\\", "/").lower()
        name = low.rsplit("/", 1)[-1]
        if "/tests/" in low or name.startswith("test_") or name.endswith("_test.py"):
            continue
        try:
            tree = ast.parse(Path(p).read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    bare = _bare_name(v)
                    if bare:
                        out.setdefault(k.value, []).append((bare, p))
    return out


def classify_handlers(conn) -> dict[str, tuple[str, str]]:
    """{handler_name: ("wired"|"defined", evidence)} for names the code provides.

    Names absent from the result are missing. Uses the corpus DB for which functions
    exist (is_stub=0, Python) and the Python source for registry dict literals."""
    try:
        impl_rows = conn.execute(
            "SELECT DISTINCT name FROM functions "
            "WHERE is_stub=0 AND file_path LIKE '%.py' AND name NOT LIKE '%::%'"
        ).fetchall()
        path_rows = conn.execute(
            "SELECT DISTINCT file_path FROM functions WHERE file_path LIKE '%.py'"
        ).fetchall()
    except Exception:
        return {}
    impl = {r[0].rsplit(".", 1)[-1] for r in impl_rows if r[0]}
    registries = python_registry_keys([r[0] for r in path_rows if r[0]])

    result: dict[str, tuple[str, str]] = {}
    for key, targets in registries.items():
        for value, file_path in targets:
            if value in impl:
                short = file_path.replace("\\", "/").rsplit("/", 1)[-1]
                result[key] = ("wired", f"{short}: '{key}' -> {value}")
                break
    for name in impl:
        result.setdefault(name, ("defined", ""))
    return result


def ingest_fsm_file(path: Path, conn, project_root: Path,
                    wiring: dict[str, tuple[str, str]] | None = None) -> int:
    """
    Ingest one FSM JSON file into the corpus DB. Idempotent.
    `wiring` is classify_handlers(conn); computed here when not given.
    Returns count of symbols inserted.
    """
    _, symbols, transitions = _parse_fsm(path)
    if wiring is None:
        wiring = classify_handlers(conn)
    for sym in symbols:
        if "::action::" not in sym.canonical and "::guard::" not in sym.canonical:
            continue
        state, evidence = wiring.get(sym.canonical.split("::")[2], ("missing", ""))
        if state == "wired":
            sym.is_stub = 0
            sym.docstring = f"[wired: {evidence}] {sym.docstring}".strip()
        elif state == "defined":
            sym.docstring = f"[defined, not registered] {sym.docstring}".strip()
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
    wiring = classify_handlers(conn)   # once per pass, not once per FSM file
    for path in discover_fsm_files(root):
        try:
            total += ingest_fsm_file(path, conn, root, wiring)
        except (ValueError, KeyError) as exc:
            print(f"[fsm_walker] skipped {path.name}: {exc}")
    return total
