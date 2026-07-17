# determined/agent/classify_stub.py
#
# RM69 — Judgment layer: classify_stub + corpus-level projections.
#
# classify_stub(assessor, args) is the entry point.  It runs two passes:
#
#   1. extract_signals(oracle, fqdn) -> dict
#      Pure DB + source read.  No LLM.  Returns all observable signals
#      about a stub: body shape, intent language, caller/callee counts,
#      concept presence, sibling density, file character.
#
#   2. score_hypotheses(signals) -> list[dict]
#      Weights signals -> ranked competing hypotheses, each with a
#      confidence score and the evidence that drove it.
#
# Four classifications (from RM69 design):
#   concept-not-applicable  — concept absent from data layer; removed by design
#   blocked-on-prerequisite — named dependency does not exist yet
#   design-intent-stated    — comment describes behaviour; prereqs present; not done
#   genuinely-unknown       — pass/trivial, no signal, no callers
#
# SOTS XI: extract_signals is the pure decision function; score_hypotheses
# interprets; classify_stub formats and returns the plan. Three layers, clean.
#
# Language note: signal extraction is language-agnostic at the schema level.
# Body-shape extraction reads source text, so body_shape_extractor() handles
# language variants (pass / {} / todo!() / raise NotImplementedError).

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor


# ---------------------------------------------------------------------------
# Intent / removal classification — delegated to stub_classifier
# ---------------------------------------------------------------------------
# stub_classifier uses the SetFit-trained model when available and falls back
# to the hybrid embedding+modal approach when the model file is not present.

from determined.agent.stub_classifier import has_intent as _has_intent
from determined.agent.stub_classifier import has_removal as _has_removal

# Body shapes: ordered from most- to least-specific
_BODY_TRIVIAL_RETURN_RE = re.compile(
    r'^\s*return\s+(None|\[\]|\{\}|""|\'\'|0|False|True)\s*$', re.MULTILINE
)
_BODY_RAISE_NOT_IMPL_RE = re.compile(
    r'raise\s+(NotImplementedError|NotImplemented)\b'
    r'|todo!\(\)'          # Rust
    r'|throw new Error\b', # JS/TS
    re.IGNORECASE,
)

# File character thresholds
_MULTI_CLASS_MIN = 2   # >= N classes in file → multi_concept


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------

