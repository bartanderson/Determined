# determined/agent/reasoning_engine.py
#
# Reasoning pipeline: Decomposer -> Router -> Synthesizer
# See docs/REASONING_MODEL.md for the full design.
#
# Public API:
#   decompose(question, symbol, conn) -> list[SubQuestion]
#   route(subq, oracle, conn)         -> Finding
#   synthesize(question, findings)    -> Recommendation
#   reason_about(question, symbol, oracle, conn) -> str

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SubQuestion:
    question: str
    route: str           # 'db' | 'evaluate'
    db_query_type: Optional[str] = None   # used when route='db'


@dataclass
class Finding:
    question: str
    answer: str
    source: str          # 'db:caller_count', 'evaluate', etc.
    confidence: float    # 1.0 for deterministic DB; model confidence for evaluate


@dataclass
class Recommendation:
    decision: str        # one-line recommendation
    confidence: float    # 0.0-1.0
    reasoning: str       # 2-4 sentences
    provenance: list[str] = field(default_factory=list)  # sub-questions that drove it


# ---------------------------------------------------------------------------
# Available query types — fed to the Decomposer so it knows what's possible
# ---------------------------------------------------------------------------

_AVAILABLE_QUERY_TYPES = """
DB query types (deterministic, no LLM):
  caller_count      - how many distinct callers does the symbol have?
  callee_count      - how many distinct callees does the symbol have?
  class_membership  - is the symbol defined inside a class (method)?
  sibling_pattern   - do other functions in the same file share this symbol's name pattern?
  import_coupling   - how many other files import the file this symbol lives in?
  is_stub           - is the symbol currently a stub (unimplemented)?

Evaluate routes (focused LLM judgment, one claim per call):
  sots_match        - which SOTS design tenets apply to this symbol/question?
  design_judgment   - given structural facts, what does design reasoning suggest?
"""

# ---------------------------------------------------------------------------
# R1 — Decomposer
# ---------------------------------------------------------------------------

_DECOMPOSE_PROMPT = """\
You are a code-analysis assistant. Your job is to break an architectural question into \
sub-questions that can each be answered by a single DB query or a single focused evaluation.

QUESTION: {question}

SYMBOL CONTEXT: {symbol_context}

AVAILABLE QUERY TYPES:
{available}

List 3-6 sub-questions that together answer the main question. \
For each, choose the best route (db or evaluate) and the db_query_type if applicable.

Reply with ONLY a JSON array — no prose, no markdown fences:
[
  {{"question": "<sub-question>", "route": "db", "db_query_type": "<type>"}},
  {{"question": "<sub-question>", "route": "evaluate", "db_query_type": null}}
]
"""


def decompose(
    question: str,
    symbol: str,
    conn: sqlite3.Connection,
) -> list[SubQuestion]:
    """
    R1 — Decomposer. Calls quality LLM to break the question into sub-questions.
    Falls back to a minimal default partition if the LLM is unavailable.
    """
    from determined.agent.evaluator import collect_symbol_context
    from determined.agent.llm_client import chat_quality, LLM_QUALITY_TIMEOUT

    sym_ctx = collect_symbol_context(conn, symbol) if symbol else "(no symbol specified)"

    prompt = _DECOMPOSE_PROMPT.format(
        question=question,
        symbol_context=sym_ctx,
        available=_AVAILABLE_QUERY_TYPES,
    )

    raw = chat_quality(
        [{"role": "user", "content": prompt}],
        timeout=LLM_QUALITY_TIMEOUT,
        max_tokens=600,
    )

    if raw:
        try:
            # Strip accidental markdown fences
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.rsplit("```", 1)[0]
            items = json.loads(text.strip())
            result = []
            for item in items:
                result.append(SubQuestion(
                    question=item["question"],
                    route=item.get("route", "evaluate"),
                    db_query_type=item.get("db_query_type"),
                ))
            if result:
                return result
        except Exception as e:
            logger.warning("decompose: parse failed (%s), using fallback", e)

    # Fallback: minimal structural partition
    logger.info("decompose: using fallback partition for '%s'", symbol)
    return [
        SubQuestion("How many callers does this symbol have?", "db", "caller_count"),
        SubQuestion("Is this symbol currently a stub?", "db", "is_stub"),
        SubQuestion("Is this symbol defined inside a class?", "db", "class_membership"),
        SubQuestion("What SOTS design tenets apply?", "evaluate", "sots_match"),
        SubQuestion("Given the structural facts, what does design reasoning suggest?", "evaluate", "design_judgment"),
    ]


# ---------------------------------------------------------------------------
# R2 — Router
# ---------------------------------------------------------------------------

