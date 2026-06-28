# SESSION STATE - session 28/29 handoff
_Overwrite completely each session. Not authoritative - see Determined/docs/TRACKER.md for truth._

## What happened this session (session 28)

**Merged ui/corpus-map to main. Fixed orient entry points. Built generic doc
discovery and rule extraction (items 22a+22b).**

### orient_to_codebase improvements (commit 52cab06)
- Fixed `find_entry_points`: bare names like `from_dict` were missed in the
  "called" set because graph_edges stores callees as `ClassName.from_dict`.
  Now strips dot-prefix from callees. Eliminated 12-copy `from_dict` flood.
- Deduplication: same bare name in multiple files all shared edge records,
  causing identical out_degree. Now keeps first occurrence only.
- `graph_clusters`: separated test-file pairs from production pairs so real
  subsystem connections aren't buried.

### Item 25: corpus map merged to main
ui/corpus-map branch merged. Item 25 closed.

### Item 22a+22b: doc discovery + rule extraction (commit 4929939)
New module: `determined/agent/doc_extractor.py`
- `discover_docs(project_root)`: walks any project, finds .md/.rst/.txt,
  classifies (design/readme/changelog/notes), scores by constraint language
  density. No hardcoded paths or project assumptions.
- `extract_rules(doc_path)`: splits by heading, finds constraint sentences
  (must/must not/only/never/forbidden). Deterministic — no model required.

Two new agent tools registered in tool_registry:
- `discover_docs` — inventory of all project docs ranked by design-relevance
- `ingest_design_docs(min_score)` — extract rules from high-signal docs,
  store as design_note artifacts. Idempotent.

Tested on dj2: finds 225 docs (after venv/site-packages exclusion), stores
58 rules from 18 docs at min_score=0.07. EscalationEngine and authority
boundary rules extracted correctly from 00B/00F sections.

### Architecture clarification this session
Bart confirmed the right generic framing:
- No docs exist → code IS the design → infer design from structure (item 22c, future)
- Docs exist → extract rules → compare to code (items 22a+22b done, item 23 next)
- No hardcoded assumptions about project layout anywhere in the tool

## Current state

Branch: main
Tests: 321/322 passing (1 pre-existing stale fixture, unrelated)
Items closed this session: 25 (corpus map), 22a+22b (doc discovery + extraction)

## FIRST THING NEXT SESSION

Start item 23: frame comparison.

When the agent spotlights a symbol or produces a risk profile, automatically
look up design_notes whose subject matches the symbol's filename or system
name and include them in the LLM context.

Key files to read before starting:
- `determined/agent/agent_tools.py::symbol_brief` (assessor tool, ~line 800)
- `determined/agent/agent_tools.py::risk_profile` (oracle tool)
- `determined/assessor/assessor.py::get_artifacts` (how to query design_notes)

The subject matching needs two lookups:
  1. Exact filename: `event_log.py` → find design_notes with subject="event_log.py"
  2. System name: derive from filename (strip .py, CamelCase → EventLog) →
     find design_notes with subject="EventLog"

Then include matching notes in the prompt context passed to Ollama for
interpretation. Existing design_notes from mine_design_docs.py + newly
extracted ones from ingest_design_docs both feed this.

## What comes after item 23

Item 22c - Code-as-design inference (no docs case)
  When discover_docs finds nothing useful, infer design intent from code
  structure: naming patterns, call graph shape, comment density, TODO clusters.
  Ollama-appropriate (synthesis, not extraction). Produces design_note
  artifacts in the same shape as 22b output.

Item 24 - Goal intake
  Developer states intent → tool assembles: matching design rules + hot/safe
  zones + relevant stubs + safe insertion point → navigation plan.
  Requires items 22 + 23 first.

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, separate venv
UI: python -m determined.agent.local_agent --ui then http://127.0.0.1:5050
Active branch: main
