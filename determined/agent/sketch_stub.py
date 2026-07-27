# determined/agent/sketch_stub.py
#
# sketch_stub — solution candidate generator for classified stubs.
#
# Works in two layers:
#   1. Deterministic brief — always runs. Pulls signature, intent, caller
#      context, and style-matching siblings from the DB and source.
#   2. LLM candidate — runs when llama-server is reachable. Sends the brief
#      to the model and asks for a function body only.
#
# Only generates candidates for stubs classified as:
#   - design-intent-stated   (intent is documented, prereqs present, not done)
#   - blocked-on-prerequisite (named dependency is missing; sketch the handler)
#   - config_declared body   (FSM action/guard; sketch the Python handler)
#
# SOTS XI: brief is the pure decision function; LLM is interpretation.
# SOTS XIII: LLM failure is visible — output marks it, never swallowed.

from __future__ import annotations

import ast
import builtins as _builtins_module
import difflib
import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BODY_CAP = 30   # max lines to read from each sibling body
_SIBLING_CAP = 3  # max siblings to include

_PYTHON_BUILTINS = frozenset(dir(_builtins_module))


def _read_function_body(file_path: str, line_number: int, cap: int = _BODY_CAP) -> str:
    """Read a function's body lines (after the def) up to cap lines."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return ""
    start = line_number  # 1-based; this is the def line
    if start < 1 or start > len(lines):
        return ""
    def_indent = len(lines[start - 1]) - len(lines[start - 1].lstrip())
    body: list[str] = []
    for line in lines[start : start + cap]:
        stripped = line.strip()
        if not stripped:
            body.append("")
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= def_indent and not stripped.startswith("#"):
            break
        body.append(line.rstrip())
    return "\n".join(body).rstrip()


def _build_signature(name: str, param_types_json: str | None, return_type: str | None) -> str:
    """Reconstruct a Python def signature from DB fields."""
    # FSM config stubs use FSM::action::name notation — not a valid Python identifier.
    # Produce a conventional Python handler name instead.
    if "::" in name:
        parts = name.split("::")
        py_name = parts[-1]  # e.g. "start_combat"
        return f"def {py_name}(self, context: dict) -> None:  # FSM handler for {name}"
    try:
        params = json.loads(param_types_json or "[]")
    except (ValueError, TypeError):
        params = []
    param_str = ", ".join(params) if params else ""
    ret = f" -> {return_type}" if return_type else ""
    return f"def {name}({param_str}){ret}:"


_CALLER_BODY_CAP = 20  # lines of caller body to include in prompt


def _caller_context(conn, name: str, file_path: str, limit: int = 3) -> list[dict]:
    """Return up to limit callers with their full source bodies."""
    rows = conn.execute(
        "SELECT DISTINCT e.caller, f.file_path, f.line_number "
        "FROM graph_edges e "
        "LEFT JOIN functions f ON f.name = e.caller "
        "WHERE e.callee = ? OR e.callee LIKE ? "
        "LIMIT ?",
        (name, f"%.{name}", limit),
    ).fetchall()
    result = []
    for caller, fp, ln in rows:
        body = _read_function_body(fp, ln, cap=_CALLER_BODY_CAP) if fp and ln else ""
        result.append({
            "name": caller,
            "file": (fp or "").replace("\\", "/").rsplit("/", 1)[-1],
            "body": body or None,
        })
    return result


def _style_siblings(conn, file_path: str, stub_name: str) -> list[dict]:
    """Return implemented sibling functions from the same file (fallback for pattern search)."""
    rows = conn.execute(
        "SELECT name, line_number FROM functions "
        "WHERE file_path = ? AND is_stub = 0 AND name != ? "
        "ORDER BY line_number LIMIT ?",
        (file_path, stub_name, _SIBLING_CAP),
    ).fetchall()
    result = []
    for sib_name, ln in rows:
        body = _read_function_body(file_path, ln) if ln else ""
        result.append({
            "name": sib_name,
            "file": file_path.replace("\\", "/").rsplit("/", 1)[-1],
            "body_preview": body[:400] if body else None,
        })
    return result


# Common verb prefixes stripped before name similarity comparison.
# Order matters: longer prefixes first to avoid partial matches.
_STRIP_PREFIXES = (
    "_get_", "_build_", "_compute_", "_create_", "_make_",
    "_fetch_", "_load_", "_run_", "_handle_", "_process_",
    "get_", "build_", "compute_", "create_", "make_",
    "fetch_", "load_", "run_", "handle_", "process_",
)

# Minimum similarity ratio to count as a real pattern match.
# Below this the normalized names share too little structure to be useful.
_PATTERN_FLOOR = 0.4


def _normalize_name(name: str) -> str:
    """Strip a leading underscore and common verb prefixes for name comparison.
    Dunder methods (__ prefix + suffix) are left as-is — they are protocol
    names, not verb-prefixed domain names."""
    if name.startswith("__") and name.endswith("__"):
        return name.lower()
    n = name.lstrip("_")
    for prefix in _STRIP_PREFIXES:
        if n.startswith(prefix):
            n = n[len(prefix):]
            break
    return n.lower()


def _pattern_siblings(conn, file_path: str, stub_name: str,
                      limit: int = _SIBLING_CAP) -> list[dict]:
    """
    Find implemented functions with similar name patterns, corpus-wide.

    Scores by difflib ratio on normalized names (verb-prefix stripped).
    Only considers is_stub=0 functions — stubs have nothing to show.
    Falls back to file-scoped _style_siblings() when no corpus match
    exceeds _PATTERN_FLOOR, so the prompt always has something to work from.
    """
    normalized_stub = _normalize_name(stub_name)

    # Load all implemented function names — names only, bodies fetched for top matches only
    rows = conn.execute(
        "SELECT name, file_path, line_number FROM functions "
        "WHERE is_stub = 0 AND name != ?",
        (stub_name,),
    ).fetchall()

    scored = []
    for name, fp, ln in rows:
        norm = _normalize_name(name)
        if not norm:
            continue
        ratio = difflib.SequenceMatcher(None, normalized_stub, norm).ratio()
        if ratio >= _PATTERN_FLOOR:
            scored.append((ratio, name, fp, ln))

    scored.sort(reverse=True)
    top = scored[:limit]

    if not top:
        return _style_siblings(conn, file_path, stub_name)

    result = []
    for ratio, name, fp, ln in top:
        body = _read_function_body(fp, ln) if fp and ln else ""
        result.append({
            "name": name,
            "file": (fp or "").replace("\\", "/").rsplit("/", 1)[-1],
            "body_preview": body[:400] if body else None,
            "similarity": round(ratio, 2),
        })
    return result


# ---------------------------------------------------------------------------
# Return-shape inference (Step 4)
# ---------------------------------------------------------------------------

def _infer_return_shape(callers: list[dict]) -> dict:
    """
    AST-walk caller bodies to infer what shape the stub must return.

    Confidence levels:
      STRONG — direct subscript ("result['key']") or attribute ("result.state")
               access on the call result found in caller body.
      WEAK   — result passed as argument to another function (keys unknown).
      NONE   — pattern not parseable or callers absent.

    Returns {"confidence": "STRONG"|"WEAK"|"NONE", "hints": [str, ...]}.
    Hints are de-duplicated and capped at 5. NONE returns empty hints.
    """
    hints: list[str] = []
    confidence = "NONE"

    for caller in callers:
        body = caller.get("body")
        if not body:
            continue
        try:
            tree = ast.parse(body)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            # Look for: var = <call>; then var["key"] or var.attr
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            # Identify the assigned target name
            if isinstance(node, ast.Assign) and node.targets:
                target = node.targets[0]
            elif isinstance(node, ast.AnnAssign):
                target = node.target
            else:
                continue
            if not isinstance(target, ast.Name):
                continue
            var_name = target.id

            # Walk entire tree for uses of this variable
            for use in ast.walk(tree):
                # Subscript access: var["key"] or var[0]
                if (isinstance(use, ast.Subscript)
                        and isinstance(use.value, ast.Name)
                        and use.value.id == var_name):
                    # Extract key if it's a string constant
                    slice_node = use.slice
                    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                        hint = f'["{slice_node.value}"]'
                    elif isinstance(slice_node, ast.Constant):
                        hint = f"[{slice_node.value!r}]"
                    else:
                        hint = "[...]"
                    if hint not in hints:
                        hints.append(hint)
                    confidence = "STRONG"

                # Attribute access: var.attr
                elif (isinstance(use, ast.Attribute)
                      and isinstance(use.value, ast.Name)
                      and use.value.id == var_name):
                    hint = f".{use.attr}"
                    if hint not in hints:
                        hints.append(hint)
                    confidence = "STRONG"

                # Passed as arg to another call — WEAK unless already STRONG
                elif isinstance(use, ast.Call):
                    for arg in use.args:
                        if isinstance(arg, ast.Name) and arg.id == var_name:
                            if confidence == "NONE":
                                confidence = "WEAK"
                                hints.append("(passed to another function)")

    return {"confidence": confidence, "hints": hints[:5]}


# ---------------------------------------------------------------------------
# Verification (V1 + V2)
# ---------------------------------------------------------------------------

def _verify_candidate(code: str, oracle: "DBOracle") -> dict:
    """
    Score a generated candidate on two signals.

    V1 — syntactic validity: ast.parse(). Hard gate.
    V2 — corpus call validity: fraction of called names that exist in the
         corpus functions table. Primary quality signal.

    Returns:
        v1_pass:      bool
        v1_error:     str | None
        v2_score:     float  0.0–1.0
        v2_calls:     list[str]  — checkable names found in candidate
        v2_unresolved: list[str] — names not in corpus
        composite:    float  = V2 * 0.6  (V3/V4 weights added in later steps)
    """
    # V1
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {
            "v1_pass": False,
            "v1_error": str(e),
            "v2_score": 0.0,
            "v2_calls": [],
            "v2_unresolved": [],
            "composite": 0.0,
        }

    # V2 — collect all called names from Call nodes
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)

    # Strip Python builtins and dunder methods — these are never in the corpus
    checkable = [
        n for n in called
        if n not in _PYTHON_BUILTINS and not (n.startswith("__") and n.endswith("__"))
    ]

    if not checkable:
        # No corpus-checkable calls — valid but uninformative; score 1.0 by convention
        return {
            "v1_pass": True,
            "v1_error": None,
            "v2_score": 1.0,
            "v2_calls": [],
            "v2_unresolved": [],
            "composite": 0.6,
        }

    conn = oracle.conn
    resolved, unresolved = [], []
    for name in checkable:
        row = conn.execute(
            "SELECT 1 FROM functions WHERE name = ? LIMIT 1", (name,)
        ).fetchone()
        (resolved if row else unresolved).append(name)

    score = len(resolved) / len(checkable)
    return {
        "v1_pass": True,
        "v1_error": None,
        "v2_score": round(score, 3),
        "v2_calls": sorted(checkable),
        "v2_unresolved": sorted(unresolved),
        "composite": round(score * 0.6, 3),
    }


# ---------------------------------------------------------------------------
# Brief builder (deterministic)
# ---------------------------------------------------------------------------

def build_brief(oracle: "DBOracle", symbol: str, class_name: str | None = None,
                file_path_hint: str | None = None) -> dict:
    """
    Build a solution candidate brief from the DB and source.
    Returns a dict with all context needed to generate or display a sketch.
    """
    from determined.agent.classify_stub import extract_signals, score_hypotheses

    signals = extract_signals(oracle, symbol, class_name=class_name,
                              file_path_hint=file_path_hint)
    if "error" in signals:
        return {"error": signals["error"]}

    hypotheses = score_hypotheses(signals)
    top = hypotheses[0] if hypotheses else None
    top_cls = top["classification"] if top else "uncertain"
    top_score = top["score"] if top else 0.0

    actionable = top_cls in ("design-intent-stated", "blocked-on-prerequisite") or \
                 signals.get("body_shape") == "config_declared"
    if not actionable:
        return {
            "symbol": symbol,
            "actionable": False,
            "classification": top_cls,
            "score": top_score,
            "reason": f"classify_stub verdict is '{top_cls}' — no candidate generated. "
                      "sketch_stub targets design-intent-stated and blocked-on-prerequisite.",
        }

    conn = oracle.conn
    file_path = signals["file_path"]
    line_number = signals.get("line_number")

    # Pull param_types_json and return_type (not in extract_signals output)
    row = conn.execute(
        "SELECT param_types_json, return_type FROM functions "
        "WHERE name = ? AND is_stub = 1 LIMIT 1",
        (symbol,),
    ).fetchone()
    ptj, return_type = row if row else (None, None)

    signature = _build_signature(symbol, ptj, return_type)
    callers = _caller_context(conn, symbol, file_path)
    siblings = _pattern_siblings(conn, file_path, symbol)
    return_shape = _infer_return_shape(callers)
    short_path = (file_path or "").replace("\\", "/").rsplit("/", 1)[-1]

    return {
        "symbol":         symbol,
        "actionable":     True,
        "classification": top_cls,
        "score":          top_score,
        "file":           short_path,
        "file_path":      file_path,
        "line_number":    line_number,
        "signature":      signature,
        "intent_text":    signals.get("intent_text"),
        "body_shape":     signals.get("body_shape"),
        "callers":        callers,
        "siblings":       siblings,
        "concepts":       signals.get("concept_presence", {}),
        "return_type":    return_type,
        "return_shape":   return_shape,
    }


# ---------------------------------------------------------------------------
# LLM candidate
# ---------------------------------------------------------------------------

def _build_prompt(brief: dict) -> str:
    """
    Build a completion-mode prompt: the signature + partial body so the model
    fills in the rest. Sibling bodies are shown as style examples before the
    target stub so the model completes in the same style.
    """
    parts = []

    # Style examples — implemented siblings shown first
    for s in brief.get("siblings", []):
        body = s.get("body_preview", "")
        doc = f'    """{s["docstring"]}"""' if s.get("docstring") else ""
        parts.append(f"def {s['name']}(...):")
        if doc:
            parts.append(doc)
        if body:
            for line in body.splitlines()[:8]:
                parts.append(line)
        parts.append("")

    # Caller bodies as comments — shows how return value is used without
    # creating a completable def that the model would fill instead of the target
    for c in brief.get("callers", []):
        if c.get("body"):
            parts.append(f"# usage in {c['name']} ({c['file']}):")
            for line in c["body"].splitlines()[:_CALLER_BODY_CAP]:
                parts.append(f"#   {line}")
            parts.append("")

    # Separator
    if parts:
        parts.append("# --- implement below ---")
        parts.append("")

    # Intent as a comment
    if brief.get("intent_text"):
        parts.append(f"# {brief['intent_text'][:200]}")
    if brief.get("callers"):
        caller_names = ", ".join(c["name"] for c in brief["callers"])
        parts.append(f"# Called by: {caller_names}")
    if brief.get("body_shape") == "config_declared":
        parts.append("# FSM handler — implement the action/guard logic below")

    # Return-shape hint (STRONG or WEAK only; NONE omitted)
    rs = brief.get("return_shape", {})
    if rs.get("confidence") in ("STRONG", "WEAK") and rs.get("hints"):
        hint_str = ", ".join(rs["hints"])
        if rs["confidence"] == "STRONG":
            parts.append(f"# returns: {hint_str}")
        else:
            parts.append(f"# returns: {hint_str}  (uncertain)")

    # The def line — model completes the body
    parts.append(brief["signature"])
    parts.append("    ")  # one indent to seed the model

    return "\n".join(parts)


def _llm_candidate(brief: dict) -> str | None:
    """
    Generate a candidate body via llama-server using completion mode.
    The prompt ends at the def line so the model fills in the body.
    Returns None on failure or if the result looks like prose.
    """
    from determined.agent.llm_client import generate, is_available
    if not is_available(timeout=3):
        return None
    prompt = _build_prompt(brief)
    result = generate(prompt, max_tokens=200)
    if not result:
        return None
    # Take only the first block — stop at the next blank line after first content
    # or at the next def/class (next function started)
    lines = result.splitlines()
    body: list[str] = []
    had_content = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("def ", "class ")):
            break  # next function started
        if not stripped and had_content:
            break  # blank line after first real content = end of body
        body.append(line)
        if stripped:
            had_content = True
    candidate = "\n".join(body).strip()
    # Reject if it's all prose (no Python syntax indicators)
    has_code = any(ch in candidate for ch in ("=", "(", "return", "self.", "raise", "->"))
    return candidate if candidate and has_code else None


# ---------------------------------------------------------------------------
# Tool entry point
# ---------------------------------------------------------------------------

def sketch_stub(assessor: "Assessor", args: dict) -> str:
    """
    sketch_stub(symbol) — generate a candidate implementation for a stub.

    Runs classify_stub first. For design-intent-stated or
    blocked-on-prerequisite stubs, builds a context brief and generates
    a candidate function body (LLM if available, deterministic brief always).

    Args:
        symbol:     stub function name (required)
        class_name: disambiguate lifecycle methods (optional)
        file_path:  disambiguate when name appears in multiple files (optional)
    """
    oracle = assessor.oracle
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    class_name = args.get("class_name", "").strip() or None
    file_path  = args.get("file_path", "").strip() or None

    brief = build_brief(oracle, symbol, class_name=class_name, file_path_hint=file_path)
    if "error" in brief:
        return f"sketch_stub: {brief['error']}"
    if not brief.get("actionable"):
        return (
            f"sketch_stub: {symbol}\n"
            f"  Classification: {brief['classification']} [{brief['score']:.2f}]\n"
            f"  {brief['reason']}"
        )

    # ── Format deterministic brief ──────────────────────────────────────
    out = [
        f"sketch_stub: {symbol}  ({brief['file']}:{brief.get('line_number', '?')})",
        f"  classify: {brief['classification']} [{brief['score']:.2f}]",
        "",
        "CONTEXT",
    ]
    if brief.get("intent_text"):
        out.append(f"  intent:  {brief['intent_text'][:200]}")
    if brief.get("callers"):
        caller_names = ", ".join(c["name"] for c in brief["callers"])
        out.append(f"  callers: {caller_names}")
    if brief.get("concepts"):
        present = [c for c, n in brief["concepts"].items() if n > 0]
        absent  = [c for c, n in brief["concepts"].items() if n == 0]
        if present:
            out.append(f"  concepts present: {', '.join(present)}")
        if absent:
            out.append(f"  concepts absent:  {', '.join(absent)}")
    if brief.get("return_type"):
        out.append(f"  return type: {brief['return_type']}")
    if brief.get("body_shape") == "config_declared":
        out.append("  source: FSM config declaration (Python handler missing)")

    out += ["", "SIGNATURE", f"  {brief['signature']}", ""]

    # ── LLM candidate ───────────────────────────────────────────────────
    candidate = _llm_candidate(brief)
    if candidate:
        out.append("CANDIDATE (LLM)")
        out.append("  # --- begin ---")
        for line in candidate.splitlines():
            out.append(f"  {line}")
        out.append("  # --- end ---")
        out.append("")

        # ── Verification ────────────────────────────────────────────────
        vr = _verify_candidate(candidate, oracle)
        out.append("VERIFICATION")
        v1 = "PASS" if vr["v1_pass"] else f"FAIL ({vr['v1_error']})"
        out.append(f"  V1 syntax:        {v1}")
        if vr["v1_pass"]:
            n_calls = len(vr["v2_calls"])
            n_ok = n_calls - len(vr["v2_unresolved"])
            if n_calls == 0:
                out.append("  V2 corpus calls:  n/a (no checkable calls)")
            else:
                out.append(f"  V2 corpus calls:  {vr['v2_score']:.2f}  ({n_ok}/{n_calls} resolved)")
            if vr["v2_unresolved"]:
                out.append(f"  V2 unresolved:    {', '.join(vr['v2_unresolved'])}")
            out.append(f"  composite score:  {vr['composite']:.2f}  (V2×0.6; V3/V4 pending)")
        out.append("")
        out.append("NOTE: Review against callers and project conventions before applying.")
        out.append("      classify_stub evidence is the ground truth; this sketch interprets it.")
    else:
        out.append("CANDIDATE")
        out.append("  (LLM not available — start with the signature above and intent text)")
        if brief.get("siblings"):
            out.append("  Style reference: see implemented siblings in same file:")
            for s in brief["siblings"]:
                out.append(f"    {s['name']}")

    return "\n".join(out)