def _db_caller_count(symbol: str, conn: sqlite3.Connection) -> Finding:
    row = conn.execute(
        "SELECT COUNT(DISTINCT caller) FROM graph_edges WHERE callee = ? OR callee LIKE '%.' || ?",
        (symbol, symbol),
    ).fetchone()
    count = row[0] if row else 0
    return Finding(
        question="How many distinct callers does this symbol have?",
        answer=f"{count} callers",
        source="db:caller_count",
        confidence=1.0,
    )


def _db_callee_count(symbol: str, conn: sqlite3.Connection) -> Finding:
    row = conn.execute(
        "SELECT COUNT(DISTINCT callee) FROM graph_edges WHERE caller = ?", (symbol,)
    ).fetchone()
    count = row[0] if row else 0
    return Finding(
        question="How many distinct callees does this symbol have?",
        answer=f"{count} callees",
        source="db:callee_count",
        confidence=1.0,
    )


def _db_class_membership(symbol: str, conn: sqlite3.Connection) -> Finding:
    row = conn.execute(
        "SELECT class_name FROM class_attributes WHERE attribute = ? LIMIT 1", (symbol,)
    ).fetchone()
    if row:
        answer = f"method on class '{row[0]}'"
    else:
        answer = "standalone function (not a class method)"
    return Finding(
        question="Is this symbol a class method?",
        answer=answer,
        source="db:class_membership",
        confidence=1.0,
    )


def _db_sibling_pattern(symbol: str, conn: sqlite3.Connection) -> Finding:
    row = conn.execute(
        "SELECT file_path FROM functions WHERE name = ? LIMIT 1", (symbol,)
    ).fetchone()
    if not row:
        return Finding(
            question="Do siblings in the same file share a naming pattern?",
            answer="symbol not found in functions table",
            source="db:sibling_pattern",
            confidence=1.0,
        )
    file_path = row[0]
    prefix = symbol.split("_")[0] if "_" in symbol else symbol[:4]
    siblings = conn.execute(
        "SELECT COUNT(*) FROM functions WHERE file_path = ? AND name LIKE ? AND name != ?",
        (file_path, f"{prefix}%", symbol),
    ).fetchone()[0]
    total = conn.execute(
        "SELECT COUNT(*) FROM functions WHERE file_path = ?", (file_path,)
    ).fetchone()[0]
    answer = f"{siblings} siblings share the '{prefix}*' prefix pattern out of {total} functions in file"
    return Finding(
        question="Do siblings in the same file share a naming pattern?",
        answer=answer,
        source="db:sibling_pattern",
        confidence=1.0,
    )


def _db_import_coupling(symbol: str, conn: sqlite3.Connection) -> Finding:
    row = conn.execute(
        "SELECT file_path FROM functions WHERE name = ? LIMIT 1", (symbol,)
    ).fetchone()
    if not row:
        return Finding(
            question="How many files import the module this symbol lives in?",
            answer="symbol not found",
            source="db:import_coupling",
            confidence=1.0,
        )
    file_path = row[0].replace("\\", "/").split("/")[-1].replace(".py", "")
    count_row = conn.execute(
        "SELECT COUNT(DISTINCT file_path) FROM imports WHERE module LIKE ?",
        (f"%{file_path}%",),
    ).fetchone()
    count = count_row[0] if count_row else 0
    return Finding(
        question="How many files import the module this symbol lives in?",
        answer=f"{count} files import the '{file_path}' module",
        source="db:import_coupling",
        confidence=1.0,
    )


def _db_is_stub(symbol: str, conn: sqlite3.Connection) -> Finding:
    row = conn.execute(
        "SELECT is_stub FROM functions WHERE name = ? LIMIT 1", (symbol,)
    ).fetchone()
    is_stub = bool(row and row[0]) if row else False
    return Finding(
        question="Is this symbol currently a stub?",
        answer="yes (stub — body is pass/raise NotImplemented or empty)" if is_stub else "no (has implementation)",
        source="db:is_stub",
        confidence=1.0,
    )


def _evaluate_route(
    subq: SubQuestion,
    symbol: str,
    conn: sqlite3.Connection,
) -> Finding:
    """Route to evaluate() kernel for semantic sub-questions."""
    from determined.agent.evaluator import (
        evaluate, collect_symbol_context, retrieve_evidence,
    )
    from determined.data.sots_loader import tenet_texts

    claim = collect_symbol_context(conn, symbol)
    surfaces = ["design_note"]
    extra = list(tenet_texts()) if subq.db_query_type == "sots_match" else []
    evidence = retrieve_evidence(claim, conn, surfaces=surfaces, top_n=5, extra_items=extra)

    if not evidence:
        return Finding(
            question=subq.question,
            answer="no design evidence found (run ingest_design_docs first)",
            source="evaluate:no_evidence",
            confidence=0.0,
        )

    try:
        j = evaluate(claim, evidence, subq.question)
        return Finding(
            question=subq.question,
            answer=f"{j.verdict}: {j.reasoning}",
            source="evaluate",
            confidence=j.confidence,
        )
    except RuntimeError as e:
        return Finding(
            question=subq.question,
            answer=f"LLM unavailable: {e}",
            source="evaluate:error",
            confidence=0.0,
        )


