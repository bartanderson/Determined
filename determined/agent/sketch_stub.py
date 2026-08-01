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
_FSM_SIBLING_CAP = 3   # max FSM builtin siblings to include


def _fsm_transition_context(json_path: str, symbol: str) -> dict | None:
    """Read an FSM JSON config and return the transition(s) that use this action/guard.

    Corpus-agnostic: works for any FSM whose config is a JSON file with the
    {states, events: {name: {transitions: [{from, to, cond?, actions?}]}}} shape.
    Returns None if the file is unreadable or the symbol is not found.
    """
    try:
        with open(json_path, encoding="utf-8") as fh:
            definition = json.load(fh)
    except (OSError, ValueError):
        return None

    local = symbol.rsplit("::", 1)[-1]
    kind = (
        "action" if "::action::" in symbol else
        "guard"  if "::guard::"  in symbol else
        "unknown"
    )

    transitions = []
    for event_name, event_def in definition.get("events", {}).items():
        for t in event_def.get("transitions", []):
            froms = t["from"] if isinstance(t["from"], list) else [t["from"]]
            if kind == "action" and local in t.get("actions", []):
                transitions.append({
                    "event": event_name,
                    "from": froms,
                    "to": t["to"],
                    "cond": t.get("cond"),
                })
            elif kind == "guard" and t.get("cond") == local:
                transitions.append({
                    "event": event_name,
                    "from": froms,
                    "to": t["to"],
                    "actions": t.get("actions", []),
                })

    if not transitions:
        return None

    return {
        "fsm_name": definition.get("name", ""),
        "kind": kind,
        "local_name": local,
        "transitions": transitions,
        "states": [s["name"] for s in definition.get("states", [])],
    }


def _fsm_builtin_siblings(conn, stub_name: str, limit: int = _FSM_SIBLING_CAP) -> list[dict]:
    """Find implemented FSM handler functions from corpus files whose path contains 'fsm'.

    Corpus-agnostic: any language corpus with an fsm/ directory will produce matches.
    Prefers same-kind (action vs guard) siblings when the name encodes the kind.
    """
    local = stub_name.rsplit("::", 1)[-1]
    rows = conn.execute(
        "SELECT name, file_path, line_number FROM functions "
        "WHERE file_path LIKE '%fsm%' AND is_stub = 0 AND line_number > 0 AND name != ? "
        "ORDER BY line_number LIMIT ?",
        (local, limit * 4),
    ).fetchall()

    result = []
    for name, fp, ln in rows:
        if len(result) >= limit:
            break
        body = _read_function_body(fp, ln, cap=_BODY_CAP) if fp and ln else ""
        if not body:
            continue
        result.append({
            "name": name,
            "file": (fp or "").replace("\\", "/").rsplit("/", 1)[-1],
            "body_preview": body[:400],
        })
    return result


def _caller_context(conn, name: str, file_path: str, limit: int = 3) -> list[dict]:
    """Return up to limit callers with their full source bodies."""
    callers = conn.execute(
        "SELECT DISTINCT e.caller FROM graph_edges e "
        "WHERE e.callee = ? OR e.callee LIKE ? LIMIT ?",
        (name, f"%.{name}", limit),
    ).fetchall()
    result = []
    for (caller,) in callers:
        # Exact match first; then try treating caller as a suffix (Class.method → method).
        row = conn.execute(
            "SELECT file_path, line_number FROM functions WHERE name = ?",
            (caller,),
        ).fetchone()
        if row is None:
            short = caller.rsplit(".", 1)[-1]
            if short != caller:
                row = conn.execute(
                    "SELECT file_path, line_number FROM functions WHERE name = ?",
                    (short,),
                ).fetchone()
        fp, ln = (row[0], row[1]) if row else (None, None)
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


