"""
Item 14 - Phase 1: Pattern tool sequence test (no LLM).

Runs orient_to_codebase and understand_symbol patterns against the harrow DB
using run_no_llm() - confirms each step fires and returns data before
involving the model.

Usage:
    cd C:\Users\bartl\dev\Determined
    .venv\Scripts\python.exe tests\item14_phase1_pattern_tools.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.agent.pattern_executor import PatternExecutor
from determined.agent.tool_registry import TASK_PATTERNS

DB_PATH = "C_Users_bartl_dev_harrow.db"

DIVIDER = "-" * 60


def check_db():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found.")
        print("Run ingest first:")
        print("  .venv\\Scripts\\python.exe determined\\engine\\run_engine.py C:\\Users\\bartl\\dev\\harrow")
        sys.exit(1)


def run_pattern(executor, pattern_name, subject, oracle, assessor):
    print(f"\n{'=' * 60}")
    print(f"PATTERN: {pattern_name}  subject={subject!r}")
    steps = TASK_PATTERNS[pattern_name]["steps"]
    print(f"Steps defined: {len(steps)}")
    for i, s in enumerate(steps):
        print(f"  {i+1}. {s['tool']} — {s.get('why','')}")
    print(DIVIDER)

    result = executor.run_no_llm(pattern_name, subject, oracle, assessor, verbose=False)
    print(result)


def main():
    check_db()

    print(f"Loading {DB_PATH} ...")
    oracle = DBOracle(DB_PATH)
    assessor = Assessor(oracle)
    executor = PatternExecutor(
        ollama_url="http://localhost:11434/api/chat",
        ollama_model="llama3.2:3b",
    )

    root = oracle.get_project_root() or DB_PATH
    print(f"Project root: {root}")

    # --- orient_to_codebase (no subject) ---
    run_pattern(executor, "orient_to_codebase", None, oracle, assessor)

    # --- find what symbols exist so we can pick one for understand_symbol ---
    print(f"\n{'=' * 60}")
    print("SYMBOL SAMPLE (to pick understand_symbol target)")
    print(DIVIDER)
    from determined.agent.agent_tools import dispatch
    sample = dispatch("graph_most_connected", {}, oracle, assessor)
    print(sample)

    # --- understand_symbol on world_gen (likely candidate from harrow) ---
    # Try a few names; first non-empty result wins
    candidates = ["world_gen", "WorldGen", "generate", "render", "GameState"]
    chosen = None
    for c in candidates:
        r = dispatch("search_symbols", {"query": c}, oracle, assessor)
        if "No symbols" not in r and "ERROR" not in r:
            chosen = c
            print(f"\nChosen symbol for understand_symbol: {c}")
            break

    if chosen:
        run_pattern(executor, "understand_symbol", chosen, oracle, assessor)
    else:
        print("\nCould not find a suitable symbol - check corpus.")

    print(f"\n{'=' * 60}")
    print("Phase 1 complete. Review output above:")
    print("  - Did each step return data or '(no data)'?")
    print("  - Are the symbol/file names recognizable as harrow code?")
    print("  - Any tool errors?")
    print("Then run Phase 2 (full LLM) via the agent REPL with --verbose.")


if __name__ == "__main__":
    main()
