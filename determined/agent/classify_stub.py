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

# ---------------------------------------------------------------------------
# Lifecycle method detection (language-specific)
# ---------------------------------------------------------------------------

# Python dunder methods that appear in every class and cannot be classified
# by name alone — need class context.
_PYTHON_MAGIC_METHODS = frozenset({
    "__init__", "__new__", "__del__",
    "__str__", "__repr__", "__bytes__", "__format__",
    "__len__", "__length_hint__", "__bool__",
    "__call__", "__hash__", "__eq__", "__ne__",
    "__lt__", "__le__", "__gt__", "__ge__",
    "__getitem__", "__setitem__", "__delitem__", "__contains__",
    "__iter__", "__next__", "__reversed__",
    "__enter__", "__exit__",
    "__get__", "__set__", "__delete__",
    "__getattr__", "__setattr__", "__delattr__",
    "__add__", "__sub__", "__mul__", "__truediv__",
    "__radd__", "__rsub__", "__rmul__",
    "__iadd__", "__isub__", "__imul__",
    "__neg__", "__pos__", "__abs__",
    "__int__", "__float__", "__index__",
    "__await__", "__aiter__", "__anext__",
    "__aenter__", "__aexit__",
})

# Base class names that indicate interface/contract role (not implementation gaps)
_ABC_BASES = frozenset({"Protocol", "ABC", "ABCMeta"})

# self.attr = assignment pattern (Python __init__ body check)
_SELF_ASSIGN_RE = re.compile(r'\bself\.\w+\s*=')


def _is_lifecycle_method(name: str, file_path: str | None) -> bool:
    """
    True if name is a constructor/lifecycle method that appears in every class
    and cannot be classified by bare name alone.

    Python: dunder methods (__init__, __str__, etc.)
    JS/TS:  constructor
    Other languages: False (no equivalent naming convention to detect statically)
    """
    ext = (file_path or "").rsplit(".", 1)[-1].lower()
    if ext == "py":
        return name in _PYTHON_MAGIC_METHODS
    if ext in ("js", "ts", "jsx", "tsx"):
        return name == "constructor"
    # Default: treat Python-style dunders as lifecycle even without file context
    return name.startswith("__") and name.endswith("__") and len(name) > 4


def _check_init_self_assigns(file_path: str, line_number: int | None) -> bool:
    """
    Return True if the __init__ body at line_number assigns at least one
    self.attr = value.  Returns True (unknown/assumed assigned) on any error.
    Only meaningful for Python __init__.
    """
    if not line_number:
        return True
    try:
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        start = line_number  # 1-based; this is the def line
        if start < 1 or start > len(lines):
            return True
        def_indent = len(lines[start - 1]) - len(lines[start - 1].lstrip())
        for line in lines[start:start + 40]:
            stripped = line.strip()
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= def_indent and not stripped.startswith('#'):
                break
            if _SELF_ASSIGN_RE.search(line):
                return True
        return False
    except OSError:
        return True


def _extract_class_context(
    conn,
    name: str,
    file_path: str | None,
    class_name: str | None = None,
    line_number: int | None = None,
) -> dict:
    """
    Extract class-level signals for a lifecycle method.
    Language-agnostic: reads from the classes table schema only.

    Returns dict with:
        is_protocol_or_abc    : bool — class inherits from Protocol/ABC (contract role)
        class_docstring       : str | None — class-level docstring
        class_sibling_stubs   : int — other stubs in the same file
        instance_vars_assigned: bool — __init__ assigns self.x (Python only)
    """
    import json as _json

    result = {
        "is_protocol_or_abc": False,
        "class_docstring": None,
        "class_sibling_stubs": 0,
        "instance_vars_assigned": True,  # assume true unless we can verify
    }

    if not file_path:
        return result

    # Find the class row — prefer explicit class_name, fall back to first in file
    if class_name:
        cls_row = conn.execute(
            "SELECT name, base_classes_json, docstring FROM classes "
            "WHERE file_path = ? AND name LIKE ?",
            (file_path, f"%{class_name}%"),
        ).fetchone()
    else:
        cls_row = conn.execute(
            "SELECT name, base_classes_json, docstring FROM classes "
            "WHERE file_path = ?",
            (file_path,),
        ).fetchone()

    if cls_row:
        _, bases_json, cls_doc = cls_row
        result["class_docstring"] = (cls_doc or "").strip() or None

        try:
            bases = _json.loads(bases_json or "[]")
            if isinstance(bases, list):
                result["is_protocol_or_abc"] = any(
                    any(abc in b for abc in _ABC_BASES)
                    for b in bases
                )
        except (ValueError, TypeError):
            pass

    # Sibling stubs: other stubs in the same file (file = proxy for class scope)
    result["class_sibling_stubs"] = conn.execute(
        "SELECT COUNT(*) FROM functions "
        "WHERE file_path = ? AND is_stub = 1 AND name != ?",
        (file_path, name),
    ).fetchone()[0]

    # instance_vars_assigned: Python __init__ specific
    if name == "__init__" and file_path and file_path.endswith(".py"):
        result["instance_vars_assigned"] = _check_init_self_assigns(
            file_path, line_number
        )

    return result


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

