Commonplace -- User-Facing Journey (Synthesized)
==================================================

Extracted from Walk 1, Walk 2, Walk 3 developer logs. This is what a new user
should see and do, distilled from actual tool output. Use this to validate the
next clean attempt and to design the guided UI (Phase 4).

Last updated: 2026-07-08 (session 114). Actuals from complete corpus also recorded.

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

## PHASE 0 -- Scratch (NOT YET WALKED)

**Starting state:** blank directory, no files, no DB.

**Blocker:** Determined has no "new corpus from directory" flow. `reingest_file`
requires a DB to already exist. Full corpus Analyze creates the DB but requires
at least one file. The two-step bootstrap is:
  1. Write first file
  2. Hit Analyze (creates DB)
  3. From then on: write → reingest_file (incremental)

**UI gap:** No "New corpus" prompt. User lands on corpus switcher with nothing
to switch to. There is no guidance for starting from zero.

**Filed as:** RM22. Must be solved before Phase 0 can be walked.

**[Expected] first-file state after Analyze:**
```
CORPUS TOPOLOGY
  Total files: 1  |  Total stubs: 0  |  Total implemented: N
  (depends on first file written)
```

---

## PHASE 1 -- Seed (PARTIALLY WALKED)

Walk 1 and Walk 2 walked the seed corpus. The seed lives at
`examples/commonplace/seed/`. Load it via corpus switcher.

### Step 1 -- Orient (Walk 1, Step 1) [VERIFIED]

**User action:** Switch corpus to seed, open corpus panel.

**What they see:**
```
8 files · 0 hot · 2 stubs
Roots: capture, index
```

**What it teaches:** Entry point + direct-call frontier. "Here is what exists.
Here is where it stops."

---

### Step 2 -- Read the frontier (Walk 1, Steps 2-3) [VERIFIED]

**User action:** Frontier tab → set Direct mode → Load.

**What they see:**
```
extract_metadata   (red -- stub, direct-call)
extract_full_content  (red -- stub, direct-call)
extract            (orange -- caller of stubs)
```

**User action:** Click `extract_metadata` in graph.

**What they see:** Spotlight: declaration + STUB docstring + SAFE risk + 1 caller.

**What it teaches:** The graph shows the edges of the working system. Stubs are
the frontier. Implement them in priority order.

**Known issue:** Spotlight panel invisible in preview pane (too narrow). Works in
real browser. Not a bug.

---

### Step 3 -- Implement first stub (Walk 1, Step 5-6) [VERIFIED]

**User action:** Editor tab → open `extractor.py` → implement `extract_metadata`
(urllib + HTMLParser, already shown in seed as partial implementation) → Save.

**What they see after save:**
```
Sidebar: 2 stubs → 1 stub (live, no reload)
```

**What it teaches:** write → reingest → frontier moves. The loop is:
edit_file → Save → watch sidebar update.

**Known issue fixed during walk:** UI was calling `reingest_file(oracle, fp)`
with wrong signature. Fixed to `reingest_file(db_path, fp)`. Now works correctly.

---

### Step 4 -- Topology (Walk 1, Step 4) [VERIFIED]

**User action:** Topology tab → Refresh.

**What they see:**
```
CORPUS TOPOLOGY
  Total stubs: 2  |  Total implemented: N

  Direct-call: 2   extract_metadata, extract_full_content
  Action queue: implement direct-call stubs
```

**What it teaches:** Topology tab explains WHY stubs matter and what to do next.
It's the "decide what to write" surface, not just a count.

---

### Step 5 -- Design doc (Walk 2, Step 4) [VERIFIED]

**User action:** Ingest `docs/DESIGN.md` via ingest_design_docs.

**Note:** Auto-discovery doesn't find DESIGN.md when it lives outside the seed/
project root. Must call ingest_design_docs manually with the correct path.
Known limitation -- filed as RM15 known issue.

**What they see after ingest:**
```
10 design rules extracted, stored as design_note artifacts
```

**User action:** Run `check_design_violations` on `extract_metadata`.

**What they see:**
```
0.43 -- extractor.py: one module or three? (real tension)
0.41 -- PERMISSION: same rule (duplicate -- noise, known issue RM20)
0.32 -- searcher.py: bypasses service layer (cross-symbol noise)
```

**User action:** Run `reason_about` on `extract_metadata`.

