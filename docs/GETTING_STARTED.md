Getting Started with Determined
================================

Determined is a code analysis engine. You point it at a Python project and
it tells you what is incomplete, what is unwired, where the design intent is
drifting from the code, and what to build next. It does this through a set of
tools: structural queries backed by SQLite, semantic search over embeddings,
and an optional local LLM for narration and stub generation.

This document is a map and a tour guide. The tool carries inline context at
every step. This fills the picture around it.

---

## What you're looking at

The Commonplace corpus is the teaching vehicle. It is a small Python web app --
a personal knowledge base for saving and searching web content. Four terminals
exist so you can load any point in the journey:

| Terminal | Location | What it is |
|----------|----------|------------|
| 0 -- Empty | `examples/commonplace/noseed/` (create it) | A blank directory you build from scratch |
| 1 -- Skeleton | `examples/commonplace/seed/` | 17 files, all stubs closed, pre-wiring |
| 2 -- Complete | `examples/commonplace/` | 25 files, stub-closure arc finished |
| 3 -- Enhanced | `examples/enhanced/` | Complete + LLM tagging, semantic search, cosine similarity |

Terminal 0 is not a directory you copy. You create it yourself. The name is the
instruction: `noseed` -- no seed provided, you start from nothing. `seed/` sits
next to it so the relationship is explicit: seed is the answer key.

---

## How to load a terminal

In the Determined UI:

1. Click the **Corpus** icon (🗄) in the left rail
2. Click **Switch corpus**
3. Enter the full path to the terminal directory
4. Click **Scan**

If the directory has never been analyzed, you'll see: "Analyze this project?" with
a file count and estimated time. Click **Analyze ↵**. Determined creates the DB and
loads the corpus.

If you've analyzed it before, a DB file already exists. Determined loads it
directly. To pick up code changes, use **Re-analyze** (full reingest) or call
`reingest_file(path)` from the Python CLI for a single changed file.

---

## Three phases, one arc

The forward tour moves left to right through the terminals:

```
Phase 1: Empty → Skeleton    (Terminal 0 → 1)
Phase 2: Skeleton → Complete (Terminal 1 → 2)
Phase 3: Complete → Enhanced (Terminal 2 → 3)
```

Each phase has a specific story. Work through them in order on a first pass.
Once you've done the tour, any terminal is navigable directly.

---

## Phase 1: Empty → Skeleton

**The story:** Build a codebase from scratch. Determined has nothing to look at
yet. You write files, Analyze, and watch the tool's picture fill in as code arrives.

**Starting state (Terminal 0):** Create an empty directory at
`examples/commonplace/noseed/`. Switch corpus to that path. Because there are no
source files yet, the modal tells you: write your first `.py` file, come back and
click Analyze, then use `reingest_file` incrementally from there.

This is the bootstrap pattern. Write first, analyze second, reingest for each
new file after that.

**Goal for Phase 1:** Reproduce the skeleton at Terminal 1. The seed lives at
`examples/commonplace/seed/` -- 17 files, 0 stubs, the same state as having written
all the scaffolding without wiring anything up.

**What Determined shows you on the seed (Terminal 1):**

Load Terminal 1 to see the goal state before you build toward it.

*Corpus panel:*
```
17 files · 0 hot · 0 stubs

Roots:
  capture          ↗13
  validate_entry   ↗6
  index            ↗2
  EntryProcessor   ↗0
  EnrichmentProcessor ↗0
```

Roots are functions or classes with no callers -- they are how the outside world
enters this codebase. `capture` is the heaviest root (13 outbound calls): that is
where the application's work happens. `EntryProcessor` and `EnrichmentProcessor`
surface immediately because they are abstract base classes -- Determined treats
ABC classes as roots even without explicit stub detection.

*Frontier tab → Orphan mode:*
```
[Orphan] 1 anticipatory · 0 stranded

validate_entry  (blue node)
```

`validate_entry` exists and works but nothing calls it yet. "Anticipatory" means
written ahead of its callers. This is your first actionable finding: wire a caller
into `capture` to use the validator.

*Frontier tab → Direct mode:*
```
No frontier edges found.
```

The seed has 0 stubs. Nothing is definitively broken. Direct mode is empty because
Direct mode shows caller→stub edges, and there are no stubs.

*Frontier tab → ABC mode:*
```
No frontier edges found.
```

`EntryProcessor` has 3 subclasses (`CleanupProcessor`, `DeduplicateProcessor`,
`EnrichmentProcessor`) all with overrides in place. No interface gaps.

*Topology:*
```
Total stubs: 0  |  Total implemented: 31
Orphaned-impl: 2
Action queues:
  Write callers: orphaned-impl (2)
```

The topology summarizes the whole corpus in one view. 0 stubs means nothing is
broken. 2 orphaned-impl means there is implemented code that is not yet called.
The action queue tells you where to work next.

**Key dependencies to know:**

- `capture` is the entry point. Everything flows through it.
- `storage/db.py::get_db` is the DB hotspot: 7 callers, every route goes through it.
- `validate_entry` is anticipatory: fully implemented, no callers yet.
- `create_app` will always appear as possibly-stranded. Flask factories are called
  by the WSGI server, not by any in-corpus symbol. Static analysis cannot see this.
  This is a known false positive -- not a bug in your code.

