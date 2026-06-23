# tools/analysis/engine/structural_parity_diff.py

import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass
class FileDiff:
    file_path: str
    engine_count: int
    db_count: int
    mismatch: bool


@dataclass
class EdgeDiff:
    file_path: str
    caller: str
    callee: str
    line_number: int
    in_engine: bool
    in_db: bool


@dataclass
class StructuralDiffResult:
    file_diffs: list[FileDiff]
    edge_diffs: list[EdgeDiff]


# -------------------------------------------------
# DB LOADERS
# -------------------------------------------------

def load_db_file_counts(db_path: str) -> dict[str, int]:
    conn = sqlite3.connect(db_path)

    rows = conn.execute("""
        SELECT file_path, COUNT(*)
        FROM symbol_references
        GROUP BY file_path
    """).fetchall()

    conn.close()
    return {r[0]: r[1] for r in rows}


def load_db_edges(db_path: str) -> set[tuple]:
    conn = sqlite3.connect(db_path)

    rows = conn.execute("""
        SELECT file_path, caller, callee, line_number
        FROM symbol_references
    """).fetchall()

    conn.close()
    return {(r[0], r[1], r[2], r[3]) for r in rows}


# -------------------------------------------------
# ENGINE EXTRACTORS
# -------------------------------------------------

def extract_engine_file_counts(file_analyses) -> dict[str, int]:
    result = {}

    for a in file_analyses:
        result[a.file_path] = len(getattr(a, "symbol_references", []))

    return result


def extract_engine_edges(file_analyses) -> set[tuple]:
    edges = set()

    for a in file_analyses:
        for r in getattr(a, "symbol_references", []):
            edges.add((a.file_path, r.caller, r.callee, r.line_number))

    return edges


# -------------------------------------------------
# CORE DIFF
# -------------------------------------------------

def run_structural_diff(db_path: str, file_analyses) -> StructuralDiffResult:

    db_counts = load_db_file_counts(db_path)
    db_edges = load_db_edges(db_path)

    eng_counts = extract_engine_file_counts(file_analyses)
    eng_edges = extract_engine_edges(file_analyses)

    all_files = set(db_counts.keys()) | set(eng_counts.keys())

    file_diffs = []
    edge_diffs = []

    # -------------------------
    # FILE LEVEL DIFF
    # -------------------------
    for f in all_files:
        ec = eng_counts.get(f, 0)
        dc = db_counts.get(f, 0)

        file_diffs.append(FileDiff(
            file_path=f,
            engine_count=ec,
            db_count=dc,
            mismatch=(ec != dc)
        ))

    # -------------------------
    # EDGE LEVEL DIFF
    # -------------------------
    all_edges = eng_edges | db_edges

    for e in all_edges:
        file_path, caller, callee, line = e

        edge_diffs.append(EdgeDiff(
            file_path=file_path,
            caller=caller,
            callee=callee,
            line_number=line,
            in_engine=e in eng_edges,
            in_db=e in db_edges,
        ))

    return StructuralDiffResult(
        file_diffs=file_diffs,
        edge_diffs=edge_diffs,
    )


# -------------------------------------------------
# REPORT
# -------------------------------------------------

def print_structural_diff(diff: StructuralDiffResult) -> None:

    print("\n=== FILE LEVEL DIFF ===")
    mismatched_files = [d for d in diff.file_diffs if d.mismatch]

    print("total files:", len(diff.file_diffs))
    print("mismatched files:", len(mismatched_files))

    for d in mismatched_files[:20]:
        print(
            d.file_path,
            "| engine:", d.engine_count,
            "| db:", d.db_count,
        )

    print("\n=== EDGE LEVEL DIFF ===")

    missing_in_db = [e for e in diff.edge_diffs if e.in_engine and not e.in_db]
    missing_in_engine = [e for e in diff.edge_diffs if e.in_db and not e.in_engine]

    print("missing in DB:", len(missing_in_db))
    print("missing in engine:", len(missing_in_engine))

    for e in missing_in_db[:20]:
        print("ENGINE_ONLY:", e.file_path, e.caller, "->", e.callee)

    for e in missing_in_engine[:20]:
        print("DB_ONLY:", e.file_path, e.caller, "->", e.callee)