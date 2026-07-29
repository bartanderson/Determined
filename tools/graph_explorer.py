"""Standalone launcher for the Determined graph explorer.

Usage:
    python tools/graph_explorer.py dj2
    python tools/graph_explorer.py C:/Users/bartl/dev/Determined/C_Users_bartl_dev_dj2.db
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from determined.ui.graph_explorer import launch, resolve_db

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/graph_explorer.py <corpus_name_or_db_path>")
        print("\nKnown corpora: dj2, raylib, ebiten, zig-gamedev, batteries, brogue-ce, ...")
        sys.exit(1)
    try:
        db = resolve_db(sys.argv[1])
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    launch(db)