**What this phase teaches:**

The corpus panel, frontier (all three modes), and topology together give you a
complete picture of a codebase's structural state. The action queue is not an
opinion -- it is derived directly from the call graph. A 0-stub corpus has nothing
in the "Implement now" queue, but `validate_entry` sitting in "Write callers" is
telling you exactly what to do next.

---

## Phase 2: Skeleton → Complete

**The story:** The skeleton is built. Now close the stubs, wire the orphans, and
bring the codebase to a fully-functional state. This is the phase where Determined
acts as a navigator: it surfaces what is incomplete, you implement it, you reingest,
and the picture updates.

**Starting state (Terminal 1):** 17 files, 0 stubs (all skeleton functions are
implemented), 2 orphaned impls (validate_entry + create_app).

**Goal for Phase 2:** Reach the state at Terminal 2. The complete corpus lives at
`examples/commonplace/` -- 25 files, 6 stubs closed, full routing and service layers
wired. Load Terminal 2 to see the goal state.

**What Determined shows you on the complete corpus (Terminal 2):**

*Corpus panel (before stub closure):*
```
25 files · 1 hot · 6 stubs

Direct-call: 3   (extract_full_content, semantic_search, enrich_entry)
Chain-tail:  2   (find_connections, suggest_tags)
Disconnected: 1  (_similarity_score)
```

These are your work items, in priority order from the action queue:
1. **Chain-tail stubs first:** `find_connections` and `suggest_tags` are at the
   end of call chains. Something calls them expecting an answer. Fix these first.
2. **Direct-call stubs:** `extract_full_content`, `semantic_search`, `enrich_entry`
   are called directly by functional code. Broken paths.
3. **Disconnected stubs:** `_similarity_score` has no callers at all. The tool
   labels this "Decide" -- it might be dead scaffolding, it might be an intended
   future feature. Investigate before implementing.

**Closing a stub:**

1. Read the stub (Determined shows you the line). Understand what it is supposed to do.
2. Implement it.
3. Run `reingest_file` on the changed file (or use Re-analyze for the whole corpus).
4. Check the Frontier tab again -- the stub should be gone.

After each closure, the topology updates. Chain-tail stubs that disappear unlock
the chain-head, which may appear in the action queue next.

**The stub closure arc (Terminal 2 actuals):**

```
After closing find_connections + suggest_tags:  Chain-tail 0, Disconnected 0
After closing extract_full_content + EnrichmentProcessor:  Total broken stubs 0
Remaining: 2 intentional stubs (enrich_entry stub_by_doc, semantic_search fallback)
```

"Intentional stubs" are functions that are documented as incomplete by design.
`enrich_entry` has `STUB:` in its docstring. `semantic_search` delegates to text
search with a comment that it should use embeddings. Determined detects both
patterns and correctly leaves them in the results -- they are documented decisions,
not broken code.

**ABC interface gaps:**

The `EntryProcessor` ABC is abstract. `find_abc_gaps` checks whether every abstract
method has at least one concrete override somewhere in the corpus. On the complete
corpus this returns clean. If you add a new abstract method and don't implement it
in a subclass, `find_abc_gaps` will surface it immediately.

**What this phase teaches:**

The priority order in the action queue is real. Chain-tail stubs block execution
chains. Disconnected stubs are a decision point. The tool does not tell you what to
implement -- it tells you what is incomplete and in what order incomplete things
matter to running code.

---

## Phase 3: Complete → Enhanced

**The story:** The codebase is functional. Now add intelligence: LLM-powered
tagging, real semantic search via embeddings, and cosine-similarity connection
scoring. The enhanced corpus lives at `examples/enhanced/`.

**What changed in Terminal 3 vs Terminal 2:**

| File | What changed |
|------|-------------|
| `services/tagger.py` | `suggest_tags` now calls the llama-server endpoint |
| `services/searcher.py` | `semantic_search` uses sentence-transformers embeddings |
| `services/linker.py` | `_similarity_score` upgraded from Jaccard to cosine similarity |
| `utils/text.py` | Shared `get_embed_model()` and `cosine_similarity()` helpers added |

Each of these was surfaced by Determined on the complete corpus (Terminal 2) as a
stub or functional fallback. The tool identified the right insertion points. The
user implemented them. This is the pattern Phase 3 demonstrates.

**How Determined surfaces these:**

*Frontier tab → Direct mode (complete corpus):*
```
enrich_entry  →  suggest_tags  (chain-tail stub, LLM_ENDPOINT missing)
```

`suggest_tags` had the full `_call_llm` path already written. The `endpoint`
parameter existed but was never threaded through from callers. Determined found
the gap. The fix was wiring, not implementing.

*Frontier tab → Direct mode (complete corpus):*
```
semantic_search  (functional-fallback -- delegates to search())
```

Functional fallback means the stub has a real body but it is not doing what the
name implies. `routes/search.py` was calling `searcher.search()` directly,
bypassing the semantic layer. Determined flagged it correctly.