def _same_class_siblings(conn, stub_name: str, limit: int) -> list[dict]:
    """Return implemented siblings that share the same class prefix (e.g. EncounterFSM::).

    For framework-dispatched methods (FSM actions/guards, protocol methods) the
    class prefix encodes the interface contract. Siblings in the same class are
    the highest-fidelity style examples — same signature, same dispatch context.
    Only triggered when stub_name contains '::' (class-qualified names).
    """
    if "::" not in stub_name:
        return []
    class_prefix = stub_name.split("::")[0] + "::"
    rows = conn.execute(
        "SELECT name, file_path, line_number FROM functions "
        "WHERE name LIKE ? AND is_stub = 0 AND name != ? "
        "ORDER BY line_number LIMIT ?",
        (class_prefix + "%", stub_name, limit),
    ).fetchall()
    result = []
    for name, fp, ln in rows:
        body = _read_function_body(fp, ln) if fp and ln else ""
        if not body:
            continue
        result.append({
            "name": name,
            "file": (fp or "").replace("\\", "/").rsplit("/", 1)[-1],
            "body_preview": body[:400] if body else None,
            "similarity": 1.0,  # same-class match is highest confidence
        })
    return result


def _pattern_siblings(conn, file_path: str, stub_name: str,
                      limit: int = _SIBLING_CAP) -> list[dict]:
    """
    Find implemented functions with similar name patterns, corpus-wide.

    Same-class siblings (shared ClassName:: prefix) are returned first —
    they share the interface contract and are the highest-fidelity examples.
    Falls back to corpus-wide difflib ratio on normalized names.
    Falls back further to file-scoped _style_siblings() when nothing scores
    above _PATTERN_FLOOR, so the prompt always has something to work from.
    """
    # Same-class siblings first — highest priority for class-qualified names
    same_class = _same_class_siblings(conn, stub_name, limit)
    if len(same_class) >= limit:
        return same_class[:limit]

    normalized_stub = _normalize_name(stub_name)
    already = {s["name"] for s in same_class}

    # Load all implemented function names — names only, bodies fetched for top matches only
    rows = conn.execute(
        "SELECT name, file_path, line_number FROM functions "
        "WHERE is_stub = 0 AND name != ?",
        (stub_name,),
    ).fetchall()

    scored = []
    for name, fp, ln in rows:
        if name in already:
            continue
        norm = _normalize_name(name)
        if not norm:
            continue
        ratio = difflib.SequenceMatcher(None, normalized_stub, norm).ratio()
        if ratio >= _PATTERN_FLOOR:
            scored.append((ratio, name, fp, ln))

    scored.sort(reverse=True)
    remaining = limit - len(same_class)
    top = scored[:remaining]

    if not top and not same_class:
        return _style_siblings(conn, file_path, stub_name)

    corpus_results = []
    for ratio, name, fp, ln in top:
        body = _read_function_body(fp, ln) if fp and ln else ""
        corpus_results.append({
            "name": name,
            "file": (fp or "").replace("\\", "/").rsplit("/", 1)[-1],
            "body_preview": body[:400] if body else None,
            "similarity": round(ratio, 2),
        })
    return same_class + corpus_results


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
            tree = ast.parse(_wrap_body(body))
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
# Type definition pull (Step 5)
# ---------------------------------------------------------------------------

# Regex for CamelCase identifiers (potential class names) in text.
_CAMEL_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]{2,})\b")

# Python built-in exception / type names to skip — not corpus classes.
_BUILTIN_TYPES = frozenset({
    "None", "True", "False", "Optional", "List", "Dict", "Tuple", "Set",
    "Any", "Union", "Type", "Callable", "Iterator", "Generator", "Sequence",
    "Mapping", "Iterable", "ClassVar", "Final", "Literal", "TypeVar",
    "Protocol", "NotImplemented", "Exception", "ValueError", "TypeError",
    "KeyError", "AttributeError", "RuntimeError", "StopIteration",
    "NameError", "IndexError", "OSError", "IOError", "FileNotFoundError",
})


def _extract_type_names(signature: str, docstring: str | None) -> list[str]:
    """Extract candidate class names from a stub's signature and docstring."""
    text = (signature or "") + " " + (docstring or "")
    names = _CAMEL_RE.findall(text)
    seen: set[str] = set()
    result = []
    for n in names:
        if n not in _BUILTIN_TYPES and n not in seen:
            seen.add(n)
            result.append(n)
    return result


