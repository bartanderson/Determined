# tools/analysis/truth/query_compiler.py
# CLAUDE-EDIT 2026-06-16: full rewrite of Layer 4 compiler. Was a rule-based
# stub only. Now tries local Ollama (llama3.2:3b @ localhost:11434/api/generate)
# first, validates output through QueryPlanner, falls back to the original
# rule-based intent->AST table on any failure (connection error, timeout,
# bad JSON, invalid view/combine). Does NOT use Anthropic API - local only.
#
# LAYER 4 - QUERY COMPILER
#
# Translates natural language -> valid Query AST.
#
# Two modes (selected automatically):
#   1. Ollama mode  - calls llama3.2:3b via local Ollama API.
#                     The model is given the closed algebra spec and must
#                     emit only valid JSON. Output is validated through
#                     QueryPlanner before use. Falls back to rule-based
#                     on any failure (service down, invalid JSON, invalid AST).
#
#   2. Rule-based fallback - deterministic intent->AST table.
#                     Always available. Used when Ollama is unreachable or
#                     the model output fails validation.
#
# CONTRACT (from Truth Kernel spec):
#   INPUT:  natural language text + detected intent
#   OUTPUT: valid QueryPlan (Select / Combine only, from registry)
#   NEVER:  invents new views, emits invalid AST, raises to caller

import json
import logging
import re

from determined.truth.query_ast import Select, Combine, Filter
from determined.truth.query_plan import QueryPlan, QueryPlanner, QuerySemanticsRegistry

logger = logging.getLogger(__name__)

_registry = QuerySemanticsRegistry()
_planner = QueryPlanner(_registry)

# =========================================================
# CLOSED-WORLD SPEC (fed verbatim to the model)
# =========================================================
# CLAUDE-EDIT 2026-06-17: the VIEWS/METRICS/COMBINES sections below used
# to be a hand-typed copy of QueryPlan.VALID_METRICS / QuerySemanticsRegistry
# .VALID_COMBINES - two sources of truth for the same facts, with nothing
# stopping them from silently drifting apart (a future metric/combine
# added to the registry just wouldn't be offered to the model; a typo'd
# copy here could offer the model something the registry would then
# reject). Generated from the registry instead, so the prompt the model
# sees and the rules QueryPlanner actually enforces can never disagree.
# Found while auditing the full Select/Combine shape contract after the
# Windows-only ROLE-view bug (REFACTOR OPS BOARD.md 2026-06-17).

def _build_algebra_spec() -> str:
    views_line = ", ".join(sorted(QueryPlan.VALID_METRICS))

    metrics_lines = "\n".join(
        f"  {view}: {', '.join(sorted(metrics))}"
        for view, metrics in sorted(QueryPlan.VALID_METRICS.items())
    )

    combines_lines = "\n".join(
        f"  ({left}, {right})"
        for left, right in sorted(QuerySemanticsRegistry.VALID_COMBINES)
    )

    return f"""\
You are a query compiler for a closed-world code analysis system.
Your ONLY job is to translate a natural language question into a JSON query AST.
Output JSON only. No explanation. No markdown. No extra keys.

VALID VIEWS: {views_line}

VALID METRICS PER VIEW:
{metrics_lines}

VALID COMBINE PAIRS (unordered):
{combines_lines}

QUERY TYPES:
  Select(view)           -> {{"type": "select", "view": "VIEW"}}
  Select(view, metric)   -> {{"type": "select", "view": "VIEW", "metric": "METRIC"}}
  Combine(left, right)   -> {{"type": "combine", "left": <node>, "right": <node>}}

MAPPING GUIDANCE:
  "what depends on X" / "who calls X" / "what breaks if X changes"
    -> {{"type":"combine","left":{{"type":"select","view":"STRUCTURE"}},"right":{{"type":"select","view":"INTEGRITY"}}}}

  "what does X call" / "show surface of X" / "forward dependencies"
    -> {{"type":"combine","left":{{"type":"select","view":"STRUCTURE"}},"right":{{"type":"select","view":"STABILITY"}}}}

  "show hotspots" / "most connected symbols"
    -> {{"type":"select","view":"STRUCTURE","metric":"hotspots"}}

  "system health" / "stability overview"
    -> {{"type":"combine","left":{{"type":"select","view":"STABILITY"}},"right":{{"type":"select","view":"INTEGRITY"}}}}

  "what is the purpose of X" / "why does X exist" / "what is the role of X"
  asked about a specific named file - the full ROLE view (no metric) and
  the "files" metric alone are both valid; prefer "files" when exactly
  one file is named, since it's the more precise answer to "this file":
    -> {{"type":"select","view":"ROLE","metric":"files"}}
  prefer the full view (no metric) for a question about the codebase's
  roles in general, not one named file:
    -> {{"type":"select","view":"ROLE"}}

  general / unclear
    -> {{"type":"select","view":"STRUCTURE"}}
"""


