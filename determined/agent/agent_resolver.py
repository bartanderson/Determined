# tools/analysis/agent/agent_resolver.py
#
# Phase 2 of the three-phase agent pipeline (DESIGN.md section 8).
# Maps NEED lines produced by Phase 1 to tool calls, executes them,
# and returns a flat fact set. Pure Python, no AI calls - independently
# testable.

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor

from determined.agent.agent_tools import dispatch


# ------------------------------------------------------------------
# Phase 0: GROUND
# Extract keywords from the question, run broad searches, return
# a summary of what actually exists in the corpus. This is injected
# into the Phase 1 prompt so the model selects from real names
# rather than inventing plausible-sounding ones.
# ------------------------------------------------------------------

_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must",
    "what", "how", "where", "when", "why", "which", "who", "whom",
    "this", "that", "these", "those", "it", "its",
    "of", "in", "on", "at", "to", "for", "by", "with", "about",
    "from", "into", "through", "during", "before", "after",
    "and", "or", "but", "not", "so", "yet", "both", "either",
    "currently", "handled", "status", "tell", "me", "show", "find",
    "get", "give", "list", "describe", "explain", "there", "their",
    "they", "them", "we", "our", "my", "your", "any", "all", "each",
    "more", "most", "other", "some", "such", "no", "nor", "only",
    "own", "same", "than", "too", "very", "just", "also", "now",
    "system", "code", "codebase", "file", "files", "function",
    "functions", "class", "classes", "module", "modules",
})


def _extract_keywords(question: str) -> list[str]:
    """
    Extract search-worthy keywords from a natural language question.
    Returns words ordered longest-first (longer = more specific).
    """
    words = re.findall(r"[a-zA-Z_]\w*", question)
    seen: set[str] = set()
    keywords = []
    for w in words:
        low = w.lower()
        if low not in _STOPWORDS and len(low) >= 3 and low not in seen:
            seen.add(low)
            keywords.append(w)
    # Longer words are more specific - sort descending by length, keep top 5
    keywords.sort(key=len, reverse=True)
    return keywords[:5]


def ground_question(question: str, oracle: "DBOracle", assessor: "Assessor") -> str:
    """
    Phase 0: broad keyword search against the corpus.
    Returns a short grounding block (text) for injection into the Phase 1 prompt.
    Empty string if nothing found.
    """
    keywords = _extract_keywords(question)
    if not keywords:
        return ""

    found_symbols: dict[str, str] = {}   # name -> file_short
    found_files: list[str] = []
    seen_files: set[str] = set()

    for kw in keywords:
        # Search symbols
        try:
            rows = oracle.find_symbols(kw, limit=10)
            for r in rows:
                if r["name"] not in found_symbols:
                    file_short = r["file_path"].replace("\\", "/").split("/")[-1]
                    found_symbols[r["name"]] = file_short
        except Exception:
            pass

        # Search files
        try:
            rows = oracle.find_files(pattern=kw)
            root = oracle.get_project_root().replace("\\", "/")
            for r in rows:
                fp = r["file_path"].replace("\\", "/")
                if root and fp.startswith(root + "/"):
                    fp = fp[len(root) + 1:]
                if fp not in seen_files:
                    seen_files.add(fp)
                    found_files.append(fp)
        except Exception:
            pass

    if not found_symbols and not found_files:
        return ""

    lines = ["Corpus search results (use these actual names in your NEED: lines):"]
    if found_symbols:
        sym_list = ", ".join(
            f"{n} (in {f})" for n, f in list(found_symbols.items())[:10]
        )
        lines.append(f"  Symbols found: {sym_list}")
    if found_files:
        lines.append(f"  Files found: {', '.join(found_files[:8])}")

    # Pull pre-built findings from knowledge.db for matched symbols and files
    known = _ground_findings(list(found_symbols.keys())[:5], assessor)
    # Also pull file-level findings (subject is bare filename)
    file_subjects = [fp.replace("\\", "/").split("/")[-1] for fp in found_files[:3]]
    known += _ground_findings(file_subjects, assessor)
    if known:
        lines.append(f"  Known findings:")
        for line in known:
            lines.append(f"    {line}")

    return "\n".join(lines)


def _ground_findings(symbols: list[str], assessor: "Assessor") -> list[str]:
    """Pull the most relevant knowledge.db findings for a list of symbol names."""
    if assessor is None:
        return []
    try:
        conn = getattr(assessor, "_knowledge_conn", None)
        if conn is None:
            return []
        lines = []
        for sym in symbols:
            rows = conn.execute(
                "SELECT kind, content FROM knowledge_artifacts "
                "WHERE subject = ? OR subject LIKE ? "
                "ORDER BY created_at DESC LIMIT 2",
                (sym, f"%::{sym}"),
            ).fetchall()
            for row in rows:
                lines.append(f"[{row[0]}] {sym}: {row[1][:120]}")
        return lines
    except Exception:
        return []


# ------------------------------------------------------------------
# Pattern table: (regex, tool_name, arg_key, group_index)
# Patterns are tried in order; first match wins for each NEED line.
# ------------------------------------------------------------------