def _pull_type_defs(conn, type_names: list[str]) -> list[dict]:
    """
    For each name that resolves to a class in the DB, return its
    __init__ signature and public non-stub methods with their signatures.

    Returns a list of dicts: {class_name, file, init_sig, methods: [{name, sig}]}.
    Caps at 3 classes and 8 methods per class to keep prompts bounded.
    """
    results = []
    seen_classes: set[str] = set()
    for name in type_names:
        if name in seen_classes or len(results) >= 3:
            break
        row = conn.execute(
            "SELECT file_path, methods_json FROM classes WHERE name = ? LIMIT 1",
            (name,),
        ).fetchone()
        if not row:
            continue
        file_path, methods_json = row
        try:
            method_names = json.loads(methods_json or "[]")
        except (ValueError, TypeError):
            method_names = []

        short_file = (file_path or "").replace("\\", "/").rsplit("/", 1)[-1]

        # Fetch __init__ and public non-stub methods (no leading underscore except __init__)
        public = ["__init__"] + [
            m for m in method_names
            if not m.startswith("_") and m != "__init__"
        ]
        public = public[:9]  # __init__ + up to 8 public methods

        if not public:
            continue

        placeholders = ",".join("?" * len(public))
        rows = conn.execute(
            f"SELECT name, param_types_json, return_type, is_stub "
            f"FROM functions WHERE file_path = ? AND name IN ({placeholders})",
            [file_path] + public,
        ).fetchall()

        methods_out = []
        init_sig = None
        for mname, ptj, rtype, is_stub in rows:
            if is_stub:
                continue
            try:
                params = json.loads(ptj or "[]")
            except (ValueError, TypeError):
                params = []
            param_str = ", ".join(params) if params else ""
            ret = f" -> {rtype}" if rtype else ""
            sig = f"{mname}({param_str}){ret}"
            if mname == "__init__":
                init_sig = sig
            else:
                methods_out.append({"name": mname, "sig": sig})

        if init_sig or methods_out:
            results.append({
                "class_name": name,
                "file": short_file,
                "init_sig": init_sig,
                "methods": methods_out[:8],
            })
            seen_classes.add(name)

    return results


# ---------------------------------------------------------------------------
# Verification (V1 + V2 + V3 + V4)
# ---------------------------------------------------------------------------

def _wrap_body(code: str) -> str:
    """Wrap a function body fragment in a dummy def so ast.parse() accepts it."""
    return "def _f():\n" + "\n".join("    " + line for line in code.splitlines())


def _ast_node_sequence(code: str) -> list[str]:
    """
    Flatten an AST into a sequence of statement-node type names.
    Used by V4 to compare structural shape between candidate and sibling.
    Returns empty list on parse error.
    """
    try:
        tree = ast.parse(_wrap_body(code))
    except SyntaxError:
        return []
    return [type(n).__name__ for n in ast.walk(tree) if isinstance(n, ast.stmt)]


def _v3_return_type_score(tree: ast.AST, declared_return_type: str | None) -> float:
    """
    V3 — return type compatibility.

    If the declared return type is 'dict' (or starts with 'dict'), check that
    at least one return statement returns a dict literal ({...}) or a Name
    (variable — assumed compatible). If 'None' or absent, passes trivially.
    Returns 0.0 or 1.0 — no partial credit.
    """
    if not declared_return_type:
        return 1.0
    rtype = declared_return_type.strip().lower()
    if rtype in ("none", ""):
        return 1.0
    if not rtype.startswith("dict"):
        # For non-dict types we don't have enough signal — pass trivially
        return 1.0

    # Check for at least one return statement returning a dict or variable
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value is not None:
            if isinstance(node.value, ast.Dict):
                return 1.0
            if isinstance(node.value, ast.Name):
                return 1.0  # variable — plausibly correct
    return 0.0


def _v4_pattern_similarity(candidate_seq: list[str], sibling_body: str | None) -> float:
    """
    V4 — pattern similarity to best sibling.

    Computes difflib ratio on AST node-type sequences (statement types only).
    Returns 0.5 when no sibling is available — neutral, not penalizing.
    """
    if not sibling_body or not candidate_seq:
        return 0.5
    sibling_seq = _ast_node_sequence(sibling_body)
    if not sibling_seq:
        return 0.5
    return difflib.SequenceMatcher(None, candidate_seq, sibling_seq).ratio()


