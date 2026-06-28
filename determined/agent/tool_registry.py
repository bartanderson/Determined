"""
Tool registry for the Determined analysis agent.

REGISTRY   - full metadata for every tool (purpose, args, output, feeds, use_when)
TASK_PATTERNS - named workflows: task name -> ordered tool sequence with rationale
describe_tool - tool function: on-demand rich detail for any tool by name

Design note: system prompt stays short (one line per tool) for the small model.
Call describe_tool at the start of a session or when the model needs detail.
"""

from __future__ import annotations

# ------------------------------------------------------------------
# Tool registry
# Each entry:
#   purpose   - one sentence: what this tool does
#   args      - {arg_name: description} dict
#   output    - what the return string contains
#   feeds     - list of tools that naturally follow this one
#   use_when  - when to reach for this tool (vs alternatives)
#   category  - discovery | understanding | graph | knowledge | workflow | meta
# ------------------------------------------------------------------

REGISTRY: dict[str, dict] = {

    # ── DISCOVERY ──────────────────────────────────────────────────
    "search_symbols": {
        "purpose": "Find functions and classes by name substring.",
        "args": {"query": "name fragment to search"},
        "output": "name, file, line, type for up to 20 matches",
        "feeds": ["symbol_intent", "list_callers", "risk_profile", "symbol_brief"],
        "use_when": "You have a partial name and need the full symbol location.",
        "category": "discovery",
    },
    "search_files": {
        "purpose": "Find files by path substring.",
        "args": {"query": "path fragment to match"},
        "output": "matching file paths with line counts",
        "feeds": ["symbols_in_file", "describe_file", "files_in_directory"],
        "use_when": "You know part of a filename and need the full path.",
        "category": "discovery",
    },
    "list_callers": {
        "purpose": "Show all functions that directly call a given symbol.",
        "args": {"symbol": "exact or qualified symbol name"},
        "output": "caller name, file, line for each direct caller",
        "feeds": ["risk_profile", "graph_subgraph", "list_callers"],
        "use_when": "Assessing impact of changing a symbol; tracing who depends on it.",
        "category": "discovery",
    },
    "list_callees": {
        "purpose": "Show all functions a given symbol calls.",
        "args": {"symbol": "exact symbol name"},
        "output": "callee name, file, line for each call site",
        "feeds": ["symbol_intent", "risk_profile"],
        "use_when": "Understanding what a symbol depends on; tracing outward dependencies.",
        "category": "discovery",
    },
    "symbols_in_file": {
        "purpose": "List all functions and classes defined in a file.",
        "args": {"file_path": "relative or bare filename"},
        "output": "line number, type, name, has-docstring flag for each symbol",
        "feeds": ["symbol_intent", "list_callers", "risk_profile"],
        "use_when": "Exploring a file's surface area before diving into a symbol.",
        "category": "discovery",
    },
    "files_in_directory": {
        "purpose": "List all files in a directory from the corpus.",
        "args": {"path": "relative directory name e.g. 'world' or 'dungeon_neo'"},
        "output": "file paths with line counts",
        "feeds": ["symbols_in_file", "describe_file"],
        "use_when": "Exploring what a module or folder contains.",
        "category": "discovery",
    },

    # ── UNDERSTANDING ──────────────────────────────────────────────
    "describe_file": {
        "purpose": "AI semantic summary of a file's role and contents (uses Ollama).",
        "args": {"file_path": "relative or bare filename"},
        "output": "natural-language summary; cached on second call",
        "feeds": ["symbols_in_file", "get_findings", "store_finding"],
        "use_when": "You need to understand what a file does before querying its symbols.",
        "category": "understanding",
    },
    "symbol_intent": {
        "purpose": "Return the docstring for a function or class (Layer 2, no LLM).",
        "args": {"symbol": "function or class name", "file_path": "(optional) disambiguate by file"},
        "output": "docstring text or 'no docstring' note with file/line",
        "feeds": ["list_callers", "risk_profile", "get_findings"],
        "use_when": "Quick intent check from source; faster than describe_file.",
        "category": "understanding",
    },
    "symbol_brief": {
        "purpose": "Richest single-symbol view: risk badge + callers + impact zone.",
        "args": {"symbol": "function or class name"},
        "output": "HOT/WARM/SAFE badge, reason list, caller tree, blast radius",
        "feeds": ["store_finding", "list_findings_by_kind"],
        "use_when": "Deep dive on one symbol before modifying it.",
        "category": "understanding",
    },
    "risk_profile": {
        "purpose": "Structural change-risk rating: HOT/WARM/SAFE with reasons.",
        "args": {"symbol": "function or class name"},
        "output": "badge + in_degree, out_degree, mutation_count, reason list",
        "feeds": ["list_callers", "graph_subgraph"],
        "use_when": "Fast risk check before touching a symbol; lighter than symbol_brief.",
        "category": "understanding",
    },

    # ── GRAPH ──────────────────────────────────────────────────────
    "graph_path": {
        "purpose": "Find shortest call path between two symbols.",
        "args": {"src": "starting symbol", "dst": "target symbol"},
        "output": "ordered chain of symbols from src to dst, or 'no path'",
        "feeds": ["symbol_intent", "risk_profile"],
        "use_when": "Understanding how control flows from one part of the code to another.",
        "category": "graph",
    },
    "graph_entry_points": {
        "purpose": "Show functions with no callers (roots of the call graph).",
        "args": {},
        "output": "list of entry-point symbol names with file locations",
        "feeds": ["list_callees", "risk_profile"],
        "use_when": "Orienting to a codebase; finding where execution begins.",
        "category": "graph",
    },
    "graph_most_connected": {
        "purpose": "Return the most-called project symbols (by in-degree).",
        "args": {"filter": "(optional) path fragment to limit scope"},
        "output": "ranked list: symbol, file, in-degree count",
        "feeds": ["risk_profile", "list_callers", "symbol_brief"],
        "use_when": "Finding architectural hot spots; high-degree = high risk.",
        "category": "graph",
    },
    "graph_subgraph": {
        "purpose": "Show immediate neighbors (callers + callees) of a symbol.",
        "args": {"symbol": "central symbol"},
        "output": "callers and callees one hop out",
        "feeds": ["risk_profile", "symbol_intent"],
        "use_when": "Local topology view around a symbol without full blast-radius.",
        "category": "graph",
    },
    "graph_clusters": {
        "purpose": "Detect file-level clusters (tightly coupled file groups).",
        "args": {},
        "output": "cluster list with member files and coupling strength",
        "feeds": ["files_in_directory", "describe_file"],
        "use_when": "Finding hidden coupling; planning module boundaries.",
        "category": "graph",
    },

    # ── KNOWLEDGE ──────────────────────────────────────────────────
    "get_findings": {
        "purpose": "Retrieve stored knowledge artifacts and semantic summaries for a symbol.",
        "args": {"symbol": "function, class, or file::symbol subject"},
        "output": "findings list by kind/provenance; includes LLM summaries; stale flags",
        "feeds": ["store_finding", "list_findings_by_kind"],
        "use_when": "Check what is already known before asking the LLM again.",
        "category": "knowledge",
    },
    "store_finding": {
        "purpose": "Save a non-obvious finding to knowledge.db for future sessions.",
        "args": {"symbol": "subject", "kind": "artifact kind e.g. 'bug', 'design_note'", "content": "finding text"},
        "output": "confirmation with artifact ID",
        "feeds": ["get_findings"],
        "use_when": "After discovering something important that would be lost after the session.",
        "category": "knowledge",
    },
    "list_findings_by_kind": {
        "purpose": "List all stored artifacts of a given kind across the corpus.",
        "args": {"kind": "structural: 'hot' | 'dead' | 'entry' | 'stub'; "
                         "knowledge: 'design_note' | 'known_issue' | 'file_purpose' | "
                         "'strategy_decision' | 'query_finding'"},
        "output": "subject + content snippet for each matching artifact",
        "feeds": ["get_findings", "symbol_brief"],
        "use_when": "Broad sweep: all hot symbols (kind='hot'), all dead code (kind='dead'), "
                    "all stubs (kind='stub'), all entry points (kind='entry').",
        "category": "knowledge",
    },
    "knowledge_status": {
        "purpose": "Coverage report: how many files have semantic summaries vs total corpus.",
        "args": {},
        "output": "files summarized / total, artifact counts by kind",
        "feeds": ["describe_file", "extract_design_facts"],
        "use_when": "At session start to gauge what the knowledge layer already knows.",
        "category": "knowledge",
    },
    "extract_design_facts": {
        "purpose": "Structural fact extraction without LLM: entry points, dead code, hot symbols, stub files.",
        "args": {"min_in_degree": "(optional int) threshold for hot-symbol classification"},
        "output": "counts written to knowledge.db; summary of what was stored",
        "feeds": ["list_findings_by_kind", "knowledge_status"],
        "use_when": "After ingesting a new corpus to populate knowledge.db with graph-derived facts.",
        "category": "knowledge",
    },
    "ask_truth_layer": {
        "purpose": "Ask a free-form question; Ollama reasons over stored knowledge artifacts.",
        "args": {"question": "natural language question about the codebase"},
        "output": "LLM-generated answer grounded in knowledge artifacts",
        "feeds": ["store_finding", "get_findings"],
        "use_when": "Synthesis question that crosses multiple symbols or files.",
        "category": "knowledge",
    },

    # ── STUB TOOLS ─────────────────────────────────────────────────
    "list_stubs": {
        "purpose": "List stub functions ranked by caller count (highest priority first).",
        "args": {"limit": "(optional) max results, default 20"},
        "output": "stub name, file, caller count",
        "feeds": ["project_stub", "risk_profile"],
        "use_when": "Finding which stubs are blocking the most callers; deciding what to implement next.",
        "category": "discovery",
    },
    "project_stub": {
        "purpose": "Generate a concrete implementation for a stub function using call-graph context.",
        "args": {"symbol": "name of the stub function to implement"},
        "output": "suggested function body with context summary",
        "feeds": ["store_finding", "symbol_intent"],
        "use_when": "You want to fill a stub with a reasonable implementation guided by callers and contracts.",
        "category": "understanding",
    },

    # ── DESIGN DOCS ────────────────────────────────────────────────
    "discover_docs": {
        "purpose": "Find all documentation files in the project, ranked by design-relevance.",
        "args": {},
        "output": "inventory of doc files with type, size, heading count, and constraint density score",
        "feeds": ["ingest_design_docs"],
        "use_when": "First step when orienting to an unfamiliar project — find what docs exist before reading code.",
        "category": "discovery",
    },
    "ingest_design_docs": {
        "purpose": "Extract design rules from project docs and store as design_note artifacts.",
        "args": {"min_score": "minimum constraint density score to process (default 0.05)"},
        "output": "count of rules stored and list of docs processed",
        "feeds": ["knowledge_status"],
        "use_when": "After discover_docs, to load design intent into the knowledge base for frame comparison.",
        "category": "knowledge",
    },

    # ── PROJECT STATUS ─────────────────────────────────────────────
    "project_status": {
        "purpose": "Structural picture of the whole project: subsystems, implementation status, critical path gaps, coupling, and architecture constraints. Synthesizes with Ollama when a goal is given.",
        "args": {"goal": "optional question to focus synthesis (e.g. 'what should I work on first?')"},
        "output": "subsystem matrix (fns/stubs/entry_pts/hot), critical stubs ranked by callers, cluster pairs, architecture flags; optionally followed by Ollama narrative synthesis",
        "feeds": ["risk_profile", "list_stubs", "goal_intake"],
        "use_when": "Start of a session to get the big-picture view of the project before diving into specifics.",
        "category": "understanding",
    },

    # ── DESIGN VIOLATION CHECK ─────────────────────────────────────
    "check_design_violations": {
        "purpose": "Cross-reference a symbol against design constraints in knowledge.db. Returns constraint-bearing design_notes that semantically match the symbol.",
        "args": {"symbol": "function or class name to check"},
        "output": "list of matching design constraints with similarity scores, or explanation if none found",
        "feeds": ["risk_profile", "store_finding"],
        "use_when": "Before modifying a HOT symbol, or when adding new functionality near architectural boundaries.",
        "category": "understanding",
    },

    # ── DISTILLATION ───────────────────────────────────────────────
    "distill_corpus": {
        "purpose": "Compress each semantic_summary and file_purpose artifact into a one-sentence distillation stored in knowledge.db.",
        "args": {},
        "output": "count of distilled entries stored vs skipped",
        "feeds": ["symbol_brief", "goal_intake"],
        "use_when": "After describe_file/semantic summaries are populated; run once to seed distilled layer for faster symbol scanning.",
        "category": "knowledge",
    },

    # ── GOAL INTAKE ────────────────────────────────────────────────
    "goal_intake": {
        "purpose": "Translate a developer goal into a navigation plan: relevant design rules, hot/safe zones, stubs, safe insertion points.",
        "args": {"goal": "natural language description of what you want to build or change"},
        "output": "navigation plan: relevant area, design rules, scaffolding, ordered approach (READ/REVIEW/EXTEND/MODIFY)",
        "feeds": ["risk_profile", "symbol_intent", "list_callers"],
        "use_when": "Developer states intent ('I want to add X') and needs to know where to start and what to avoid.",
        "category": "understanding",
    },

    # ── CODE HYGIENE ───────────────────────────────────────────────
    "missing_docstrings": {
        "purpose": "Find functions and classes with no docstring.",
        "args": {},
        "output": "up to 20 symbol names with file/line",
        "feeds": ["symbol_intent", "store_finding"],
        "use_when": "Hygiene pass; finding undocumented surface area.",
        "category": "discovery",
    },
    "find_todos": {
        "purpose": "Scan source files for TODO/FIXME/HACK/XXX comments.",
        "args": {},
        "output": "file, line, comment text for each hit",
        "feeds": ["store_finding", "risk_profile"],
        "use_when": "Finding deferred work embedded in source comments.",
        "category": "discovery",
    },
    "git_log_for": {
        "purpose": "Recent git commits that touched a file or directory.",
        "args": {"path": "relative file or directory path"},
        "output": "commit hash, author, date, message for recent commits",
        "feeds": ["risk_profile", "describe_file"],
        "use_when": "Understanding churn rate; identifying recently changed files.",
        "category": "discovery",
    },

    # ── WORKFLOW ───────────────────────────────────────────────────
    "workflow_status": {
        "purpose": "Show the current work queue: next_up, backlog, future_plans.",
        "args": {"kind": "(optional) filter to one kind: next_up / backlog / future_plan / session_decision"},
        "output": "ranked list of workflow items with kind labels",
        "feeds": ["prioritize_work", "store_workflow_item"],
        "use_when": "Starting a session; deciding what to work on next.",
        "category": "workflow",
    },
    "prioritize_work": {
        "purpose": "Rank all next_up items by structural risk and open findings.",
        "args": {},
        "output": "ordered next_up list with risk rationale",
        "feeds": ["risk_profile", "workflow_status"],
        "use_when": "When you have a backlog and need guidance on ordering.",
        "category": "workflow",
    },
    "store_workflow_item": {
        "purpose": "Add a task to the work queue (next_up / backlog / future_plan / session_decision).",
        "args": {"kind": "queue bucket name", "content": "task description"},
        "output": "confirmation",
        "feeds": ["workflow_status"],
        "use_when": "Recording a task discovered during a session for future work.",
        "category": "workflow",
    },
    "rerank_workflow": {
        "purpose": "Reorder the next_up queue by specifying item positions.",
        "args": {"order": "comma-separated item numbers in new order e.g. '3,1,2'"},
        "output": "updated queue display",
        "feeds": ["workflow_status"],
        "use_when": "After a priority change that makes a different task more urgent.",
        "category": "workflow",
    },

    # ── META ───────────────────────────────────────────────────────
    "describe_tool": {
        "purpose": "Show full documentation for any tool by name (from the tool registry).",
        "args": {"name": "tool name to look up"},
        "output": "purpose, args, output description, feeds, use_when",
        "feeds": [],
        "use_when": "When you need to know how to use a specific tool or what it returns.",
        "category": "meta",
    },

    # ── EDGE (Level 4) ─────────────────────────────────────────────
    "edges_of": {
        "purpose": "All edges touching a symbol or file: calls in/out and imports in/out.",
        "args": {
            "name": "symbol name or file path (relative or basename)",
            "direction": "(optional) 'in' | 'out' | 'both' (default 'both')",
            "type": "(optional) 'call' | 'import' | 'all' (default 'all')",
        },
        "output": "grouped edge list by type and direction with line numbers",
        "feeds": ["edge_detail", "risk_profile", "list_import_deps"],
        "use_when": "Understanding all connections to/from a symbol or file at once.",
        "category": "edge",
    },
    "edge_detail": {
        "purpose": "Richest view of one specific connection: call sites, risk, import metadata.",
        "args": {
            "src": "source symbol name or file path",
            "dst": "destination symbol name or file path",
            "type": "(optional) 'call' | 'import' | 'all' (default 'all')",
        },
        "output": "call site count, line numbers, endpoint risk badges, import type/line",
        "feeds": ["risk_profile", "add_edge", "store_finding"],
        "use_when": "Deep dive on why two specific things are connected.",
        "category": "edge",
    },
    "list_import_deps": {
        "purpose": "Show project-internal import dependencies resolved to file paths.",
        "args": {
            "file_path": "(optional) relative path or basename to scope to one file; "
                         "omit to see all file-to-file import edges in the corpus",
        },
        "output": "resolved import edges: source file → target file (internal only); "
                  "stdlib/external imports shown separately",
        "feeds": ["edges_of", "describe_file", "graph_clusters"],
        "use_when": "Understanding module coupling via imports; finding import chains.",
        "category": "edge",
    },
    "add_edge": {
        "purpose": "Manually assert a connection and store it in knowledge.db.",
        "args": {
            "src": "source symbol or file name",
            "dst": "destination symbol or file name",
            "type": "(optional) edge type label: 'manual', 'data_flow', 'co_change', etc. (default 'manual')",
            "note": "(optional) why this connection matters",
        },
        "output": "confirmation of stored edge",
        "feeds": ["bag_list", "list_findings_by_kind"],
        "use_when": "Capturing a connection the graph doesn't show: data flow, conceptual coupling, "
                    "indirect dependency you want to track.",
        "category": "edge",
    },

    # ── BAG ────────────────────────────────────────────────────────
    "bag_status": {
        "purpose": "Show all bags and their item counts (edges, symbols, files, findings).",
        "args": {},
        "output": "bag name, total items, and type breakdown for each bag",
        "feeds": ["bag_list", "bag_report"],
        "use_when": "Starting a session; seeing what has accumulated so far.",
        "category": "bag",
    },
    "bag_list": {
        "purpose": "List the contents of a bag, grouped by item type.",
        "args": {
            "bag": "(optional) bag id (default 'system')",
            "type": "(optional) filter to one type: 'edge' | 'symbol' | 'file' | 'finding'",
        },
        "output": "typed item list with edge labels, symbol names, file paths",
        "feeds": ["bag_report", "edge_detail", "risk_profile"],
        "use_when": "Reviewing what you've accumulated; navigating the session workspace.",
        "category": "bag",
    },
    "bag_add": {
        "purpose": "Manually add a symbol, file, edge, or finding to a bag.",
        "args": {
            "bag": "(optional) target bag (default 'user:default')",
            "type": "item type: 'symbol' | 'file' | 'edge' | 'finding'",
            "ref": "symbol name, file path, or 'src->dst' for edges",
            "note": "(optional) why you're keeping this",
        },
        "output": "confirmation",
        "feeds": ["bag_list", "bag_report"],
        "use_when": "Curating a user bag with things you want to track or report on.",
        "category": "bag",
    },
    "bag_label": {
        "purpose": "Set a human-readable label on a bag.",
        "args": {
            "bag": "bag id (e.g. 'user:1' or 'user:auth-flow')",
            "label": "display name",
        },
        "output": "confirmation",
        "feeds": ["bag_status"],
        "use_when": "Naming a user bag for an investigation thread.",
        "category": "bag",
    },
    "bag_clear": {
        "purpose": "Empty a bag.",
        "args": {"bag": "(optional) bag id to clear (default 'system')"},
        "output": "count of items removed",
        "feeds": ["bag_status"],
        "use_when": "Starting a fresh investigation; cleaning up the system bag between sessions.",
        "category": "bag",
    },
    "bag_report": {
        "purpose": "Generate a structured summary of everything in a bag.",
        "args": {"bag": "(optional) bag id (default 'system')"},
        "output": "grouped summary: edges by type, symbols with risk badges, files, findings",
        "feeds": ["store_finding", "store_workflow_item"],
        "use_when": "End of an investigation; writing a report; deciding what to act on.",
        "category": "bag",
    },
}