_PATTERNS = [
    # "files in <dir>"
    (re.compile(r"files?\s+in\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "files_in_directory", "path", 1),

    # "files matching <query>" / "files named <query>"
    (re.compile(r"files?\s+(?:matching|named)\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "search_files", "query", 1),

    # "symbols named <name>" / "symbol named <name>"
    (re.compile(r"symbols?\s+named\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "search_symbols", "query", 1),

    # "symbols in <file>" / "symbols in <file>.py"
    (re.compile(r"symbols?\s+in\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "symbols_in_file", "file_path", 1),

    # "what calls <symbol>" / "callers of <symbol>" / "what invokes <symbol>" / "what uses <symbol>"
    (re.compile(r"(?:what\s+(?:calls|invokes?|uses?)|callers?\s+of)\s+['\"]?(\S+?)['\"]?\s*$", re.I),
     "list_callers", "symbol", 1),

    # "what <symbol> calls" / "callees of <symbol>"
    (re.compile(r"(?:what\s+\S+\s+calls|callees?\s+of)\s+['\"]?(\S+?)['\"]?\s*$", re.I),
     "list_callees", "symbol", 1),

    # "what does <file>.py do" / "describe <file>"
    (re.compile(r"(?:what\s+does\s+['\"]?(.+?\.py)['\"]?\s+do|describe\s+(?:file\s+)?['\"]?(.+?\.py)['\"]?)\s*$", re.I),
     "describe_file", "file_path", None),  # group_index=None: handle multi-group below

    # "intent of <symbol>" / "purpose of <symbol>"
    (re.compile(r"(?:intent|purpose)\s+of\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "symbol_intent", "symbol", 1),

    # "findings for <symbol>" / "known findings for <symbol>"
    (re.compile(r"(?:known\s+)?findings?\s+for\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "get_findings", "symbol", 1),

    # "git history of <path>" / "recent commits for <path>"
    (re.compile(r"(?:git\s+(?:history|log)\s+(?:of|for)\s+|recent\s+commits?\s+(?:for|to|in)\s+)"
                r"['\"]?([^\s'\"]+)['\"]?\s*$", re.I),
     "git_log_for", "path", 1),

    # "prioritize work" / "what to work on"
    (re.compile(r"prioriti[sz]e\s+work\s*$", re.I),
     "prioritize_work", None, None),

    # "missing docstrings" / "no docstrings"
    (re.compile(r"missing\s+docstrings?\s*$|no\s+docstrings?\s*$", re.I),
     "missing_docstrings", None, None),

    # "find todos" / "show todos"
    (re.compile(r"(?:find|show|list)\s+(?:all\s+)?(?:todos?|fixmes?|hacks?)\s*$", re.I),
     "find_todos", None, None),

    # "findings of kind <kind>" / "all <kind> findings"
    (re.compile(r"(?:findings?\s+of\s+kind\s+|all\s+)([a-z_]+)(?:\s+findings?)?\s*$", re.I),
     "list_findings_by_kind", "kind", 1),

    # "brief for <symbol>"
    (re.compile(r"brief\s+for\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "symbol_brief", "symbol", 1),

    # "path from X to Y" / "how does X reach Y"
    (re.compile(r"(?:path\s+from|how\s+does\s+)\s*['\"]?(\S+?)['\"]?\s+(?:to\s+|reach\s+)['\"]?(\S+?)['\"]?\s*$", re.I),
     "graph_path", None, None),  # special: two groups -> src + dst

    # "entry points" / "system roots" / "what are the entry points"
    (re.compile(r"(?:entry\s+points?|system\s+roots?|what\s+are\s+the\s+entry\s+points?)\s*$", re.I),
     "graph_entry_points", None, None),

    # "most connected" / "most connected in X" / "highest degree"
    (re.compile(r"most\s+connected(?:\s+in\s+['\"]?([^'\"]*?)['\"]?)?\s*$", re.I),
     "graph_most_connected", "filter", 1),

    # "subgraph around X" / "neighbors of X"
    (re.compile(r"(?:subgraph\s+around|neighbors?\s+of)\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "graph_subgraph", "symbol", 1),

    # "clusters" / "file clusters" / "cluster containing X"
    (re.compile(r"(?:file\s+)?clusters?(?:\s+containing\s+\S+)?\s*$", re.I),
     "graph_clusters", None, None),

    # "workflow status" / "what's next" / "current priorities" / "what am I working on"
    (re.compile(r"(?:workflow\s+status|what'?s?\s+next|current\s+priorities|what\s+am\s+I\s+working\s+on)\s*$", re.I),
     "workflow_status", None, None),

    # "next_up" / "backlog" / "future_plan" / "session_decision" (direct kind query)
    (re.compile(r"(?:show\s+)?(?:my\s+)?(next_up|backlog|future_plans?|session_decisions?)\s*$", re.I),
     "workflow_status", "kind", 1),

    # "add to backlog: X" / "remember as next_up: X" / "store workflow ..."
    (re.compile(r"(?:add\s+to|remember\s+as|store\s+as)\s+(next_up|backlog|future_plan|session_decision)[:\s]+(.+)$", re.I),
     "store_workflow_item", None, None),  # special: multi-group

    # "reorder as 3,1,2" / "rerank 2,3,1"
    (re.compile(r"(?:reorder|rerank)\s+(?:as\s+)?(\d[\d,\s]*)$", re.I),
     "rerank_workflow", "order", 1),

    # "risk profile for X" / "risk of X"
    (re.compile(r"(?:risk\s+profile\s+(?:for|of)|risk\s+of)\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "risk_profile", "symbol", 1),

    # "infer behavior of <symbol>" / "infer role of <symbol>"
    (re.compile(r"infer\s+(?:behavior|role)\s+of\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "infer_behavior", "symbol", 1),

    # "trace data flow of/for <symbol>" / "trace flow of <symbol>"
    (re.compile(r"trace\s+(?:data\s+)?flow\s+(?:of|for)\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "trace_data_flow", "symbol", 1),

    # "search <query>" / "find <query>" - fallback to search_symbols
    (re.compile(r"(?:search|find)\s+['\"]?([^'\"]+?)['\"]?\s*$", re.I),
     "search_symbols", "query", 1),
]


# ------------------------------------------------------------------
# Named heuristics: high-level query patterns → pre-wired NEED sequences
# Checked before Phase 1 (Ollama decompose). If matched, the NEED lines
# are returned directly and the Ollama call is skipped entirely.
# Each entry: (regex, builder_fn) where builder_fn(match) -> list[str]
# ------------------------------------------------------------------

# Suffix words that form meaningful compound class names (e.g. "adjudication engine" -> AdjudicationEngine)
_CLASS_SUFFIXES = frozenset({
    "engine", "system", "manager", "handler", "controller", "service",
    "generator", "builder", "parser", "router", "resolver", "tracker",
    "monitor", "processor", "dispatcher", "coordinator", "registry",
})


def _compound_term(word1: str, word2: str | None) -> str | None:
    """Return CamelCase compound if word2 is a class suffix, else None."""
    if word2 and word2.lower() in _CLASS_SUFFIXES:
        return word1.capitalize() + word2.capitalize()
    return None


def _camel_variant(term: str) -> str | None:
    """If term is snake_case, return CamelCase variant (world_controller -> WorldController)."""
    if "_" in term:
        return "".join(w.capitalize() for w in term.split("_"))
    return None


def _similar_needs(term: str) -> list[str]:
    """
    NEEDs for 'how was X done / find similar to X' queries.
    Looks up X's structure, its callers (who uses the pattern), and similarly-named
    symbols (same suffix class, e.g. QuestManager -> other *Manager classes).
    Note: 'similar' means same name-pattern or same usage site, not same purpose -
    semantic similarity would require embeddings not available here.
    """
    camel = _camel_variant(term)
    primary = camel if camel else term
    # Find the suffix if term ends with a known class suffix word
    suffix_match = next(
        (s for s in _CLASS_SUFFIXES if primary.lower().endswith(s)),
        None,
    )
    needs = [
        f"symbols named {primary}",
        f"what calls {primary}",
        f"callees of {primary}",
        f"findings for {primary}",
    ]
    if suffix_match:
        # Search for other symbols sharing the same suffix (e.g. other *Manager classes)
        needs.append(f"symbols named {suffix_match}")
    return needs


def _trace_needs(term: str, suffix: str | None = None) -> list[str]:
    """Standard trace NEEDs. Uses compound or CamelCase variant as primary when applicable."""
    compound = _compound_term(term, suffix)
    camel = _camel_variant(term) if not compound else None
    primary = compound if compound else (camel if camel else term)
    needs = [
        f"symbols named {primary}",
        f"intent of {primary}",
        f"callees of {primary}",
        f"what calls {primary}",
        f"findings for {primary}",
    ]
    if compound or camel:
        needs.insert(1, f"symbols named {term}")  # bare term search as fallback
    return needs


def _explain_needs(term: str, suffix: str | None = None) -> list[str]:
    """Standard explain NEEDs. Uses compound or CamelCase variant as primary when applicable."""
    compound = _compound_term(term, suffix)
    camel = _camel_variant(term) if not compound else None
    primary = compound if compound else (camel if camel else term)
    needs = [
        f"symbols named {primary}",
        f"intent of {primary}",
        f"brief for {primary}",
        f"callees of {primary}",
        f"findings for {primary}",
    ]
    if compound or camel:
        needs.insert(1, f"symbols named {term}")  # bare term search as fallback
    return needs


_HEURISTICS: list[tuple] = [
    # --- Entry points ---
    # "what are the entry points" / "list entry points" / "entry points for X"
    (
        re.compile(
            r"(?:what\s+are\s+(?:the\s+)?|list\s+(?:the\s+)?|show\s+(?:me\s+)?(?:the\s+)?)?entry\s+points?",
            re.I,
        ),
        lambda m: ["entry points"],
    ),

    # --- Risk heuristics ---

    # "is X safe to modify/change" / "how risky is X" / "can I safely change X"
    # / "risk profile for X" / "what is the blast radius of X"
    (
        re.compile(
            r"(?:is\s+['\"]?([A-Za-z_]\w*)['\"]?\s+safe\s+to\s+(?:modify|change|edit|touch)|"
            r"(?:how\s+risky|what\s+is\s+the\s+risk)\s+(?:is\s+|of\s+)['\"]?([A-Za-z_]\w*)['\"]?|"
            r"can\s+I\s+safely\s+(?:change|modify|edit)\s+['\"]?([A-Za-z_]\w*)['\"]?|"
            r"(?:blast\s+radius|change\s+risk)\s+(?:of|for)\s+['\"]?([A-Za-z_]\w*)['\"]?)",
            re.I,
        ),
        lambda m: (lambda t: [
            f"risk profile for {t}",
            f"symbols named {t}",
            f"what calls {t}",
        ])(next(g for g in m.groups() if g)),
    ),

    # --- Debug heuristics ---

    # "why is X broken/failing/wrong" / "what's wrong with X" / "why does X fail/error/crash"
    (
        re.compile(
            r"(?:why\s+(?:is|does|did|won'?t|doesn'?t|can'?t)\s+['\"]?([A-Za-z_]\w*)['\"]?\s+"
            r"(?:fail|break|crash|error|hang|not\s+work|return\s+wrong|throw)|"
            r"what'?s?\s+wrong\s+with\s+['\"]?([A-Za-z_]\w*)['\"]?|"
            r"['\"]?([A-Za-z_]\w*)['\"]?\s+(?:is\s+)?(?:broken|failing|crashed|erroring|not\s+working))",
            re.I,
        ),
        lambda m: (lambda t: [
            f"symbols named {t}",
            f"findings for {t}",
            "find todos",
            f"what calls {t}",
            f"brief for {t}",
        ])(next(g for g in m.groups() if g)),
    ),

    # --- Mutation heuristics ---

    # "what mutates X" / "who mutates X" / "where is X modified/changed/set" / "what changes X"
    (
        re.compile(
            r"(?:what|who|where)\s+(?:mutates?|modifi(?:es|ed)|changes?|sets?|writes?\s+to)\s+"
            r"['\"]?([A-Za-z_]\w*)['\"]?|"
            r"['\"]?([A-Za-z_]\w*)['\"]?\s+(?:is\s+)?(?:mutated|modified|changed|set)\s+(?:by|in|where)",
            re.I,
        ),
        lambda m: (lambda t: [
            f"symbols named {t}",
            f"findings for {t}",
            f"what calls {t}",
            f"callees of {t}",
        ])(next(g for g in m.groups() if g)),
    ),

    # --- Connection (two-symbol) heuristics first - must beat single-symbol patterns ---

    # "compare X and Y" / "what is the difference between X and Y" / "X vs Y"
    (
        re.compile(
            r"(?:compare\s+|what\s+(?:is\s+the\s+)?difference\s+between\s+|difference\s+between\s+)"
            r"['\"]?([A-Za-z_]\w*)['\"]?\s+(?:and|vs\.?|versus)\s+['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"symbols named {m.group(1)}",
            f"intent of {m.group(1)}",
            f"findings for {m.group(1)}",
            f"symbols named {m.group(2)}",
            f"intent of {m.group(2)}",
            f"findings for {m.group(2)}",
            f"path from {m.group(1)} to {m.group(2)}",
        ],
    ),
    # "what is the relationship between X and Y" / "relationship between X and Y"
    (
        re.compile(
            r"(?:what\s+is\s+(?:the\s+)?)?(?:relationship|connection|link|interaction)\s+between\s+"
            r"['\"]?([A-Za-z_]\w*)['\"]?\s+and\s+['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"path from {m.group(1)} to {m.group(2)}",
            f"what calls {m.group(1)}",
            f"callees of {m.group(1)}",
            f"what calls {m.group(2)}",
            f"callees of {m.group(2)}",
            f"findings for {m.group(1)}",
            f"findings for {m.group(2)}",
        ],
    ),

    # "how does X relate to Y" / "how does X connect to Y" / "how does X reach Y"
    (
        re.compile(
            r"how\s+does\s+['\"]?([A-Za-z_]\w*)['\"]?\s+"
            r"(?:relate\s+to|connect\s+to|reach)\s+"
            r"['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"path from {m.group(1)} to {m.group(2)}",
            f"what calls {m.group(1)}",
            f"callees of {m.group(1)}",
            f"what calls {m.group(2)}",
            f"callees of {m.group(2)}",
        ],
    ),
    # "what connects X and Y" / "link X to Y" / "interface between X and Y"
    (
        re.compile(
            r"(?:what\s+connects?\s+|link\s+|interface\s+between\s+)"
            r"['\"]?([A-Za-z_]\w*)['\"]?\s+(?:to|and|with)\s+['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"path from {m.group(1)} to {m.group(2)}",
            f"what calls {m.group(1)}",
            f"callees of {m.group(1)}",
            f"what calls {m.group(2)}",
            f"callees of {m.group(2)}",
        ],
    ),

    # --- Single-symbol depth heuristics ---

    # "how is X handled" / "how is X done" / "how is X implemented"
    # also "how is character creation handled" (optional extra word before verb)
    (
        re.compile(
            r"how\s+is\s+(?:a\s+|an\s+|the\s+)?"
            r"['\"]?([A-Za-z_]\w*)['\"]?"
            r"(?:\s+[A-Za-z_]\w*)?\s+"
            r"(?:handled|done|implemented|managed|processed|used)",
            re.I,
        ),
        lambda m: [
            f"symbols named {m.group(1)}",
            f"intent of {m.group(1)}",
            f"callees of {m.group(1)}",
            f"what calls {m.group(1)}",
            f"findings for {m.group(1)}",
        ],
    ),
    # "where is X triggered" / "where does X happen" / "where is X called"
    (
        re.compile(
            r"where\s+(?:is\s+(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?\s+(?:triggered|called|fired|invoked|initiated)|"
            r"does\s+(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?\s+happen)",
            re.I,
        ),
        lambda m: [
            f"what calls {m.group(1) or m.group(2)}",
            f"symbols named {m.group(1) or m.group(2)}",
        ],
    ),
    # "what happens when X" / "what happens if X"
    (
        re.compile(
            r"what\s+happens\s+when\s+(?:a\s+|an\s+|the\s+)?(?:player\s+|user\s+)?['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"symbols named {m.group(1)}",
            f"what calls {m.group(1)}",
            f"intent of {m.group(1)}",
            f"findings for {m.group(1)}",
        ],
    ),
    # "what is responsible for X"
    (
        re.compile(
            r"what\s+(?:is\s+)?responsible\s+for\s+(?:a\s+|an\s+|the\s+)?"
            r"['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"symbols named {m.group(1)}",
            f"files matching {m.group(1)}",
            f"findings for {m.group(1)}",
        ],
    ),
    # "how do/does X [Y] work" - captures compound like "adjudication engine"
    # Negative lookahead skips "I" - "how do I ..." is dev_plan, not trace
    (
        re.compile(
            r"how\s+do(?:es)?\s+(?:a\s+|an\s+|the\s+)?(?!I\b)"
            r"['\"]?([A-Za-z_]\w*)['\"]?(?:\s+([A-Za-z_]\w*))?",
            re.I,
        ),
        lambda m: _trace_needs(m.group(1), m.group(2)),
    ),
    # "trace X [Y]" / "how does X [Y] work" / "walk me through X [Y]"
    (
        re.compile(
            r"(?:trace(?:\s+implementation\s+of)?|how\s+does\s+|walk\s+(?:me\s+)?through\s+)"
            r"(?:a\s+|an\s+|the\s+)?"
            r"['\"]?([A-Za-z_]\w*)['\"]?(?:\s+([A-Za-z_]\w*))?",
            re.I,
        ),
        lambda m: _trace_needs(m.group(1), m.group(2)),
    ),
    # "what does X.py do" / "describe X.py" / "explain X.py" - file form before symbol
    (
        re.compile(
            r"(?:what\s+does\s+|describe\s+(?:the\s+)?(?:file\s+)?|explain\s+)"
            r"['\"]?([A-Za-z_][\w/\\]*\.py)['\"]?",
            re.I,
        ),
        lambda m: [
            f"findings for {m.group(1).replace('/', '_').replace(chr(92), '_')}",
            f"what does {m.group(1)} do",
            f"symbols in {m.group(1)}",
        ],
    ),
    # "what symbols [are/exist] in X.py" / "list symbols in X.py" / "symbols in X.py"
    # also "what functions/classes are in X.py" / "what is in X.py"
    # also "what are all the classes in X.py" / "what are the functions in X.py"
    (
        re.compile(
            r"(?:what\s+(?:symbols?|functions?|classes?|methods?|is)\s+(?:are\s+|exist\s+)?in\s+|"
            r"what\s+are\s+(?:all\s+(?:the\s+)?)?(?:symbols?|functions?|classes?|methods?)\s+in\s+|"
            r"list\s+(?:a\s+|an\s+|the\s+)?(?:symbols?|functions?|classes?|methods?)\s+in\s+|"
            r"symbols?\s+in\s+)"
            r"['\"]?([A-Za-z_][\w/\\]*\.py)['\"]?",
            re.I,
        ),
        lambda m: [
            f"symbols in {m.group(1)}",
            f"findings for {m.group(1).replace('/', '_').replace(chr(92), '_')}",
        ],
    ),
    # "what does X [Y] do" / "explain X [Y]" / "purpose of X [Y]" / "describe X" (symbol form)
    # Captures optional second word for compound terms like "escalation engine"
    (
        re.compile(
            r"(?:what\s+does\s+|explain\s+|purpose\s+of\s+|describe\s+(?:the\s+)?)"
            r"(?:a\s+|an\s+|the\s+)?"
            r"['\"]?([A-Za-z_]\w*)['\"]?(?:\s+([A-Za-z_]\w*))?",
            re.I,
        ),
        lambda m: _explain_needs(m.group(1), m.group(2)),
    ),
    # "what calls X" / "callers of X" / "who calls X" / "what invokes X" / "what uses X"
    (
        re.compile(
            r"(?:what\s+(?:calls|invokes?|uses?)|callers?\s+of|who\s+calls)\s+['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"what calls {m.group(1)}",
            f"symbols named {m.group(1)}",
        ],
    ),
    # "where is X used"
    (
        re.compile(r"where\s+is\s+['\"]?([A-Za-z_]\w*)['\"]?\s+used", re.I),
        lambda m: [
            f"what calls {m.group(1)}",
            f"symbols named {m.group(1)}",
        ],
    ),
    # "where is X defined" / "where is X located" / "where is X implemented"
    (
        re.compile(
            r"where\s+is\s+(?:the\s+|a\s+|an\s+)?['\"]?([A-Za-z_]\w*)['\"]?"
            r"\s+(?:defined|located|implemented|declared|found)",
            re.I,
        ),
        lambda m: [
            f"symbols named {m.group(1)}",
            f"files matching {m.group(1)}",
            f"findings for {m.group(1)}",
        ],
    ),
    # "what files import from X" / "what imports X" / "who imports X"
    (
        re.compile(
            r"(?:what\s+(?:files?\s+)?(?:import\s+from|imports?)|who\s+imports?)\s+"
            r"['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"what calls {m.group(1)}",
            f"symbols named {m.group(1)}",
            f"files matching {m.group(1)}",
        ],
    ),
    # "files that use X" / "list files that use X" / "list all files using X"
    (
        re.compile(
            r"(?:(?:can\s+you\s+)?list\s+(?:all\s+)?)?files?\s+(?:that\s+|which\s+)?use\s+"
            r"['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"what calls {m.group(1)}",
            f"symbols named {m.group(1)}",
            f"files matching {m.group(1)}",
        ],
    ),
    # "show me how X is used" / "show me an example of how X" / "example of X usage"
    # Must be before survey heuristic so 'show me' + skip-words don't capture 'example'
    (
        re.compile(
            r"(?:show\s+me\s+(?:an?\s+)?(?:example\s+of\s+)?how\s+|example\s+of\s+how\s+)"
            r"(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"what calls {m.group(1)}",
            f"symbols named {m.group(1)}",
            f"callees of {m.group(1)}",
            f"findings for {m.group(1)}",
        ],
    ),

    # "what has no docstrings" / "what functions are missing docstrings" / "undocumented code"
    # "show me functions without docstrings" / "find undocumented functions"
    (
        re.compile(
            r"(?:what\s+(?:functions?|classes?|symbols?|code)\s+(?:have?|has|are?|is)\s+"
            r"(?:no|missing|without|lacking)\s+docstrings?|"
            r"(?:show\s+(?:me\s+)?)?(?:functions?|classes?|symbols?|code)\s+(?:without|with\s+no|missing|lacking)\s+docstrings?|"
            r"(?:find|list|show)\s+(?:all\s+)?undocumented\s+(?:functions?|classes?|symbols?|code)|"
            r"(?:undocumented|missing\s+docstrings?|no\s+docstrings?))",
            re.I,
        ),
        lambda m: ["missing docstrings"],
    ),

    # "what has TODOs" / "find all TODOs" / "what is unfinished" / "show me FIXMEs"
    (
        re.compile(
            r"(?:what\s+(?:has|have|contains?)\s+(?:todos?|fixmes?|hacks?)|"
            r"(?:find|show|list)\s+(?:all\s+)?(?:todos?|fixmes?|hacks?|unfinished)|"
            r"what\s+is\s+unfinished|what\s+needs?\s+(?:to\s+be\s+)?(?:done|fixed|finished))",
            re.I,
        ),
        lambda m: ["find todos", "findings of kind known_issue"],
    ),

    # "what changed in X" / "when was X last modified" / "recent changes to X"
    # "what was modified in X" / "git history for X"
    (
        re.compile(
            r"(?:what\s+(?:changed?|was\s+(?:changed?|modified?))\s+(?:recently\s+)?(?:in|to|for)\s+|"
            r"when\s+was\s+(?:the\s+)?['\"]?(\S+?)['\"]?\s+(?:last\s+)?(?:changed?|modified?|updated?)|"
            r"(?:recent|latest)\s+(?:changes?|commits?|updates?)\s+(?:to|in|for)\s+|"
            r"(?:git\s+)?(?:history|log)\s+(?:of|for)\s+|"
            r"show\s+(?:me\s+)?(?:the\s+)?(?:git\s+)?(?:history|log)\s+(?:of|for)\s+)"
            r"(?:the\s+|a\s+|an\s+)?['\"]?([A-Za-z_][\w./]*)['\"]?",
            re.I,
        ),
        lambda m: (lambda t: [
            f"git history of {t}",
            f"symbols named {t}",
            f"findings for {t}",
        ])(next(g for g in m.groups() if g)),
    ),

    # "how was X implemented" / "find something similar to X" / "what follows the same pattern as X"
    # "same pattern as X" / "what is similar to X" / "other things like X"
    (
        re.compile(
            r"(?:how\s+(?:was|were|is|are)\s+(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?"
            r"\s+(?:implemented|built|structured|designed|done)|"
            r"find\s+(?:something\s+)?similar\s+to\s+(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?|"
            r"(?:what\s+is\s+)?similar\s+to\s+(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?|"
            r"(?:same\s+pattern\s+as|same\s+as)\s+(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?|"
            r"what\s+(?:else\s+)?follows\s+(?:the\s+)?(?:same\s+)?pattern\s+(?:as\s+|of\s+)"
            r"(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?|"
            r"(?:other|similar)\s+(?:things?|classes?|modules?)\s+like\s+"
            r"(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?)",
            re.I,
        ),
        lambda m: _similar_needs(next(g for g in m.groups() if g)),
    ),

    # "if I change X what breaks" / "what depends on X" / "impact of changing X"
    # "what would break if I modify X" / "blast radius of X" / "ripple effect of X"
    (
        re.compile(
            r"(?:if\s+I\s+(?:change|modify|refactor|rename|remove|delete)\s+"
            r"(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?|"
            r"(?:what|which)\s+(?:breaks?|depends?\s+on|is\s+affected\s+by|would\s+break)\s+"
            r"(?:if\s+I\s+(?:change|modify)?\s*)?(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?|"
            r"what\s+would\s+break\s+if\s+I\s+(?:change|modify|refactor)\s+"
            r"(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?|"
            r"impact\s+of\s+(?:changing\s+)?(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?|"
            r"(?:ripple(?:\s+effect)?|blast\s+radius)\s+(?:of\s+|from\s+)?(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?)",
            re.I,
        ),
        lambda m: (lambda t: [
            f"brief for {t}",
            f"what calls {t}",
            f"findings for {t}",
        ])(next(g for g in m.groups() if g)),
    ),

    # --- Workflow heuristics ---

    # "what's next" / "what should I work on" / "what are my priorities" / "dev plan"
    # "what's next on the backlog" / "what is the top priority" / "what should I do next"
    (
        re.compile(
            r"(?:what'?s?\s+next(?:\s+on\s+(?:the\s+)?(?:backlog|list|queue))?|"
            r"what\s+should\s+I\s+(?:work\s+on|do(?:\s+next)?|focus\s+on)|"
            r"what\s+(?:is|are)\s+(?:the\s+)?(?:my\s+)?(?:top\s+)?priorit(?:y|ies)|"
            r"(?:show\s+(?:me\s+)?)?(?:my\s+)?(?:current\s+)?priorities|"
            r"workflow\s+status|what\s+am\s+I\s+working\s+on|"
            r"(?:show\s+(?:me\s+)?(?:the\s+)?|what(?:'?s|\s+is)\s+(?:the\s+)?)"
            r"dev(?:elopment)?\s+plan)",
            re.I,
        ),
        lambda m: ["prioritize work"],
    ),

    # "reprioritize" / "suggest order" / "what should I do first"
    # Returns workflow status so Ollama can read it and suggest priority order
    (
        re.compile(
            r"(?:reprioritize|re-prioritize|suggest\s+(?:priority\s+)?order|"
            r"what\s+should\s+I\s+(?:do|tackle|start)\s+first)",
            re.I,
        ),
        lambda m: ["workflow status", "entry points"],
    ),

    # --- Breadth / survey heuristics ---

    # "find all files related to X" / "find files about X"
    (
        re.compile(
            r"find\s+(?:all\s+)?files?\s+(?:related\s+to|about|for|matching)\s+"
            r"(?:a\s+|an\s+|the\s+)?['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"files matching {m.group(1)}",
            f"symbols named {m.group(1)}",
            f"findings for {m.group(1)}",
        ],
    ),

    # "what modules/files exist in X/" / "what is in world/"
    # "list files in the X directory" / "what files are in the X folder"
    # "how many files are in X"
    (
        re.compile(
            r"(?:what\s+(?:modules?|files?)\s+(?:exist|are)\s+in\s+|"
            r"list\s+(?:the\s+)?(?:modules?|files?)\s+in\s+|"
            r"how\s+many\s+(?:files?|modules?)\s+are\s+in\s+|"
            r"what\s+is\s+in\s+)"
            r"(?:the\s+|a\s+|an\s+)?['\"]?([A-Za-z_][\w/]*/?)['\"]?"
            r"(?:\s+(?:folder|directory|dir|package|module))?",
            re.I,
        ),
        lambda m: [
            f"files in {m.group(1).rstrip('/')}",
        ],
    ),

    # "what exists for X" / "find everything about X" / "what's related to X"
    # / "survey X" / "what's there for X"
    # Skips leading articles (a/an/the) before the key term.
    (
        re.compile(
            r"(?:what\s+exists?\s+for\s+|"
            r"find\s+(?:everything|all)\s+(?:about|for|related\s+to)\s+|"
            r"what'?s?\s+(?:there\s+for|related\s+to)\s+|"
            r"what\s+is\s+(?:the\s+)?(?:current\s+)?(?:state|status)\s+of\s+(?:the\s+)?|"
            r"what\s+is\s+(?:the\s+)?(?:architecture|design|structure|overview)\s+of\s+(?:the\s+)?|"
            r"describe\s+(?:the\s+)?(?:architecture|design|structure|overview)\s+of\s+(?:the\s+)?|"
            r"tell\s+me\s+(?:more\s+)?about\s+(?:the\s+)?|"
            r"what\s+is\s+(?!(?:the\s+)?(?:most|least|best|worst|biggest|largest|smallest|simplest|hardest|easiest|fastest|slowest)\b)|"
            r"show\s+me\s+(?:all\s+|everything\s+(?:about|for)\s+)?(?:the\s+)?|"
            r"survey\s+)"
            r"(?:a\s+|an\s+|the\s+)?"
            r"['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"symbols named {m.group(1)}",
            f"files matching {m.group(1)}",
            f"findings for {m.group(1)}",
        ],
    ),

    # "trace data flow of X" / "trace mutations in X" / "what does X mutate"
    # / "what side effects does X have" / "does X mutate state"
    (
        re.compile(
            r"(?:trace\s+(?:data\s+)?flow\s+(?:of|for|through)\s+['\"]?([A-Za-z_]\w*)['\"]?|"
            r"trace\s+mutations?\s+(?:in|of|for)\s+['\"]?([A-Za-z_]\w*)['\"]?|"
            r"what\s+(?:does\s+['\"]?([A-Za-z_]\w*)['\"]?\s+mutate|"
            r"side\s+effects?\s+does\s+['\"]?([A-Za-z_]\w*)['\"]?\s+have)|"
            r"does\s+['\"]?([A-Za-z_]\w*)['\"]?\s+mutate\s+(?:state|data|anything))",
            re.I,
        ),
        lambda m: (lambda t: [
            f"trace data flow of {t}",
            f"symbols named {t}",
        ])(next(g for g in m.groups() if g)),
    ),

    # "what role does X play" / "infer behavior of X" / "what is the behavioral role of X"
    # / "what kind of object is X" / "classify X"
    (
        re.compile(
            r"(?:what\s+(?:(?:behavioral\s+)?role|kind\s+of\s+(?:object|class|function))\s+"
            r"(?:does\s+['\"]?([A-Za-z_]\w*)['\"]?\s+(?:play|have|fulfill)|"
            r"is\s+['\"]?([A-Za-z_]\w*)['\"]?)|"
            r"infer\s+(?:behavior|role)\s+(?:of|for)\s+['\"]?([A-Za-z_]\w*)['\"]?|"
            r"(?:classify|categorize)\s+['\"]?([A-Za-z_]\w*)['\"]?\s+(?:by\s+role|behaviorally)?)",
            re.I,
        ),
        lambda m: (lambda t: [
            f"infer behavior of {t}",
            f"symbols named {t}",
        ])(next(g for g in m.groups() if g)),
    ),

    # "how would I add X" / "how do I implement X" / "how should I build X"
    # / "where would I add/put X" / "implement a new X" / "build a new X"
    # Skips leading articles (a, an, the) before the subject word.
    (
        re.compile(
            r"(?:how\s+(?:would\s+I|do\s+I|should\s+I|to)\s+(?:add|implement|extend|build|create|integrate)|"
            r"where\s+would\s+I\s+(?:add|put|place)|"
            r"(?:implement|build|create)\s+(?:a\s+|an\s+|the\s+)?(?:new\s+|different\s+|custom\s+)?(?=[A-Za-z_]))"
            r"\s*(?:a\s+|an\s+|the\s+)?(?:new\s+|different\s+|custom\s+)?['\"]?([A-Za-z_]\w*)['\"]?",
            re.I,
        ),
        lambda m: [
            f"symbols named {m.group(1)}",
            f"files matching {m.group(1)}",
            f"entry points",
            f"findings for {m.group(1)}",
        ],
    ),
]


def detect_heuristic(question: str) -> list[str] | None:
    """
    Check if the question matches a named heuristic pattern.
    Returns pre-wired NEED lines if matched, None otherwise.
    Tries patterns in order; first match wins.
    """
    for pattern, builder in _HEURISTICS:
        m = pattern.search(question)
        if m:
            return builder(m)
    return None


def parse_needs(model_output: str) -> list[str]:
    """
    Extract NEED lines from Phase 1 model output.
    Accepts 'NEED: ...' or '- NEED: ...' or '* NEED: ...' forms.
    Returns list of need strings (stripped, lowercased).
    """
    needs = []
    for line in model_output.splitlines():
        line = line.strip()
        m = re.match(r"[-*]?\s*NEED:\s*(.+)", line, re.I)
        if m:
            needs.append(m.group(1).strip())
    return needs


def resolve_need(need: str) -> tuple[str, dict] | None:
    """
    Map a single NEED string to (tool_name, args_dict).
    Returns None if no pattern matches.
    """
    for pattern, tool_name, arg_key, group_idx in _PATTERNS:
        m = pattern.search(need)
        if m:
            # Special case: store_workflow_item - kind + content from two groups
            if tool_name == "store_workflow_item":
                groups = [g for g in m.groups() if g is not None]
                if len(groups) >= 2:
                    kind = groups[0].strip().lower().rstrip("s")  # normalize plural
                    if kind == "future_plan":
                        pass  # already correct
                    return tool_name, {
                        "kind": kind,
                        "subject": groups[1].strip()[:60],
                        "content": groups[1].strip(),
                    }
                continue

            # Special case: graph_path needs two named args (src, dst)
            if tool_name == "graph_path":
                groups = [g for g in m.groups() if g is not None]
                if len(groups) >= 2:
                    return tool_name, {"src": groups[0].strip(), "dst": groups[1].strip()}
                continue

            # No-arg tools (entry points, clusters)
            if arg_key is None:
                return tool_name, {}

            if group_idx is None:
                value = next((g for g in m.groups() if g is not None), "").strip()
            else:
                value = m.group(group_idx).strip() if m.group(group_idx) else ""

            # Strip glob characters - the DB uses substring matching, not glob
            if tool_name in ("search_files", "search_symbols"):
                value = value.replace("*", "").replace("?", "").strip()

            # "files in X.py" is a file treated as a directory - redirect to describe_file
            if tool_name == "files_in_directory" and value.endswith(".py"):
                return "describe_file", {"file_path": value}

            # No-arg tools where group is optional (e.g. most_connected with no filter)
            if not value and tool_name in ("graph_most_connected",):
                return tool_name, {}

            if value:
                return tool_name, {arg_key: value}
    return None


# Tools that take a symbol name as their primary arg - eligible for root resolution
_SYMBOL_ARG_TOOLS = frozenset({
    "list_callers", "list_callees", "symbol_intent", "symbol_brief",
    "get_findings", "graph_subgraph",
})


def _resolve_to_symbol(keyword: str, oracle: "DBOracle") -> str:
    """
    Given a bare keyword, try to find the actual symbol name in the corpus.
    Priority: exact match > starts-with match > substring match > original.
    Returns the best symbol name found, or the original keyword unchanged.
    """
    if not keyword:
        return keyword
    try:
        rows = oracle.find_symbols(keyword, limit=20)
    except Exception:
        return keyword
    if not rows:
        return keyword

    kw_lower = keyword.lower()
    exact = [r["name"] for r in rows if r["name"].lower() == kw_lower]
    if exact:
        return exact[0]

    # Prefer symbols that START with the keyword (e.g. "authority" -> "AuthoritySystem")
    starts = [r["name"] for r in rows if r["name"].lower().startswith(kw_lower)]
    if starts:
        # Among prefix matches, prefer shorter names (more specific root)
        return min(starts, key=len)

    # Fall back to first substring match
    return rows[0]["name"]


def resolve_all(
    needs: list[str],
    oracle: "DBOracle",
    assessor: "Assessor",
) -> list[dict]:
    """
    Resolve and execute all NEEDs. Returns list of fact dicts:
      { "need": str, "tool": str, "args": dict, "result": str }
    Unmatched NEEDs are included with tool="unmatched" and result="".
    Duplicate (tool, args) pairs are deduplicated - each unique call runs once.
    """
    facts = []
    seen: set[tuple] = set()

    for need in needs:
        resolved = resolve_need(need)
        if resolved is None:
            facts.append({"need": need, "tool": "unmatched", "args": {}, "result": ""})
            continue

        tool_name, args = resolved

        # Root resolution: if the tool takes a symbol name, resolve bare keywords
        # to actual corpus symbol names (e.g. "authority" -> "AuthoritySystem").
        if tool_name in _SYMBOL_ARG_TOOLS:
            arg_key = next((k for k in ("symbol", "src", "dst") if k in args), None)
            if arg_key and args[arg_key]:
                args = dict(args)
                args[arg_key] = _resolve_to_symbol(args[arg_key], oracle)

        dedup_key = (tool_name, tuple(sorted(args.items())))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        result = dispatch(tool_name, args, oracle, assessor)
        facts.append({"need": need, "tool": tool_name, "args": args, "result": result})

    return facts


# ------------------------------------------------------------------
# Phase 2b: auto-expansion
# Extract leads from Phase 2 results and run follow-up tool calls.
# All pure Python - no AI call needed.
# ------------------------------------------------------------------

_SYM_LINE = re.compile(r"^\s+(\w+)\s+\(\w+\)\s+in\s+\S+\s+line\s+\d+")
_FILE_LINE = re.compile(r"^\s+(\S+\.py)\s+\(\d+\s+lines\)")
_SIF_LINE  = re.compile(r"^\s+line\s+\d+:\s+(?:function|class)\s+(\w+)")

_MAX_EXPAND = 5  # max symbols or files to follow up per result

# Generic boilerplate names not worth expanding - they appear everywhere
# and produce noisy, question-irrelevant results.
_EXPANSION_NOISE = frozenset({
    "__init__", "__str__", "__repr__", "__eq__", "__hash__", "__len__",
    "__iter__", "__next__", "__contains__", "__getitem__", "__setitem__",
    "__delitem__", "__enter__", "__exit__", "__call__", "__del__",
    "to_dict", "from_dict", "to_json", "from_json", "serialize",
    "deserialize", "update", "get", "set", "reset", "clear",
})


def _symbols_from_result(result: str) -> list[str]:
    """Extract symbol names from search_symbols or symbols_in_file output.
    Filters out generic boilerplate names that add noise to expansion."""
    names = []
    for line in result.splitlines():
        m = _SYM_LINE.match(line) or _SIF_LINE.match(line)
        if m:
            name = m.group(1)
            if name not in _EXPANSION_NOISE and not name.startswith("__"):
                names.append(name)
        if len(names) >= _MAX_EXPAND:
            break
    return names


def _files_from_result(result: str) -> list[str]:
    """Extract .py file paths from files_in_directory or search_files output."""
    paths = []
    for line in result.splitlines():
        m = _FILE_LINE.match(line)
        if m:
            paths.append(m.group(1))
        if len(paths) >= _MAX_EXPAND:
            break
    return paths


def _run_expansion(
    tool_name: str,
    args: dict,
    result: str,
    seen: set[tuple],
    oracle: "DBOracle",
    assessor: "Assessor",
) -> list[dict]:
    """
    Given one Phase 2 result, produce follow-up facts (Phase 2b).
    Expansion rules:
      search_symbols / symbols_in_file -> list_callers + symbol_intent per symbol
      files_in_directory / search_files -> symbols_in_file + get_findings per file
      list_callers                      -> symbol_intent per caller name
    """
    expansions = []

    if tool_name in ("files_in_directory", "search_files"):
        for fpath in _files_from_result(result):
            fname = fpath.replace("\\", "/").split("/")[-1]
            for follow_tool, follow_args in [
                ("get_findings", {"symbol": fname}),
            ]:
                key = (follow_tool, tuple(sorted(follow_args.items())))
                if key in seen:
                    continue
                seen.add(key)
                r = dispatch(follow_tool, follow_args, oracle, assessor)
                expansions.append({
                    "need": f"[auto] {follow_tool}({fname})",
                    "tool": follow_tool,
                    "args": follow_args,
                    "result": r,
                })

    if tool_name in ("search_symbols", "symbols_in_file", "list_callers"):
        # When expanding from symbols_in_file, pass the source file so
        # symbol_intent picks the right definition (disambiguation fix).
        file_hint = args.get("file_path", "") if tool_name == "symbols_in_file" else ""
        intent_args = {"symbol": None, "file_path": file_hint} if file_hint else {"symbol": None}
        for sym in _symbols_from_result(result):
            intent_a = {**intent_args, "symbol": sym}
            for follow_tool, follow_args in [
                ("list_callers",  {"symbol": sym}),
                ("symbol_intent", intent_a),
            ]:
                key = (follow_tool, tuple(sorted(follow_args.items())))
                if key in seen:
                    continue
                seen.add(key)
                r = dispatch(follow_tool, follow_args, oracle, assessor)
                expansions.append({
                    "need": f"[auto] {follow_tool}({sym})",
                    "tool": follow_tool,
                    "args": follow_args,
                    "result": r,
                })

    return expansions


def expand_facts(
    facts: list[dict],
    oracle: "DBOracle",
    assessor: "Assessor",
    seen: set[tuple],
) -> list[dict]:
    """
    Phase 2b: run one round of follow-up tool calls based on Phase 2 results.
    Returns new fact dicts to append (does not mutate `facts`).
    `seen` is the dedup set from resolve_all, passed in and extended in place.
    """
    new_facts = []
    for f in facts:
        if f["tool"] == "unmatched" or not f["result"]:
            continue
        new_facts.extend(_run_expansion(f["tool"], f["args"], f["result"], seen, oracle, assessor))
    return new_facts


def resolve_and_expand(
    needs: list[str],
    oracle: "DBOracle",
    assessor: "Assessor",
) -> list[dict]:
    """
    Phase 2 + Phase 2b combined entry point.
    Returns all facts (Phase 2 results + auto-expansion follow-ups).
    """
    seen: set[tuple] = set()

    # Phase 2 - primary resolution
    facts = []
    for need in needs:
        resolved = resolve_need(need)
        if resolved is None:
            facts.append({"need": need, "tool": "unmatched", "args": {}, "result": ""})
            continue
        tool_name, args = resolved
        key = (tool_name, tuple(sorted(args.items())))
        if key in seen:
            continue
        seen.add(key)
        result = dispatch(tool_name, args, oracle, assessor)
        facts.append({"need": need, "tool": tool_name, "args": args, "result": result})

    # Phase 2b - auto-expansion
    facts.extend(expand_facts(facts, oracle, assessor, seen))

    # Phase 2c - LINK: find relationships between symbols discovered so far
    facts.extend(link_facts(facts, oracle, seen))

    return facts


def link_facts(
    facts: list[dict],
    oracle: "DBOracle",
    seen: set[tuple],
) -> list[dict]:
    """
    Phase 2c LINK: given the collected facts, find call paths between
    discovered symbols and surface the most-connected one.
    Adds connective tissue so Phase 3 sees relationships, not just a flat list.
    Limits to avoid noise: max 3 paths, only between symbols that appear in
    multiple fact results (i.e. genuinely relevant).
    """
    from determined.agent.graph_utils import shortest_path, most_connected

    # Collect all symbol names mentioned across fact results
    sym_freq: dict[str, int] = {}
    for f in facts:
        if f["tool"] == "unmatched" or not f["result"]:
            continue
        for name in _symbols_from_result(f["result"]):
            sym_freq[name] = sym_freq.get(name, 0) + 1

    # Only symbols mentioned in 2+ results are genuinely cross-cutting
    hot_syms = [s for s, c in sym_freq.items() if c >= 2][:6]

    links = []

    # Find shortest paths between pairs of hot symbols
    paths_found = 0
    for i, src in enumerate(hot_syms):
        for dst in hot_syms[i+1:]:
            if paths_found >= 3:
                break
            key = ("graph_path", tuple(sorted([("dst", dst), ("src", src)])))
            if key in seen:
                continue
            seen.add(key)
            path = shortest_path(oracle, src, dst)
            if path and 1 < len(path) <= 6:
                result = f"Call path from '{src}' to '{dst}':\n  " + " -> ".join(path)
                links.append({
                    "need": f"[link] path {src} -> {dst}",
                    "tool": "graph_path",
                    "args": {"src": src, "dst": dst},
                    "result": result,
                })
                paths_found += 1

    return links


def facts_to_text(facts: list[dict]) -> str:
    """
    Format fact set as readable text block for Phase 3 prompt.
    Skips unmatched and empty results.
    """
    sections = []
    for f in facts:
        if f["tool"] == "unmatched" or not f["result"]:
            continue
        sections.append(f["result"])
    return "\n\n".join(sections) if sections else "(no facts retrieved)"