def _verify_candidate(code: str, oracle: "DBOracle",
                      declared_return_type: str | None = None,
                      best_sibling_body: str | None = None) -> dict:
    """
    Score a generated candidate on four signals.

    V1 — syntactic validity: ast.parse(). Hard gate.
    V2 — corpus call validity: fraction of called names in DB. Weight 0.6.
    V3 — return type compatibility: dict return check. Weight 0.2.
    V4 — pattern similarity to best sibling (AST seq). Weight 0.2. Tiebreaker only.

    composite = V2*0.6 + V3*0.2 + V4*0.2  (V1 is hard gate, not weighted)
    """
    # V1 — wrap body fragment in a dummy def for parsing
    try:
        tree = ast.parse(_wrap_body(code))
    except SyntaxError as e:
        return {
            "v1_pass": False,
            "v1_error": str(e),
            "v2_score": 0.0,
            "v2_calls": [],
            "v2_unresolved": [],
            "v3_score": 0.0,
            "v4_score": 0.0,
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
        v2_score = 1.0
        resolved, unresolved = [], []
    else:
        conn = oracle.conn
        resolved, unresolved = [], []
        for name in checkable:
            row = conn.execute(
                "SELECT 1 FROM functions WHERE name = ? LIMIT 1", (name,)
            ).fetchone()
            (resolved if row else unresolved).append(name)
        v2_score = len(resolved) / len(checkable)

    # V3 and V4
    v3 = _v3_return_type_score(tree, declared_return_type)
    candidate_seq = _ast_node_sequence(code)
    v4 = _v4_pattern_similarity(candidate_seq, best_sibling_body)

    composite = v2_score * 0.6 + v3 * 0.2 + v4 * 0.2

    return {
        "v1_pass": True,
        "v1_error": None,
        "v2_score": round(v2_score, 3),
        "v2_calls": sorted(checkable),
        "v2_unresolved": sorted(unresolved),
        "v3_score": round(v3, 3),
        "v4_score": round(v4, 3),
        "composite": round(composite, 3),
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

    docstring = signals.get("docstring") or ""
    type_names = _extract_type_names(signature, docstring)
    type_defs = _pull_type_defs(conn, type_names)

    # FSM-specific context: JSON transition spec + implemented handler siblings
    fsm_context = None
    fsm_siblings: list[dict] = []
    if signals.get("body_shape") == "config_declared" and file_path and file_path.endswith(".json"):
        fsm_context = _fsm_transition_context(file_path, symbol)
        fsm_siblings = _fsm_builtin_siblings(conn, symbol)

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
        "fsm_context":    fsm_context,
        "fsm_siblings":   fsm_siblings,
        "concepts":       signals.get("concept_presence", {}),
        "return_type":    return_type,
        "return_shape":   return_shape,
        "type_defs":      type_defs,
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

    # Style examples — FSM builtin siblings first (when present), then pattern siblings
    for s in brief.get("fsm_siblings", []):
        body = s.get("body_preview", "")
        parts.append(f"def {s['name']}(instance, event_data):")
        if body:
            for line in body.splitlines()[:8]:
                parts.append(line)
        parts.append("")

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

    # FSM transition spec — where this action/guard fits in the state machine
    fc = brief.get("fsm_context")
    if fc:
        parts.append(f"# FSM: {fc['fsm_name']} ({fc['kind']} '{fc['local_name']}')")
        for t in fc["transitions"]:
            froms = ", ".join(t["from"])
            if fc["kind"] == "action":
                cond_note = f" [if {t['cond']}]" if t.get("cond") else ""
                parts.append(f"#   event '{t['event']}': {froms} -> {t['to']}{cond_note}")
            else:
                acts = ", ".join(t.get("actions", [])) or "none"
                parts.append(f"#   guards '{t['event']}': {froms} -> {t['to']} (actions: {acts})")
        parts.append(f"#   states: {', '.join(fc['states'])}")
    elif brief.get("body_shape") == "config_declared":
        parts.append("# FSM handler — implement the action/guard logic below")

    # Return-shape hint (STRONG or WEAK only; NONE omitted)
    rs = brief.get("return_shape", {})
    if rs.get("confidence") in ("STRONG", "WEAK") and rs.get("hints"):
        hint_str = ", ".join(rs["hints"])
        if rs["confidence"] == "STRONG":
            parts.append(f"# returns: {hint_str}")
        else:
            parts.append(f"# returns: {hint_str}  (uncertain)")

    # Available type APIs — what the body is allowed to call
    for td in brief.get("type_defs", []):
        parts.append(f"# {td['class_name']} ({td['file']}):")
        if td.get("init_sig"):
            parts.append(f"#   {td['init_sig']}")
        for m in td.get("methods", []):
            parts.append(f"#   {m['sig']}")

    # The def line — model completes the body
    parts.append(brief["signature"])
    parts.append("    ")  # one indent to seed the model

    return "\n".join(parts)


def _llm_candidate(brief: dict, extra_constraint: str | None = None) -> str | None:
    """
    Generate a candidate body via llama-server using completion mode.
    The prompt ends at the def line so the model fills in the body.
    extra_constraint is appended as a comment after the def line to guide retry.
    Returns None on failure or if the result looks like prose.
    """
    from determined.agent.llm_client import generate, is_available
    if not is_available(timeout=3):
        return None
    prompt = _build_prompt(brief)
    if extra_constraint:
        prompt = prompt.rstrip() + f"\n    # CONSTRAINT: {extra_constraint}\n    "
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


_REFINE_CEILING = 3  # max feedback iterations before giving up


def _feedback_constraint(vr: dict, brief: dict) -> str | None:
    """
    Build a specific constraint string from verification results.
    Returns None when there is no actionable feedback.

    Priority: V1 (syntax error) > V2 (unresolved calls).
    V3/V4 are soft signals — not fed back as constraints.
    """
    if not vr["v1_pass"]:
        return f"syntax error in previous attempt: {vr['v1_error']}. Write valid Python only."

    if vr["v2_unresolved"]:
        bad = ", ".join(f"`{n}`" for n in vr["v2_unresolved"][:3])
        # Collect available alternatives from type_defs
        available: list[str] = []
        for td in brief.get("type_defs", []):
            cls = td["class_name"]
            for m in td.get("methods", []):
                available.append(f"{cls}.{m['name']}")
        if available:
            avail_str = ", ".join(available[:6])
            return f"{bad} not in codebase. Available: {avail_str}."
        return f"{bad} not in codebase. Use only names from the context above."

    return None


def _run_quick(brief: dict, oracle: "DBOracle",
               best_sibling_body: str | None) -> tuple[str | None, dict | None, int, bool]:
    """
    Quick mode: 1 sample; retry with feedback on V1/V2 failure up to ceiling.

    Returns (best_candidate, best_vr, iterations_used, ceiling_hit).
    best_candidate/best_vr are None if LLM is unavailable.
    """
    constraint: str | None = None
    best_candidate: str | None = None
    best_vr: dict | None = None

    for iteration in range(1, _REFINE_CEILING + 1):
        candidate = _llm_candidate(brief, extra_constraint=constraint)
        if candidate is None:
            return None, None, iteration, False

        vr = _verify_candidate(
            candidate, oracle,
            declared_return_type=brief.get("return_type"),
            best_sibling_body=best_sibling_body,
        )

        # Keep the best composite seen
        if best_vr is None or vr["composite"] > best_vr["composite"]:
            best_candidate, best_vr = candidate, vr

        # Stop if passing
        if vr["v1_pass"] and vr["v2_score"] >= 0.8:
            return best_candidate, best_vr, iteration, False

        # Build feedback for next round
        new_constraint = _feedback_constraint(vr, brief)
        if new_constraint is None or new_constraint == constraint:
            # No new feedback to give — stop early
            return best_candidate, best_vr, iteration, False
        constraint = new_constraint

    return best_candidate, best_vr, _REFINE_CEILING, True


def _run_thorough(brief: dict, oracle: "DBOracle",
                  best_sibling_body: str | None,
                  k: int = 3) -> list[tuple[str, dict]]:
    """
    Thorough mode: generate k independent samples, verify all, return sorted by composite.
    Each sample is generated without feedback — independent draws for diversity.
    Returns list of (candidate, vr) sorted best-first. Empty if LLM unavailable.
    """
    results = []
    for _ in range(k):
        candidate = _llm_candidate(brief)
        if candidate is None:
            break
        vr = _verify_candidate(
            candidate, oracle,
            declared_return_type=brief.get("return_type"),
            best_sibling_body=best_sibling_body,
        )
        results.append((candidate, vr))
    results.sort(key=lambda t: t[1]["composite"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Tool entry point
# ---------------------------------------------------------------------------

def _format_vr(vr: dict, out: list[str]) -> None:
    """Append verification lines to out list."""
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
        out.append(f"  V3 return type:   {vr['v3_score']:.2f}")
        out.append(f"  V4 pattern sim:   {vr['v4_score']:.2f}")
        out.append(f"  composite score:  {vr['composite']:.2f}  (V2×0.6 + V3×0.2 + V4×0.2)")


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
        mode:       "quick" (default) or "thorough" (K=3 samples, ranked)
    """
    oracle = assessor.oracle
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    class_name = args.get("class_name", "").strip() or None
    file_path  = args.get("file_path", "").strip() or None
    mode       = args.get("mode", "quick").strip().lower()
    if mode not in ("quick", "thorough"):
        mode = "quick"

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
    if brief.get("type_defs"):
        for td in brief["type_defs"]:
            method_names = [m["name"] for m in td.get("methods", [])]
            out.append(f"  type APIs: {td['class_name']} → {', '.join(method_names) or '(none)'}")

    out += ["", "SIGNATURE", f"  {brief['signature']}", ""]

    # ── LLM candidate ───────────────────────────────────────────────────
    best_sibling_body = brief["siblings"][0].get("body_preview") if brief.get("siblings") else None

    if mode == "thorough":
        ranked = _run_thorough(brief, oracle, best_sibling_body)
        if not ranked:
            out.append("CANDIDATE")
            out.append("  (LLM not available — start with the signature above and intent text)")
            return "\n".join(out)

        best_cand, best_vr = ranked[0]
        out.append(f"CANDIDATE (LLM — thorough, {len(ranked)} sample(s))")
        out.append("  # --- begin ---")
        for line in best_cand.splitlines():
            out.append(f"  {line}")
        out.append("  # --- end ---")
        out.append("")
        out.append("VERIFICATION (best of batch)")
        _format_vr(best_vr, out)
        if len(ranked) > 1:
            out.append("")
            out.append("ALTERNATES")
            for i, (alt_cand, alt_vr) in enumerate(ranked[1:], start=2):
                out.append(f"  #{i} composite={alt_vr['composite']:.2f}:")
                for line in alt_cand.splitlines()[:4]:
                    out.append(f"    {line}")
                if len(alt_cand.splitlines()) > 4:
                    out.append("    ...")

    else:
        # Quick mode — 1 sample with feedback-guided retry
        best_cand, best_vr, iterations, ceiling_hit = _run_quick(brief, oracle, best_sibling_body)
        if best_cand is None:
            out.append("CANDIDATE")
            out.append("  (LLM not available — start with the signature above and intent text)")
            if brief.get("siblings"):
                out.append("  Style reference: see implemented siblings in same file:")
                for s in brief["siblings"]:
                    out.append(f"    {s['name']}")
            return "\n".join(out)

        label = "CANDIDATE (LLM)"
        if iterations > 1:
            label += f"  [{iterations} iteration(s)"
            label += ", ceiling hit — best attempt shown]" if ceiling_hit else "]"
        out.append(label)
        out.append("  # --- begin ---")
        for line in best_cand.splitlines():
            out.append(f"  {line}")
        out.append("  # --- end ---")
        out.append("")
        out.append("VERIFICATION")
        _format_vr(best_vr, out)

    out.append("")
    out.append("NOTE: Review against callers and project conventions before applying.")
    out.append("      classify_stub evidence is the ground truth; this sketch interprets it.")
    return "\n".join(out)
