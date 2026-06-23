# tools/analysis/ask.py
#
# CLAUDE-EDIT 2026-06-16: the real, wired entrypoint.
#
# The 2026-06-16 agent-readiness assessment (see docs/REFACTOR OPS BOARD.md)
# found that QuerySession.run_algebra() — the one method that chains
# real NL -> oracle router -> AI compiler -> AST -> executor -> real Truth
# Layer views — had ZERO callers anywhere in the codebase. It had never
# been run end-to-end against a live project DB. This script is that
# caller. It is the "front door": agent asks a question, Truth Layer
# answers it, against a real DB, with no stub data anywhere in the path.
#
# It supersedes oracle/agent.py and oracle/nl_agent.py, which looked like
# "the agent" but bypassed oracle_router / QuerySession / the Truth Layer
# entirely (raw LLM-extracted intent dict -> direct oracle call, no AST,
# no validation, no determinism guarantee). Those two files have been
# deleted; this is what replaced them.
#
# Usage:
#     python -m determined.ask <db_path> "<question>"
#
# Example:
#     python -m determined.ask corpus.db \
#         "what depends on resolve_analysis_db_path"
#
# What it does, concretely:
#     oracle = DBOracle(db_path)
#     assessor = Assessor(oracle)
#     result = assessor.ask(question)
#         -> session().run_algebra(question, views=all_views())
#         -> all_views() builds STRUCTURE/STABILITY/INTEGRITY/SUMMARY/
#            SUBSYSTEM from real DB-backed data (assessor.py), all 5 —
#            none of them are stub objects.
#
# `result` contains both the oracle-router trace (intent, seeds,
# expansion) and the Truth Layer algebra result (the actual Select/
# Combine projection over the real views).

import sys
import json
from pathlib import Path

from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor


def _jsonable(obj):
    """
    Best-effort conversion of dataclasses / QueryResult-ish objects into
    something json.dumps can print. CLI display only — never used inside
    the actual query/algebra path, which stays fully typed.
    """
    if hasattr(obj, "__dict__"):
        return {k: _jsonable(v) for k, v in vars(obj).items()}
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    return obj


def ask(db_path: str, question: str) -> dict:
    """Programmatic entrypoint — same thing main() drives from argv."""
    oracle = DBOracle(db_path)
    assessor = Assessor(oracle)
    return assessor.ask(question)


def main():
    if len(sys.argv) != 3:
        print('Usage: python -m determined.ask <db_path> "<question>"')
        sys.exit(1)

    db_path, question = sys.argv[1], sys.argv[2]

    if not Path(db_path).exists():
        print(f"Error: db not found: {db_path}")
        sys.exit(1)

    result = ask(db_path, question)

    print("\n=== QUESTION ===")
    print(result["text"])

    print("\n=== INTENT (oracle router) ===")
    print(result["intent"])

    print("\n=== ORACLE TRACE ===")
    oracle_result = result["oracle"]
    print("seeds:", oracle_result.seeds[:10])
    print("expanded:", oracle_result.expanded[:15])

    print("\n=== COMPILED AST ===")
    print(result["compiled_ast"])
    print("compiler:", result["compiler_explanation"])

    print("\n=== ALGEBRA RESULT (Truth Layer, real views) ===")
    print(json.dumps(_jsonable(result["algebra_result"]), indent=2, default=str))


if __name__ == "__main__":
    main()
