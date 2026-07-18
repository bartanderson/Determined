# determined/agent/evaluator.py
#
# The evaluate kernel: the fundamental reasoning primitive.
#
# evaluate(claim, evidence_items, question) -> Judgment
#
# Takes one small observation (claim), a pre-selected list of relevant norms
# or patterns (evidence_items), and a question that frames what kind of
# relationship to look for.  Makes one focused LLM call and returns a
# structured Judgment.
#
# retrieve_evidence(query, conn, surfaces, top_n, threshold) -> list[str]
#
# Cosine-searches one or more named knowledge surfaces in the corpus DB and
# returns the top matching content strings.  This is the "Situate" step;
# callers compose it with evaluate() to get Observe -> Situate -> Evaluate.
#
# Both functions are independently testable: evaluate() accepts an optional
# llm_fn override so tests can inject a stub; retrieve_evidence() works on
# any sqlite3 connection with the standard schema.

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Judgment dataclass
# ---------------------------------------------------------------------------

VALID_VERDICTS = frozenset({
    "VIOLATES",        # observation contradicts a norm
    "CONFIRMS",        # observation is consistent with / expected by a norm
    "EXPLAINS",        # a norm explains why the observation exists
    "MATCHES_PATTERN", # observation fits a named structural pattern
    "UNRELATED",       # no meaningful relationship found
    "UNCERTAIN",       # model could not reach a verdict
})


@dataclass
class Judgment:
    verdict: str                 # one of VALID_VERDICTS
    reasoning: str               # one sentence: why this verdict
    confidence: float            # 0.0 – 1.0; model's self-reported certainty
    evidence_used: list[str] = field(default_factory=list)  # which evidence items drove the verdict

    def __post_init__(self):
        if self.verdict not in VALID_VERDICTS:
            self.verdict = "UNCERTAIN"
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def __str__(self) -> str:
        conf_pct = int(self.confidence * 100)
        evid = f"  Evidence: {self.evidence_used[0][:80]}" if self.evidence_used else ""
        return f"[{self.verdict}] ({conf_pct}%) {self.reasoning}{chr(10) + evid if evid else ''}"


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_PROMPT = """\
You are a code-analysis assistant. Answer with a single JSON object — no prose, no markdown fences.

CLAIM: {claim}

QUESTION: {question}

EVIDENCE ({n} items):
{evidence_block}

Reply with ONLY this JSON (no other text):
{{
  "verdict": "<one of: VIOLATES, CONFIRMS, EXPLAINS, MATCHES_PATTERN, UNRELATED, UNCERTAIN>",
  "reasoning": "<one sentence explaining the verdict>",
  "confidence": <0.0 to 1.0>,
  "evidence_indices": [<0-based indices of the evidence items that drove the verdict>]
}}"""


# ---------------------------------------------------------------------------
# EvalRequest — the unit of work for evaluate() and MCTS
# ---------------------------------------------------------------------------

@dataclass
class EvalRequest:
    """
    A fully-specified evaluation request, ready to send to the LLM.

    Separating construction (build_eval_request) from execution
    (execute_eval_request) lets MCTS generate and score candidate
    requests without committing to LLM calls.
    """
    claim: str
    question: str
    evidence_items: list[str]
    prompt: str          # pre-rendered, ready to pass to llm_fn


# ---------------------------------------------------------------------------
# build_eval_request() — pure, no LLM call
# ---------------------------------------------------------------------------

def build_eval_request(
    claim: str,
    evidence_items: list[str],
    question: str,
) -> EvalRequest:
    """
    Build an EvalRequest from inputs — no LLM call.

    Pure and independently testable.  MCTS uses this to generate
    candidate evaluation nodes before deciding which to score.

    Does not enforce guards (empty claim, no evidence); call evaluate()
    for guarded convenience, or enforce guards in the caller.
    """
    evidence_block = "\n".join(
        f"[{i}] {item[:300]}" for i, item in enumerate(evidence_items)
    )
    prompt = _PROMPT.format(
        claim=claim.strip(),
        question=question.strip(),
        n=len(evidence_items),
        evidence_block=evidence_block,
    )
    return EvalRequest(
        claim=claim,
        question=question,
        evidence_items=evidence_items,
        prompt=prompt,
    )


