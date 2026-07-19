# determined/agent/corpus_projections.py
#
# RM69 Phase 2: corpus-level projections.
# Aggregates classify_stub judgments into higher-order shapes.
#
# Four tools (each callable as an agent tool):
#
#   stub_file_shape([scope])
#       Stub density + dominant classification per file.
#       "Which files are most stub-heavy, and what kind of gap do they represent?"
#
#   stub_subsystem_shape([scope])
#       Stubs clustered by directory.
#       "Is this subsystem a design skeleton (blocked) or a dead-concept remnant?"
#
#   stub_prerequisite_map([scope])
#       Stubs grouped by shared named prerequisite extracted from docstrings.
#       "What needs to be built first? N stubs all blocked on X => X is priority."
#
#   stub_concept_ghost_map([scope])
#       Concepts named in stub docstrings vs. symbols in live corpus.
#       "Which concepts referenced in stubs don't exist anywhere in the graph?"
#
# All tools accept an optional `scope` arg (directory prefix, e.g. "world/")
# to restrict the analysis to a subsystem.
#
# SOTS XI: signal extraction is pure / no side effects; presentation is separate.
# Language note: tools work from the DB schema. No language-specific logic here.

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor

from determined.agent.classify_stub import extract_signals, score_hypotheses


# ---------------------------------------------------------------------------
# Prerequisite extraction (text pattern, language-agnostic)
# ---------------------------------------------------------------------------

# Patterns that signal a named dependency blocking implementation.
# Captures the first CamelCase or capitalized token after the trigger phrase.
_PREREQ_RE = re.compile(
    r'\b(?:until|blocked\s+on|blocked\s+by|waiting\s+on|'
    r'depends\s+on|requires?|once|when|after)\b'
    r'\s+([A-Z][a-zA-Z0-9]+)',
    re.IGNORECASE,
)

# Noise words that aren't real prerequisites even when capitalized
_PREREQ_SKIP = frozenset({
    "The", "This", "That", "It", "A", "An", "If", "When", "Once",
    "After", "Before", "Until", "None", "True", "False",
    "LLM", "API", "DB", "SQL", "HTTP", "JSON", "UI", "ID",
})


def _extract_prerequisites(text: str) -> list[str]:
    """Return named prerequisites from stub docstring / comment text."""
    if not text:
        return []
    results = []
    for m in _PREREQ_RE.finditer(text):
        name = m.group(1)
        if name not in _PREREQ_SKIP and len(name) > 1:
            results.append(name)
    return list(dict.fromkeys(results))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fetch_stubs(conn, scope: str) -> list[tuple]:
    """
    Return (name, file_path, line_number, docstring) for all stubs,
    optionally filtered to files under `scope` (directory prefix).
    """
    rows = conn.execute(
        "SELECT name, file_path, line_number, docstring "
        "FROM functions WHERE is_stub = 1"
        "  AND file_path NOT LIKE '%/test_%'"
        "  AND file_path NOT LIKE '%\\test_%'"
        "  AND file_path NOT LIKE '%/tests/%'"
        "  AND file_path NOT LIKE '%\\tests\\%'"
    ).fetchall()
    if scope:
        norm = scope.lower().replace("\\", "/").rstrip("/")
        rows = [r for r in rows if norm in (r[1] or "").replace("\\", "/").lower()]
    return rows


def _dir_key(file_path: str) -> str:
    """Return the immediate parent directory of a file path."""
    parts = file_path.replace("\\", "/").split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else "."


def _classify_stub_row(oracle, name: str, file_path: str) -> tuple[str, list[dict]]:
    """
    Run extract_signals + score_hypotheses for a single stub row.
    Returns (top_classification, hypotheses).
    """
    signals = extract_signals(oracle, name, file_path_hint=file_path)
    if "error" in signals:
        return "genuinely-unknown", []
    hypotheses = score_hypotheses(signals)
    top = hypotheses[0]["classification"] if hypotheses else "genuinely-unknown"
    return top, hypotheses


# ---------------------------------------------------------------------------
# Tool 1: stub_file_shape
# ---------------------------------------------------------------------------