_DB_ROUTES = {
    "caller_count":    _db_caller_count,
    "callee_count":    _db_callee_count,
    "class_membership": _db_class_membership,
    "sibling_pattern": _db_sibling_pattern,
    "import_coupling": _db_import_coupling,
    "is_stub":         _db_is_stub,
}


def route(subq: SubQuestion, symbol: str, conn: sqlite3.Connection) -> Finding:
    """
    R2 — Router. Dispatches one sub-question to DB query or evaluate() call.
    """
    if subq.route == "db" and subq.db_query_type in _DB_ROUTES:
        fn = _DB_ROUTES[subq.db_query_type]
        return fn(symbol, conn)
    return _evaluate_route(subq, symbol, conn)


# ---------------------------------------------------------------------------
# R3 — Synthesizer
# ---------------------------------------------------------------------------

_SYNTHESIZE_PROMPT = """\
You are a software architect. Given concrete findings about a codebase symbol, \
produce a clear recommendation.

ORIGINAL QUESTION: {question}

FINDINGS:
{findings_block}

Reply with ONLY this JSON (no prose, no markdown fences):
{{
  "decision": "<one-line recommendation>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<2-4 sentences explaining the recommendation>",
  "key_findings": [<0-based indices of the findings that most drove this recommendation>]
}}
"""


def synthesize(question: str, findings: list[Finding]) -> Recommendation:
    """
    R3 — Synthesizer. Calls quality LLM to produce a recommendation from findings.
    Falls back to a structured summary if LLM is unavailable.
    """
    from determined.agent.llm_client import chat_quality, LLM_QUALITY_TIMEOUT

    findings_block = "\n".join(
        f"[{i}] ({f.source}, conf={f.confidence:.1f}) {f.question}\n    -> {f.answer}"
        for i, f in enumerate(findings)
    )

    prompt = _SYNTHESIZE_PROMPT.format(
        question=question,
        findings_block=findings_block,
    )

    raw = chat_quality(
        [{"role": "user", "content": prompt}],
        timeout=LLM_QUALITY_TIMEOUT,
        max_tokens=400,
    )

    if raw:
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.rsplit("```", 1)[0]
            data = json.loads(text.strip())
            key = data.get("key_findings", [])
            provenance = [findings[i].source for i in key if 0 <= i < len(findings)]
            return Recommendation(
                decision=data.get("decision", "(no decision)"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                provenance=provenance,
            )
        except Exception as e:
            logger.warning("synthesize: parse failed (%s), using fallback", e)

    # Fallback: deterministic summary
    high_conf = [f for f in findings if f.confidence >= 0.9]
    summary = "; ".join(f.answer for f in high_conf[:3]) if high_conf else "insufficient evidence"
    return Recommendation(
        decision="(LLM unavailable — see findings)",
        confidence=0.0,
        reasoning=f"Structural facts: {summary}",
        provenance=[f.source for f in high_conf[:3]],
    )


# ---------------------------------------------------------------------------
# reason_about — full pipeline
# ---------------------------------------------------------------------------

def reason_about(
    question: str,
    symbol: str,
    conn: sqlite3.Connection,
) -> str:
    """
    Full pipeline: Decompose -> Route (all sub-questions) -> Synthesize.
    Returns a formatted recommendation block.
    """
    # R1 — Decompose
    subquestions = decompose(question, symbol, conn)

    # R2 — Route each sub-question
    findings: list[Finding] = []
    for subq in subquestions:
        finding = route(subq, symbol, conn)
        findings.append(finding)

    # R3 — Synthesize
    rec = synthesize(question, findings)

    # Format output
    lines = [
        f"=== reason_about: {symbol or '(no symbol)'} ===",
        f"Question: {question}",
        "",
        "Sub-question findings:",
    ]
    for i, f in enumerate(findings):
        conf_pct = int(f.confidence * 100)
        lines.append(f"  [{i}] ({f.source}, {conf_pct}%) {f.question}")
        lines.append(f"      -> {f.answer}")

    lines.extend([
        "",
        "--- Recommendation ---",
        f"Decision:   {rec.decision}",
        f"Confidence: {int(rec.confidence * 100)}%",
        f"Reasoning:  {rec.reasoning}",
    ])
    if rec.provenance:
        lines.append(f"Driven by:  {', '.join(rec.provenance)}")

    return "\n".join(lines)