# ---------------------------------------------------------------------------
# execute_eval_request() — LLM call + parse
# ---------------------------------------------------------------------------

def execute_eval_request(
    request: EvalRequest,
    llm_fn: Optional[Callable[[str], Optional[str]]] = None,
) -> Judgment:
    """
    Execute an EvalRequest: call the LLM and parse the response.

    MCTS uses this to score candidate nodes.  Raises RuntimeError if
    the LLM returns no output (llama-server not running).
    """
    if llm_fn is None:
        from determined.agent import llm_client
        def llm_fn(p: str) -> str | None:
            return llm_client.chat([{"role": "user", "content": p}])

    raw = llm_fn(request.prompt)
    if not raw:
        raise RuntimeError("evaluator.evaluate: LLM returned no output (is llama-server running?)")

    return _parse_judgment(raw, request.evidence_items)


# ---------------------------------------------------------------------------
# evaluate() — guarded convenience wrapper
# ---------------------------------------------------------------------------

def evaluate(
    claim: str,
    evidence_items: list[str],
    question: str,
    llm_fn: Optional[Callable[[str], Optional[str]]] = None,
) -> Judgment:
    """
    Core reasoning kernel.  Convenience wrapper: guards → build → execute.

    Args:
        claim:          A single, specific observation about the codebase.
        evidence_items: Pre-selected norms, constraints, or patterns relevant
                        to the claim.  Retrieve via retrieve_evidence().
        question:       Frames what relationship to look for.
        llm_fn:         Optional override for the LLM call (for testing).
                        Must accept a prompt str and return str | None.

    Returns:
        A Judgment.  On LLM failure, raises RuntimeError.  On parse error,
        returns Judgment(UNCERTAIN) so callers can always rely on the type.

    For MCTS or batched use, call build_eval_request() + execute_eval_request()
    directly to control when the LLM call happens.
    """
    if not claim.strip():
        return Judgment(verdict="UNCERTAIN", reasoning="empty claim", confidence=0.0)

    if not evidence_items:
        return Judgment(
            verdict="UNRELATED",
            reasoning="no evidence items provided; cannot evaluate",
            confidence=0.0,
        )

    return execute_eval_request(build_eval_request(claim, evidence_items, question), llm_fn)


# ---------------------------------------------------------------------------
# retrieve_evidence() and retrieve_evidence_scored()
# ---------------------------------------------------------------------------

def retrieve_evidence_scored(
    query: str,
    conn: sqlite3.Connection,
    surfaces: list[str] = ("design_note",),
    top_n: int = 5,
    threshold: float = 0.25,
    extra_items: list[str] = (),
) -> list[tuple[float, str]]:
    """
    Cosine-search knowledge surfaces and return (score, content) pairs.

    Args:
        query:       Natural language description of the claim being evaluated.
        conn:        sqlite3 connection to the corpus DB.
        surfaces:    Which `kind` values in knowledge_artifacts to search.
        top_n:       Maximum number of items to return.
        threshold:   Minimum cosine similarity to include.
        extra_items: Additional content strings to score alongside DB results
                     (e.g. SOTS tenet texts that live outside knowledge_artifacts).

    Returns:
        List of (score, content) tuples, best-match first.
    """
    from determined.oracle.embedding_model import embed_text, cosine_similarity

    placeholders = ",".join("?" * len(surfaces))
    try:
        rows = conn.execute(
            f"SELECT content FROM knowledge_artifacts WHERE kind IN ({placeholders}) "
            f"AND content IS NOT NULL AND content != ''",
            list(surfaces),
        ).fetchall()
    except Exception as exc:
        logger.warning("retrieve_evidence: DB query failed: %s", exc)
        rows = []

    contents = [r[0] for r in rows] + list(extra_items)
    if not contents:
        return []

    try:
        q_vec = embed_text(query)
        scored = []
        for content in contents:
            c_vec = embed_text(content[:400])
            sim = cosine_similarity(q_vec, c_vec)
            if sim >= threshold:
                scored.append((sim, content))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_n]
    except Exception as exc:
        logger.warning("retrieve_evidence: embedding failed: %s", exc)
        return []


