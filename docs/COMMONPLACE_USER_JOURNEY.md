Commonplace -- User-Facing Journey (Synthesized)
==================================================

Extracted from Walk 1, Walk 2, Walk 3 developer logs. This is what a new user
should see and do, distilled from actual tool output. Use this to validate the
next clean attempt and to design the guided UI (Phase 4).

Last updated: 2026-07-08 (session 119). Phase 0 walked and recorded. Phase 1 walked and updated (session 119, current 17-file seed). Actuals from complete corpus also recorded.

---

## How to read this document

Each phase has:
- **What the user sees** -- actual Determined output, verified against walks
- **What the user does** -- the action the output implies
- **What changes** -- verified result after reingest
- **The lesson** -- what this step teaches about Determined

"Verified" means it came from a real walk. "[Expected]" means derived from design
intent but not yet walked.

---

## PHASE 0 -- Scratch (WALKED 2026-07-08, session 116)

**Starting state:** blank directory `C:\Users\bartl\dev\commonplace-walk`, no files, no DB.

**RM22 blocker resolved:** UI now shows a 3-step bootstrap guide when Analyze is
clicked on a directory with 0 source files (committed 0aaa111). Walk proceeded
by writing all seed files first, then Analyze.

### Step 0 -- Empty directory: what the UI shows [VERIFIED]

**User action:** Enter path to blank directory → click Switch corpus → path scanned.

**What they see (0-file scan result modal):**
```
No source files found
<directory path>

This directory has no recognized source files yet.
To bootstrap a new corpus:
1. Write your first .py file to this directory
2. Come back and click Analyze — Determined will create the corpus DB
3. After that, use Re-analyze or reingest_file for each new file

[OK]
```

**What it teaches:** The bootstrap pattern. Write first, then Analyze, then
reingest_file incrementally. This closes the "where do I start" gap.

---

### Step 1 -- Write seed files, then Analyze [VERIFIED]

**User action:** Write all seed files to directory. Enter path → Switch corpus →
scan finds 17 files → modal: "Analyze this project?"

**What they see (scan modal):**
```
Analyze this project?
C:\Users\bartl\dev\commonplace-walk
17 source files · 0 MB · ~34s
[Cancel]  [Analyze ↵]
```

**User action:** Click Analyze ↵.

**What happens:** Ingest runs (~30s for 17 files). DB created at
`C_Users_bartl_dev_commonplace_walk.db`.

---

### Step 2 -- After Analyze: what Determined shows [VERIFIED]

**Corpus map after first Analyze of walk directory (all 17 seed files):**
```
17 files · 1 hot · 0 stubs

Roots:
  capture ↗13
  validate_entry ↗6
  index ↗2
  EntryProcessor ↗0
  EnrichmentProcessor ↗0

Core:
  process ↙0
  capture ↙0
  search ↙1
  _similarity_score ↙1
  insert_entry ↙0
  _call_llm ↙1
  get_db ↙7
  extract_metadata ↙2
  create_app ↙1
  enrich_entry ↙0

Gaps:
  docs 71% (9 missing)
  distilled 76%
  5 design notes
```

**Verified corpus DB facts:**
- 17 files ingested (all seed files)
- Roles: 3 entry_points (app.py, capture.py, search.py), 1 config, 4 inits, 9 modules
- 1 hot file: storage/db.py (most inbound connections: get_db called 7 times)
- 31 functions, 5 classes, 137 graph edges
- 0 stubs detected (seed extractor.py and processor.py are now implemented from Walk 4 extras)
- ABC classes: EntryProcessor (ABC), CleanupProcessor, DeduplicateProcessor, EnrichmentProcessor

**What it teaches:**
- `capture` is the heaviest entry point (13 outbound calls) -- that's where the
  application's work happens.
- `storage/db.py::get_db` is hot (7 callers) -- the DB connection is the bottleneck.
- 0 stubs in current seed state: Walk 4 extras implemented the extractor and
  processor functions that were stubs in earlier walks.
- EntryProcessor ABC with 3 subclasses surfaces immediately in Roots -- Determined
  shows abstract class hierarchies even without explicit stub detection.

**Note on stub state:** Earlier walks (Phase 1 Walk 1) showed 2 stubs in the seed.
Those stubs (`extract_metadata`, `extract_full_content`) were implemented during
Walk 4 Extras 1-3. The seed corpus reflects those implementations. A user starting
from the current seed sees a 0-stub, 17-file codebase with a clear entry point
and DB bottleneck as the first signals.

---

## PHASE 1 -- Seed (WALKED 2026-07-08, session 119)