**To activate the enhanced features:**

```
set LLM_ENDPOINT=http://localhost:8081
set TAGGING_ENABLED=true
python app.py
```

Requires llama-server running on port 8081 and `sentence-transformers` installed.
Without them, the app falls back to text-based search and empty tag lists.

**What this phase teaches:**

Determined becomes the navigation layer for a codebase you already understand.
The tool knows what is wired and what is not. It does not know whether semantic
search is "better" than text search -- that is a design decision you bring.
It surfaces the incomplete connections and shows you where to plug things in.

---

## Tools at each phase

Every tool below is available at any phase. The column shows where its output is
most informative.

| Tool | Best phase | What it shows |
|------|-----------|---------------|
| Corpus panel | All | File count, hot files, stub count, roots, gaps at a glance |
| Frontier → Direct | 2 | Caller→stub edges: broken execution paths |
| Frontier → Orphan | 1, 2 | Implemented code with no callers: anticipatory vs stranded |
| Frontier → ABC | 2, 3 | Abstract methods with no concrete override |
| `detect_topology` | 1, 2 | Full structural summary + action queue |
| `find_orphaned_impls` | 1, 2 | Detailed list of disconnected functions |
| `find_abc_gaps` | 2, 3 | Interface gap list |
| `find_conditional_stubs` | 2 | Runtime-only gaps (conditional NotImplementedError) |
| `knowledge_status` | All | Coverage gaps: docstrings, distillation, design notes |
| `ingest_design_docs` | 3 | Import design rules from markdown; enables `check_design_violations` |
| `check_design_violations` | 3 | Cross-reference a symbol against ingested design rules |
| `distill_corpus` | 3 | Generate one-sentence summaries for all files (requires LLM) |
| `gap_analysis` | 3 | LLM brainstorm of what's missing in a scoped area |

---

## Dependencies and dead ends

These are the places where a new user gets stuck. Knowing them in advance saves time.

**`check_design_violations` requires design notes.**
Run `ingest_design_docs` on a design doc first. A fresh corpus has 0 design notes.
The tool will tell you this; it is not broken.

**`ingest_design_docs` requires an explicit path on the seed corpus.**
The seed's `docs/DESIGN.md` lives at `examples/commonplace/docs/DESIGN.md`. Auto-discovery
won't find it because it is outside the seed project root. Pass the path explicitly:
`ingest_design_docs(path="examples/commonplace/docs/DESIGN.md")`.

**`distill_corpus` and LLM tools require llama-server on port 8081.**
The UI starts llama-server automatically. For CLI use, start it manually:
```
llama-server.exe -m C:\Users\...\models\gguf\Qwen3-8B.gguf --port 8081
```
If llama-server is not running, LLM tools return None silently. The error
surfaces at the query layer, not the tool layer.

**`create_app` always appears as possibly-stranded.**
Flask application factories are called by the WSGI server at runtime. Static
analysis cannot see this. Every Flask corpus will show `create_app` as a
possibly-stranded symbol. It is a known false positive, not a bug.

**Seed DB accumulates artifacts across sessions.**
If you run `ingest_design_docs` or `distill_corpus` during the tour, those
artifacts are stored in the seed DB. A clean user demo needs them cleared.
From Python: `DELETE FROM knowledge_artifacts WHERE kind IN ('design_note', 'distilled')`.
Structural facts (entry, hot, stub) survive -- they come from the ingest pass and
are valid first-run output.

**Re-analyze vs reingest_file.**
Re-analyze is a full corpus reingest. `reingest_file` re-ingests one file,
propagates its edge delta, and is much faster. For step-by-step stub closure
during the tour, `reingest_file` is the right tool. For a fresh load after major
structural changes, use Re-analyze.

---

## Navigating to any point

After completing the forward tour, you can load any terminal directly:

```
Terminal 0: examples/commonplace/noseed/    (create if not exists)
Terminal 1: examples/commonplace/seed/
Terminal 2: examples/commonplace/
Terminal 3: examples/enhanced/
```

Each has a DB file at `C_Users_bartl_dev_Determined_examples_<dirname>.db`.
The DB file preserves the full corpus state including any knowledge artifacts
you generated during the tour. Delete the DB file and Re-analyze to start fresh.

---

## Two audiences

**No prior experience with Determined:**
Every concept is defined in this document and in the tool's inline output.
Read the corpus panel explanation before looking at the numbers. The tool
uses the same terms everywhere (hot, stub, orphan, anticipatory, stranded).
Once you know what each term means, the output is self-interpreting.

**Experienced with static analysis, new to Determined:**
The concepts will feel familiar but the framing is different. Determined does
not produce a list of warnings. It produces an action queue derived from the
call graph. "Direct-call stub" means "your call graph has a dangling edge --
this function is called and it does nothing." The priority order (chain-tail
before direct-call before disconnected) reflects execution risk, not code
quality.

The ABC mode is the one that most surprises experienced users: it catches
abstract methods with zero concrete overrides anywhere in the corpus. This
is not a linter check -- it is a graph query. The tool finds interfaces that
were never implemented, not just interfaces that were declared incorrectly.
