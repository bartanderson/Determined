# determined/agent/claim_verifier.py
#
# Technique 1 of RM21: verification loops.
#
# After the ASSEMBLE phase produces an answer, extract verifiable structural
# claims and check them against the corpus DB.  If any claim is wrong, return
# corrections so the caller can re-assemble once with the facts corrected.
#
# Only checks deterministic structural facts (call edges, callers).
# Design-constraint claims are handled by evaluate_claim / check_design_violations.

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Claim and Correction types
# ---------------------------------------------------------------------------

@dataclass
class Claim:
    text: str       # the phrase in the answer that asserts the claim
    kind: str       # CALLS | NO_CALLERS
    subject: str    # symbol the claim is about
    object_: str = ""  # for CALLS: the callee being asserted


@dataclass
class Correction:
    original_claim: str
    actual_fact: str
    correction_text: str   # one sentence, ready to prepend to facts block


# ---------------------------------------------------------------------------
# Regex patterns for claim extraction
# ---------------------------------------------------------------------------

# "X calls Y"  /  "X invokes Y"  /  "X calls into Y"
_CALLS_PATS = [
    re.compile(r'\b(\w+)\s+calls?\s+into\s+(\w+)', re.I),
    re.compile(r'\b(\w+)\s+calls?\s+(\w+)', re.I),
    re.compile(r'\b(\w+)\s+invokes?\s+(\w+)', re.I),
]

# "X has no callers"  /  "X is not called"  /  "no callers of X"
_NO_CALLER_PATS = [
    re.compile(r'\b(\w+)\s+has\s+no\s+(?:direct\s+)?callers?', re.I),
    re.compile(r'\b(\w+)\s+is\s+not\s+called\b', re.I),
    re.compile(r'no\s+(?:direct\s+)?callers?\s+(?:of|for)\s+(\w+)', re.I),
    re.compile(r'nothing\s+calls?\s+(\w+)', re.I),
    re.compile(r'\b(\w+)\s+(?:has\s+)?no\s+callers?\b', re.I),
]

# Short common words the model uses as connectors — skip these as symbol names
_NOISE_WORDS = frozenset({
    "it", "this", "that", "the", "and", "or", "not", "also", "which",
    "then", "when", "if", "is", "are", "was", "were", "be", "a", "an",
})


def _is_valid_symbol(name: str) -> bool:
    return len(name) >= 3 and name.lower() not in _NOISE_WORDS


# ---------------------------------------------------------------------------
# extract_claims
# ---------------------------------------------------------------------------

def extract_claims(answer: str) -> list[Claim]:
    """
    Regex-scan an assembled answer and return a list of verifiable structural
    claims.  May include duplicates — verify_answer deduplicates by symbol.
    """
    claims: list[Claim] = []
    seen: set[tuple] = set()

    def _add(kind: str, subject: str, object_: str = "") -> None:
        key = (kind, subject.lower(), object_.lower())
        if key not in seen:
            seen.add(key)
            claims.append(Claim(text="", kind=kind, subject=subject, object_=object_))

    for pat in _CALLS_PATS:
        for m in pat.finditer(answer):
            subj, obj = m.group(1), m.group(2)
            if _is_valid_symbol(subj) and _is_valid_symbol(obj):
                _add("CALLS", subj, obj)

    for pat in _NO_CALLER_PATS:
        for m in pat.finditer(answer):
            sym = m.group(1)
            if _is_valid_symbol(sym):
                _add("NO_CALLERS", sym)

    return claims


# ---------------------------------------------------------------------------
# verify_claim
# ---------------------------------------------------------------------------

def verify_claim(claim: Claim, conn: sqlite3.Connection) -> Optional[Correction]:
    """
    Check one claim against the corpus DB.
    Returns a Correction if the claim is wrong, None if it checks out.
    """
    if claim.kind == "CALLS":
        # Check whether the asserted edge actually exists
        row = conn.execute(
            "SELECT 1 FROM graph_edges WHERE caller = ? AND callee = ? LIMIT 1",
            (claim.subject, claim.object_),
        ).fetchone()
        if row:
            return None  # claim is correct

        # Edge missing — find what subject actually calls (up to 4)
        actual = [r[0] for r in conn.execute(
            "SELECT DISTINCT callee FROM graph_edges WHERE caller = ? LIMIT 4",
            (claim.subject,),
        ).fetchall()]
        if not actual:
            return None  # no edges at all — can't refute confidently

        return Correction(
            original_claim=f"{claim.subject} calls {claim.object_}",
            actual_fact=f"{claim.subject} calls: {', '.join(actual)}",
            correction_text=(
                f"CORRECTION: '{claim.subject}' does not call '{claim.object_}'. "
                f"Actual callees: {', '.join(actual[:3])}."
            ),
        )

    elif claim.kind == "NO_CALLERS":
        callers = [r[0] for r in conn.execute(
            "SELECT DISTINCT caller FROM graph_edges WHERE callee = ? LIMIT 4",
            (claim.subject,),
        ).fetchall()]
        if not callers:
            return None  # claim is correct — no callers found

        return Correction(
            original_claim=f"{claim.subject} has no callers",
            actual_fact=f"{claim.subject} callers: {', '.join(callers)}",
            correction_text=(
                f"CORRECTION: '{claim.subject}' IS called. "
                f"Direct callers: {', '.join(callers[:3])}."
            ),
        )

    return None


# ---------------------------------------------------------------------------
# verify_answer / build_correction_block
# ---------------------------------------------------------------------------

def verify_answer(answer: str, conn: sqlite3.Connection) -> list[Correction]:
    """
    Extract claims from an assembled answer and verify each against the DB.
    Returns only the corrections (claims that are wrong).
    """
    corrections = []
    for claim in extract_claims(answer):
        correction = verify_claim(claim, conn)
        if correction:
            corrections.append(correction)
    return corrections


def build_correction_block(corrections: list[Correction]) -> str:
    """
    Build a text block to prepend to the facts for re-assembly.
    """
    lines = ["\nFACT CORRECTIONS (your previous answer had errors — fix these):"]
    for c in corrections:
        lines.append(f"  - {c.correction_text}")
    return "\n".join(lines)
