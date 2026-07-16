# determined/agent/claim_verifier.py
#
# Technique 1 of RM21: verification loops.
#
# After the ASSEMBLE phase produces an answer, extract verifiable structural
# claims and check them against the corpus DB.  If any claim is wrong, return
# corrections so the caller can re-assemble once with the facts corrected.
#
# Only checks deterministic structural facts (call edges, callers, class methods).
# Design-constraint claims are handled by evaluate_claim / check_design_violations.

from __future__ import annotations

import json
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
    kind: str       # CALLS | NO_CALLERS | HAS_METHOD
    subject: str    # symbol the claim is about
    object_: str = ""  # for CALLS: callee; for HAS_METHOD: the method name


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

# "X has a `search` method"  /  "X's `search` method"  /  "class X implements search"
# Returns (class_name, method_name) groups.
_HAS_METHOD_PATS = [
    re.compile(r'\b(\w+)\s+has\s+(?:a\s+)?[`\'"]?(\w+)[`\'"]?\s+method\b', re.I),
    re.compile(r"\b(\w+)'s\s+[`'\"]?(\w+)[`'\"]?\s+method\b", re.I),
    re.compile(r'\bclass\s+(\w+)\s+(?:implements|defines|provides)\s+(?:a\s+)?[`\'"]?(\w+)[`\'"]?\b', re.I),
    re.compile(r'\b(\w+)\.(\w+)\s*\(\)', re.I),  # "X.method()" in prose
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

    for pat in _HAS_METHOD_PATS:
        for m in pat.finditer(answer):
            cls_name, method_name = m.group(1), m.group(2)
            if _is_valid_symbol(cls_name) and _is_valid_symbol(method_name):
                _add("HAS_METHOD", cls_name, method_name)

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
            # Check if subject exists in the corpus at all
            try:
                exists = conn.execute(
                    "SELECT 1 FROM functions WHERE name = ? LIMIT 1", (claim.subject,)
                ).fetchone()
                if not exists:
                    return Correction(
                        original_claim=f"{claim.subject} calls {claim.object_}",
                        actual_fact=f"{claim.subject} does not exist in this codebase",
                        correction_text=(
                            f"CORRECTION: '{claim.subject}' does not exist in this codebase. "
                            f"Do not reference it."
                        ),
                    )
            except Exception:
                pass
            return None  # symbol exists but no outgoing edges, or table missing — can't refute

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

    elif claim.kind == "HAS_METHOD":
        row = conn.execute(
            "SELECT methods_json FROM classes WHERE name = ? LIMIT 1",
            (claim.subject,),
        ).fetchone()
        if row is None:
            # Check if the class name exists as a function at all
            try:
                fn_exists = conn.execute(
                    "SELECT 1 FROM functions WHERE name = ? LIMIT 1", (claim.subject,)
                ).fetchone()
                if not fn_exists:
                    return Correction(
                        original_claim=f"{claim.subject} has method {claim.object_}",
                        actual_fact=f"{claim.subject} does not exist in this codebase",
                        correction_text=(
                            f"CORRECTION: '{claim.subject}' does not exist in this codebase. "
                            f"Do not reference it."
                        ),
                    )
            except Exception:
                pass
            return None  # symbol not a known class, or table missing — can't refute

        try:
            methods = json.loads(row[0] or "[]")
        except (json.JSONDecodeError, TypeError):
            return None  # unparseable — don't emit a false correction

        if claim.object_.lower() in [m.lower() for m in methods]:
            return None  # method exists

        return Correction(
            original_claim=f"{claim.subject} has method {claim.object_}",
            actual_fact=f"{claim.subject} methods: {', '.join(methods[:6]) or '(none recorded)'}",
            correction_text=(
                f"CORRECTION: '{claim.subject}' does not have a '{claim.object_}' method. "
                f"Recorded methods: {', '.join(methods[:5]) or '(none)'}."
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