The seed lives at `examples/commonplace/seed/`. Load via corpus switcher
(Switch corpus → pick `C_Users_bartl_dev_Determined_examples_commonplace_seed.db`).

**Note on seed evolution:** Walks 1+2 used an 8-file, 2-stub seed. Walk 4
extras (sessions 113-115) implemented the stubs, growing the seed to 17 files
with 0 stubs. Phase 1 actuals below reflect the current (Walk 4+) seed state.

**Pre-walk setup:** The seed DB may contain knowledge artifacts from prior developer
walks (design notes, distilled summaries). A clean user walk starts with these
cleared. Structural facts (entry, hot, dead, stub) are retained -- they come from
the ingest pass itself and are valid first-run output.

---

### Step 1 -- Orient [VERIFIED]

**User action:** Switch corpus to seed, open corpus panel (🗄 icon).

**What they see:**
```
17 files · 0 hot · 0 stubs

Roots:
  capture          ↗13
  validate_entry   ↗6
  index            ↗2
  EntryProcessor   ↗0
  EnrichmentProcessor ↗0

Gaps:
  docs 71%  distilled 0%  0 design notes  C: 71% (9 missing)
```

**What it teaches:** Entry point + call-graph roots. `capture` is the heaviest
root (13 outbound calls) -- that's where the application's work happens.
`validate_entry` appears as a root because it has many callers... but wait,
the Orphan mode will show it has zero callers. The ↗6 count is something else
(outbound calls, not inbound). EntryProcessor and EnrichmentProcessor as roots
surface the ABC class hierarchy immediately.

**No hot files:** 0 hot at seed scale is expected. The DB hotness threshold
requires multiple inbound edges; at 17 files there isn't enough density.

---

### Step 2 -- Read the frontier [VERIFIED]

**User action:** Frontier tab → Direct (caller→stub) mode → Load.

**What they see:**
```
No frontier edges found for this mode.
```

**What it teaches:** The seed has 0 stubs. Direct mode is empty. This means:
"the codebase is implemented at this scale -- nothing is definitively broken."
A new user should try Orphan mode next.

---

### Step 3 -- Orphan mode: find unwired code [VERIFIED]

**User action:** Frontier tab → Orphan (disconnected) mode → Load.

**What they see:**
```
[Orphan] 1 anticipatory · 0 stranded · 1 total

validate_entry  (blue node)
```

**What it teaches:** `validate_entry` exists and works but nothing calls it yet.
"Anticipatory" = written ahead of its callers. This is actionable: wire a caller
into `capture` or a route handler to use the validator.

---

### Step 4 -- ABC gaps [VERIFIED]

**User action:** Frontier tab → ABC (interface gaps) mode → Load.

**What they see:**
```
No frontier edges found for this mode.
```

`EntryProcessor` has 3 subclasses (`CleanupProcessor`, `DeduplicateProcessor`,
`EnrichmentProcessor`) all with overrides in place. No gaps.

---

### Step 5 -- Topology [VERIFIED]

**User action:** Topology tab → Refresh.

**What they see:**
```
CORPUS TOPOLOGY
  Total stubs: 0  |  Total implemented: 31

  Direct-call:    0
  ABC-interface:  0
  Chain-head:     0
  Chain-middle:   0
  Chain-tail:     0
  Orphaned-impl:  2   (implementations with no functional callers)
  Entry-point:    0
  Disconnected:   0

  Action queues:
    Implement now:  chain-tail (0) > direct-call (0) > abc-interface (0) > chain-head (0)
    Write callers:  orphaned-impl (2)
    Decide:         disconnected (0) | entry-point (0)

FRONTIER COVERAGE
  Implemented functions: 31
  Stubs in corpus:       0
  Has impl caller:       20  (reachable through functional code)
  No callers at all:     3   (orphaned -- see find_orphaned_impls)
  Signal: LOW stub pressure -- most implemented code is reachable.
```

**What it teaches:** The topology summarizes the whole corpus in one view.
0 stubs → nothing is broken. 2 orphaned-impl → there's code that's ready but
not yet called. Action: "Write callers: orphaned-impl (2)."

---

### Step 6 -- Drill into orphaned impls [VERIFIED]

**User action:** Run `find_orphaned_impls`.

**What they see:**
```
Orphaned implementations (2 shown)

  app.py
    create_app  line 15  [possibly-stranded (0 stub callers)]
  validator.py
    validate_entry  line 16  [anticipatory]
```

