"""
Design document discovery and rule extraction for any project.

Two public functions:
  discover_docs(project_root)  -> list[DocFile]
  extract_rules(doc_path)      -> list[DesignRule]

No assumptions about project layout, doc naming, or domain.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

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


@dataclass
class DesignRule:
    subject: str        # system/component name this rule is about
    rule: str           # the extracted constraint text
    source_file: str    # relative path of the doc it came from
    source_heading: str # heading that contained the rule
    extraction: str     # "deterministic" | "inferred"


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

        found.append(DocFile(
            path=str(p),
            rel_path=str(p.relative_to(root)).replace("\\", "/"),
            size_bytes=p.stat().st_size,
            doc_type=doc_type,
            heading_count=len(headings),
            constraint_score=round(constraint_score, 3),
        ))

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

def extract_rules(doc_path: str, rel_path: str = "") -> list[DesignRule]:
    """
    Extract design rules from a single document.
    Uses deterministic heading+constraint parsing — no model required.
    Returns list of DesignRule objects.
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
        rules.append(DesignRule(
            subject=subject,
            rule=rule_text,
            source_file=src,
            source_heading=heading,
            extraction="deterministic",
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