_ALGEBRA_SPEC = _build_algebra_spec()

# =========================================================
# RULE-BASED FALLBACK (always deterministic)
# =========================================================

_INTENT_TO_AST = {
    "impact_query":  lambda: Combine(Select("STRUCTURE"), Select("INTEGRITY")),
    "surface_query": lambda: Combine(Select("STRUCTURE"), Select("STABILITY")),
    "reverse_query": lambda: Combine(Select("STRUCTURE"), Select("INTEGRITY")),
    "general_query": lambda: Combine(Select("STABILITY"), Select("INTEGRITY")),
    # CLAUDE-EDIT 2026-06-16: per Truth.md Phase 3 Row 1 / Row 2 - routes
    # "purpose of file" style questions to the new ROLE view instead of
    # falling through to general_query's content-blind STABILITY+INTEGRITY
    # default. Select-only (not Combine): ROLE isn't in VALID_COMBINES yet,
    # since no question asked so far has needed it joined with anything.
    "role_query":    lambda: Select("ROLE"),
}

_INTENT_EXPLANATIONS = {
    "impact_query":  "STRUCTURE+INTEGRITY: who depends on this symbol, and are those callers healthy?",
    "surface_query": "STRUCTURE+STABILITY: what does this symbol call, and is that surface stable?",
    "reverse_query": "STRUCTURE+INTEGRITY: reverse dependency view with integrity check.",
    "general_query": "STABILITY+INTEGRITY: full diagnostic view of system health.",
    "role_query":    "ROLE: what kind of work does this file do, per the DB-backed responsibility classification.",
}

_DEFAULT_AST = lambda: Select("STRUCTURE")


def _rule_based_ast(intent: str):
    return _INTENT_TO_AST.get(intent, _DEFAULT_AST)()


# =========================================================
# SINGLE-NAMED-FILE SCOPING (deterministic, no AI required)
# =========================================================
# CLAUDE-EDIT 2026-06-17: closes a real bug Bart hit on his Windows
# machine - "what is the purpose of db_probe_toolsold.py" came back with
# the FULL unfiltered ROLE view (every file in the project), not just
# db_probe_toolsold.py. Root cause: truth/query_ast.py's Filter and
# truth/query_executor.py's _apply_filter were both fully implemented and
# already passing planner-validation tests, but NOTHING upstream ever
# constructed a Filter - not the Ollama prompt spec (_build_algebra_spec()
# only teaches Select/Combine), not the rule-based fallback table above.
# Select.filter has been None end-to-end since the algebra was built. Same
# "orphaned primitive" shape as the 2026-06-17 drift_signals fix (Truth.md
# Phase 3 Row 3) - the capability existed, nothing called it.
#
# This is deterministic on purpose, not an AI-compiler responsibility:
# Ollama was actually in the loop for the run that surfaced this (compiler
# explanation showed "[llama]") and still produced metric=None despite the
# prompt explicitly preferring metric="files" for one-named-file questions
# - prompt-following compliance isn't guaranteed at temperature 0 either,
# so the fix can't depend on the model getting it right. Regex + a
# planner-validated Filter is.

_FILENAME_PATTERN = re.compile(r"\b[\w\-./\\]+\.py\b")


def _extract_single_file_filter(text: str):
    """
    Returns Filter("file_path", "endswith", name) when exactly one *.py
    token appears in `text`, else None. "endswith" (not "==") because the
    question gives a bare filename ("db_probe_toolsold.py") while
    DBOracle stores full paths ("C:/Users/.../db_probe_toolsold.py") -
    exact equality would never match.
    """
    names = _FILENAME_PATTERN.findall(text)
    if len(names) == 1:
        return Filter("file_path", "endswith", names[0])
    return None