**What it teaches:**
- `create_app` is possibly-stranded. It's a Flask application factory -- called
  by the WSGI server, not by any in-corpus symbol. This is a known false positive
  for static analysis: Flask factories are always invisible to call graph tools.
- `validate_entry` is anticipatory: implemented, working, no callers yet.
  The action is to wire it into the capture route.

---

### Step 7 -- Conditional stubs [VERIFIED]

**User action:** Run `find_conditional_stubs`.

**What they see:**
```
No conditional stubs found (no non-stub functions with conditional NotImplementedError).
```

**What it teaches:** No hidden runtime gaps. `validate_entry` was a conditional
stub in earlier seed versions (Walk 2 Step 8: `if strict: raise NotImplementedError`).
That branch was removed during Walk 2. The seed is clean.

---

### Step 8 -- Knowledge status [VERIFIED]

**User action:** Knowledge tab → Refresh (or run `knowledge_status`).

**What they see:**
```
Knowledge coverage for corpus (17 files, 31 functions):
  File summaries (semantic_summaries): 0/17 files covered
  Total knowledge artifacts: 19
    by kind: file_purpose=5, reasoning_chain=4, entry=4, strategy_decision=2,
             dead=2, stub=1, hot=1
  Structural facts: entry points: 4  dead code: 2  hot: 1  stub files: 1

GAPS AT A GLANCE:
  Docstring coverage:    22/31 functions documented
  Distillation coverage: 0/17 files distilled
  Design notes:          0 total
  Modules with missing docstrings:  C:: 9/31 missing
```

**What it teaches:** The knowledge layer is empty except for structural facts
from the ingest pass. 9/31 functions lack docstrings. The action is:
- Run `extract_design_facts` + `describe_file` to populate file-level summaries
- Ingest `docs/DESIGN.md` via `ingest_design_docs` to get design rules

**Note on design doc ingest:** Auto-discovery won't find DESIGN.md if it lives
outside the seed project root. Must call `ingest_design_docs` with explicit path:
`examples/commonplace/docs/DESIGN.md`. Known limitation (filed as RM15 issue).

---

### Seed journey complete -- verified tool coverage

**What the current seed demonstrates:** A 17-file, 0-stub, implemented-but-not-fully-wired
codebase. The story is "all stubs are done -- now wire what's orphaned and document what's
undocumented." Contrast with the complete corpus which has intentional stubs.

| Tool | What it shows on current seed | Signal quality |
|------|----------------------------|----|
| Corpus panel | 17 files, 0 hot, 0 stubs; roots + gaps at a glance | HIGH |
| Frontier Direct | Empty -- correct, 0 stubs | HIGH (confirms clean state) |
| Frontier Orphan | validate_entry (anticipatory) | HIGH |
| Frontier ABC | Empty -- all overrides in place | HIGH (confirms clean state) |
| `detect_topology` | 0 stubs, 2 orphaned-impl; action: write callers | HIGH |
| `find_orphaned_impls` | create_app (false positive), validate_entry (actionable) | HIGH |
| `find_conditional_stubs` | 0 found -- no hidden runtime gaps | HIGH |
| `knowledge_status` | 0 distilled, 0 design notes, 9/31 missing docstrings | HIGH |
| `find_abc_gaps` | All overridden -- confirms ABC hierarchy is complete | HIGH |

---

## PHASE 2 -- Complete corpus (Walk 3) [VERIFIED]

The complete corpus is `examples/commonplace/` (with `seed/` excluded via
`.determinedignore`). 25 files, 55 functions.

### Actuals: complete corpus after Walk 3 stub closure

**detect_topology output (final state):**
```
CORPUS TOPOLOGY
  Total stubs: 2  |  Total implemented: 55+

  Remaining intentional stubs:
    services/pipeline.py:enrich_entry   -- stub_by_doc (docstring "STUB:")
    services/searcher.py:semantic_search -- functional fallback (delegates to search())

  All other shapes: 0
  Orphaned-impl: present (model layer + storage queries not fully wired to routes)
```

**Stub closure arc (Walk 3):**
```
Before Walk 3:
  Total stubs: 6
  Chain-tail: 2   (find_connections, suggest_tags)
  Disconnected: 1  (_similarity_score)
  Direct-call: 3   (extract_full_content, semantic_search, enrich_entry)
  ABC-interface: 2  (EnrichmentProcessor.process, EnrichmentProcessor.can_handle)
  Chain-head: 1    (enrich_entry as bridge)

After Walk 3 Step 2 (find_connections, suggest_tags implemented):
  Chain-tail: 0
  Disconnected: 0

After Walk 3 Step 3 (extract_full_content, EnrichmentProcessor implemented):
  Total broken stubs: 0
  Remaining: 2 intentional (enrich_entry stub_by_doc, semantic_search functional fallback)
```

