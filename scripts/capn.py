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
LOG_FILE = CAPN_DIR / "log.jsonl"
SESSION_FILE = CAPN_DIR / "current_session.txt"

MISS_FLOOR = 300  # minimum token cost estimate for a cache miss
REPORT_FIRST = 5   # sessions before first auto-report notice
REPORT_EVERY = 10  # sessions between subsequent notices


def _ensure_dirs():
    ENTRIES_DIR.mkdir(parents=True, exist_ok=True)


def _log(record: dict):
    record["t"] = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _current_session() -> str:
    if SESSION_FILE.exists():
        return SESSION_FILE.read_text(encoding="utf-8").strip()
    return "untracked"


def _miss_waste_estimate(stats: dict) -> int:
    hits = stats.get("hits", 0)
    saved = stats.get("tokens_saved", 0)
    mean = saved // hits if hits else 0
    return max(mean, MISS_FLOOR)


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
    # Include file paths in the haystack so file-based lookups surface relevant entries.
    files_str = " ".join(entry.get("files", {}).keys())
    haystack = (entry.get("question", "") + " " + entry.get("details", "") + " " + files_str).lower()
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
    session = _current_session()
    if hits:
        hit_tokens = sum(e.get("est_tokens", 0) for _, e, _ in hits[:5])
        stats["hits"] += 1
        stats["tokens_saved"] = stats.get("tokens_saved", 0) + hit_tokens
        _save_json(STATS_FILE, stats)
        _log({"type": "ask", "result": "hit", "query": question,
              "tokens_saved": hit_tokens, "session": session})
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
        waste = _miss_waste_estimate(stats)
        stats["misses"] += 1
        stats["tokens_wasted"] = stats.get("tokens_wasted", 0) + waste
        _save_json(STATS_FILE, stats)
        _log({"type": "ask", "result": "miss", "query": question,
              "tokens_wasted_est": waste, "session": session})
        print(f"No cache hits for: {question!r}")
        if stale_count:
            print(f"({stale_count} stale entries skipped)")
        sys.exit(1)  # exit 1 signals a miss so callers can branch


def cmd_chart(question: str, files: list[str], details: str = "", work_cost: int = 500):
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

    fm_lines = ["---", "capn: 1", f"id: {entry_id}", f"at: {now}",
                f"est_tokens: {work_cost}"]
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
    _log({"type": "chart", "entry_id": entry_id, "question": question,
          "session": _current_session()})

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


def _report_due(count: int) -> bool:
    if count == REPORT_FIRST:
        return True
    if count > REPORT_FIRST and (count - REPORT_FIRST) % REPORT_EVERY == 0:
        return True
    return False


def _last_session_summary() -> str:
    """Return a one-line summary of the most recently completed session, or ''."""
    if not LOG_FILE.exists():
        return ''
    records = []
    try:
        with LOG_FILE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        return ''

    # Walk backwards to find the last *completed* session (one with ask/chart events).
    sessions: dict[str, dict] = {}
    order: list[str] = []
    for r in records:
        sid = r.get("session", "")
        if not sid:
            continue
        if sid not in sessions:
            sessions[sid] = {"hits": 0, "misses": 0, "charted": 0, "date": ""}
            order.append(sid)
        if r.get("type") == "session_start":
            sessions[sid]["date"] = r.get("t", "")[:10]
        elif r.get("type") == "ask":
            if r.get("result") == "hit":
                sessions[sid]["hits"] += 1
            else:
                sessions[sid]["misses"] += 1
        elif r.get("type") == "chart":
            sessions[sid]["charted"] += 1

    # Find the most recent session that had actual activity (not just a start event).
    for sid in reversed(order):
        sd = sessions[sid]
        if sd["hits"] + sd["misses"] + sd["charted"] > 0:
            h, m, c = sd["hits"], sd["misses"], sd["charted"]
            date = sd["date"] or "?"
            parts = []
            if h + m:
                parts.append(f"{h}/{h+m} hits")
            if c:
                parts.append(f"{c} charted")
            return f"{date} session {sid[:6]}  --  {', '.join(parts)}"
    return ''


