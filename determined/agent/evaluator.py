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
# evaluate()
# ---------------------------------------------------------------------------

def evaluate(
    claim: str,
    evidence_items: list[str],
    question: str,
    llm_fn: Optional[Callable[[str], Optional[str]]] = None,
) -> Judgment:
    """
    Core reasoning kernel.

    Args:
        claim:          A single, specific observation about the codebase.
        evidence_items: Pre-selected norms, constraints, or patterns relevant
                        to the claim.  Retrieve via retrieve_evidence().
        question:       Frames what relationship to look for, e.g.
                        "Does this observation violate a documented constraint,
                        or is it intentional by design?"
        llm_fn:         Optional override for the LLM call (for testing).
                        Must accept a prompt str and return str | None.
                        Defaults to llm_client.generate().

    Returns:
        A Judgment.  On LLM failure or parse error, returns Judgment with
        verdict=UNCERTAIN and confidence=0.0 so callers can always rely on
        the return type.
    """
    if not claim.strip():
        return Judgment(verdict="UNCERTAIN", reasoning="empty claim", confidence=0.0)

    if not evidence_items:
        return Judgment(
            verdict="UNRELATED",
            reasoning="no evidence items provided; cannot evaluate",
            confidence=0.0,
        )

    evidence_block = "\n".join(
        f"[{i}] {item[:300]}" for i, item in enumerate(evidence_items)
    )

    prompt = _PROMPT.format(
        claim=claim.strip(),
        question=question.strip(),
        n=len(evidence_items),
        evidence_block=evidence_block,
    )

    if llm_fn is None:
        from determined.agent import llm_client
        # Use chat() not generate(): the prompt ends with '}' so a completion
        # model sees a finished JSON object and produces nothing.  Chat treats
        # the prompt as an instruction and responds to it.
        def llm_fn(p: str) -> str | None:
            return llm_client.chat([{"role": "user", "content": p}])

    raw = llm_fn(prompt)
    if not raw:
        raise RuntimeError("evaluator.evaluate: LLM returned no output (is llama-server running?)")

    return _parse_judgment(raw, evidence_items)


# ---------------------------------------------------------------------------
# retrieve_evidence()
# ---------------------------------------------------------------------------

def retrieve_evidence(
    query: str,
    conn: sqlite3.Connection,
    surfaces: list[str] = ("design_note",),
    top_n: int = 5,
    threshold: float = 0.25,
) -> list[str]:
    """
    Cosine-search named knowledge surfaces in the corpus DB.

    Args:
        query:    Natural language description of the claim being evaluated.
        conn:     sqlite3 connection to the corpus DB.
        surfaces: Which `kind` values in knowledge_artifacts to search.
                  Common values: "design_note", "pattern", "role".
        top_n:    Maximum number of items to return.
        threshold: Minimum cosine similarity to include.

    Returns:
        List of content strings (already trimmed), best-match first.
        Returns empty list if the embedding model is unavailable or the
        knowledge_artifacts table has no matching rows.
    """
    from determined.oracle.embedding_model import embed_text, cosine_similarity

    # Pull all content rows for the requested surface kinds
    placeholders = ",".join("?" * len(surfaces))
    try:
        rows = conn.execute(
            f"SELECT content FROM knowledge_artifacts WHERE kind IN ({placeholders}) "
            f"AND content IS NOT NULL AND content != ''",
            list(surfaces),
        ).fetchall()
    except Exception as exc:
        logger.warning("retrieve_evidence: DB query failed: %s", exc)
        return []

    if not rows:
        return []

    contents = [r[0] for r in rows]

    try:
        q_vec = embed_text(query)
        scored = []
        for content in contents:
            c_vec = embed_text(content[:400])
            sim = cosine_similarity(q_vec, c_vec)
            if sim >= threshold:
                scored.append((sim, content))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_n]]
    except Exception as exc:
        logger.warning("retrieve_evidence: embedding failed: %s", exc)
        return []


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