def retrieve_evidence(
    query: str,
    conn: sqlite3.Connection,
    surfaces: list[str] = ("design_note",),
    top_n: int = 5,
    threshold: float = 0.25,
    extra_items: list[str] = (),
) -> list[str]:
    """
    Cosine-search named knowledge surfaces in the corpus DB.

    Returns content strings only (scores stripped).  Use retrieve_evidence_scored()
    when scores are needed (e.g. for display in violation reports).

    Args:
        query:       Natural language description of the claim being evaluated.
        conn:        sqlite3 connection to the corpus DB.
        surfaces:    Which `kind` values in knowledge_artifacts to search.
                     Common values: "design_note", "pattern", "role".
        top_n:       Maximum number of items to return.
        threshold:   Minimum cosine similarity to include.
        extra_items: Additional content strings to score alongside DB results.

    Returns:
        List of content strings, best-match first.  Pass directly to evaluate().
    """
    return [c for _, c in retrieve_evidence_scored(query, conn, surfaces, top_n, threshold, extra_items)]


# ---------------------------------------------------------------------------
# collect_symbol_context()
# ---------------------------------------------------------------------------

def collect_symbol_context(conn: sqlite3.Connection, symbol: str) -> str:
    """
    Build a rich context string describing a symbol.

    Pulls name, file stem, docstring, param names, callers, and callees
    directly from the corpus DB.  The result is suitable as the `claim`
    argument to evaluate() or as the `query` argument to retrieve_evidence().

    Uses only a sqlite3.Connection so this function stays importable without
    pulling in agent_tools (avoids circular imports).
    """
    import json as _json

    sym_row = conn.execute(
        "SELECT file_path FROM symbols WHERE name = ? LIMIT 1", (symbol,)
    ).fetchone()
    file_stem = ""
    if sym_row and sym_row[0]:
        file_stem = sym_row[0].replace("\\", "/").split("/")[-1].replace(".py", "")

    docstring = ""
    row = conn.execute(
        "SELECT docstring FROM functions WHERE name = ? LIMIT 1", (symbol,)
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT docstring FROM classes WHERE name = ? LIMIT 1", (symbol,)
        ).fetchone()
    if row and row[0]:
        docstring = row[0][:300]

    param_names: list[str] = []
    param_row = conn.execute(
        "SELECT param_types_json FROM functions WHERE name = ? LIMIT 1", (symbol,)
    ).fetchone()
    if param_row and param_row[0]:
        try:
            params = _json.loads(param_row[0])
            param_names = [
                (k.get("name", str(k)) if isinstance(k, dict) else k)
                for k in params
                if (k.get("name") if isinstance(k, dict) else k) not in ("self", "cls")
            ]
        except Exception:
            pass

    _NOISE_PREFIXES = ("flask.", "builtins.", "os.", "sys.", "re.", "json.", "typing.")

    def _format_edge(name: str) -> str:
        # Keep module prefix for project-local symbols; strip for external noise.
        if any(name.startswith(p) for p in _NOISE_PREFIXES):
            return name.rsplit(".", 1)[-1]
        return name

    callers = [_format_edge(r[0]) for r in conn.execute(
        "SELECT DISTINCT caller FROM graph_edges WHERE callee = ? LIMIT 8", (symbol,)
    ).fetchall()]
    callees = [_format_edge(r[0]) for r in conn.execute(
        "SELECT DISTINCT callee FROM graph_edges WHERE caller = ? LIMIT 16", (symbol,)
    ).fetchall()]

    parts = [f"function: {symbol}"]
    if file_stem:
        parts.append(f"file: {file_stem}")
    if docstring:
        parts.append(docstring)
    if param_names:
        parts.append(f"params: {', '.join(param_names[:6])}")
    if callers:
        parts.append(f"called_by: {', '.join(callers)}")
    if callees:
        parts.append(f"calls: {', '.join(callees)}")

    return "  ".join(parts)