def extract_signals(
    oracle: "DBOracle",
    fqdn: str,
    class_name: str | None = None,
    file_path_hint: str | None = None,
) -> dict:
    """
    Gather all observable signals about a stub from the DB and source text.
    Returns a dict with keys documented inline.  No LLM.  No side effects.

    class_name and file_path_hint disambiguate lifecycle methods (__init__ etc.)
    that appear under multiple classes.  When file_path_hint is provided the
    query uses it to select the correct row; class_name is forwarded to
    _extract_class_context for Protocol/ABC detection.
    """
    import json as _json

    conn = oracle.conn

    # ── 1. Fetch stub row ────────────────────────────────────────────────
    # Use file_path_hint to disambiguate lifecycle methods (e.g. __init__
    # under multiple classes).  Without it, LIMIT 1 picks an arbitrary row.
    if file_path_hint:
        norm_hint = file_path_hint.replace("\\", "/").lower()
        row = conn.execute(
            "SELECT name, file_path, line_number, docstring, param_types_json, "
            "return_type, is_stub FROM functions "
            "WHERE name = ? AND LOWER(REPLACE(file_path, '\\', '/')) LIKE '%' || ? "
            "AND is_stub = 1 LIMIT 1",
            (fqdn, norm_hint)
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT name, file_path, line_number, docstring, param_types_json, "
                "return_type, is_stub FROM functions WHERE name = ? AND is_stub = 1 LIMIT 1",
                (fqdn,)
            ).fetchone()
    else:
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

    # ── 9. Lifecycle method / class context ──────────────────────────────
    is_lifecycle = _is_lifecycle_method(name, file_path)
    class_ctx: dict = {}
    if is_lifecycle:
        class_ctx = _extract_class_context(
            conn, name, file_path,
            class_name=class_name,
            line_number=line_number,
        )
        # Merge class docstring into intent text when stub has none
        if not intent_text and class_ctx.get("class_docstring"):
            all_text = class_ctx["class_docstring"]
            has_intent = _has_intent(all_text)
            has_removal = _has_removal(all_text)
            intent_text = all_text

    # ── 10. Config-layer FSM presence ────────────────────────────────────
    # Check whether any concept from the stub's docstring appears as an FSM
    # name in knowledge_artifacts (fsm_state/fsm_action/fsm_guard subjects).
    # Pattern: concept "CombatFSM" → look for "CombatFSM.*" subjects.
    # Also check whether a *different* FSM references the concept as an action
    # (e.g. EncounterFSM.start_combat) — config points to it, but no FSM exists.
    config_fsm_present: list[str] = []   # FSMs whose name matches a concept
    config_fsm_referenced: list[str] = []  # other FSMs that reference the concept
    try:
        for concept in concepts:
            base = _concept_base(concept)
            base_lower = base.lower()
            # Direct: concept is the FSM name (e.g. CombatFSM → "Combat.")
            direct = conn.execute(
                "SELECT DISTINCT subject FROM knowledge_artifacts "
                "WHERE kind IN ('fsm_state','fsm_action','fsm_guard') "
                "AND LOWER(subject) LIKE ?",
                (f"{base_lower}.%",),
            ).fetchall()
            if direct:
                config_fsm_present.append(concept)
            # Indirect: concept appears in another FSM's action/state name
            # (e.g. EncounterFSM.start_combat references "combat")
            indirect = conn.execute(
                "SELECT DISTINCT subject FROM knowledge_artifacts "
                "WHERE kind IN ('fsm_state','fsm_action','fsm_guard') "
                "AND LOWER(subject) LIKE ? AND LOWER(subject) NOT LIKE ?",
                (f"%{base_lower}%", f"{base_lower}.%"),
            ).fetchall()
            if indirect and not direct:
                config_fsm_referenced.extend(r[0] for r in indirect)
    except Exception:
        pass  # knowledge_artifacts table absent in minimal test DBs

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
        # Lifecycle / class context (populated only when is_lifecycle=True)
        "is_lifecycle":             is_lifecycle,
        "is_protocol_or_abc":       class_ctx.get("is_protocol_or_abc", False),
        "class_docstring":          class_ctx.get("class_docstring"),
        "class_sibling_stubs":      class_ctx.get("class_sibling_stubs", 0),
        "instance_vars_assigned":   class_ctx.get("instance_vars_assigned", True),
        # Config-layer FSM signals
        "config_fsm_present":       config_fsm_present,
        "config_fsm_referenced":    config_fsm_referenced,
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
    is_lifecycle     = signals.get("is_lifecycle", False)
    is_protocol_abc  = signals.get("is_protocol_or_abc", False)
    class_siblings   = signals.get("class_sibling_stubs", 0)
    vars_assigned    = signals.get("instance_vars_assigned", True)

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

        # Compound: called + no behavioral intent + empty body → slot wired up, nothing filled in
        # "placeholder" doc (label only, no behavioral language) is the same as no doc here.
        # The function exists in the call graph but carries no actionable content.
        # Strongest structural indicator of blocked-on-prerequisite.
        if doc_quality in ("none", "placeholder") and body == "empty_pass" and not has_intent:
            scores["blocked-on-prerequisite"] += 1.0
            evidence["blocked-on-prerequisite"].append(
                "called but no behavioral intent + empty body — slot wired up, implementation missing"
            )

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

    # ── Signal: lifecycle method / class context ─────────────────────────
    # Only scored when extract_signals detected a lifecycle method (is_lifecycle=True).
    # Protocol/ABC membership is the strongest possible signal: these methods are
    # interface contracts, not implementation gaps.
    if is_lifecycle:
        if is_protocol_abc:
            # Protocol/ABC methods are contract declarations.
            # Push design-intent-stated strongly; genuinely-unknown to near zero.
            scores["design-intent-stated"] += 1.5
            scores["genuinely-unknown"] = max(0.0, scores["genuinely-unknown"] - 0.5)
            evidence["design-intent-stated"].append(
                "class inherits from Protocol/ABC — method is an interface contract"
            )
        elif not vars_assigned:
            # __init__ assigns no self.x = attributes: class body is unimplemented.
            scores["blocked-on-prerequisite"] += 0.6
            scores["genuinely-unknown"] += 0.2
            evidence["blocked-on-prerequisite"].append(
                "__init__ assigns no instance vars — class body not yet implemented"
            )
        # Use class sibling stubs as a stronger design-skeleton signal when
        # file-level siblings were sparse (lifecycle methods share a class).
        if class_siblings >= 3 and not is_protocol_abc:
            scores["blocked-on-prerequisite"] += 0.4
            evidence["blocked-on-prerequisite"].append(
                f"{class_siblings} sibling stub(s) in same file — design skeleton (class level)"
            )

    # ── Signal: config-layer FSM presence ───────────────────────────────
    # If a concept's FSM exists in config → supports design-intent-stated
    # (foundation laid, implementation pending).
    # If the concept is only referenced by another FSM's action (not its own
    # config) → blocked-on-prerequisite: config points to it, but the FSM
    # itself has no config file yet.
    config_fsm_present   = signals.get("config_fsm_present", [])
    config_fsm_referenced = signals.get("config_fsm_referenced", [])
    if config_fsm_referenced and not config_fsm_present:
        scores["blocked-on-prerequisite"] += 0.8
        refs = ", ".join(config_fsm_referenced[:3])
        evidence["blocked-on-prerequisite"].append(
            f"concept referenced by config FSM action(s) ({refs}) but has no config file — config-gated prerequisite"
        )
    elif config_fsm_present:
        scores["design-intent-stated"] += 0.3
        evidence["design-intent-stated"].append(
            f"concept FSM defined in config layer: {', '.join(config_fsm_present)}"
        )

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
    class_name  = args.get("class_name", "").strip() or None
    file_path   = args.get("file_path", "").strip() or None

    signals = extract_signals(oracle, symbol, class_name=class_name, file_path_hint=file_path)
    if "error" in signals:
        return f"classify_stub: {signals['error']}"

    hypotheses = score_hypotheses(signals)

    # ── Format output ────────────────────────────────────────────────────
    fp_short = (signals.get("file_path") or "").replace("\\", "/").split("/")[-1]
    line = signals.get("line_number") or "?"
    lifecycle_tag = " [lifecycle]" if signals.get("is_lifecycle") else ""
    proto_tag = " [Protocol/ABC]" if signals.get("is_protocol_or_abc") else ""
    out = [
        f"classify_stub: {symbol}{lifecycle_tag}{proto_tag}  ({fp_short}:{line})",
        f"file character: {signals['file_character']} | "
        f"body: {signals['body_shape']} | "
        f"callers: {signals['caller_count']} | "
        f"siblings: {signals['sibling_stub_count']}",
        "",
    ]
    if signals.get("is_protocol_or_abc"):
        out.append(
            "NOTE: class inherits from Protocol/ABC — this method is likely an "
            "interface contract, not an implementation gap. Verify before treating "
            "as a real stub."
        )
        out.append("")

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
