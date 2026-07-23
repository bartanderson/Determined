#!/usr/bin/env python3
"""
capn_hook.py -- Claude Code hook integration for capn trap registry.

Called by PreToolUse and PostToolUse hooks in .claude/settings.json.
Automatically consults the capn cache before relevant tool calls and
nudges charting when a miss is followed by non-trivial output.

Usage:
  python3 scripts/capn_hook.py pre   # PreToolUse
  python3 scripts/capn_hook.py post  # PostToolUse
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

CAPN_SCRIPT = Path("scripts/capn.py")
MISS_FLAG = Path(".capn/.hook_miss")

# Bash/PowerShell command patterns that indicate capn-relevant work.
# Order matters: first match wins for query derivation.
BASH_TRIGGERS = [
    r'\bSELECT\b.{0,80}\bFROM\b',                           # SQL queries
    r'\b(walk_call_chain|list_entry_points|trace_data_flow|find_symbol|classify_stub)\b',
    r'\b(reingest|re_ingest)\b',
    r'\b(db_oracle|agent_tools|language_walker|persistence_engine)\b',
    r'\b(pattern_detect|pattern_executor|local_agent)\b',
    r'\.execute\(',
    r'\bkernel_launch\b',
    r'\b(is_stub|is_tool|is_entry_point)\b',
]

# Reading these files triggers a capn lookup automatically.
READ_KEY_FILES = {
    'db_oracle.py', 'agent_tools.py', 'language_walker.py',
    'persistence_engine.py', 'pattern_detector.py', 'pattern_executor.py',
    'local_agent.py', 'graph_utils.py',
}


def _read_stdin() -> dict:
    try:
        raw = sys.stdin.buffer.read()
        return json.loads(raw)
    except Exception:
        return {}


def _run_capn_ask(query: str) -> tuple[bool, str]:
    """Run capn ask. Returns (hit, output_text)."""
    try:
        r = subprocess.run(
            [sys.executable, str(CAPN_SCRIPT), 'ask', query],
            capture_output=True, text=True, timeout=5,
            cwd=os.getcwd()
        )
        return r.returncode == 0, r.stdout.strip()
    except Exception:
        return False, ''


def _bash_query(command: str) -> str | None:
    """Derive a capn query from a bash command, or None if not relevant."""
    cmd = command[:600]
    for pat in BASH_TRIGGERS:
        if re.search(pat, cmd, re.IGNORECASE):
            q = re.sub(r'[^\w .:/_-]', ' ', cmd)
            q = re.sub(r'\s+', ' ', q).strip()[:200]
            return q
    return None


def _read_query(file_path: str) -> str | None:
    """Derive a capn query for a Read tool call, or None if not a key file."""
    name = Path(file_path).name
    if name in READ_KEY_FILES:
        # Use the file stem — _score() now searches file paths, so this will
        # surface entries whose files dict references this file.
        return name.replace('.py', '')
    return None


def _write_miss_flag(query: str):
    try:
        MISS_FLAG.parent.mkdir(parents=True, exist_ok=True)
        MISS_FLAG.write_text(query[:200], encoding='utf-8')
    except Exception:
        pass


def cmd_pre():
    data = _read_stdin()
    tool = data.get('tool_name', '')
    inp = data.get('tool_input', {})

    if tool in ('Bash', 'PowerShell'):
        query = _bash_query(inp.get('command', ''))
    elif tool == 'Read':
        query = _read_query(inp.get('file_path', ''))
    else:
        sys.exit(0)

    if not query:
        sys.exit(0)

    hit, output = _run_capn_ask(query)

    if hit:
        MISS_FLAG.unlink(missing_ok=True)
        print(f"[CAPN] Cached knowledge for this operation:\n{output}")
    else:
        _write_miss_flag(query)

    sys.exit(0)


def cmd_post():
    if not MISS_FLAG.exists():
        sys.exit(0)

    data = _read_stdin()
    tool = data.get('tool_name', '')
    if tool not in ('Bash', 'PowerShell', 'Read'):
        sys.exit(0)

    missed_query = ''
    try:
        missed_query = MISS_FLAG.read_text(encoding='utf-8').strip()
        MISS_FLAG.unlink(missing_ok=True)
    except Exception:
        pass

    # Extract response content to gauge whether anything non-trivial was returned.
    resp = data.get('tool_response', {})
    if isinstance(resp, dict):
        content = str(resp.get('content', ''))
    else:
        content = str(resp)

    if len(content.strip()) > 100:
        print(f"[CAPN] No cache entry existed for this area. If you found something non-obvious:")
        print(f"  python scripts/capn.py chart '<what you found>' --files <file> [--details '<specifics>']")

    sys.exit(0)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'pre':
        cmd_pre()
    elif mode == 'post':
        cmd_post()
    else:
        print(__doc__)
        sys.exit(1)
