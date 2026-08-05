# determined/agent/export_context.py
#
# export_context — clipboard-ready context packet for external LLM escalation.
#
# Assembles a plain-text packet for a stub when the local LLM ceiling is
# exceeded, or on explicit user request. Designed for paste into Tier 2
# (web LLM) or Tier 3 (Claude) escalation paths.
#
# Output sections:
#   1. Function under analysis — signature, intent, classification, return shape
#   2. Neighbor context — caller bodies, pattern siblings, available type APIs
#   3. Complexity score — which signals drove escalation (visible reasoning)
#   4. Tool API manifest — what Determined can answer if asked
#
# Session accumulator (RM71):
#   export_context(symbol)            — initial packet; starts/resets session
#   export_context_append(symbol, ...) — run a follow-up tool, store + return chunk
#   export_context_dump(symbol)       — recoalesce: initial + all chunks (new LLM handoff)
#
# Each session entry carries source: "determined" (tool dispatched internally)
# or "user_supplied" (freetext pasted by user or external LLM response text).
# Future back-channel source: "back_channel" (RM77).
#
# SOTS XIII: complexity score and driving signals are always shown.
# SOTS XI:  complexity is deterministic; no LLM needed to decide tier.

from __future__ import annotations

import dataclasses
import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor


# ---------------------------------------------------------------------------
# Session accumulator
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class _SessionEntry:
    source: str          # "determined" | "user_supplied" | "back_channel"
    tool: str            # tool name if source=="determined", else ""
    args: dict           # tool args if source=="determined", else {}
    chunk: str           # formatted output
    timestamp: str       # ISO8601


@dataclasses.dataclass
class _ExportSession:
    symbol: str
    initial_packet: str
    entries: list[_SessionEntry] = dataclasses.field(default_factory=list)


# Keyed by (db_path, symbol). Resets when export_context() is called again.
_sessions: dict[tuple[str, str], _ExportSession] = {}


def _session_key(oracle: "DBOracle", symbol: str) -> tuple[str, str]:
    """Return (db_path, symbol) tuple used as the key into _sessions."""
    return (getattr(oracle, "db_path", ""), symbol)


def _get_session(oracle: "DBOracle", symbol: str) -> _ExportSession | None:
    """Return the active export session for symbol, or None if none started."""
    return _sessions.get(_session_key(oracle, symbol))


# ---------------------------------------------------------------------------
# Complexity signal
# ---------------------------------------------------------------------------

# Provisional threshold — calibrated 2026-07-29 (post RM70 Step 2 JOIN fix).
# dj2 25 stubs: range 0.342–0.500, mean 0.366. Only _get_combat_context hits
# 0.500 (caller_complexity=0.633 from 19-line callers). FSM stubs cluster at
# 0.351 (no callers in graph_edges — correct for config-declared stubs).
# type_missing=1.000 for all dj2 stubs: CamelCase words in docstrings match
# the regex but aren't corpus classes — signal is noisy on this corpus.
# Threshold 0.5 holds; may need tuning on corpora with richer type signatures.
_COMPLEXITY_THRESHOLD = 0.5


def _complexity_score(brief: dict, oracle: "DBOracle") -> tuple[float, dict[str, float]]:
    """
    Compute a complexity score (0.0–1.0) from corpus facts.
    Returns (score, signals_dict) where signals_dict shows each component.

    Signals and weights (high = 0.25, medium = 0.167):
      caller_complexity   high   avg caller body length, normalised to 30 lines
      low_confidence      high   1 - classify_stub score
      unresolved_ratio    med    fraction of neighborhood edges unresolved
      type_missing        med    1 - fraction of type names resolved in DB
      sibling_missing     med    1 if no pattern sibling found
    """
    callers = brief.get("callers", [])
    if callers:
        avg_lines = sum(
            len(c["body"].splitlines()) for c in callers if c.get("body")
        ) / len(callers)
    else:
        avg_lines = 0.0
    caller_complexity = min(avg_lines / 30.0, 1.0)

    low_confidence = 1.0 - min(brief.get("score", 0.0), 1.0)

    # Unresolved edge ratio for the symbol's neighborhood
    conn = oracle.conn
    symbol = brief.get("symbol", "")
    total = conn.execute(
        "SELECT count(*) FROM graph_edges "
        "WHERE caller = ? OR callee = ? OR callee LIKE ?",
        (symbol, symbol, f"%.{symbol}"),
    ).fetchone()[0]
    resolved = conn.execute(
        "SELECT count(*) FROM graph_edges "
        "WHERE resolved = 1 AND (caller = ? OR callee = ? OR callee LIKE ?)",
        (symbol, symbol, f"%.{symbol}"),
    ).fetchone()[0]
    unresolved_ratio = (1.0 - resolved / total) if total > 0 else 0.5

    # Type names mentioned vs resolved in DB
    type_defs = brief.get("type_defs", [])
    from determined.agent.sketch_stub import _extract_type_names
    sig = brief.get("signature", "")
    intent = brief.get("intent_text") or ""
    type_names = _extract_type_names(sig, intent)
    if type_names:
        type_missing = 1.0 - min(len(type_defs) / len(type_names), 1.0)
    else:
        type_missing = 0.0

    sibling_missing = 0.0 if brief.get("siblings") else 1.0

    signals = {
        "caller_complexity": round(caller_complexity, 3),
        "low_confidence":    round(low_confidence, 3),
        "unresolved_ratio":  round(unresolved_ratio, 3),
        "type_missing":      round(type_missing, 3),
        "sibling_missing":   sibling_missing,
    }

    score = (
        caller_complexity * 0.25
        + low_confidence  * 0.25
        + unresolved_ratio * 0.167
        + type_missing     * 0.167
        + sibling_missing  * 0.167
    )
    return round(min(score, 1.0), 3), signals