# ---------------------------------------------------------------------------
# collect_subgraph_context()
# ---------------------------------------------------------------------------

def collect_subgraph_context(conn: sqlite3.Connection, subgraph: dict) -> str:
    """
    Build a context string describing a call subgraph for pattern matching.

    Args:
        conn:     sqlite3 connection (reserved for future per-node lookups).
        subgraph: dict with 'nodes' (set[str]) and 'edges' (list[tuple[str,str]])
                  as returned by graph_utils.subgraph_around().

    Returns a string suitable as the `claim` argument to evaluate() or as the
    `query` argument to retrieve_evidence().
    """
    nodes = list(subgraph.get("nodes", set()))
    edges = list(subgraph.get("edges", []))

    if not nodes:
        return "(empty subgraph)"

    has_incoming = {b for a, b in edges}
    has_outgoing = {a for a, b in edges}
    entry_points = [n for n in nodes if n not in has_incoming and n in has_outgoing]
    terminals    = [n for n in nodes if n not in has_outgoing]
    short_names  = [n.rsplit(".", 1)[-1] for n in nodes]

    parts = [
        f"subgraph: {len(nodes)} nodes, {len(edges)} edges",
        f"symbols: {', '.join(short_names[:12])}",
    ]
    if entry_points:
        parts.append(f"entry_points: {', '.join(n.rsplit('.', 1)[-1] for n in entry_points[:4])}")
    if terminals:
        parts.append(f"terminals: {', '.join(n.rsplit('.', 1)[-1] for n in terminals[:4])}")

    avg_out = len(edges) / len(nodes) if nodes else 0
    if avg_out <= 1.2 and len(entry_points) == 1:
        parts.append("topology: linear chain")
    elif avg_out > 2.0:
        parts.append("topology: high branching factor")
    elif len(terminals) > len(nodes) * 0.5:
        parts.append("topology: convergent")

    return "  ".join(parts)


# ---------------------------------------------------------------------------
# Internal: parse LLM output -> Judgment
# ---------------------------------------------------------------------------

def _parse_judgment(raw: str, evidence_items: list[str]) -> Judgment:
    """
    Extract a Judgment from the LLM's raw text output.
    Tries strict JSON parse first, then a lenient regex fallback.
    Returns UNCERTAIN if both fail.
    """
    # Strip any accidental markdown fences
    text = raw.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)

    # Attempt 1: full JSON parse
    try:
        data = json.loads(text)
        verdict = str(data.get("verdict", "UNCERTAIN")).upper().strip()
        reasoning = str(data.get("reasoning", "")).strip() or "no reasoning provided"
        confidence = float(data.get("confidence", 0.5))
        indices = data.get("evidence_indices", [])
        used = [evidence_items[i] for i in indices if isinstance(i, int) and 0 <= i < len(evidence_items)]
        return Judgment(verdict=verdict, reasoning=reasoning, confidence=confidence, evidence_used=used)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass

    # Attempt 2: regex extraction for malformed but partial JSON
    verdict_match = re.search(r'"verdict"\s*:\s*"([A-Z_]+)"', raw)
    reason_match  = re.search(r'"reasoning"\s*:\s*"([^"]+)"', raw)
    conf_match    = re.search(r'"confidence"\s*:\s*([0-9.]+)', raw)

    if verdict_match:
        return Judgment(
            verdict=verdict_match.group(1).upper(),
            reasoning=reason_match.group(1) if reason_match else "parse fallback",
            confidence=float(conf_match.group(1)) if conf_match else 0.4,
        )

    logger.warning("evaluator._parse_judgment: could not parse LLM output: %r", raw[:200])
    return Judgment(verdict="UNCERTAIN", reasoning="could not parse LLM response", confidence=0.0)