def cmd_context():
    _ensure_dirs()
    session_id = uuid.uuid4().hex[:8]
    SESSION_FILE.write_text(session_id, encoding="utf-8")
    _log({"type": "session_start", "session": session_id})

    stats = _load_stats()
    stats["session_count"] = stats.get("session_count", 0) + 1
    _save_json(STATS_FILE, stats)
    session_count = stats["session_count"]

    hits = stats.get("hits", 0)
    misses = stats.get("misses", 0)
    charted = stats.get("charted", 0)
    tokens_saved = stats.get("tokens_saved", 0)
    tokens_wasted = stats.get("tokens_wasted", 0)
    total = hits + misses
    hit_rate = f"{100 * hits // total}%" if total else "n/a"

    def _tok(n):
        return f"~{n // 1_000}K" if n >= 1_000 else f"~{n}"

    entries = _all_entries()
    fresh_count = sum(1 for _, e in entries if _entry_is_fresh(e))
    stale_count = len(entries) - fresh_count

    stale_line = f"  stale:  {stale_count} entries need pruning  (run: capn prune)" if stale_count else ""
    last_line = _last_session_summary()

    status_lines = [
        f"=== CAP'N HOOK: trap registry + lookup cache ===",
        f"  cache:  {fresh_count} fresh entries  |  {charted} ever charted",
        f"  stats:  {hits}/{total} hits ({hit_rate})  |  saved {_tok(tokens_saved)}  |  wasted {_tok(tokens_wasted)} on misses",
    ]
    if stale_line:
        status_lines.append(stale_line)
    if last_line:
        status_lines.append(f"  last:   {last_line}")

    print('\n'.join(status_lines))
    print("""
Hooks auto-fire on Bash/Read. To ask manually or chart a discovery:
  python scripts/capn.py ask "<what you're about to do>"
  python scripts/capn.py chart "<what you found>" --files path1 [--details "specifics"]""")

    if _report_due(session_count):
        next_due = REPORT_FIRST + ((session_count - REPORT_FIRST) // REPORT_EVERY + 1) * REPORT_EVERY if session_count >= REPORT_FIRST else REPORT_FIRST
        print(f"""
*** CAPN REPORT DUE (session {session_count}) ***
Run before starting work this session:
  python scripts/capn.py report
Next auto-notice at session {next_due if session_count > REPORT_FIRST else REPORT_FIRST + REPORT_EVERY}.
""")


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


def cmd_report(sessions: int = 10):
    if not LOG_FILE.exists():
        print("No log yet. Run some queries first.")
        return

    records = []
    with LOG_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

    # Group by session
    sessions_data: dict[str, dict] = {}
    session_order: list[str] = []
    current = None
    for r in records:
        sid = r.get("session", "untracked")
        if r.get("type") == "session_start":
            current = sid
            if sid not in sessions_data:
                session_order.append(sid)
                sessions_data[sid] = {
                    "started": r.get("t", "?"),
                    "hits": 0, "misses": 0,
                    "saved": 0, "wasted": 0,
                    "queries": [], "charted": 0,
                }
        elif current and r.get("type") == "ask":
            sd = sessions_data.setdefault(sid, {"started": r.get("t", "?"), "hits": 0,
                                                 "misses": 0, "saved": 0, "wasted": 0,
                                                 "queries": [], "charted": 0})
            if r.get("result") == "hit":
                sd["hits"] += 1
                sd["saved"] += r.get("tokens_saved", 0)
            else:
                sd["misses"] += 1
                sd["wasted"] += r.get("tokens_wasted_est", 0)
            sd["queries"].append({"q": r.get("query", ""), "result": r.get("result", "?")})
        elif current and r.get("type") == "chart":
            sessions_data.get(sid, {})  # ensure exists
            sessions_data.setdefault(sid, {}).get("charted", 0)
            if sid in sessions_data:
                sessions_data[sid]["charted"] = sessions_data[sid].get("charted", 0) + 1

    recent = session_order[-sessions:]
    print(f"=== CAP'N HOOK SESSION REPORT (last {len(recent)} sessions) ===\n")

    total_saved = total_wasted = total_hits = total_misses = 0
    for sid in recent:
        sd = sessions_data[sid]
        hits, misses = sd["hits"], sd["misses"]
        saved, wasted = sd["saved"], sd["wasted"]
        total = hits + misses
        rate = f"{100 * hits // total}%" if total else "n/a"
        date = sd["started"][:10] if len(sd["started"]) >= 10 else sd["started"]
        print(f"  [{date}] session {sid}")
        print(f"    hits={hits} misses={misses} rate={rate} | "
              f"saved=~{saved} wasted=~{wasted} | charted={sd.get('charted', 0)}")
        misses_list = [q["q"] for q in sd["queries"] if q["result"] == "miss"]
        if misses_list:
            print(f"    missed queries:")
            for q in misses_list:
                print(f"      - {q}")
        total_saved += saved
        total_wasted += wasted
        total_hits += hits
        total_misses += misses
        print()

    grand_total = total_hits + total_misses
    grand_rate = f"{100 * total_hits // grand_total}%" if grand_total else "n/a"
    print(f"  TOTALS ({len(recent)} sessions): hits={total_hits} misses={total_misses} "
          f"rate={grand_rate} | saved=~{total_saved} wasted=~{total_wasted}")
    net = total_saved - total_wasted
    sign = "+" if net >= 0 else ""
    print(f"  NET: {sign}{net} tokens ({'+' if net >= 0 else ''}{'ahead' if net >= 0 else 'behind'})")


def cmd_savings(as_json: bool = False):
    """Aggregate saved/wasted tokens by day, week, and month."""
    from collections import defaultdict

    if not LOG_FILE.exists():
        print("No log yet.")
        return

    records = []
    with LOG_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

    asks = [r for r in records if r.get("type") == "ask" and "t" in r]

    def week_of(date_str: str) -> str:
        from datetime import datetime, timedelta
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

    def make_bucket():
        return {"saved": 0, "wasted": 0, "hits": 0, "misses": 0}

    by_day: dict = defaultdict(make_bucket)
    by_week: dict = defaultdict(make_bucket)
    by_month: dict = defaultdict(make_bucket)

    for r in asks:
        day = r["t"][:10]
        buckets = [by_day[day], by_week[week_of(day)], by_month[day[:7]]]
        if r.get("result") == "hit":
            for b in buckets:
                b["saved"] += r.get("tokens_saved", 0)
                b["hits"] += 1
        else:
            for b in buckets:
                b["wasted"] += r.get("tokens_wasted_est", 0)
                b["misses"] += 1

    if as_json:
        from datetime import datetime

        def to_rows(d: dict, label_fn) -> list:
            rows = []
            cum_s = cum_w = 0
            for k in sorted(d):
                b = d[k]
                cum_s += b["saved"]
                cum_w += b["wasted"]
                rows.append({
                    "period": k,
                    "label": label_fn(k),
                    "saved": b["saved"],
                    "wasted": b["wasted"],
                    "hits": b["hits"],
                    "misses": b["misses"],
                    "cum_saved": cum_s,
                    "cum_wasted": cum_w,
                })
            return rows

        def day_label(k):
            from datetime import datetime
            return datetime.strptime(k, "%Y-%m-%d").strftime("%b %-d")

        def week_label(k):
            from datetime import datetime
            return datetime.strptime(k, "%Y-%m-%d").strftime("%-d %b")

        def month_label(k):
            from datetime import datetime
            return datetime.strptime(k + "-01", "%Y-%m-%d").strftime("%b %Y")

        total_s = sum(b["saved"] for b in by_day.values())
        total_w = sum(b["wasted"] for b in by_day.values())
        total_h = sum(b["hits"] for b in by_day.values())
        total_m = sum(b["misses"] for b in by_day.values())
        out = {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "totals": {"saved": total_s, "wasted": total_w, "hits": total_h, "misses": total_m},
            "day": to_rows(by_day, day_label),
            "week": to_rows(by_week, week_label),
            "month": to_rows(by_month, month_label),
        }
        print(json.dumps(out, indent=2))
        return

    def print_table(title, d: dict):
        print(f"\n{title}")
        print(f"  {'Period':<13} {'Saved':>7} {'Wasted':>8} {'Net':>8} {'Hits':>5} {'Misses':>7}")
        print("  " + "-" * 52)
        cum_s = cum_w = 0
        for k in sorted(d):
            b = d[k]
            cum_s += b["saved"]
            cum_w += b["wasted"]
            net = b["saved"] - b["wasted"]
            sign = "+" if net >= 0 else ""
            print(f"  {k:<13} {b['saved']:>7,} {b['wasted']:>8,} {sign}{net:>7,} {b['hits']:>5} {b['misses']:>7}")
        print("  " + "-" * 52)
        net_tot = cum_s - cum_w
        sign = "+" if net_tot >= 0 else ""
        print(f"  {'TOTAL':<13} {cum_s:>7,} {cum_w:>8,} {sign}{net_tot:>7,}")

    print("=== CAP'N HOOK — SAVINGS REPORT ===")
    print_table("BY DAY", by_day)
    print_table("BY WEEK (Mon)", by_week)
    print_table("BY MONTH", by_month)


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
    p_chart.add_argument("--work-cost", type=int, default=500,
                         help="Estimated tokens saved by hitting this cache entry (default 500)")

    sub.add_parser("prune", help="Remove entries whose files have changed")
    sub.add_parser("context", help="Print session-start instructions + stats")
    sub.add_parser("list", help="List all entries with freshness status")
    p_report = sub.add_parser("report", help="Per-session token saved/wasted summary")
    p_report.add_argument("--sessions", type=int, default=10,
                          help="Number of recent sessions to show (default 10)")
    p_savings = sub.add_parser("savings", help="Savings aggregated by day/week/month")
    p_savings.add_argument("--json", action="store_true", help="Output JSON for chart embedding")

    args = ap.parse_args()
    if args.cmd == "ask":
        cmd_ask(args.question, args.threshold)
    elif args.cmd == "chart":
        cmd_chart(args.question, args.files, args.details, args.work_cost)
    elif args.cmd == "prune":
        cmd_prune()
    elif args.cmd == "context":
        cmd_context()
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "report":
        cmd_report(args.sessions)
    elif args.cmd == "savings":
        cmd_savings(as_json=args.json)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