def extract_signals(oracle: "DBOracle", fqdn: str) -> dict:
    """
    Gather all observable signals about a stub from the DB and source text.
    Returns a dict with keys documented inline.  No LLM.  No side effects.
    """
    import json as _json

    conn = oracle.conn

    # ── 1. Fetch stub row ────────────────────────────────────────────────
    row = conn.execute(
        "SELECT name, file_path, line_number, docstring, param_types_json, "
        "return_type, is_stub FROM functions WHERE name = ? AND is_stub = 1 LIMIT 1",
        (fqdn,)
    ).fetchone()

    if not row:
        return {"error": f"stub '{fqdn}' not found"}

    name, file_path, line_number, docstring, ptj, return_type, is_stub = row

    # ── 2. Body shape ────────────────────────────────────────────────────
    body_shape, inline_comments = _extract_body(file_path, line_number)

    # ── 3. Intent / removal language ────────────────────────────────────
    all_text = " ".join(filter(None, [docstring, inline_comments]))
    has_intent = _has_intent(all_text)
    has_removal = _has_removal(all_text)
    intent_text = all_text.strip() or None

    # ── 4. Caller / callee counts ────────────────────────────────────────
    # Direct count queries avoid the symbol_references dependency of _list_callers_raw.
    caller_count = conn.execute(
        "SELECT COUNT(DISTINCT caller) FROM graph_edges "
        "WHERE callee = ? OR callee LIKE ?",
        (name, f"%.{name}"),
    ).fetchone()[0]
    callee_count = conn.execute(
        "SELECT COUNT(DISTINCT callee) FROM graph_edges WHERE caller = ?",
        (name,),
    ).fetchone()[0]

    # ── 5. Concept presence (corpus-wide grep via DB) ────────────────────
    from determined.agent.agent_tools import _extract_docstring_concepts, _concept_base
    concepts = _extract_docstring_concepts(all_text)
    concept_presence: dict[str, int] = {}
    for concept in concepts:
        base = _concept_base(concept)
        count = conn.execute(
            "SELECT COUNT(*) FROM functions WHERE name LIKE ? OR file_path LIKE ?",
            (f"%{base}%", f"%{base}%"),
        ).fetchone()[0]
        count += conn.execute(
            "SELECT COUNT(*) FROM classes WHERE name LIKE ? OR file_path LIKE ?",
            (f"%{base}%", f"%{base}%"),
        ).fetchone()[0]
        concept_presence[concept] = count

    # ── 6. Sibling stubs in same file ────────────────────────────────────
    sibling_rows = conn.execute(
        "SELECT name, docstring, line_number FROM functions "
        "WHERE file_path = ? AND is_stub = 1 AND name != ?",
        (file_path, name)
    ).fetchall()
    sibling_stubs = [r[0] for r in sibling_rows]
    sibling_stub_count = len(sibling_stubs)
    # Trend: fraction of siblings with removal language in their full text
    # (docstring + inline comments).  Uses the same text extraction as the
    # main stub so the algebra is consistent across the cluster.
    if sibling_stub_count > 0:
        removal_count = 0
        for sib_name, sib_doc, sib_line in sibling_rows:
            _, sib_inline = _extract_body(file_path, sib_line)
            sib_text = " ".join(filter(None, [sib_doc, sib_inline]))
            if _has_removal(sib_text):
                removal_count += 1
        sibling_removal_trend = removal_count / sibling_stub_count
    else:
        sibling_removal_trend = 0.0

    # ── 7. File character ────────────────────────────────────────────────
    file_character = _classify_file_character(conn, file_path)

    # ── 8. Docstring quality ─────────────────────────────────────────────
    doc = (docstring or "").strip()
    if not doc:
        docstring_quality = "none"
    elif _has_intent(doc):
        docstring_quality = "behavioral"
    else:
        docstring_quality = "placeholder"

    return {
        "name":               name,
        "file_path":          file_path,
        "line_number":        line_number,
        "body_shape":         body_shape,
        "inline_comments":    inline_comments or None,
        "has_intent":         has_intent,
        "has_removal":        has_removal,
        "intent_text":        intent_text,
        "caller_count":       caller_count,
        "callee_count":       callee_count,
        "concept_presence":   concept_presence,
        "sibling_stub_count":    sibling_stub_count,
        "sibling_stubs":         sibling_stubs,
        "sibling_removal_trend": sibling_removal_trend,
        "file_character":     file_character,
        "docstring_quality":  docstring_quality,
        "return_type":        return_type,
    }


def _extract_body(file_path: str | None, line_number: int | None) -> tuple[str, str]:
    """
    Read the stub's source body to determine shape and extract inline comments.
    Returns (body_shape, inline_comment_text).

    body_shape values:
      empty_pass       — only `pass` (Python) or empty braces / {} (JS/TS/Go/Rust)
      trivial_return   — returns a zero/empty value ([], {}, None, 0, False, "")
      raise_not_impl   — raises NotImplementedError / todo!() / throw new Error
      has_content      — something real is there (not a stub by body alone)
    """
    if not file_path or not line_number:
        return "unknown", ""

    try:
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return "unknown", ""

    # Collect the function body: lines after the def line until next
    # non-indented line or EOF.  Cap at 40 lines to stay cheap.
    start = line_number  # line_number is 1-based; line_number is the def line
    if start < 1 or start > len(lines):
        return "unknown", ""

    def_indent = len(lines[start - 1]) - len(lines[start - 1].lstrip())
    body_lines: list[str] = []
    comment_lines: list[str] = []

    for line in lines[start:start + 40]:
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= def_indent and stripped and not stripped.startswith('#'):
            break  # back to enclosing scope
        if stripped.startswith('#'):
            comment_lines.append(stripped.lstrip('# ').strip())
        elif stripped.startswith('"""') or stripped.startswith("'''"):
            continue  # skip docstring lines
        else:
            body_lines.append(stripped)

    inline_text = " ".join(comment_lines)
    body_text = " ".join(body_lines)

    if not body_text or body_text in ("pass", "..."):
        shape = "empty_pass"
    elif _BODY_RAISE_NOT_IMPL_RE.search(body_text):
        shape = "raise_not_impl"
    elif _BODY_TRIVIAL_RETURN_RE.search(body_text):
        shape = "trivial_return"
    else:
        shape = "has_content"

    return shape, inline_text


