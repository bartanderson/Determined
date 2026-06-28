tools/analysis - TRACKER (consolidated)
=========================================

This file is the canonical open-items list and at-a-glance status for the
Determined analysis tool. Active open items only. For closed items, phase
plans, tier status, UI vision, branch methodology, and environment defects,
see docs/archive/TRACKER_history.md. For architecture/intent (the why
behind the design), see DESIGN.md.

Per CLAUDE.md's working agreement: update this file in place as part of
finishing work (checkboxes, dated notes) so Bart can see what changed via
`git diff`, and so a future session doesn't need conversation history to
know where things stand.

---

## Dashboard - at a glance

**Last session (2026-06-28, session 32):** Items 9, 10, 19 done.
Item 9: distillation pass - distill_corpus() tool, distilled kind in knowledge_artifacts,
wired into symbol_brief (preamble) and goal_intake step 1 (enriched embedding). 301 tests.
Item 10: _raw helpers layer - 5 private raw helpers (_search_symbols_raw, _list_callers_raw,
_list_callees_raw, _graph_most_connected_raw, _graph_subgraph_raw), string tools now derive
from raw (XIV: one source of truth), goal_intake step 1 uses _search_symbols_raw. 303 tests.
Item 19: check_design_violations tool - semantic cosine-search against design_notes, constraint
language filter, wired into risk_profile, pure analysis only (SOTS XI). Self-audit ran against
Determined's own corpus (168 design_notes, 5 WARM symbols) - produced real findings, validated.

**Before that (2026-06-28, session 30):** Mentor arc complete. Items 23/24/25 closed.
Item 23 rebuilt on embeddings (all-MiniLM-L6-v2, docstring-enriched queries, threshold 0.32).
SOTS (shapeofthesystem.com, 25 tenets) ingested into knowledge.db as design_notes -- surfaces
automatically via frame comparison. Item 24: goal_intake tool -- natural language goal ->
navigation plan (relevant symbols + risk badges + design rules + ordered approach). Item 25:
corpus map branch merged and deleted. Determined .claude/ added (same as dj2). 320/322 passing.

**Before that (2026-06-25/26, session 19):** Multiple bug fixes + corpus scoping + dj2 design docs.
Items 16/17/18 all fixed and closed. run_engine.py repo_root hardcoded to "." - fixed. scan_project_files.py:
3.10/3.11/3.12 venv dirs now excluded. knowledge.db corpus scoping complete (corpus column on knowledge_artifacts
+ semantic_summaries, scoped across all read/write paths: intent, oracle, assessor, agent layers). UI corpus
switch tab refresh fixed (_startupFiredFor tracks DB path). DB lock on re-analysis fixed (close oracle before
unlink). ingest_done now triggers corpus_status -> corpus_ready -> tab refresh. Regression fix: stale
test_list_callees_no_callees assertion. 298/298 passing. dj2 design docs written: 00E AI_LAYER_OPPORTUNITIES,
00F ASPIRATIONAL_DESIGN_INTENT (section H links back to item 19). Item 14 (validate small-model) is now
unblocked - all blockers resolved, harrow corpus clean and scoped.

**Before that (2026-06-24, session 17, continued):** Tool registry. New file:
determined/agent/tool_registry.py - REGISTRY (28 tools, full metadata: purpose/args/output/feeds/use_when/category),
TASK_PATTERNS (7 named workflows), describe_tool (callable from agent). agent_prompt.py now generates
TOOL_DESCRIPTIONS from the registry (all 28 tools, grouped by category). describe_tool wired into TOOLS.
2 new tests. 276/276 passing.

**Before that (2026-06-24, session 17, continued):** Knowledge layer additions.
extract_design_facts() - no-LLM structural extraction (entry points, dead code, hot symbols, stub files).
knowledge_status tool, get_findings expanded to semantic_summaries. 274/274 passing.

**Before that (2026-06-24, session 17):** Ran tool against dj2 corpus, found and fixed 5 real bugs.
is_hot was hardcoded False (now bool(mutations)); is_stub column missing from old DBs (migration added);
graph_most_connected returned builtins/externals (now project-only); find_todos only scanned docstrings
(now scans file content); task_generator had tools/analysis branding. Also fixed 2 stale regression tests.
274/274 passing. dj2 corpus re-ingested: 150 files, 132 hot, 47 stubs detected.

**Previously (2026-06-24, session 16):** Migration complete.
tools/analysis/ deleted from dj2. Engine now lives exclusively in Determined.
28 regression test files (279 tests) passing. knowledge.db intact (77KB).
dj2 is game code only. Both repos committed and pushed.

**Item 14 done (2026-06-27):** llama3.2:3b validated cold against harrow corpus.
All 7 orient_to_codebase steps fired in order. Model did not hallucinate tool names or skip steps.
Final synthesis correctly identified the key symbols. Pattern executor works. Item 14 closed.