# ------------------------------------------------------------------
# Task patterns: named multi-tool workflows
# Each entry: {steps: list[{tool, args_hint, why}], description: str}
# args_hint is a template - replace <X> with actual values.
# ------------------------------------------------------------------

TASK_PATTERNS: dict[str, dict] = {

    "understand_symbol": {
        "description": "Full picture of one symbol: intent, risk, callers, known findings.",
        "steps": [
            {"tool": "search_symbols",   "args_hint": {"query": "<name>"},    "why": "find exact name and location"},
            {"tool": "symbol_intent",    "args_hint": {"symbol": "<name>"},   "why": "read the docstring"},
            {"tool": "risk_profile",     "args_hint": {"symbol": "<name>"},   "why": "HOT/WARM/SAFE + reasons"},
            {"tool": "list_callers",     "args_hint": {"symbol": "<name>"},   "why": "who depends on this"},
            {"tool": "get_findings",     "args_hint": {"symbol": "<name>"},   "why": "check what's already known"},
        ],
    },

    "explore_file": {
        "description": "Orient to a file: what it contains, its symbols, open findings.",
        "steps": [
            {"tool": "search_files",     "args_hint": {"query": "<filename>"}, "why": "resolve full path"},
            {"tool": "describe_file",    "args_hint": {"file_path": "<path>"}, "why": "AI summary of purpose"},
            {"tool": "symbols_in_file",  "args_hint": {"file_path": "<path>"}, "why": "list all symbols"},
            {"tool": "git_log_for",      "args_hint": {"path": "<path>"},      "why": "recent churn history"},
            {"tool": "get_findings",     "args_hint": {"symbol": "<path>"},    "why": "known issues for this file"},
        ],
    },

    "assess_change_risk": {
        "description": "Before modifying a symbol: full blast-radius and risk analysis.",
        "steps": [
            {"tool": "risk_profile",     "args_hint": {"symbol": "<name>"},   "why": "HOT/WARM/SAFE badge"},
            {"tool": "list_callers",     "args_hint": {"symbol": "<name>"},   "why": "direct blast radius"},
            {"tool": "graph_subgraph",   "args_hint": {"symbol": "<name>"},   "why": "extended neighborhood"},
            {"tool": "get_findings",     "args_hint": {"symbol": "<name>"},   "why": "known bugs or contracts"},
            {"tool": "symbol_brief",     "args_hint": {"symbol": "<name>"},   "why": "full summary with impact zone"},
        ],
    },

    "orient_to_codebase": {
        "description": "First-time orientation: extract facts, find hot spots, map subsystems, surface open work.",
        "steps": [
            {"tool": "extract_design_facts", "args_hint": {},                  "why": "populate entry/hot/dead/stub facts (idempotent)"},
            {"tool": "knowledge_status",     "args_hint": {},                  "why": "show coverage after fact extraction"},
            {"tool": "graph_most_connected", "args_hint": {},                  "why": "architectural hot spots with risk badges"},
            {"tool": "graph_entry_points",   "args_hint": {},                  "why": "execution roots ranked by fan-out"},
            {"tool": "graph_clusters",       "args_hint": {},                  "why": "file coupling groups — subsystem map"},
            {"tool": "find_todos",           "args_hint": {},                  "why": "deferred work, hot-file TODOs first"},
            {"tool": "workflow_status",      "args_hint": {},                  "why": "existing work queue"},
        ],
    },

    "find_dead_code": {
        "description": "Identify code that is defined but never called.",
        "steps": [
            {"tool": "extract_design_facts",  "args_hint": {},                 "why": "ensure dead-code facts are populated (idempotent)"},
            {"tool": "list_findings_by_kind", "args_hint": {"kind": "dead"},   "why": "all extracted dead code candidates"},
            {"tool": "graph_most_connected",  "args_hint": {},                 "why": "high-degree = definitely alive (cross-check)"},
        ],
    },

    "trace_data_flow": {
        "description": "Follow data through the call graph from a source to a sink.",
        "steps": [
            {"tool": "search_symbols",   "args_hint": {"query": "<source>"},          "why": "locate source symbol"},
            {"tool": "list_callees",     "args_hint": {"symbol": "<source>"},         "why": "what source calls"},
            {"tool": "graph_path",       "args_hint": {"src": "<source>", "dst": "<sink>"}, "why": "shortest path"},
            {"tool": "symbol_intent",    "args_hint": {"symbol": "<each node>"},      "why": "understand each step"},
        ],
    },

    "session_startup": {
        "description": "Standard session start: check knowledge coverage, orient, read work queue.",
        "steps": [
            {"tool": "knowledge_status",  "args_hint": {},                 "why": "gauge coverage"},
            {"tool": "workflow_status",   "args_hint": {},                 "why": "what's next"},
            {"tool": "prioritize_work",   "args_hint": {},                 "why": "order the queue by risk"},
        ],
    },

    "goal_intake": {
        "description": "Translate a developer goal into a navigation plan: design rules, hot/safe zones, stubs, safe insertion points.",
        "steps": [
            {"tool": "goal_intake", "args_hint": {"goal": "<goal>"}, "why": "assemble goal-directed context and return navigation plan"},
        ],
    },
}