def _classify_file_character(conn, file_path: str | None) -> str:
    """
    Classify the file as a whole based on its symbol composition.

      single_class   — one dominant class; all/most functions are methods
      utility_bag    — many functions, few or no classes; loose collection
      multi_concept  — multiple classes; several distinct concepts in one file
      mixed          — doesn't fit cleanly into the above
    """
    if not file_path:
        return "unknown"

    fn_count = conn.execute(
        "SELECT COUNT(*) FROM functions WHERE file_path = ?", (file_path,)
    ).fetchone()[0]

    cls_rows = conn.execute(
        "SELECT name FROM classes WHERE file_path = ?", (file_path,)
    ).fetchall()
    cls_count = len(cls_rows)

    if cls_count == 0:
        return "utility_bag"
    if cls_count >= _MULTI_CLASS_MIN:
        return "multi_concept"
    # One class: check whether most functions look like methods (file is a
    # single-class module) vs a mix of top-level functions and one class.
    cls_name = cls_rows[0][0].rsplit(".", 1)[-1].lower()
    method_like = conn.execute(
        "SELECT COUNT(*) FROM functions WHERE file_path = ? AND ("
        "  name LIKE ? OR name LIKE ? OR name LIKE ?"
        ")",
        (file_path, f"{cls_name}.%", f"%.{cls_name}.%", f"__{cls_name}%"),
    ).fetchone()[0]
    if fn_count > 0 and method_like / fn_count >= 0.5:
        return "single_class"
    return "mixed"


# ---------------------------------------------------------------------------
# Hypothesis scorer
# ---------------------------------------------------------------------------

# Weights are applied additively.  Each hypothesis accumulates evidence;
# the raw score is normalised to [0, 1] at the end.
_MAX_RAW = 3.0  # rough ceiling for normalisation

