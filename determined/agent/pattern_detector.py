# determined/agent/pattern_detector.py
#
# Scoring-based pattern detection: each tool registers canonical example questions.
# Used as a fallback when regex detection returns None -- covers natural phrasings
# that regex misses without weakening hard structural guarantees.
#
# Adding a new tool: add an entry to TOOL_REGISTRY. The examples serve as
# documentation AND routing logic; no regex branch needed for coverage.

from __future__ import annotations
import re

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

# Common question-structure words that appear across all patterns and inflate scores.
_STOP_WORDS = {
    "what", "does", "do", "is", "are", "was", "were", "be", "been",
    "a", "an", "the", "this", "that", "it", "in", "of", "to", "for",
    "from", "with", "at", "by", "how", "where", "who", "which", "when",
    "why", "me", "my", "i", "you", "your", "we", "our", "can", "could",
    "should", "would", "will", "may", "might", "must", "have", "has",
    "had", "get", "got", "if", "and", "or", "not", "on", "up", "any",
}


def _word_set(text: str) -> set[str]:
    return set(re.findall(r'\w+', text.lower())) - _STOP_WORDS


def _overlap(question: str, example: str) -> float:
    """Fraction of meaningful question words that appear in the example."""
    q = _word_set(question)
    e = _word_set(example)
    if not q:
        return 0.0
    return len(q & e) / len(q)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: list[dict] = [
    {
        "name": "orient_to_codebase",
        "subject": None,
        "examples": [
            "give me an overview of this codebase",
            "what does this project do",
            "what does this tool do",
            "where do I start in this repo",
            "explain this codebase to me",
            "describe the system",
            "I am new here give me an overview",
            "never seen this code before help me understand it",
            "quick summary of what this repo does",
            "what is this project",
        ],
    },
    {
        "name": "blast_radius",
        "subject": "_extract_blast_target",
        "examples": [
            "what would break if I deleted this file",
            "what breaks if I remove this function",
            "impact of deleting this module",
            "what would happen if this file was deleted",
            "if I remove this function what breaks",
            "what depends on this file",
            "what would change if I removed this",
        ],
    },
    {
        "name": "trace_call_chain",
        "subject": None,
        "examples": [
            "trace the call chain from the HTTP handler to the database",
            "what is the path from the web route to the database",
            "walk the flow from the endpoint to storage",
            "which functions run between the route and the database insert",
            "follow the path from the request handler to db",
            "how does data flow from the route to the database",
            "what is the call path from the web route to storage",
        ],
    },
    {
        "name": "find_dead_code",
        "subject": None,
        "examples": [
            "find dead code in this codebase",
            "what code is never called",
            "show me unused functions",
            "what is unused in this codebase",
            "find unused functions and code",
            "what functions are never invoked",
        ],
    },
    {
        "name": "docstring_health",
        "subject": None,
        "examples": [
            "show me missing docstrings",
            "which functions lack documentation",
            "docstring coverage across the codebase",
            "what functions have no docstrings",
            "documentation gaps in this project",
            "stale or missing docstrings",
        ],
    },
    {
        "name": "gap_analysis",
        "subject": None,
        "examples": [
            "gap analysis of this codebase",
            "what is missing in this project",
            "analyze the gaps in this codebase",
            "what could bridge the gap between these modules",
            "what architectural gaps exist",
        ],
    },
    {
        "name": "assess_change_risk",
        "subject": "_extract_last_symbol",
        "examples": [
            "is it safe to change this function",
            "risk of changing this file",
            "should I modify this function",
            "impact of modifying this module",
            "how risky is it to refactor this",
        ],
    },
    {
        "name": "goal_intake",
        "subject": "_extract_goal",
        "examples": [
            "I want to add a new feature",
            "I am trying to implement this capability",
            "help me build a new endpoint",
            "how do I add this to the codebase",
            "I need to write a new module",
            "I want to extend this with new functionality",
        ],
    },
    {
        "name": "corpus_synthesis",
        "subject": None,
        "examples": [
            "full system analysis",
            "synthesize the corpus",
            "what is broken in this codebase",
            "architectural gaps and issues",
        ],
    },
]

# ---------------------------------------------------------------------------
# Subject extractors
# ---------------------------------------------------------------------------

_REMOVAL_VERBS = re.compile(
    r"(?:remov(?:e|ed|ing)|delet(?:e|ed|ing)|eliminat(?:e|ed|ing)|chang(?:e|ed|ing)|modif(?:y|ied|ying))\s+",
    re.I,
)
_GOAL_VERBS = re.compile(
    r"(?:add|build|implement|create|write|extend|make)\s+(.+)", re.I
)
_SYMBOL_RE = re.compile(r"[A-Za-z_][\w./\\]*")


def _extract_blast_target(question: str) -> str | None:
    m = _REMOVAL_VERBS.search(question)
    if m:
        rest = question[m.end():].split()[0] if question[m.end():].split() else None
        if rest:
            return rest.strip("'\"")
    # fallback: last symbol-like token
    tokens = _SYMBOL_RE.findall(question)
    return tokens[-1] if tokens else None


def _extract_last_symbol(question: str) -> str | None:
    tokens = _SYMBOL_RE.findall(question)
    # skip common noise words at the end
    noise = {"me", "it", "this", "that", "the", "a", "an"}
    for tok in reversed(tokens):
        if tok.lower() not in noise:
            return tok
    return tokens[-1] if tokens else None


def _extract_goal(question: str) -> str | None:
    m = _GOAL_VERBS.search(question)
    return m.group(1).strip() if m else None


_EXTRACTORS = {
    "_extract_blast_target": _extract_blast_target,
    "_extract_last_symbol": _extract_last_symbol,
    "_extract_goal": _extract_goal,
}

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_by_score(
    question: str,
    threshold: float = 0.35,
) -> tuple[str | None, object]:
    """
    Score question against canonical examples for each tool.
    Returns (pattern_name, subject) if best score >= threshold, else (None, None).
    Subject extraction uses the tool's registered extractor, applied to the
    original question text so proper nouns and filenames survive.
    """
    best_name: str | None = None
    best_score: float = 0.0

    for tool in TOOL_REGISTRY:
        score = max(_overlap(question, ex) for ex in tool["examples"])
        if score > best_score:
            best_score = score
            best_name = tool["name"]

    if best_score < threshold or best_name is None:
        return None, None

    # Extract subject using the tool's registered extractor
    tool_def = next(t for t in TOOL_REGISTRY if t["name"] == best_name)
    extractor_key = tool_def.get("subject")
    if extractor_key is None:
        subject = None
    elif extractor_key in _EXTRACTORS:
        subject = _EXTRACTORS[extractor_key](question)
    else:
        subject = None

    return best_name, subject