**Item 15 done (session 18):** Pattern executor built and wired in. Model no longer picks
tools when a named pattern matches - executor drives the sequence, model only interprets
each step result. 293/293 tests passing.

**Full history:** HISTORY.md.

---

## Open items

---

19. **[DONE 2026-06-28] Design intent layer: check_design_violations + self-audit**

   The tool analyzes code structure but has no awareness of what the code is *supposed*
   to do. Design docs (architectural constitutions, subsystem specs, authority boundaries)
   are the authoritative intent for a project -- currently they live entirely outside
   the tool's knowledge layer.

   **The gap:** The tool can find that dm_chat_handler.py bypasses the authority layer,
   but cannot tell you *why* that's wrong or what the correct boundary is. Design intent
   has no representation in knowledge.db.

   **What this enables:**
   - Ingest design docs (markdown) as a separate artifact class alongside code
   - Extract aspirational constraints: authority boundaries, layer rules, forbidden patterns,
     named invariants, "must not" / "only X may" rules
   - Cross-reference code findings against design intent:
     "This symbol violates a documented boundary" not just "this symbol calls that one"
   - Surface drift: "ContextBuilder re-resolves entities -- constitution says it must not"
   - Inform every "where does this go" coding decision without dictating order

   **Nature of this item:** Living, aspirational, off-and-on. Not a one-time feature --
   a capability that deepens as the tool matures. Early stab: extract key constraints
   from design docs into knowledge_artifacts (kind=design_note, provenance=human-confirmed).
   Later: automated cross-reference against structural findings.

   **First concrete step:** Write a doc extractor that reads markdown design docs,
   pulls out named invariants and authority rules, and stores them as human-confirmed
   design_note artifacts scoped to the corpus. Then wire findings to check against them.

   **Primary target docs (dj2 corpus, all committed 2026-06-26):**
   - `docs/design/00A ARCHITECTURAL_CONSTITUTION.md` - the authority hierarchy and invariants
   - `docs/design/00B SYSTEM_CONSTRAINTS.md` - hard constraints
   - `docs/design/00F ASPIRATIONAL_DESIGN_INTENT.md` - authority boundaries (section B), AI DM
     vision (section C), world architecture (section D); section H explicitly describes what
     Determined should eventually extract and cross-reference from these docs
   - `docs/design/00E AI_LAYER_OPPORTUNITIES.md` - AI layer constraints and patterns

   When dj2 is the active corpus, these docs are the authoritative intent surface.
   The extractor should prioritize "must not", "only X may", "never", "must" phrases
   in these docs as the highest-signal invariants to store as design_note artifacts.

   **Why HIGH:** Without this, the tool cannot help maintain design integrity as code
   grows. It finds structural facts but misses the most important class of bugs:
   architectural violations.

1. **[LOW] `files.role` is never populated** - `parse_ast.py` sets `role=None`
   and has a comment "DO NOT recompute elsewhere." The `describe_file` and
   `find_files(role=...)` tools return no role info. Either implement role
   classification at ingestion time or remove the column and tool parameter.

2. **[LOW] `search_symbols` only finds 2 results for 'game_state'** but there
   are likely more (GameState class, game_state parameter names, etc.).
   Current query hits `symbols.name` substring match only - doesn't search
   behavioral_contracts.description or docstrings. Expand when it proves
   insufficient in real use.

3. **[LOW] `missing_docstrings` limit is hardcoded 20** with no way to get
   the full list or filter by file/module. Fine for now; revisit when the
   user actually needs coverage reporting.

