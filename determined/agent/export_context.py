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
# SOTS XIII: complexity score and driving signals are always shown.
# SOTS XI:  complexity is deterministic; no LLM needed to decide tier.

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor


# ---------------------------------------------------------------------------
# Complexity signal
# ---------------------------------------------------------------------------

# Provisional threshold — calibrate after RM70 Step 2 (caller body reader).
# RM71 baseline (2026-07-29, dj2 25 stubs): all real gaps score 0.24-0.48;
# only 1 test mock crosses 0.5. caller_complexity=0 for all (LEFT JOIN name
# mismatch in graph_edges vs functions table — fixed by RM70 Step 2).
# Recalibrate once caller bodies are read correctly; threshold will likely
# need to move up since caller_complexity carries 0.25 weight.
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
    if score >= _COMPLEXITY_THRESHOLD:
        return "TIER 2 (web LLM recommended — paste this packet)"
    return "TIER 1 (local LLM; escalate if output quality is low)"


# ---------------------------------------------------------------------------
# Tool API manifest
# ---------------------------------------------------------------------------

_TOOL_MANIFEST = """\
If the external LLM needs more context, ask Determined with these tools:

  classify_stub(symbol=X)
      Why does this stub exist? Ranked hypotheses with evidence.

  sketch_stub(symbol=X)
      Generate a candidate implementation (local LLM + corpus context).
      Use mode=thorough for K=3 ranked samples.

  blast_radius(symbol=X)
      What breaks if this function is changed or implemented incorrectly?

  symbol_context(symbol=X)
      Full caller/callee list, declaration, design frame for any symbol.

  find_call_chain(from_symbol=X, to_symbol=Y)
      Trace the execution path between two symbols.

  list_stubs()
      All stubs in the active corpus, ranked by caller count.

  stub_prerequisite_map(symbol=X)
      What must exist before this stub can be implemented?

  explore_stub(symbol=X)
      Deep dive: callers, callees, sibling patterns, concept presence.

To run a tool: call it via the Workbench tab in Determined, or via Python:
  from determined.agent.agent_tools import <tool>; <tool>(assessor, {args})"""


# ---------------------------------------------------------------------------
# Packet assembly
# ---------------------------------------------------------------------------

_CALLER_DISPLAY_CAP = 15   # lines of caller body shown in packet
_SIBLING_DISPLAY_CAP = 20  # lines of sibling body shown in packet


def _section(title: str, lines: list[str]) -> str:
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
    s4: list[str] = [_TOOL_MANIFEST]

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

    return _build_packet(brief, oracle)
