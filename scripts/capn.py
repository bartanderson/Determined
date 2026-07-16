#!/usr/bin/env python3
"""
capn -- trap registry and lookup cache for Determined sessions.
Adapted from cap'n hook (github.com/cyrusNuevoDia/capn-hook), reimplemented in Python.
No external dependencies beyond stdlib.

Two use cases:

  TRAPS: Non-obvious facts that cause wrong answers when unknown -- wrong column names,
  silent defaults, schema quirks, routing collisions. Invisible until you hit them.
  Chart after getting burned. Consult before touching that area again.

  FREQUENT LOOKUPS: Things re-derived from scratch every session that cost more than
  a single grep -- entry points requiring multiple files to locate, non-obvious call
  chains, places where the obvious file isn't the right one.

File-anchored: entries auto-expire when the referenced source files change.
Not for simple file locations (grep is faster).

Commands:
  ask "question"                                    search cache, log hit/miss
  chart "question" --files f1 [f2] [--details ""]  record a trap or lookup with file hashes
  prune                                             remove stale entries
  context                                           print session-start summary + stats
  list                                              list all entries with freshness
"""

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

CAPN_DIR = Path(".capn")
ENTRIES_DIR = CAPN_DIR / "entries"
MAP_FILE = CAPN_DIR / "map.json"
STATS_FILE = CAPN_DIR / "stats.json"


def _ensure_dirs():
    ENTRIES_DIR.mkdir(parents=True, exist_ok=True)


def _file_hash(path: str) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except (OSError, IOError):
        return None


def _load_json(p: Path, default) -> dict:
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_json(p: Path, data):
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_stats() -> dict:
    return _load_json(STATS_FILE, {"hits": 0, "misses": 0, "charted": 0, "tokens_saved": 0})


def _parse_entry(path: Path) -> dict | None:
    """Parse a capn entry: YAML-like frontmatter between --- delimiters."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    fm: dict = {}
    files: dict = {}
    in_files = False
    for line in parts[1].strip().splitlines():
        if line.startswith("files:"):
            in_files = True
            continue
        if in_files:
            m = re.match(r'^\s+(.+):\s+(\S+)$', line)
            if m:
                files[m.group(1).strip()] = m.group(2).strip()
                continue
            in_files = False
        kv = re.match(r'^(\w+):\s+(.+)$', line)
        if kv:
            fm[kv.group(1)] = kv.group(2).strip()

    fm["files"] = files
    if "est_tokens" in fm:
        try:
            fm["est_tokens"] = int(fm["est_tokens"])
        except (ValueError, TypeError):
            fm.pop("est_tokens", None)
    body = parts[2].strip()
    q_match = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
    fm["question"] = q_match.group(1) if q_match else ""
    if q_match:
        details_start = body.index(q_match.group(0)) + len(q_match.group(0))
        fm["details"] = body[details_start:].strip()
    else:
        fm["details"] = body.strip()
    return fm


def _entry_is_fresh(entry: dict) -> bool:
    for fpath, stored_hash in entry.get("files", {}).items():
        current = _file_hash(fpath)
        if current is None or current != stored_hash:
            return False
    return True


def _all_entries() -> list[tuple[Path, dict]]:
    if not ENTRIES_DIR.exists():
        return []
    results = []
    for p in sorted(ENTRIES_DIR.glob("*.md")):
        e = _parse_entry(p)
        if e:
            results.append((p, e))
    return results


def _score(query: str, entry: dict) -> float:
    """Word-overlap score: what fraction of query words appear in the entry."""
    q_words = set(re.findall(r'\w+', query.lower()))
    if not q_words:
        return 0.0
    haystack = (entry.get("question", "") + " " + entry.get("details", "")).lower()
    h_words = set(re.findall(r'\w+', haystack))
    return len(q_words & h_words) / len(q_words)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_ask(question: str, threshold: float = 0.3):
    entries = _all_entries()
    fresh = [(p, e) for p, e in entries if _entry_is_fresh(e)]
    stale_count = len(entries) - len(fresh)

    scored = [(p, e, _score(question, e)) for p, e in fresh]
    hits = sorted([(p, e, s) for p, e, s in scored if s >= threshold],
                  key=lambda x: x[2], reverse=True)

    stats = _load_stats()
    if hits:
        hit_tokens = sum(e.get("est_tokens", 0) for _, e, _ in hits[:5])
        stats["hits"] += 1
        stats["tokens_saved"] = stats.get("tokens_saved", 0) + hit_tokens
        _save_json(STATS_FILE, stats)
        lifetime_k = stats["tokens_saved"]
        lifetime_display = f"~{lifetime_k // 1_000}K" if lifetime_k >= 1_000 else f"~{lifetime_k}"
        for p, e, s in hits[:5]:
            files_str = ", ".join(e.get("files", {}).keys())
            print(f"[score={s:.2f}] {e['question']}")
            if e.get("details"):
                print(f"  {e['details'][:300]}")
            if files_str:
                print(f"  files: {files_str}")
        print(f"  [capn: ~{hit_tokens} tokens | lifetime: {lifetime_display} across {stats['hits']} hits]")
        print()
        if stale_count:
            print(f"({stale_count} stale entries skipped -- run capn prune)")
    else:
        stats["misses"] += 1
        _save_json(STATS_FILE, stats)
        print(f"No cache hits for: {question!r}")
        if stale_count:
            print(f"({stale_count} stale entries skipped)")
        sys.exit(1)  # exit 1 signals a miss so callers can branch


def cmd_chart(question: str, files: list[str], details: str = ""):
    if "\n" in question:
        print("Error: question cannot contain newlines", file=sys.stderr)
        sys.exit(1)
    _ensure_dirs()

    file_hashes: dict[str, str] = {}
    for f in files:
        h = _file_hash(f)
        if h is None:
            print(f"Error: file not found: {f}", file=sys.stderr)
            sys.exit(1)
        file_hashes[f] = h

    entry_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()

    est_tokens = (len(question) + len(details)) // 4

    fm_lines = ["---", "capn: 1", f"id: {entry_id}", f"at: {now}",
                f"est_tokens: {est_tokens}"]
    if file_hashes:
        fm_lines.append("files:")
        for fp, h in file_hashes.items():
            fm_lines.append(f"  {fp}: {h}")
    fm_lines.append("---")

    body = f"# {question}"
    if details:
        body += f"\n{details}"

    (ENTRIES_DIR / f"{entry_id}.md").write_text(
        "\n".join(fm_lines) + "\n" + body + "\n", encoding="utf-8"
    )

    # Update reverse map
    m = _load_json(MAP_FILE, {})
    for fp, h in file_hashes.items():
        if fp not in m:
            m[fp] = {"hash": h, "entries": []}
        m[fp]["hash"] = h
        if entry_id not in m[fp]["entries"]:
            m[fp]["entries"].append(entry_id)
    _save_json(MAP_FILE, m)

    stats = _load_stats()
    stats["charted"] += 1
    _save_json(STATS_FILE, stats)

    print(f"Charted {entry_id}: {question}")


def cmd_prune():
    entries = _all_entries()
    pruned = 0
    for p, e in entries:
        if not _entry_is_fresh(e):
            p.unlink(missing_ok=True)
            pruned += 1
            print(f"Pruned {e.get('id', p.stem)}: {e.get('question', '?')}")

    # Rebuild map from surviving entries
    remaining = _all_entries()
    m: dict = {}
    for _, e in remaining:
        eid = e.get("id")
        for fp, h in e.get("files", {}).items():
            if fp not in m:
                m[fp] = {"hash": h, "entries": []}
            if eid and eid not in m[fp]["entries"]:
                m[fp]["entries"].append(eid)
    _save_json(MAP_FILE, m)
    print(f"Pruned {pruned} stale entries." if pruned else "No stale entries found.")


def cmd_context():
    stats = _load_stats()
    hits = stats.get("hits", 0)
    misses = stats.get("misses", 0)
    charted = stats.get("charted", 0)
    tokens_saved = stats.get("tokens_saved", 0)
    total = hits + misses
    hit_rate = f"{100 * hits // total}%" if total else "n/a"
    saved_display = f"~{tokens_saved // 1_000}K" if tokens_saved >= 1_000 else f"~{tokens_saved}"

    entries = _all_entries()
    fresh_count = sum(1 for _, e in entries if _entry_is_fresh(e))
    stale_count = len(entries) - fresh_count

    stale_note = f" ({stale_count} stale -- run capn prune)" if stale_count else ""

    print(f"""=== CAP'N HOOK: trap registry + lookup cache ===
{fresh_count} entries{stale_note} | {charted} recorded | {hits}/{total} lookups hit ({hit_rate}) | est. {saved_display} tokens saved