**What they see:**
```
Decision:   Keep extractor.py as a single module
Confidence: 95%
Reasoning:  SOTS tenet: minimize indirection. 2 callers, 5 callees -- manageable.
```

**What it teaches:** Determined surfaces design questions, not just structural gaps.
`check_design_violations` at >= 0.45 is high signal. 0.30-0.40 is noise floor.

---

### Step 6 -- ABC gap (Walk 2, Steps 1-2) [VERIFIED]

**User action:** Run `find_abc_gaps`.

**What they see:**
```
EnrichmentProcessor (inherits EntryProcessor)
  can_handle  [not overridden]
  process     [not overridden]
```

**User action:** Implement `can_handle` and `process` on `EnrichmentProcessor`.
Reingest `processor.py`.

**What they see:**
```
find_abc_gaps: (empty -- 0 gaps)
detect_topology: ABC-interface: 0 (was 2)
```

**What it teaches:** ABC gaps are a different stub shape. `find_abc_gaps` is
distinct from `detect_topology` -- it checks per-subclass, not globally.

---

### Step 7 -- Orphaned-impl (Walk 2, Step 3) [VERIFIED]

**User action:** Run `detect_topology`.

**What they see:**
```
Orphaned-impl: 2  (semantic_search, init_db)
Action queue:  write callers
```

**User action:** Wire `search_bp` into `app.py`. Change route to call
`semantic_search` instead of `search`. Reingest both files.

**What they see:**
```
Orphaned-impl: 1  (init_db -- known false positive, Flask app_context)
```

**What it teaches:** Orphaned-impl means "working code with no callers."
Sometimes it's a gap (wire it up); sometimes it's a known analysis limit
(Flask app_context is invisible to static analysis). Read the reason.

---

### Step 8 -- Conditional stub (Walk 2, Steps 5-7) [VERIFIED]

**User action:** Run `find_conditional_stubs`.

**What they see:**
```
1 found:
  validator.py :: validate_entry  (raise NotImplementedError inside if strict:)
  "implemented functions with raise NotImplementedError in a branch"
```

**User action:** Run `reason_about` on `validate_entry`.

**What they see:**
```
Decision:   Remove the strict branch entirely
Confidence: 95%
Reasoning:  No callers need strict=True yet. Removing simplifies the function.
```

**User action:** Remove `if strict: raise NotImplementedError`. Reingest.

**What they see:**
```
find_conditional_stubs: 0 found
detect_topology: Total stubs: 0  |  Orphaned-impl: 1 (known false positive)
```

**What it teaches:** Conditional stubs pass structural analysis but fail at
runtime on specific inputs. They represent deferred decisions disguised as
working code. `find_conditional_stubs` is the only tool that catches these.

---

### Seed journey complete -- verified tool coverage

| Tool | Lesson demonstrated | Signal quality |
|------|--------------------|----|
| `detect_topology` | structural shape of the corpus | HIGH |
| `find_abc_gaps` | missing ABC overrides | HIGH |
| `find_conditional_stubs` | hidden runtime gaps | HIGH |
| `check_design_violations` | design rule cross-reference | HIGH at >= 0.45, NOISY below |
| `reason_about` | architectural decisions grounded in SOTS | HIGH (correct conclusion, slight reasoning path drift) |
| `symbol_context` | everything known about one symbol | HIGH |
| `reingest_file` | incremental re-ingest after edit | HIGH |
| Editor tab save | live reingest trigger | HIGH |

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

## PHASE 3 -- Extras (PARTIALLY WALKED)

Filed as RM23. Three natural next steps surfaced by Determined on the complete corpus:

1. **Wire suggest_tags to llama-server** [WALKED -- Extra 1, session 115]
2. **Semantic search with real embeddings** [NOT YET WALKED]
3. **Connection inference live** [NOT YET WALKED]

Each extra: Determined surfaces the frontier → user implements → reingest → verify.
The tool becomes navigation layer for a codebase the user already understands.

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

### Extra 2 -- Semantic search with real embeddings [NOT YET WALKED]

`semantic_search` currently delegates to text `search()`. Wire sentence-transformers
or llama-server `/embeddings` endpoint. Medium effort. Demonstrates Determined
navigating an actively evolving feature.

---

### Extra 3 -- Connection inference upgrade [NOT YET WALKED]

`find_connections` uses keyword overlap (Jaccard). Wire `_similarity_score` as
scoring upgrade (embedding-based similarity). Shows the "Decide" disconnected stub
resolving into a real enhancement.

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