# ------------------------------------------------------------------
# Tool categories for quick orientation
# ------------------------------------------------------------------

CATEGORIES: dict[str, list[str]] = {}
for _name, _meta in REGISTRY.items():
    CATEGORIES.setdefault(_meta["category"], []).append(_name)


# ------------------------------------------------------------------
# describe_tool: callable from agent (registered in TOOLS)
# ------------------------------------------------------------------

def describe_tool_fn(oracle_or_assessor, args: dict) -> str:
    """
    describe_tool(name) - show full registry entry for a tool.
    Also accepts name='all' to list all tools with one-line summaries,
    or name='patterns' to list all task patterns.
    """
    name = args.get("name", "").strip().lower()
    if not name:
        return "ERROR: name argument required. Use 'all' for a tool listing or 'patterns' for workflows."

    if name == "all":
        lines = ["All tools (category: name - purpose):"]
        for cat, names in sorted(CATEGORIES.items()):
            for n in sorted(names):
                lines.append(f"  [{cat}] {n} - {REGISTRY[n]['purpose']}")
        return "\n".join(lines)

    if name == "patterns":
        lines = ["Task patterns (use these as multi-step guides):"]
        for pname, pdata in TASK_PATTERNS.items():
            steps = ", ".join(s["tool"] for s in pdata["steps"])
            lines.append(f"  {pname}: {pdata['description']}")
            lines.append(f"    steps: {steps}")
        return "\n".join(lines)

    if name not in REGISTRY:
        close = [k for k in REGISTRY if name in k or k in name]
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        return f"Unknown tool '{name}'.{hint} Use describe_tool(name='all') to list all tools."

    entry = REGISTRY[name]
    lines = [
        f"Tool: {name}",
        f"  Purpose : {entry['purpose']}",
        f"  Category: {entry['category']}",
        f"  Args    : {entry['args']}",
        f"  Output  : {entry['output']}",
        f"  Use when: {entry['use_when']}",
    ]
    if entry["feeds"]:
        lines.append(f"  Feeds   : {', '.join(entry['feeds'])}")
    return "\n".join(lines)


def get_compact_tool_list() -> str:
    """
    One-line-per-tool summary for inclusion in the system prompt.
    Grouped by category. Stays short for small models.
    """
    lines = ["Tools (one call at a time):"]
    for cat, names in sorted(CATEGORIES.items()):
        lines.append(f" # {cat}")
        for n in sorted(names):
            # Show key arg names only
            arg_keys = list(REGISTRY[n]["args"].keys())
            arg_str = ", ".join(f'"{k}": ...' for k in arg_keys) if arg_keys else ""
            lines.append(f'  {n}  {{{arg_str}}}')
    lines.append('  (call describe_tool(name="<tool>") for details or describe_tool(name="patterns") for workflows)')
    return "\n".join(lines)