Before touching DB queries, symbol resolution, ingestion routing, or re-deriving any
entry point or call chain you've looked up before:
  python scripts/capn.py ask "<what you're about to do or find>"

Chart when you:
  - hit a non-obvious trap (wrong column, silent default, schema quirk, routing collision)
  - locate something that took more than a grep to find (entry point, non-obvious chain)
  python scripts/capn.py chart "<description>" --files path1 [path2] [--details "specifics"]

Entries auto-expire when referenced files change. Run prune to clean stale entries.""")


def cmd_list():
    entries = _all_entries()
    if not entries:
        print("No entries.")
        return
    for p, e in entries:
        fresh = _entry_is_fresh(e)
        status = "OK   " if fresh else "STALE"
        files_str = ", ".join(e.get("files", {}).keys())
        print(f"[{status}] {e.get('id', '?')} -- {e.get('question', '?')}")
        if files_str:
            print(f"         {files_str}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(prog="capn", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    p_ask = sub.add_parser("ask", help="Search discovery cache")
    p_ask.add_argument("question")
    p_ask.add_argument("--threshold", type=float, default=0.3,
                       help="Minimum word-overlap score (default 0.3)")

    p_chart = sub.add_parser("chart", help="Record a discovery")
    p_chart.add_argument("question")
    p_chart.add_argument("--files", nargs="+", required=True,
                         help="Source files this discovery is grounded in")
    p_chart.add_argument("--details", default="", help="Extra context")

    sub.add_parser("prune", help="Remove entries whose files have changed")
    sub.add_parser("context", help="Print session-start instructions + stats")
    sub.add_parser("list", help="List all entries with freshness status")

    args = ap.parse_args()
    if args.cmd == "ask":
        cmd_ask(args.question, args.threshold)
    elif args.cmd == "chart":
        cmd_chart(args.question, args.files, args.details)
    elif args.cmd == "prune":
        cmd_prune()
    elif args.cmd == "context":
        cmd_context()
    elif args.cmd == "list":
        cmd_list()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
