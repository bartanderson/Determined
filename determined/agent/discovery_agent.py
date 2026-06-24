# tools/analysis/agent/discovery_agent.py
#
# Autonomous discovery loop - surveys the corpus and populates knowledge.db.
# Designed to run in finite batches; resume-safe (skips already-stored subjects).
#
# Usage:
#   python -m determined.agent.discovery_agent.py corpus.db
#   python -m determined.agent.discovery_agent.py corpus.db --limit 10 --verbose

from __future__ import annotations

import argparse
import sys

from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.agent.graph_utils import find_entry_points, bfs_callees


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _already_stored(assessor: Assessor, subject: str, kind: str) -> bool:
    """True if knowledge.db already has a finding of this kind for this subject."""
    conn = getattr(assessor, "_knowledge_conn", None)
    if conn is None:
        return False
    row = conn.execute(
        "SELECT 1 FROM knowledge_artifacts WHERE subject = ? AND kind = ? LIMIT 1",
        (subject, kind),
    ).fetchone()
    return row is not None


def _store(assessor: Assessor, subject: str, kind: str, content: str, verbose: bool) -> None:
    if verbose:
        print(f"  [store] {kind} / {subject[:60]}")
    assessor.add_artifact(subject, kind, content, "ai-generated")


# ------------------------------------------------------------------
# Phase A: survey files
# ------------------------------------------------------------------

def survey_files(
    oracle: DBOracle,
    assessor: Assessor,
    limit: int = 5,
    verbose: bool = False,
) -> int:
    """
    For each file in the corpus (up to limit), generate and store a file_purpose finding.
    Skips files already in knowledge.db. Returns count of new findings stored.
    """
    files = oracle.find_files()
    stored = 0

    for f in files:
        if stored >= limit:
            break
        fp = f["file_path"]
        rel = fp.replace("\\", "/")
        # Use filename as subject key
        subject = rel.split("/")[-1]

        if _already_stored(assessor, subject, "file_purpose"):
            if verbose:
                print(f"  [skip] {subject} (already stored)")
            continue

        if verbose:
            print(f"  [describe] {subject} ...", end=" ", flush=True)

        result = assessor.semantic_summary(rel, kind="file")
        content = result.get("content", "").strip()

        if not content or "[heuristic]" in content or "no source text" in content.lower():
            if verbose:
                print("skipped (no useful content)")
            continue

        _store(assessor, subject, "file_purpose", content, verbose=False)
        if verbose:
            print("done")
        stored += 1

    return stored


# ------------------------------------------------------------------
# Phase B: entry points
# ------------------------------------------------------------------

def survey_entry_points(
    oracle: DBOracle,
    assessor: Assessor,
    limit: int = 5,
    verbose: bool = False,
) -> int:
    """
    Find system entry points (symbols with no callers) and store a design_note for each.
    """
    eps = find_entry_points(oracle)
    stored = 0

    for ep in eps:
        if stored >= limit:
            break
        name = ep["name"]
        fp = ep["file_path"].replace("\\", "/").split("/")[-1]

        if _already_stored(assessor, name, "design_note"):
            continue

        # Get intent if available
        row = oracle.conn.execute(
            "SELECT docstring FROM functions WHERE name = ? LIMIT 1", (name,)
        ).fetchone()
        docstring = (row[0] or "").strip() if row else ""

        content = f"Entry point in {fp}."
        if docstring:
            content += f" {docstring}"
        content += " No callers found in corpus - likely a public API, script root, or dead code."

        _store(assessor, name, "design_note", content, verbose)
        stored += 1

    return stored


# ------------------------------------------------------------------
# Phase C: trace call chains from entry points
# ------------------------------------------------------------------

def survey_call_chains(
    oracle: DBOracle,
    assessor: Assessor,
    limit: int = 3,
    depth: int = 3,
    verbose: bool = False,
) -> int:
    """
    BFS from entry points, store a strategy_decision summarizing each call chain.
    Uses AI (describe_file) only for the root file; chain summary is deterministic.
    """
    eps = find_entry_points(oracle)[:limit]
    stored = 0

    for ep in eps:
        root = ep["name"]
        subject = f"chain::{root}"

        if _already_stored(assessor, subject, "strategy_decision"):
            continue

        chain = bfs_callees(oracle, root, max_depth=depth, max_nodes=20)
        if not chain:
            continue

        chain_str = " -> ".join(n["symbol"] for n in chain[:10])
        content = f"Call chain from entry point '{root}': {root} -> {chain_str}"
        if len(chain) > 10:
            content += f" ... ({len(chain)} total nodes)"

        if verbose:
            print(f"  [chain] {root}: {len(chain)} nodes")

        _store(assessor, subject, "strategy_decision", content, verbose=False)
        stored += 1

    return stored


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def run(db_path: str, limit: int = 5, verbose: bool = False) -> int:
    """Run one discovery batch. Returns total new findings stored (0 = nothing left to find)."""
    print(f"\nLoading corpus: {db_path}")
    try:
        oracle = DBOracle(db_path)
        assessor = Assessor(oracle)
    except Exception as e:
        print(f"ERROR loading corpus: {e}")
        sys.exit(1)

    print(f"Discovery run (limit={limit} per phase)\n")

    total = 0

    print("Phase A: surveying files...")
    n = survey_files(oracle, assessor, limit=limit, verbose=verbose)
    print(f"  {n} file_purpose findings stored")
    total += n

    print("Phase B: entry points...")
    n = survey_entry_points(oracle, assessor, limit=limit, verbose=verbose)
    print(f"  {n} design_note findings stored")
    total += n

    print("Phase C: call chains...")
    n = survey_call_chains(oracle, assessor, limit=min(limit, 3), verbose=verbose)
    print(f"  {n} strategy_decision findings stored")
    total += n

    print("\nDone. Run again to continue (already-stored subjects are skipped).")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous codebase discovery agent.")
    parser.add_argument("db_path", help="Corpus DB path (e.g. corpus.db)")
    parser.add_argument("--limit", type=int, default=5, help="Max findings per phase (default 5)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    run(args.db_path, limit=args.limit, verbose=args.verbose)
