"""
Design document discovery and rule extraction for any project.

Public functions:
  discover_docs(project_root)               -> list[DocFile]
  extract_rules(doc_path)                   -> list[DesignRule]
  extract_rules_llm(doc_path, heading, body, source_confidence) -> list[DesignRule]
  grade_doc(doc_file)                       -> str  (confidence level)
  detect_conflicts(rules)                   -> list[DesignRule]
  deduplicate(rules)                        -> list[DesignRule]

No assumptions about project layout, doc naming, or domain.

Confidence levels (carried on DocFile and DesignRule):
  authoritative  - explicit design doc with high constraint-signal density
  high           - design doc with moderate constraint language
  medium         - README, docstring, or decision log
  low            - minimal signal, inferred context
  conflicted     - multiple sources disagree; needs human review
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_LLM_TIMEOUT = 120

# Confidence ordering (higher = more trustworthy)
CONFIDENCE_RANK: dict[str, int] = {
    "inferred":      0,
    "low":           1,
    "medium":        2,
    "high":          3,
    "authoritative": 4,
    "conflicted":   -1,
}

# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class DocFile:
    path: str           # absolute path
    rel_path: str       # relative to project root
    size_bytes: int
    doc_type: str       # design | readme | changelog | notes | unknown
    heading_count: int
    constraint_score: float   # 0.0-1.0: fraction of lines with constraint language
    confidence: str = "medium"  # authoritative | high | medium | low
    mtime: float = 0.0


@dataclass
class DesignRule:
    subject: str        # system/component name this rule is about
    rule: str           # the extracted constraint text
    source_file: str    # relative path of the doc it came from
    source_heading: str # heading that contained the rule
    extraction: str     # "deterministic" | "llm" | "inferred"
    confidence: str = "medium"   # mirrors source DocFile confidence
    provenance: str = ""         # "{confidence}:{rel_path}:{extraction}"
    kind: str = "constraint"     # constraint | requirement | permission | intent


# ---------------------------------------------------------------------------
# Constraint language patterns
# ---------------------------------------------------------------------------

_CONSTRAINT_RE = re.compile(
    r"\b(must not|must|may not|shall not|shall|never|forbidden|only|required|"
    r"invariant|non-negotiable|always|prohibited|cannot|will not)\b",
    re.I,
)

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)", re.M)

# Doc type classification signals
_DOC_TYPE_SIGNALS: list[tuple[str, list[str]]] = [
    ("changelog", ["changelog", "change log", "release notes", "history", "## [", "### ["]),
    ("readme",    ["readme", "# getting started", "## installation", "## usage", "## quickstart"]),
    ("design",    ["design", "architect", "constitution", "constraint", "invariant",
                   "authority", "must not", "shall not", "intent", "principles"]),
    ("notes",     ["notes", "scratchpad", "todo", "brainstorm", "ideas"]),
]

# Files/dirs to skip regardless of extension
_SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".tox",
              "dist", "build", ".mypy_cache", ".pytest_cache", "migrations",
              "site-packages", "Lib", "Scripts", "Include",   # Windows venv layout
              "lib", "bin", "include",                         # Unix venv layout
              "ai_context",                                    # session/runtime data
              "archive", "archives",                           # old/superseded docs
              "prompts",                                       # LLM prompt templates, not design docs
              "external_corpora", "external", "vendor", "third_party",  # external code/docs
              }
_SKIP_FILES = {"license", "licence", "contributing", "code_of_conduct",
               "security", "authors", "credits"}


# ---------------------------------------------------------------------------
# Doc discovery
# ---------------------------------------------------------------------------

def discover_docs(project_root: str, max_size_kb: int = 512) -> list[DocFile]:
    """
    Walk project_root recursively, find all text-based documentation files.
    Returns list sorted by constraint_score descending (most design-relevant first).
    """
    root = Path(project_root)
    found: list[DocFile] = []

    for p in root.rglob("*"):
        # Skip hidden dirs and known non-doc dirs
        if any(part.startswith(".") or part in _SKIP_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".md", ".rst", ".txt", ".adoc"}:
            continue
        if p.stat().st_size > max_size_kb * 1024:
            continue
        stem_lower = p.stem.lower()
        if stem_lower in _SKIP_FILES:
            continue

        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        lines = text.splitlines()
        headings = _HEADING_RE.findall(text)
        constraint_lines = sum(1 for ln in lines if _CONSTRAINT_RE.search(ln))
        constraint_score = constraint_lines / max(len(lines), 1)
        doc_type = _classify_doc(p.name, text)

        doc = DocFile(
            path=str(p),
            rel_path=str(p.relative_to(root)).replace("\\", "/"),
            size_bytes=p.stat().st_size,
            doc_type=doc_type,
            heading_count=len(headings),
            constraint_score=round(constraint_score, 3),
            mtime=p.stat().st_mtime,
        )
        doc.confidence = grade_doc(doc)
        found.append(doc)

    found.sort(key=lambda d: (d.doc_type == "design", d.constraint_score), reverse=True)
    return found


def _classify_doc(filename: str, text: str) -> str:
    name_lower = filename.lower()
    text_lower = text[:3000].lower()
    scores: dict[str, int] = {t: 0 for t, _ in _DOC_TYPE_SIGNALS}
    for doc_type, signals in _DOC_TYPE_SIGNALS:
        for sig in signals:
            if sig in name_lower:
                scores[doc_type] += 3
            if sig in text_lower:
                scores[doc_type] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "unknown"


# ---------------------------------------------------------------------------
# Rule extraction
# ---------------------------------------------------------------------------

def extract_rules(doc_path: str, rel_path: str = "", source_confidence: str = "medium") -> list[DesignRule]:
    """
    Extract design rules from a single document.
    Uses deterministic heading+constraint parsing — no model required.
    Returns list of DesignRule objects with confidence and provenance populated.
    """
    text = Path(doc_path).read_text(encoding="utf-8", errors="ignore")
    src = rel_path or doc_path
    rules: list[DesignRule] = []

    sections = _split_by_headings(text)
    for heading, body in sections:
        subject = _heading_to_subject(heading)
        constraint_sentences = _extract_constraint_sentences(body)
        if not constraint_sentences:
            continue
        # Group into one rule per heading section (keeps context intact)
        rule_text = _compress_constraints(heading, constraint_sentences)

        # Classify kind from dominant signal
        if _MUST_NOT_RE.search(rule_text):
            kind = "constraint"
        elif _MUST_RE.search(rule_text):
            kind = "requirement"
        else:
            kind = "permission"

        rules.append(DesignRule(
            subject=subject,
            rule=rule_text,
            source_file=src,
            source_heading=heading,
            extraction="deterministic",
            confidence=source_confidence,
            provenance=f"{source_confidence}:{src}:deterministic",
            kind=kind,
        ))

    return rules


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """Split text into (heading, body) pairs. First chunk before any heading gets heading=''."""
    parts: list[tuple[str, str]] = []
    current_heading = ""
    current_body: list[str] = []

    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if current_body:
                parts.append((current_heading, "\n".join(current_body).strip()))
            current_heading = m.group(2).strip()
            current_body = []
        else:
            current_body.append(line)

    if current_body:
        parts.append((current_heading, "\n".join(current_body).strip()))

    return parts


def _heading_to_subject(heading: str) -> str:
    """
    Derive a subject key from a heading.
    'EscalationEngine authority boundary' -> 'EscalationEngine'
    '3. Visibility Contract: WorldController' -> 'WorldController'
    'B1. Mutation authority' -> 'mutation_authority'
    """
    # Strip leading numbering like "3.", "B1.", "##"
    h = re.sub(r"^[\dA-Za-z]+\.\s*", "", heading).strip()
    # Take up to the first colon or parenthesis
    h = re.split(r"[:(]", h)[0].strip()
    # If it looks like a CamelCase class/system name, keep it
    if re.match(r"^[A-Z][a-zA-Z]+$", h.split()[0] if h.split() else ""):
        return h.split()[0]
    # Otherwise slugify
    return re.sub(r"[^a-zA-Z0-9]+", "_", h).strip("_").lower() or heading[:40]


def _extract_constraint_sentences(body: str) -> list[str]:
    """Return sentences/lines that contain constraint language."""
    results: list[str] = []
    for line in body.splitlines():
        line = line.strip().lstrip("-•*").strip()
        if len(line) < 10:
            continue
        if _CONSTRAINT_RE.search(line):
            results.append(line)
    return results


def _compress_constraints(heading: str, sentences: list[str]) -> str:
    """Combine heading and constraint sentences into a compact rule string."""
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique = []
    for s in sentences:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)
    body = " | ".join(unique[:8])   # cap at 8 sentences per section
    return f"[{heading}] {body}" if heading else body


# ---------------------------------------------------------------------------
# Confidence grading
# ---------------------------------------------------------------------------

def grade_doc(doc: DocFile) -> str:
    """
    Assign a confidence level to a DocFile based on constraint density and type.
    Constitutional / high-density design docs -> authoritative.
    Design docs with moderate signal -> high.
    READMEs and decision logs -> medium.
    Low signal -> low.
    """
    name_up = Path(doc.path).name.upper()

    if doc.constraint_score >= 0.12 or any(
        k in name_up for k in ("CONSTITUTION", "CONSTRAINTS", "INVARIANT")
    ):
        return "authoritative"
    if doc.constraint_score >= 0.05 or (
        doc.doc_type == "design"
        and any(k in name_up for k in ("DESIGN", "ARCHITECTURE", "SPEC", "ASPIRATIONAL", "SYSTEM"))
    ):
        return "high"
    if doc.doc_type in ("readme",) or doc.constraint_score >= 0.01:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# LLM extraction (fallback for sparse-signal sections)
# ---------------------------------------------------------------------------

_MUST_NOT_RE = re.compile(
    r"\b(must\s+not|must\s+never|shall\s+not|never|forbidden|prohibited|may\s+not)\b",
    re.IGNORECASE,
)
_MUST_RE = re.compile(
    r"\b(must(?!\s+not)|shall(?!\s+not)|required\s+to|is\s+required)\b",
    re.IGNORECASE,
)


def _downgrade_confidence(level: str) -> str:
    rank = CONFIDENCE_RANK.get(level, 0)
    for conf, r in sorted(CONFIDENCE_RANK.items(), key=lambda x: x[1]):
        if r == rank - 1:
            return conf
    return "low"


def extract_rules_llm(
    doc_path: str,
    heading: str,
    body: str,
    source_confidence: str,
    rel_path: str = "",
) -> list[DesignRule]:
    """
    Use the local 3B model to extract implied design rules from a prose section.
    Called only when deterministic extraction yields < 2 rules for a section
    that still has design intent language.
    Returns [] silently if llama-server is unavailable.
    """
    from determined.agent.llm_client import chat as _llm_chat
    llm_confidence = _downgrade_confidence(source_confidence)
    src = rel_path or doc_path

    prompt = (
        "Extract design rules from this software architecture text.\n"
        "Return a JSON array only - no other text. Each item must have:\n"
        '  "subject": system or component the rule applies to\n'
        '  "rule": the rule as a single concise statement (under 80 words)\n'
        '  "kind": "constraint" (must not/never/forbidden), '
        '"requirement" (must/shall), or "permission" (may/can)\n\n'
        "Only extract rules present in the text. If none, return [].\n\n"
        f"Section: {heading}\n\nText:\n{body[:1500]}"
    )

    try:
        text = _llm_chat([{"role": "user", "content": prompt}], timeout=_LLM_TIMEOUT)
        if not text:
            return []

        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if not json_match:
            return []
        items = json.loads(json_match.group())

        rules: list[DesignRule] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            subj = (item.get("subject") or _heading_to_subject(heading)).strip()
            rule_text = (item.get("rule") or "").strip()
            kind = (item.get("kind") or "constraint").strip()
            if rule_text and len(rule_text) > 10:
                rules.append(DesignRule(
                    subject=subj,
                    rule=rule_text,
                    source_file=src,
                    source_heading=heading,
                    extraction="llm",
                    confidence=llm_confidence,
                    provenance=f"{llm_confidence}:{src}:llm",
                    kind=kind,
                ))
        return rules

    except (json.JSONDecodeError, KeyError, ValueError):
        return []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Conflict detection and deduplication
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "must", "should", "never", "only", "shall", "that", "this",
    "with", "from", "into", "when", "not", "may", "will", "are",
    "the", "and", "for", "its", "any", "all",
})


def _key_terms(rule: str) -> set[str]:
    return set(re.findall(r"\b\w{4,}\b", rule.lower())) - _STOP_WORDS


def detect_conflicts(rules: list[DesignRule]) -> list[DesignRule]:
    """
    Flag rules where the same subject has potentially contradicting constraints
    from different source files. Marks conflicted rules with confidence="conflicted".
    A heuristic: a constraint and a requirement from different files share >= 2 key terms.
    """
    by_subject: dict[str, list[DesignRule]] = {}
    for r in rules:
        by_subject.setdefault(r.subject, []).append(r)

    result: list[DesignRule] = []
    for group in by_subject.values():
        sources = {r.source_file for r in group}
        if len(sources) < 2:
            result.extend(group)
            continue

        constraints = [r for r in group if r.kind == "constraint"]
        requirements = [r for r in group if r.kind == "requirement"]
        conflicted_ids: set[int] = set()

        for c in constraints:
            for req in requirements:
                if c.source_file != req.source_file:
                    if len(_key_terms(c.rule) & _key_terms(req.rule)) >= 2:
                        conflicted_ids.add(id(c))
                        conflicted_ids.add(id(req))

        for r in group:
            if id(r) in conflicted_ids:
                r.confidence = "conflicted"
                r.provenance = f"conflicted:{r.provenance}"
            result.append(r)

    return result


def deduplicate(rules: list[DesignRule]) -> list[DesignRule]:
    """Remove near-duplicate rules for the same subject, keeping highest confidence."""
    seen: dict[str, DesignRule] = {}
    for r in sorted(rules, key=lambda x: CONFIDENCE_RANK.get(x.confidence, 0), reverse=True):
        norm = re.sub(r"\s+", " ", r.rule.lower().strip())
        norm = re.sub(r"[^\w\s]", "", norm)
        key = f"{r.subject.lower()}::{norm[:60]}"
        if key not in seen:
            seen[key] = r
    return list(seen.values())