6. **[MEDIUM] Live sync loop: edit -> re-ingest -> update** - re-ingest a
   single changed file without full corpus re-run. Currently the only option
   is full re-ingest (fast at 150 files, but won't scale to large corpora).
   Requires: incremental re-ingestion by file_path, edge delta propagation.

7. **[DEFERRED] contracts/orchestration feature decision** -
   `contracts/load_contract.py` has a dormant KeyError bug (loads wrong JSON,
   calls `contract["domains"]` which doesn't exist). Nothing calls it yet so
   it's silent. Decision: wire the typed loader + build orchestration layer,
   or delete all three (contract_types.py, tool_system_contract.json,
   orchestration/). Must decide before anything tries to use contracts.

8. **[DONE 2026-06-28] Auto-populate semantic summaries at ingestion**

   `--summarize` flag added to `local_agent --source`. After ingestion and
   structural fact extraction, iterates all corpus files and calls
   semantic_summary() for each. Skips already-cached. Aborts gracefully on
   Ollama connection failure with count of summaries written. 297/297 passing.

9. **[DONE 2026-06-28] Distillation pass** -
   `semantic_summaries` and `file_purpose` artifacts store 3-4 paragraph LLM
   responses verbatim. Add a distillation step: pass each verbose blob back to
   Ollama with a compression prompt ("one sentence: what does this file/symbol
   do?") and store the result as a separate `distilled` kind in
   `knowledge_artifacts`. The distilled form is what `symbol_brief` and the
   agent resolver use as a quick-scan; the verbose form stays for full context.
   Subject naming convention: `distilled::<subject>`.

10. **[DONE 2026-06-28] Tool chaining: structured output mode** - every tool returns a
    string (right for LLM consumption). When one tool's output drives another
    programmatically (e.g. `list_callers` -> `risk_profile` for each caller,
    or `graph_subgraph` nodes -> `symbol_intent` for each node), the agent has
    to re-parse its own text. Add an internal `_raw` variant for key tools that
    returns structured data (list of dicts), used by agent_resolver's auto-
    expansion phase (phase 2b) instead of text-parsing. External API stays
    string-only. Affected tools: `list_callers`, `list_callees`,
    `graph_most_connected`, `graph_subgraph`, `search_symbols`.

11. **[FUTURE] Trace-weighted ranking** - replace heuristic scoring with
    trace-weighted ranking from expansion provenance. After real usage patterns
    are clear.

14. **[FUTURE] Semantic speculative decoding** - once item 10 (structured output)
    is in place, explore using the 3B model as a reasoning-step predictor: 3B
    predicts which tools/symbols/docs are needed, Oracle fetches them, 8B reasons
    only over the pre-assembled result. Analogous to token-level speculative
    decoding but at the semantic level. Revisit after item 10 is shipped and
    real usage patterns show where the 8B is spending time unnecessarily.

13. **[FUTURE] Self-Harness pattern** - knowledge.db is the natural store for
    harvested failure patterns. After ADVERSARIAL traces accumulate, mine them
    into `known_issue` artifacts keyed by failure category, then use those
    artifacts to tune agent_resolver heuristics. Loop: ADVERSARIAL run ->
    extract failure patterns -> store as known_issue -> harness reads on next
    run -> better routing. Closes the improvement loop without touching Ollama.

---

### MENTOR CAPABILITY ARC (session 26, 2026-06-27)

The goal of Determined is to approximate what Claude does when a developer brings
it an unfamiliar codebase: orient quickly, identify what is dangerous vs safe,
surface mismatches between design intent and code reality, and guide the developer
toward the right approach for their goal. Not answer queries - navigate.

This requires three capabilities that do not yet exist, plus one prerequisite.
All four build on existing infrastructure rather than replacing it.

**What the tool already has that these build on:**
- knowledge_artifacts (design_note kind) - foundation for design intent storage
- pattern_executor + orient_to_codebase - structured orientation, extendable
- risk_annotator - already scores hot/warm/safe per symbol
- stub detection - already knows what scaffolding exists but is unimplemented
- bag_store - already accumulates session context across queries
- mine_design_docs.py - hand-authored design notes in the right shape, wrong source

**The 3B model's role:** connector of pieces, not memory. DB holds structured
knowledge; the model reasons over what it is given. Architecture is: assemble
the right context for each step, let the model connect it.

---

22. **[DONE 2026-06-28] Design doc extraction: auto-mine markdown into design_note artifacts**

   Shipped as `ingest_design_docs` tool and `discover_docs` tool in agent_tools.py.
   discover_docs scans project for markdown with constraint density scoring.
   ingest_design_docs uses the 3B model (Ollama) to extract named invariants, authority
   rules, forbidden patterns from those docs and stores as design_note artifacts
   (provenance=llm-extracted). Re-running is idempotent. Wired into TOOLS and REGISTRY.

---

23. **[DONE 2026-06-28] Frame comparison: surface design intent automatically when code touches documented areas**

   Rebuilt session 30 on semantic embeddings (all-MiniLM-L6-v2). _get_design_frame()
   embeds symbol+docstring context, cosine-searches all design_notes in knowledge.db
   (threshold 0.32). Query enriched with docstring so abstract principle text (SOTS)
   surfaces alongside project-specific constraints. Replaces fragile string matching.
   320/322 passing (2 pre-existing failures, unrelated).

---

24. **[DONE 2026-06-28] Goal intake: developer states intent, tool assembles goal-directed context**

   goal_intake(goal) in agent_tools.py. Takes natural language goal, returns navigation plan:
   - Semantic search over symbol docstrings -> top 5 relevant symbols
   - HOT/WARM/SAFE risk badge for each
   - Design rules from knowledge.db (SOTS + project notes) semantically matched to goal
   - Uncalled functions near relevant files as safe insertion candidates
   - Ordered approach: READ (hot boundaries) -> REVIEW (warm) -> EXTEND (stubs) -> MODIFY (safe)

   Trigger phrase: "I want to add/build/implement/create/extend X"
   Wired into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern. 320/322 passing.

---

25. **[DONE 2026-06-28] Corpus map: merged and shipped**

   Branch ui/corpus-map merged to main and branch deleted. Corpus map panel
   (Roots/Core with risk badges, collapsible) is live in the UI.

---

## Chronological session log

Moved to HISTORY.md (section B) as part of the 2026-06-18 TRACKER/HISTORY
split - full dated session-by-session record, verbatim, nothing dropped.
