# tools/analysis/agent/task_rereferencer.py
#
# Re-reference path for task.md (TRACKER item 10 step 2, 2026-06-19).
#
# Workflow:
#   1. Read an existing task.md
#   2. Extract the originating symbol from the header line
#   3. Re-run generate_task_md for that symbol against the current DB
#   4. Diff old vs new: additions/removals in both tiers
#   5. Return a diff report (as dict and/or Markdown)
#
# The diff is a "what changed" signal, not a full re-render. The caller
# decides whether to overwrite the old task.md or keep both for review.

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from determined.agent.task_generator import (
    generate_task_md,
    _direct_callers,
    _impact_zone,
)


# =========================================================
# SYMBOL EXTRACTION
# =========================================================

_HEADER_RE = re.compile(r"^# task: review impact of changes to `(.+?)`", re.MULTILINE)


def extract_symbol(task_md_content: str) -> Optional[str]:
    """
    Pull the originating symbol out of a task.md string.
    Returns None if the header is missing or malformed.
    """
    m = _HEADER_RE.search(task_md_content)
    return m.group(1) if m else None


# =========================================================
# DIRECT-CALLER SET EXTRACTION FROM EXISTING TASK.MD
# =========================================================

_CALLER_RE = re.compile(r"^- \[[ x]\] `(.+?)` at `", re.MULTILINE)
_IMPACT_RE = re.compile(r"^- \[[ x]\] `(.+?)`\s*$", re.MULTILINE)
_DIRECT_SECTION_RE = re.compile(
    r"## Direct callers.*?\n(.*?)## Impact zone",
    re.DOTALL,
)
_IMPACT_SECTION_RE = re.compile(
    r"## Impact zone.*?\n(.*?)(?:^---|\Z)",
    re.DOTALL | re.MULTILINE,
)


def _parse_direct_callers(content: str) -> set[str]:
    m = _DIRECT_SECTION_RE.search(content)
    if not m:
        return set()
    return set(_CALLER_RE.findall(m.group(1)))


def _parse_impact_zone(content: str) -> set[str]:
    m = _IMPACT_SECTION_RE.search(content)
    if not m:
        return set()
    return set(_IMPACT_RE.findall(m.group(1)))


# =========================================================
# DIFF
# =========================================================

def diff_task_md(
    old_content: str,
    symbol: str,
    oracle,
) -> dict:
    """
    Compare old task.md content against a fresh query for `symbol`.

    Returns a dict:
      {
        "symbol": str,
        "direct_callers": {"added": [...], "removed": [...]},
        "impact_zone":    {"added": [...], "removed": [...]},
        "unchanged": bool,   # True if both tiers are identical
      }
    """
    old_direct = _parse_direct_callers(old_content)
    old_impact = _parse_impact_zone(old_content)

    new_direct_rows = _direct_callers(oracle.conn, symbol)
    new_direct = {r["caller"] for r in new_direct_rows}

    new_impact_list = _impact_zone(symbol, oracle)
    # Exclude direct callers from impact zone (mirrors generate_task_md)
    new_impact = set(new_impact_list) - new_direct - {symbol}

    return {
        "symbol": symbol,
        "direct_callers": {
            "added":   sorted(new_direct - old_direct),
            "removed": sorted(old_direct - new_direct),
        },
        "impact_zone": {
            "added":   sorted(new_impact - old_impact),
            "removed": sorted(old_impact - new_impact),
        },
        "unchanged": (new_direct == old_direct and new_impact == old_impact),
    }


# =========================================================
# RENDER DIFF AS MARKDOWN
# =========================================================

def render_diff_md(diff: dict) -> str:
    symbol = diff["symbol"]
    today = date.today().isoformat()
    lines = [
        f"# task re-reference: `{symbol}`",
        f"Re-run {today}. Comparing stored task.md against current DB.",
        "",
    ]

    if diff["unchanged"]:
        lines += [
            "**No changes.** Both tiers match the stored task.md.",
            "",
            "The stored task.md is still current - no update needed.",
        ]
        return "\n".join(lines) + "\n"

    lines += ["## Direct callers", ""]
    dc = diff["direct_callers"]
    if dc["added"]:
        lines.append("**New callers (added since last run):**")
        for s in dc["added"]:
            lines.append(f"- [ ] `{s}`  _(new - add to task checklist)_")
        lines.append("")
    if dc["removed"]:
        lines.append("**Callers no longer present (removed since last run):**")
        for s in dc["removed"]:
            lines.append(f"- ~~`{s}`~~  _(no longer calls `{symbol}` - remove from checklist)_")
        lines.append("")
    if not dc["added"] and not dc["removed"]:
        lines += ["_(unchanged)_", ""]

    lines += ["## Impact zone", ""]
    iz = diff["impact_zone"]
    if iz["added"]:
        lines.append("**New in impact zone:**")
        for s in iz["added"]:
            lines.append(f"- [ ] `{s}`")
        lines.append("")
    if iz["removed"]:
        lines.append("**Left impact zone:**")
        for s in iz["removed"]:
            lines.append(f"- ~~`{s}`~~")
        lines.append("")
    if not iz["added"] and not iz["removed"]:
        lines += ["_(unchanged)_", ""]

    lines += [
        "---",
        "",
        "Re-run `Assessor.rereference_task_md(path)` after applying changes",
        "to confirm the impact zone has contracted as expected.",
    ]

    return "\n".join(lines) + "\n"


# =========================================================
# TOP-LEVEL ENTRYPOINT
# =========================================================

def rereference_task_md(
    task_md_path: str,
    oracle,
    diff_out_path: Optional[str] = None,
) -> dict:
    """
    Read task_md_path, extract symbol, diff against current DB, return result.

    diff_out_path: if given, write the diff markdown to this path.

    Returns the diff dict (same shape as diff_task_md()).
    Also returns "diff_md" key with the rendered Markdown.
    """
    with open(task_md_path, encoding="utf-8") as f:
        old_content = f.read()

    symbol = extract_symbol(old_content)
    if symbol is None:
        raise ValueError(
            f"Could not extract symbol from {task_md_path}. "
            "Expected header: '# task: review impact of changes to `<symbol>`'"
        )

    diff = diff_task_md(old_content, symbol, oracle)
    diff["diff_md"] = render_diff_md(diff)

    if diff_out_path:
        with open(diff_out_path, "w", encoding="utf-8") as f:
            f.write(diff["diff_md"])

    return diff