def score_hypotheses(signals: dict) -> list[dict]:
    """
    Weight signals into four competing hypotheses.
    Returns list of dicts sorted by score descending, each with:
      { classification, score, evidence }
    Only hypotheses with score >= 0.2 are returned (floor filters noise).
    """
    scores: dict[str, float] = {
        "concept-not-applicable":  0.0,
        "blocked-on-prerequisite": 0.0,
        "design-intent-stated":    0.0,
        "genuinely-unknown":       0.0,
    }
    evidence: dict[str, list[str]] = {k: [] for k in scores}

    body             = signals.get("body_shape", "unknown")
    has_intent       = signals.get("has_intent", False)
    has_removal      = signals.get("has_removal", False)
    intent_text      = signals.get("intent_text") or ""
    caller_count     = signals.get("caller_count", 0)
    callee_count     = signals.get("callee_count", 0)
    concepts         = signals.get("concept_presence", {})
    sibling_count    = signals.get("sibling_stub_count", 0)
    sib_removal_trend = signals.get("sibling_removal_trend", 0.0)
    file_char        = signals.get("file_character", "unknown")
    doc_quality      = signals.get("docstring_quality", "none")

    # ── Signal: removal/obsolescence language ────────────────────────────
    # Strongest positive signal for concept-not-applicable.  Takes priority
    # over intent language if both fire (author who says "doesn't have X" wins).
    if has_removal:
        scores["concept-not-applicable"] += 1.5
        snippet = intent_text[:80].replace("\n", " ") if intent_text else ""
        evidence["concept-not-applicable"].append(f"removal language found: \"{snippet}\"")

    # ── Signal: intent language in comments/docstring ────────────────────
    # Strongest positive signal for design-intent-stated.
    # Suppressed when removal language also fires — removal is more specific.
    if has_intent and not has_removal:
        scores["design-intent-stated"] += 1.2
        snippet = intent_text[:80].replace("\n", " ") if intent_text else ""
        evidence["design-intent-stated"].append(f"intent language found: \"{snippet}\"")

    # ── Signal: concept presence ─────────────────────────────────────────
    absent  = [c for c, n in concepts.items() if n == 0]
    present = [c for c, n in concepts.items() if n > 0]

    if absent and not present:
        # All referenced concepts absent → concept-not-applicable, BUT only
        # strongly if there are also no callers.  Callers mean someone expects
        # this to work → prefer blocked-on-prerequisite in that case.
        if caller_count == 0:
            scores["concept-not-applicable"] += 1.2
        else:
            scores["concept-not-applicable"] += 0.5
            scores["blocked-on-prerequisite"] += 0.8
        evidence["concept-not-applicable"].append(
            f"referenced concept(s) absent from corpus: {', '.join(absent)}"
        )
    elif absent and present:
        # Some absent, some present → blocked-on-prerequisite
        scores["blocked-on-prerequisite"] += 1.0
        evidence["blocked-on-prerequisite"].append(
            f"concepts absent (prerequisite missing): {', '.join(absent)}"
        )
        evidence["blocked-on-prerequisite"].append(
            f"concepts present (partial foundation exists): {', '.join(present)}"
        )
    # All concepts present: mild positive for design-intent-stated
    elif present and not absent:
        scores["design-intent-stated"] += 0.3
        evidence["design-intent-stated"].append(
            f"all referenced concepts present in corpus: {', '.join(present)}"
        )

    # ── Signal: caller count ─────────────────────────────────────────────
    if caller_count == 0:
        # No callers: mild genuinely-unknown or concept-not-applicable signal
        scores["genuinely-unknown"] += 0.4
        scores["concept-not-applicable"] += 0.2
        evidence["genuinely-unknown"].append("no callers — may be dead code or early placeholder")
    else:
        # Has callers: something is waiting on this; intent is alive
        scores["design-intent-stated"] += 0.3 * min(caller_count, 3)
        scores["blocked-on-prerequisite"] += 0.2
        evidence["design-intent-stated"].append(f"{caller_count} caller(s) — slot is live")

    # ── Signal: body shape ───────────────────────────────────────────────
    if body == "empty_pass":
        # Weakest discriminator alone; combine with other signals
        scores["genuinely-unknown"] += 0.2
    elif body == "trivial_return":
        # Returns a zero value: placeholder holding a slot
        scores["design-intent-stated"] += 0.2
        scores["blocked-on-prerequisite"] += 0.3
        evidence["blocked-on-prerequisite"].append("body returns trivial zero-value (placeholder holding slot)")
    elif body == "raise_not_impl":
        # Explicit not-implemented marker: strong design-intent signal
        scores["design-intent-stated"] += 0.5
        evidence["design-intent-stated"].append("body raises NotImplementedError (explicit intent marker)")

    # ── Signal: sibling stub density (composition-aware) ─────────────────
    # A cluster of stubs is either a design skeleton (blocked-on-prerequisite)
    # or a dead-concept cluster (concept-not-applicable).  sibling_removal_trend
    # is the fraction of siblings whose docstrings contain removal language.
    if sibling_count >= 3:
        if sib_removal_trend >= 0.5:
            # Majority of siblings also carry removal language → dead-concept cluster.
            # Scale weight by trend strength: 50% trend = +0.9, 100% trend = +1.3.
            scores["concept-not-applicable"] += 0.5 + (sib_removal_trend * 0.8)
            evidence["concept-not-applicable"].append(
                f"{sibling_count} sibling stubs, {int(sib_removal_trend*100)}% with removal language — dead-concept cluster"
            )
        else:
            # Siblings trend forward-intent → design skeleton waiting on prerequisite
            scores["blocked-on-prerequisite"] += 0.4
            scores["design-intent-stated"] += 0.2
            evidence["blocked-on-prerequisite"].append(
                f"{sibling_count} sibling stubs in same file — design skeleton pattern"
            )
    elif sibling_count >= 1:
        scores["design-intent-stated"] += 0.1
        evidence["design-intent-stated"].append(
            f"{sibling_count} sibling stub(s) in same file"
        )

    # ── Signal: file character ───────────────────────────────────────────
    if file_char == "single_class":
        # Stub in a coherent single-class file: likely design-intent or blocked
        scores["design-intent-stated"] += 0.15
        scores["blocked-on-prerequisite"] += 0.1
        evidence["design-intent-stated"].append("stub lives in single-class file (coherent intent context)")
    elif file_char == "utility_bag":
        # Utility bag: stub floating loose is a weaker signal
        scores["genuinely-unknown"] += 0.15
        evidence["genuinely-unknown"].append("stub in utility-bag file (loose context)")
    elif file_char == "multi_concept":
        # Multi-concept: concept-not-applicable is more plausible here
        scores["concept-not-applicable"] += 0.1

    # ── Signal: docstring quality ────────────────────────────────────────
    if doc_quality == "placeholder":
        scores["concept-not-applicable"] += 0.2
        evidence["concept-not-applicable"].append("docstring is a placeholder label only")
    elif doc_quality == "none":
        scores["genuinely-unknown"] += 0.3
        evidence["genuinely-unknown"].append("no docstring — no stated intent")

    # ── Normalise and rank ───────────────────────────────────────────────
    results = []
    for cls, raw in scores.items():
        norm = min(raw / _MAX_RAW, 1.0)
        if norm >= 0.2:
            results.append({
                "classification": cls,
                "score":          round(norm, 2),
                "evidence":       evidence[cls],
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Tool entry point
# ---------------------------------------------------------------------------

def classify_stub(assessor: "Assessor", args: dict) -> str:
    """
    classify_stub(symbol) — judgment layer: classify why a stub exists.

    Runs deterministic signal extraction (body shape, intent language,
    caller count, concept presence, sibling density, file character) then
    scores four competing hypotheses with evidence.

    Output: ranked hypotheses with confidence scores and supporting signals.
    When top score < 0.4: returns UNCERTAIN with raw signals for human review.

    Args:
        symbol: stub function name (required)
    """
    oracle = assessor.oracle
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"

    signals = extract_signals(oracle, symbol)
    if "error" in signals:
        return f"classify_stub: {signals['error']}"

    hypotheses = score_hypotheses(signals)

    # ── Format output ────────────────────────────────────────────────────
    fp_short = (signals.get("file_path") or "").replace("\\", "/").split("/")[-1]
    line = signals.get("line_number") or "?"
    out = [
        f"classify_stub: {symbol}  ({fp_short}:{line})",
        f"file character: {signals['file_character']} | "
        f"body: {signals['body_shape']} | "
        f"callers: {signals['caller_count']} | "
        f"siblings: {signals['sibling_stub_count']}",
        "",
    ]

    if not hypotheses:
        out.append("UNCERTAIN — no signal above threshold.")
        out.append("Raw signals:")
        out.append(f"  body_shape:      {signals['body_shape']}")
        out.append(f"  has_intent:      {signals['has_intent']}")
        out.append(f"  caller_count:    {signals['caller_count']}")
        out.append(f"  concept_presence: {signals['concept_presence']}")
        return "\n".join(out)

    top = hypotheses[0]
    if top["score"] < 0.4:
        out.append("UNCERTAIN (low confidence — top score below threshold):")
    else:
        out.append("Judgment:")

    for h in hypotheses:
        bar = "█" * int(h["score"] * 10)
        out.append(f"  [{h['score']:.2f}] {bar:<10}  {h['classification']}")
        for ev in h["evidence"]:
            out.append(f"             · {ev}")

    if top["score"] < 0.4:
        out.append("")
        out.append("What would resolve it:")
        if not signals["concept_presence"]:
            out.append("  · Add docstring or comments describing the intended behaviour")
        if signals["caller_count"] == 0:
            out.append("  · Find or add a caller — zero callers suggests dead code or premature stub")

    return "\n".join(out)