**What the complete corpus exercises beyond seed:**
- Chain positions (head/tail) visible and correctly prioritized
- Disconnected stubs represent deferred design (_similarity_score correctly flagged "Decide")
- stub_by_doc detection extends coverage to functions with real bodies but documented incompleteness
- Orphaned-impl at 16 explainable in three categories (Flask routes, model layer, storage queries)

**check_design_violations (complete corpus, calibrated thresholds):**
- >= 0.45: high signal -- real rule matches the right symbol
- 0.30-0.40: noise floor -- duplicate rule entries, cross-symbol contamination
- Known issue: RM20 (design_note deduplication) inflates duplicate entries

---

## PHASE 3 -- Extras (WALKED 2026-07-08, session 117)

Filed as RM23. Three natural next steps surfaced by Determined on the complete corpus:

1. **Wire suggest_tags to llama-server** [WALKED -- Extra 1, session 115]
2. **Semantic search with real embeddings** [WALKED -- Extra 2, session 115]
3. **Connection inference live** [WALKED -- Extra 3, session 115]

Each extra: Determined surfaces the frontier → user implements → reingest → verify.
The tool becomes navigation layer for a codebase the user already understands.

---

### Phase 3 Walk -- Determined's view of the complete corpus (session 117)

Walk date: 2026-07-08. DB reingested 3 Walk 4 files before walking
(`services/linker.py`, `routes/search.py`, `services/searcher.py`).
Corpus: 25 files, 64 functions.

**Step 1 -- knowledge_status**

```
Knowledge coverage for corpus (25 files, 64 functions):
  File summaries (semantic_summaries): 0/25 files covered
  Total knowledge artifacts: 0
  Structural facts extracted:
    entry points: 0  dead code candidates: 0  hot symbols: 0  stub files: 0

GAPS AT A GLANCE:
  Docstring coverage:    22/64 functions documented
  Distillation coverage: 0/25 files distilled
  Design notes:          0 total
  Modules with missing docstrings:
    C:: 42/64 missing
```

Fresh corpus -- knowledge layer empty. This is the expected starting state before
any `describe_file` or `extract_design_facts` pass. 42/64 functions missing
docstrings is the documentation debt surfaced immediately.

**Step 2 -- find_abc_gaps**

```
All ABC stub methods have at least one non-stub override in the corpus.
```

`EntryProcessor` base + `CleanupProcessor`, `DeduplicateProcessor`,
`EnrichmentProcessor` subclasses are all fully overriding. No gaps.

**Step 3 -- frontier_coverage**

```
FRONTIER COVERAGE
  Implemented functions : 64
  Stubs in corpus       : 0

  Stub-gated (1-hop)    : 0  (0.0% of implemented corpus)
  Has impl caller       : 30  (reachable through functional code)
  Has stub caller only  : 0
  No callers at all     : 16  (orphaned -- see find_orphaned_impls)

  Signal: LOW stub pressure -- most implemented code is reachable.
```

0 stubs. All 3 Walk 4 extras are implemented. 16 orphaned functions -- not broken,
just not yet called from the current routing layer (model classes, HTML parser
internals, utility functions).

**Step 4 -- find_orphaned_impls**

```
  app.py       create_app            [possibly-stranded (0 stub callers)]
  connection.py validate             [anticipatory]
  entry.py     validate, to_dict     [anticipatory]
  tag.py       validate              [anticipatory]
  extractor.py handle_starttag x2, handle_endtag x2, handle_data x2, get_text  [anticipatory]
  pipeline.py  _normalize_entry      [anticipatory]
  processor.py run_processors        [anticipatory]
  db.py        close_db              [anticipatory]
  queries.py   insert_connection     [anticipatory]
  text.py      make_excerpt          [anticipatory]
  validator.py validate_entry        [anticipatory]
```

All "anticipatory" -- implemented and waiting for callers. `create_app` is
possibly-stranded (Flask factory pattern: called by the WSGI server, not by
any in-corpus symbol). No dead code; these are all latent-functional.

**Step 5 -- check_design_violations**

Requires `symbol` arg and design_notes in DB. Corpus has 0 design notes
(no `ingest_design_docs` run yet). Tool returns "no layer rules defined" --
correct for a fresh corpus without a `LAYER_RULES.md`.

