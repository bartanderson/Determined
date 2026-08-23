"""
tools/query.py -- CLI wrapper around Determined's dispatch() layer.

Usage:
    python tools/query.py <tool_name> [args_json] [--db PATH]

Examples:
    python tools/query.py analyze_corpus
    python tools/query.py blast_radius '{"target": "EpistemicPolicy"}'
    python tools/query.py list_stubs '{"limit": 10}'
    python tools/query.py find_interplay_gaps '{}'
    python tools/query.py list_callers '{"symbol": "dispatch"}'
    python tools/query.py --db C_Users_bartl_dev_dj2.db list_stubs '{}'

The default DB is C_Users_bartl_dev_Determined.db (self-corpus).
Available tools: run with no args to list them.
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.agent.agent_tools import dispatch, TOOLS

DEFAULT_DB = "C_Users_bartl_dev_Determined.db"


def main():
    parser = argparse.ArgumentParser(
        description="Run a Determined tool against a corpus DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tool", nargs="?", help="Tool name (omit to list all)")
    parser.add_argument("args", nargs="?", default="{}", help="JSON args dict")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to corpus DB")
    args = parser.parse_args()

    if not args.tool:
        print("Available tools:")
        for name in sorted(TOOLS):
            print(f"  {name}")
        return

    try:
        tool_args = json.loads(args.args)
    except json.JSONDecodeError as e:
        print(f"ERROR: args must be valid JSON: {e}")
        sys.exit(1)

    oracle = DBOracle(args.db)
    assessor = Assessor(oracle)
    result = dispatch(args.tool, tool_args, oracle, assessor)
    print(result)


if __name__ == "__main__":
    main()