def _maybe_scope_to_named_file(plan: QueryPlan, text: str) -> QueryPlan:
    """
    If the compiled plan is a bare, unfiltered Select("ROLE", ...) and the
    question names exactly one file, rescope it to metric="files" + a
    file_path filter so the result is that file's entry, not every file.
    Re-validated through the planner, so this can never hand the executor
    an AST shape the registry wouldn't otherwise accept on its own.

    Scoped to ROLE only for now - it's the view the observed bug hit, and
    the only view with a "file_path" filter key registered
    (query_plan.py's VALID_FILTER_KEYS). Generalizing to other views needs
    their own filter-key vocabularies first, not just this function -
    documented as still-open in Truth Kernel Board.md.

    Only triggers when metric is ALSO None (the exact bug shape:
    Select('ROLE', metric=None, filter=None)) - if the compiler (Ollama or
    rule-based) already chose a specific metric like "totals", that was a
    deliberate choice this function should not silently override.
    """
    root = plan.root

    if not isinstance(root, Select):
        return plan
    if root.view != "ROLE" or root.metric is not None or root.filter is not None:
        return plan

    file_filter = _extract_single_file_filter(text)
    if file_filter is None:
        return plan

    return _planner.plan(Select("ROLE", metric="files", filter=file_filter))


# =========================================================
# JSON -> AST PARSER
# =========================================================

def _parse_ast_node(node: dict):
    """
    Recursively parse a JSON dict into a Select or Combine AST node.
    Raises ValueError on any structural problem.
    """
    t = node.get("type")
    if t == "select":
        view = node.get("view", "").upper()
        metric = node.get("metric")
        return Select(view, metric)
    elif t == "combine":
        left  = _parse_ast_node(node["left"])
        right = _parse_ast_node(node["right"])
        return Combine(left, right)
    else:
        raise ValueError(f"Unknown node type: {t!r}")


# =========================================================
# OLLAMA COMPILER CORE
# =========================================================

def _compile_via_llm(text: str, intent: str):
    """
    Call llama-server to produce a Query AST.
    Returns a validated QueryPlan, or None on any failure.
    """
    from determined.agent.llm_client import generate as _llm_generate
    prompt = (
        f"{_ALGEBRA_SPEC}\n\n"
        f"Natural language query: {text!r}\n"
        f"Detected intent: {intent!r}\n\n"
        "Output the query AST as JSON only."
    )

    try:
        raw = _llm_generate(prompt, timeout=10)
        if not raw:
            logger.debug("llama-server not reachable - using rule-based compiler")
            return None

        # strip markdown fences if the model added them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        node_dict = json.loads(raw)
        ast_node  = _parse_ast_node(node_dict)
        plan      = _planner.plan(ast_node)   # validates against registry
        return plan

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("llm compiler output invalid: %s", e)
        return None
    except Exception as e:
        logger.debug("llm compiler failed: %s - using rule-based compiler", e)
        return None
    except Exception as e:
        logger.warning("Ollama compiler unexpected failure: %s", e)
        return None


# =========================================================
# PUBLIC API
# =========================================================

def compile_query(intent: str, text: str = ""):
    """
    Translate intent (and optionally the raw NL text) into a QueryPlan.
    Tries Ollama first; falls back to rule-based table on any failure.
    Returns: QueryPlan (always valid, never raises)
    """
    if text:
        plan = _compile_via_llm(text, intent)
        if plan is not None:
            return _maybe_scope_to_named_file(plan, text)

    ast_node = _rule_based_ast(intent)
    plan = _planner.plan(ast_node)
    return _maybe_scope_to_named_file(plan, text)


def compile_and_explain(intent: str, text: str = "") -> dict:
    """
    Returns the compiled plan plus a human-readable explanation.
    """
    plan = None
    ai_used = False

    if text:
        plan = _compile_via_llm(text, intent)
        if plan is not None:
            ai_used = True

    if plan is None:
        ast_node = _rule_based_ast(intent)
        plan = _planner.plan(ast_node)

    plan = _maybe_scope_to_named_file(plan, text)

    explanation = _INTENT_EXPLANATIONS.get(intent, "Default structural projection.")
    if ai_used:
        explanation = f"[llama] {explanation}"

    return {
        "intent":      intent,
        "ast":         repr(plan.root),
        "explanation": explanation,
        "compiler":    "llama" if ai_used else "rule-based",
        "plan":        plan,
    }
