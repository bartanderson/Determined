# tools/analysis/tests/test_embedding_seeds.py
#
# Standalone test harness for embedding-based seed discovery.
# Run against your engine DB:
#
#   python tools/analysis/tests/test_embedding_seeds.py
#
# Compares token-based vs embedding-based seeds side by side
# so you can see exactly what the upgrade buys you.

import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from determined.oracle.db_oracle import DBOracle

# =========================================================
# QUERIES — mix of token-matchable and conceptual
# =========================================================

QUERIES = [
    # Token-matchable — both approaches should find these
    "what depends on route_query",
    "what depends on build_snapshot",
    "show ingestion surface",

    # Conceptual — embedding should do better
    "how does the system persist data",
    "what handles graph traversal",
    "where does classification happen",
    "what manages symbol identity",
    "show me the query execution layer",
    "what produces structural hotspots",
]


def run(db_path: str):
    oracle = DBOracle(db_path)

    print("Building embedding index...")
    count = oracle.build_embedding_index()
    print(f"Indexed {count} symbols.\n")
    print("=" * 70)

    for q in QUERIES:
        print(f"\nQUERY: {q}")
        print("-" * 60)

        token_seeds = oracle._discover_token(q, limit=6)
        semantic_seeds = oracle.discover_seed_symbols_semantic(q, limit=6)

        print(f"TOKEN    ({len(token_seeds):2d}): {token_seeds[:6]}")
        print(f"SEMANTIC ({len(semantic_seeds):2d}): {semantic_seeds[:6]}")

        token_set = set(token_seeds)
        semantic_set = set(semantic_seeds)

        only_semantic = semantic_set - token_set
        only_token = token_set - semantic_set

        if only_semantic:
            print(f"  + semantic only: {sorted(only_semantic)[:4]}")
        if only_token:
            print(f"  - token only:    {sorted(only_token)[:4]}")

    print("\n" + "=" * 70)
    print("Done.")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else \
        "corpus.db"
    run(db_path)