**What Phase 3 shows about the tool:**
- Determined correctly reports 0 stubs after Walk 4 extras land
- `find_abc_gaps` immediately surfaces the hierarchy structure and confirms override coverage
- `find_orphaned_impls` distinguishes "orphaned but well-formed" (anticipatory) from
  "orphaned and suspicious" (possibly-stranded) -- `create_app` is the one to watch
- `check_design_violations` and `knowledge_status` distillation both require a
  prior setup pass (`ingest_design_docs`, `describe_file`) -- they're navigation tools
  for a corpus the user has already annotated, not cold-start tools

---

### Extra 1 -- Wire suggest_tags to llama-server [VERIFIED]

**What Determined showed:** `suggest_tags` and `enrich_entry` as chain-tail stubs
in the complete corpus frontier. The stub docstring said "LLM_ENDPOINT" was the
missing piece.

**What the user found:**
- `services/tagger.py::suggest_tags` already had the full `_call_llm` path written.
  The `endpoint` parameter existed but was never passed from callers.
- `config.py` already had `LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://localhost:8081")`
  and `TAGGING_ENABLED` flag -- both defined, neither wired through.

**What changed (commit da8b15e):**
- `services/pipeline.py::enrich_entry` -- added `llm_endpoint` param, forwards to `suggest_tags`
- `routes/capture.py` -- reads `LLM_ENDPOINT` from `current_app.config`, passes to both
  `enrich_entry` and the direct `tagger.suggest_tags` call
- `services/processor.py::EnrichmentProcessor.process` -- fixed arg bug: was calling
  `suggest_tags(entry.get("id", ""), entry.get("content", ""))` (id as content, content as endpoint)

**To activate:** set `TAGGING_ENABLED=true` and `LLM_ENDPOINT=http://localhost:8081`
in environment before starting the app. With llama-server running on 8081, capture
will return real LLM-suggested tags.

**The lesson:** Determined surfaced the frontier correctly. The implementation was
already written -- the gap was purely in wiring (endpoint not threaded through callers).
This is the pattern Extra 1 was designed to demonstrate: "Determined as navigation
layer for a codebase you already understand."

**Bonus finding:** `EnrichmentProcessor` had a silent arg-order bug that would have
caused `id` to be treated as content and `content` as endpoint. The stub was never
called in tests, so it never surfaced. Reingest after the fix confirmed closure.

---

### Extra 2 -- Semantic search with real embeddings [VERIFIED]

**What Determined showed:** `semantic_search` as functional-fallback stub (delegates
to `search()`). `routes/search.py` calling `searcher.search()` directly, bypassing
the semantic layer entirely.

**What changed (commit d241528):**
- `utils/text.py` -- added `get_embed_model()` (lazy singleton, all-MiniLM-L6-v2)
  and `cosine_similarity()` shared by both extras
- `services/searcher.py::semantic_search` -- loads all entries, embeds query + content
  via sentence-transformers, ranks by cosine similarity (threshold 0.25), falls back
  to text search if model unavailable
- `routes/search.py` -- now calls `semantic_search` instead of `search`

**The lesson:** The stub was a functional fallback, not a broken stub. Determined
correctly flagged it as "designed not broken" -- the fix was wiring, not implementing.
The shared embedding helper in `utils/text.py` is the natural home for this since
both Extra 2 and Extra 3 needed the same model.

---

### Extra 3 -- Connection inference upgrade [VERIFIED]

**What Determined showed:** `_similarity_score` as a disconnected stub flagged
"Decide" in Walk 3. Jaccard keyword overlap was a placeholder, not the intended
implementation.

**What changed (commit d241528):**
- `services/linker.py::_similarity_score` -- upgraded from Jaccard keyword overlap
  to embedding cosine similarity using the shared `get_embed_model()` helper.
  Falls back to Jaccard if sentence-transformers unavailable.

**The lesson:** The "Decide" disconnected stub resolved exactly as Determined
predicted -- it became the scoring function upgrade. `find_connections` required
no changes; only the implementation of `_similarity_score` changed. This is the
cleanest possible outcome: Determined identified the right insertion point.

---

## PHASE 0 revisited -- what needs to be built

Filed as RM22. The scratch-to-seed arc requires:

1. "New corpus from directory" UI flow (corpus switcher must handle empty/new dir)
2. First-time ingest that creates the DB (not reingest_file, which requires existing DB)
3. Guidance for the two-step bootstrap: write first file → Analyze → then use reingest_file
4. seed/ should be buildable from scratch following these steps in reverse:
   walk the complete→seed diff backward and document each file-creation step as a journey step

The reverse-seed approach: start from complete, identify which files/functions were added
at each phase, use that as the "what to write next" script for the scratch walk.