def _tier_label(score: float) -> str:
    """Map complexity score to a human-readable escalation tier recommendation."""
    if score >= _COMPLEXITY_THRESHOLD:
        return "TIER 2 (web LLM recommended — paste this packet)"
    return "TIER 1 (local LLM; escalate if output quality is low)"


# ---------------------------------------------------------------------------
# Tool API manifest (grounded — pre-fills symbol from brief)
# ---------------------------------------------------------------------------

_BACKCHANNEL_PROTOCOL = """\
== REQUEST PROTOCOL ==
To request additional context, emit a line in exactly this format:
  DETERMINE: tool_name(arg="value", ...)
The user will run this in Determined and paste the result back.
When a back-channel is available, these commands will be executed automatically.
Emit one request per line. Chain requests only after receiving the previous result."""


def _build_manifest(brief: dict) -> str:
    """Build a grounded tool manifest with pre-filled symbol arguments."""
    sym = brief.get("symbol", "SYMBOL")
    callers = brief.get("callers", [])
    # Pick a representative caller for find_call_chain example
    caller_example = callers[0]["name"] if callers else "CALLER"

    lines = [
        _BACKCHANNEL_PROTOCOL,
        "",
        "Available tools (ready-to-run commands for this symbol):",
        "",
        f'  DETERMINE: classify_stub(symbol="{sym}")',
        f'      Why does this stub exist? Ranked hypotheses with evidence.',
        "",
        f'  DETERMINE: sketch_stub(symbol="{sym}")',
        f'      Generate a candidate implementation from corpus patterns.',
        f'      Use mode="thorough" for K=3 ranked samples.',
        "",
        f'  DETERMINE: blast_radius(symbol="{sym}")',
        f'      What breaks if this function is changed or left unimplemented?',
        "",
        f'  DETERMINE: symbol_context(symbol="{sym}")',
        f'      Full caller/callee list, declaration, design frame.',
        "",
        f'  DETERMINE: find_call_chain(from_symbol="{caller_example}", to_symbol="{sym}")',
        f'      Trace the execution path from a caller to this stub.',
        "",
        f'  DETERMINE: stub_prerequisite_map(symbol="{sym}")',
        f'      What must exist before this stub can be implemented?',
        "",
        f'  DETERMINE: explore_stub(symbol="{sym}")',
        f'      Deep dive: callers, callees, sibling patterns, concept presence.',
        "",
        f'  DETERMINE: export_context_append(symbol="{sym}", tool="TOOL", tool_args={{...}})',
        f'      Add any of the above results to the running session.',
        "",
        f'  DETERMINE: export_context_dump(symbol="{sym}")',
        f'      Recoalesce full session — use when handing off to a new LLM.',
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Packet assembly
# ---------------------------------------------------------------------------

_CALLER_DISPLAY_CAP = 15   # lines of caller body shown in packet
_SIBLING_DISPLAY_CAP = 20  # lines of sibling body shown in packet


def _section(title: str, lines: list[str]) -> str:
    """Wrap lines in a titled section with a double-bar header."""
    bar = "=" * (len(title) + 4)
    return bar + "\n" + f"== {title} ==\n" + bar + "\n" + "\n".join(lines)


def _build_packet(brief: dict, oracle: "DBOracle") -> str:
    """Assemble the four-section clipboard packet."""
    symbol = brief["symbol"]
    score, signals = _complexity_score(brief, oracle)
    tier = _tier_label(score)

    # ── Section 1: Function under analysis ──────────────────────────────
    s1: list[str] = [f"Symbol:         {symbol}"]
    s1.append(f"File:           {brief.get('file', '?')}:{brief.get('line_number', '?')}")
    s1.append(f"Signature:      {brief.get('signature', '?')}")
    if brief.get("intent_text"):
        s1.append(f"Intent:         {brief['intent_text'][:200]}")
    s1.append(f"Classification: {brief['classification']} [{brief['score']:.2f}]")
    if brief.get("return_type"):
        s1.append(f"Return type:    {brief['return_type']}")
    rs = brief.get("return_shape", {})
    if rs.get("confidence") != "NONE" and rs.get("hints"):
        conf = rs["confidence"].lower()
        hints = ", ".join(rs["hints"])
        s1.append(f"Return shape:   {hints}  ({conf} confidence)")

    # ── Section 2: Neighbor context ──────────────────────────────────────
    s2: list[str] = []

    callers = brief.get("callers", [])
    if callers:
        s2.append(f"Callers ({len(callers)}):")
        for c in callers:
            s2.append(f"\n  {c['name']} ({c['file']}):")
            if c.get("body"):
                for line in c["body"].splitlines()[:_CALLER_DISPLAY_CAP]:
                    s2.append(f"    {line}")
                if len(c["body"].splitlines()) > _CALLER_DISPLAY_CAP:
                    s2.append("    ...")
    else:
        s2.append("Callers: none found in corpus")

    siblings = brief.get("siblings", [])
    if siblings:
        s2.append(f"\nPattern siblings ({len(siblings)}):")
        for sib in siblings:
            sim = f"  similarity={sib.get('similarity', '?')}" if sib.get("similarity") else ""
            s2.append(f"\n  {sib['name']} ({sib['file']}){sim}:")
            if sib.get("body_preview"):
                for line in sib["body_preview"].splitlines()[:_SIBLING_DISPLAY_CAP]:
                    s2.append(f"    {line}")
                if len(sib["body_preview"].splitlines()) > _SIBLING_DISPLAY_CAP:
                    s2.append("    ...")
    else:
        s2.append("\nPattern siblings: none found")

    type_defs = brief.get("type_defs", [])
    if type_defs:
        s2.append("\nAvailable type APIs:")
        for td in type_defs:
            s2.append(f"\n  {td['class_name']} ({td['file']}):")
            if td.get("init_sig"):
                s2.append(f"    {td['init_sig']}")
            for m in td.get("methods", []):
                s2.append(f"    {m['sig']}")

    # ── Section 3: Complexity score ──────────────────────────────────────
    s3: list[str] = [f"Score:  {score:.3f}  →  {tier}"]
    s3.append(f"(threshold: {_COMPLEXITY_THRESHOLD}, provisional)")
    s3.append("")
    callers = brief.get("callers", [])
    avg_lines = (
        sum(len(c["body"].splitlines()) for c in callers if c.get("body")) / len(callers)
        if callers else 0
    )
    s3.append(f"  caller_complexity:  {signals['caller_complexity']:.3f}  (avg {avg_lines:.0f} lines, {len(callers)} caller(s))")
    s3.append(f"  low_confidence:     {signals['low_confidence']:.3f}  (classify score {brief['score']:.2f})")
    s3.append(f"  unresolved_ratio:   {signals['unresolved_ratio']:.3f}  (edge resolution in neighborhood)")
    s3.append(f"  type_missing:       {signals['type_missing']:.3f}  ({len(type_defs)} type(s) resolved in DB)")
    s3.append(f"  sibling_missing:    {signals['sibling_missing']:.3f}  ({'no pattern sibling' if not siblings else 'sibling found'})")

    # ── Section 4: Tool API manifest ────────────────────────────────────
    s4: list[str] = [_build_manifest(brief)]

    divider = "\n" + ("─" * 60) + "\n"
    return divider.join([
        _section("FUNCTION UNDER ANALYSIS", s1),
        _section("NEIGHBOR CONTEXT", s2),
        _section("COMPLEXITY SCORE", s3),
        _section("TOOL API MANIFEST", s4),
    ])


# ---------------------------------------------------------------------------
# Tool entry point
# ---------------------------------------------------------------------------

def export_context(assessor: "Assessor", args: dict) -> str:
    """
    export_context(symbol) — assemble a clipboard-ready context packet for
    external LLM escalation (Tier 2: web LLM, Tier 3: Claude).

    Always produces the packet. Complexity score advises which tier is
    appropriate, but the packet is useful regardless.

    Args:
        symbol:     function name (required)
        class_name: disambiguate lifecycle methods (optional)
        file_path:  disambiguate when name appears in multiple files (optional)
    """
    from determined.agent.sketch_stub import build_brief

    oracle = assessor.oracle
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    class_name = args.get("class_name", "").strip() or None
    file_path  = args.get("file_path",  "").strip() or None

    brief = build_brief(oracle, symbol, class_name=class_name,
                        file_path_hint=file_path)
    if "error" in brief:
        return f"export_context: {brief['error']}"
    if not brief.get("actionable"):
        return (
            f"export_context: {symbol}\n"
            f"  Not actionable ({brief['classification']} [{brief['score']:.2f}]).\n"
            f"  {brief.get('reason', '')}\n"
            f"  Packet not generated — classify_stub verdict is not "
            f"design-intent-stated or blocked-on-prerequisite."
        )

    packet = _build_packet(brief, oracle)

    # Start (or reset) the session for this symbol.
    key = _session_key(oracle, symbol)
    _sessions[key] = _ExportSession(symbol=symbol, initial_packet=packet)

    return packet


# ---------------------------------------------------------------------------
# Session accumulator entry points
# ---------------------------------------------------------------------------

def export_context_append(assessor: "Assessor", args: dict) -> str:
    """
    export_context_append — run a follow-up tool and add its output to the
    active export session for a symbol.

    Two modes:
      (a) tool dispatch — Determined runs the tool and stores the result:
            symbol, tool, args (dict of tool arguments)
      (b) user-supplied text — store freetext (LLM response, manual note):
            symbol, content, source (optional, default "user_supplied")

    Returns the new chunk only (differential). Use export_context_dump to
    get the full accumulated session.
    """
    from determined.agent.agent_tools import TOOLS

    oracle = assessor.oracle
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"

    session = _get_session(oracle, symbol)
    if session is None:
        return (
            f"ERROR: no active export session for '{symbol}'. "
            f"Call export_context(symbol='{symbol}') first."
        )

    now = datetime.datetime.now().isoformat(timespec="seconds")

    # Mode (b): user-supplied freetext
    content = args.get("content", "").strip()
    if content:
        source = args.get("source", "user_supplied")
        chunk = _section(
            f"USER-SUPPLIED CONTEXT ({now})",
            [f"[source: {source}]", "", content],
        )
        session.entries.append(_SessionEntry(
            source=source, tool="", args={}, chunk=chunk, timestamp=now
        ))
        return chunk

    # Mode (a): dispatch a Determined tool
    tool_name = args.get("tool", "").strip()
    if not tool_name:
        return "ERROR: provide 'tool' (tool name) or 'content' (freetext)"
    if tool_name not in TOOLS:
        return f"ERROR: unknown tool '{tool_name}'. Check export_context_dump for manifest."

    tool_args = args.get("tool_args", {})
    if not isinstance(tool_args, dict):
        return "ERROR: tool_args must be a dict"

    fn, tool_tier = TOOLS[tool_name]
    # Tools are (fn, tier_string). Assessor is always passed as first arg.
    raw = fn(assessor, tool_args)

    chunk = _section(
        f"FOLLOW-UP: {tool_name}({_fmt_args(tool_args)})  [{now}]",
        [raw] if isinstance(raw, str) else [str(raw)],
    )
    session.entries.append(_SessionEntry(
        source="determined", tool=tool_name, args=tool_args,
        chunk=chunk, timestamp=now,
    ))
    return chunk


def export_context_dump(assessor: "Assessor", args: dict) -> str:
    """
    export_context_dump — recoalesce the full session for a symbol.

    Returns: initial packet + all accumulated chunks, with a session log
    header listing every tool call that built the session. Use this to hand
    off full context to a new external LLM session.

    Args:
        symbol: function name (required)
    """
    oracle = assessor.oracle
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"

    session = _get_session(oracle, symbol)
    if session is None:
        return (
            f"ERROR: no active export session for '{symbol}'. "
            f"Call export_context(symbol='{symbol}') first."
        )

    divider = "\n" + ("─" * 60) + "\n"

    # Session log header
    if session.entries:
        log_lines = [f"Session for: {symbol}", f"Steps: {len(session.entries)}"]
        for i, e in enumerate(session.entries, 1):
            if e.source == "determined":
                log_lines.append(f"  {i}. {e.tool}({_fmt_args(e.args)})  [{e.timestamp}]")
            else:
                log_lines.append(f"  {i}. [user_supplied]  [{e.timestamp}]")
        header = _section("SESSION LOG", log_lines)
    else:
        header = _section("SESSION LOG", [f"Session for: {symbol}", "No follow-up steps yet."])

    parts = [header, session.initial_packet] + [e.chunk for e in session.entries]
    return divider.join(parts)


def _fmt_args(args: dict) -> str:
    """Format a tool-args dict as a compact 'k=v, ...' string for display."""
    return ", ".join(f"{k}={v!r}" for k, v in args.items()) if args else ""