def stub_file_shape(assessor: "Assessor", args: dict) -> str:
    """
    stub_file_shape([scope]) — stub density and dominant classification per file.

    For each file containing at least one stub:
      - stub density = stub count / total functions in file
      - dominant classification = most common top hypothesis across all stubs
      - verdict: design-skeleton / dead-concept / unknown / mixed

    Args:
        scope: (optional) directory prefix, e.g. "world/" to restrict scope
    """
    oracle = assessor.oracle
    conn = oracle.conn
    scope = args.get("scope", "").strip().replace("\\", "/").rstrip("/")

    stub_rows = _fetch_stubs(conn, scope)
    if not stub_rows:
        return f"stub_file_shape: no stubs found{' under ' + scope if scope else ''}."

    # Group stubs by file
    by_file: dict[str, list[tuple]] = defaultdict(list)
    for row in stub_rows:
        fp = (row[1] or "unknown").replace("\\", "/")
        by_file[fp].append(row)

    # Total function count per file
    fn_counts: dict[str, int] = {}
    for fp in by_file:
        fn_counts[fp] = conn.execute(
            "SELECT COUNT(*) FROM functions WHERE file_path = ?", (fp,)
        ).fetchone()[0] or 1

    results = []
    for fp, stubs in by_file.items():
        stub_count = len(stubs)
        total = fn_counts[fp]
        density = stub_count / total

        classifications: list[str] = []
        for name, file_path, _, _ in stubs:
            top, _ = _classify_stub_row(oracle, name, file_path or fp)
            classifications.append(top)

        dominant = _dominant(classifications)
        verdict = _file_verdict(dominant, classifications)

        short_fp = "/".join(fp.split("/")[-2:])
        results.append((density, stub_count, total, short_fp, fp, dominant, verdict, classifications))

    results.sort(key=lambda r: r[0], reverse=True)

    lines = [f"stub_file_shape{' (scope: ' + scope + ')' if scope else ''}\n"]
    for density, stub_count, total, short_fp, fp, dominant, verdict, classifications in results:
        lines.append(f"  {short_fp}")
        lines.append(f"    density: {stub_count}/{total} ({density:.0%})  dominant: {dominant}  verdict: {verdict}")
        cls_summary = ", ".join(f"{c}({classifications.count(c)})" for c in sorted(set(classifications)))
        lines.append(f"    breakdown: {cls_summary}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 2: stub_subsystem_shape
# ---------------------------------------------------------------------------

def stub_subsystem_shape(assessor: "Assessor", args: dict) -> str:
    """
    stub_subsystem_shape([scope]) — stub pattern at directory/subsystem level.

    Groups stubs by their parent directory and classifies each subsystem:
      design-skeleton   — dominant class is blocked-on-prerequisite
                          (stubs are waiting on dependencies to be built)
      dead-concept      — dominant class is concept-not-applicable
                          (stubs reference concepts removed from the design)
      unknown-gaps      — dominant class is genuinely-unknown (no signal)
      mixed             — no single class dominates

    Args:
        scope: (optional) directory prefix to restrict
    """
    oracle = assessor.oracle
    conn = oracle.conn
    scope = args.get("scope", "").strip().replace("\\", "/").rstrip("/")

    stub_rows = _fetch_stubs(conn, scope)
    if not stub_rows:
        return f"stub_subsystem_shape: no stubs found{' under ' + scope if scope else ''}."

    by_dir: dict[str, list[tuple]] = defaultdict(list)
    for row in stub_rows:
        fp = (row[1] or "unknown").replace("\\", "/")
        by_dir[_dir_key(fp)].append(row)

    results = []
    for directory, stubs in by_dir.items():
        classifications: list[str] = []
        for name, file_path, _, _ in stubs:
            top, _ = _classify_stub_row(oracle, name, file_path or "")
            classifications.append(top)

        dominant = _dominant(classifications)
        subsystem_verdict = _subsystem_verdict(dominant, classifications)
        results.append((len(stubs), directory, dominant, subsystem_verdict, classifications))

    results.sort(key=lambda r: r[0], reverse=True)

    lines = [f"stub_subsystem_shape{' (scope: ' + scope + ')' if scope else ''}\n"]
    for stub_count, directory, dominant, verdict, classifications in results:
        lines.append(f"  {directory}/  ({stub_count} stub{'s' if stub_count != 1 else ''})")
        lines.append(f"    verdict: {verdict}  dominant: {dominant}")
        cls_summary = ", ".join(f"{c}({classifications.count(c)})" for c in sorted(set(classifications)))
        lines.append(f"    breakdown: {cls_summary}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3: stub_prerequisite_map
# ---------------------------------------------------------------------------

def stub_prerequisite_map(assessor: "Assessor", args: dict) -> str:
    """
    stub_prerequisite_map([scope]) — group stubs by shared named prerequisite.

    Scans stub docstrings and inline comments for language like:
      "until X is built", "blocked on X", "waiting on X", "requires X", etc.

    Stubs sharing the same named prerequisite X are grouped together.
    N stubs all blocked on X => X is a build priority (ranked by N).

    Args:
        scope: (optional) directory prefix to restrict
    """
    oracle = assessor.oracle
    conn = oracle.conn
    scope = args.get("scope", "").strip().replace("\\", "/").rstrip("/")

    stub_rows = _fetch_stubs(conn, scope)
    if not stub_rows:
        return f"stub_prerequisite_map: no stubs found{' under ' + scope if scope else ''}."

    # Map prerequisite -> [(stub_name, short_path)]
    prereq_map: dict[str, list[str]] = defaultdict(list)
    no_prereq: list[str] = []

    for name, file_path, line_number, docstring in stub_rows:
        # Also read inline comments from the body
        from determined.agent.classify_stub import _extract_body
        _, inline = _extract_body(file_path, line_number)
        text = " ".join(filter(None, [docstring, inline]))

        prereqs = _extract_prerequisites(text)
        short_fp = "/".join((file_path or "").replace("\\", "/").split("/")[-2:])
        label = f"{name}  ({short_fp})"

        if prereqs:
            for p in prereqs:
                prereq_map[p].append(label)
        else:
            no_prereq.append(label)

    if not prereq_map:
        return (
            f"stub_prerequisite_map: no named prerequisites found in stub docstrings"
            f"{' under ' + scope if scope else ''}.\n"
            f"({len(no_prereq)} stub(s) have no extractable prerequisite name.)"
        )

    ranked = sorted(prereq_map.items(), key=lambda kv: len(kv[1]), reverse=True)

    lines = [f"stub_prerequisite_map{' (scope: ' + scope + ')' if scope else ''}\n"]
    for prereq, stubs in ranked:
        priority = "HIGH" if len(stubs) >= 3 else "MED" if len(stubs) >= 2 else "LOW"
        lines.append(f"  [{priority}] {prereq}  ({len(stubs)} stub(s) blocked)")
        for s in stubs:
            lines.append(f"    · {s}")
        lines.append("")

    if no_prereq:
        lines.append(f"  ({len(no_prereq)} stub(s) with no named prerequisite)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 4: stub_concept_ghost_map
# ---------------------------------------------------------------------------

def stub_concept_ghost_map(assessor: "Assessor", args: dict) -> str:
    """
    stub_concept_ghost_map([scope]) — concepts named in stubs vs. live corpus.

    For each CamelCase concept name referenced in stub docstrings:
      ghost   — no class or function with that name exists anywhere in the graph
      partial — matching function(s) exist but no class (concept half-built)
      live    — a class with a matching name exists (concept is implemented)

    Ghosts are the most important: the stub cannot be implemented until the
    ghost concept is built first. These surface ungroundable stubs.

    Args:
        scope: (optional) directory prefix to restrict stub search
    """
    oracle = assessor.oracle
    conn = oracle.conn
    scope = args.get("scope", "").strip().replace("\\", "/").rstrip("/")

    stub_rows = _fetch_stubs(conn, scope)
    if not stub_rows:
        return f"stub_concept_ghost_map: no stubs found{' under ' + scope if scope else ''}."

    from determined.agent.agent_tools import _extract_docstring_concepts

    import re as _re

    class_names_lower = {
        r[0].lower()
        for r in conn.execute("SELECT name FROM classes").fetchall()
    }
    fn_names_lower = {
        r[0].lower()
        for r in conn.execute("SELECT name FROM functions WHERE is_stub = 0").fetchall()
    }

    def _concept_snake(concept: str) -> str:
        """CamelCase or SuffixFSM → snake_case for fn-name matching."""
        s = _re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', concept)
        s = _re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s)
        return s.lower()

    def _concept_matches(concept: str, class_names: set, fn_names: set) -> str:
        """
        Return verdict for a concept: 'live', 'partial', or 'ghost'.

        Class match: the concept name (lowercased, no spaces) appears as a
        substring of a class name, or vice-versa — using the FULL concept, not
        the suffix-stripped base.  This avoids 'CombatFSM' → base 'Combat'
        matching '_validate_combat'.

        Function match (partial): the snake_case form of the full concept appears
        as a substring in a function name (e.g. 'combat_fsm' in 'combat_fsm_init').
        """
        concept_lower = concept.lower().replace(" ", "")
        class_hit = any(concept_lower in cn or cn in concept_lower for cn in class_names)
        if class_hit:
            return "live"
        snake = _concept_snake(concept)
        fn_hit = any(snake in fn or fn in snake for fn in fn_names if len(snake) >= 5)
        return "partial" if fn_hit else "ghost"

    # concept -> {verdict, stubs_referencing}
    concept_data: dict[str, dict] = {}

    for name, file_path, _, docstring in stub_rows:
        short_fp = "/".join((file_path or "").replace("\\", "/").split("/")[-2:])
        label = f"{name}  ({short_fp})"
        concepts = _extract_docstring_concepts(docstring or "")
        for concept in concepts:
            if concept not in concept_data:
                verdict = _concept_matches(concept, class_names_lower, fn_names_lower)
                concept_data[concept] = {"verdict": verdict, "stubs": []}
            concept_data[concept]["stubs"].append(label)

    if not concept_data:
        return (
            f"stub_concept_ghost_map: no concept names found in stub docstrings"
            f"{' under ' + scope if scope else ''}."
        )

    # Sort: ghosts first, then partial, then live; within each group by stub count desc
    _order = {"ghost": 0, "partial": 1, "live": 2}
    ranked = sorted(
        concept_data.items(),
        key=lambda kv: (_order[kv[1]["verdict"]], -len(kv[1]["stubs"])),
    )

    ghost_count = sum(1 for _, d in ranked if d["verdict"] == "ghost")
    partial_count = sum(1 for _, d in ranked if d["verdict"] == "partial")

    lines = [
        f"stub_concept_ghost_map{' (scope: ' + scope + ')' if scope else ''}",
        f"{ghost_count} ghost(s), {partial_count} partial(s), "
        f"{len(ranked) - ghost_count - partial_count} live\n",
    ]

    for concept, data in ranked:
        verdict = data["verdict"]
        stubs = data["stubs"]
        tag = "GHOST" if verdict == "ghost" else "PARTIAL" if verdict == "partial" else "live"
        lines.append(f"  [{tag}] {concept}  ({len(stubs)} stub reference(s))")
        for s in stubs:
            lines.append(f"    · {s}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Verdict helpers
# ---------------------------------------------------------------------------

def _dominant(classifications: list[str]) -> str:
    """Return the most common classification, or 'mixed' on a tie."""
    if not classifications:
        return "unknown"
    counts: dict[str, int] = defaultdict(int)
    for c in classifications:
        counts[c] += 1
    top = max(counts, key=lambda k: counts[k])
    # Tie: two or more classes share the maximum
    if list(counts.values()).count(counts[top]) > 1:
        return "mixed"
    return top


def _file_verdict(dominant: str, classifications: list[str]) -> str:
    if dominant == "blocked-on-prerequisite":
        return "design-skeleton"
    if dominant == "concept-not-applicable":
        return "dead-concept"
    if dominant == "genuinely-unknown":
        return "unknown-gaps"
    if dominant == "design-intent-stated":
        return "design-intent"
    return "mixed"


def _subsystem_verdict(dominant: str, classifications: list[str]) -> str:
    total = len(classifications)
    blocked = classifications.count("blocked-on-prerequisite")
    dead = classifications.count("concept-not-applicable")
    if blocked / total >= 0.6:
        return "design-skeleton"
    if dead / total >= 0.6:
        return "dead-concept"
    if (blocked + dead) / total >= 0.8:
        # Clear split but no single dominant — report both
        return "mixed-skeleton-and-dead-concept"
    return "mixed"
