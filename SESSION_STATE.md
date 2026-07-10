Written at commit: c5d06ab
# SESSION STATE - session 140 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 140, 2026-07-10)

**RM21 adversarial probe follow-up against Determined corpus [V]**

Prior handoff (session 139) incorrectly said "all 6 pass." Actual results were
3 pass / 2 partial / 1 improved. Fixed and re-probed.

**Q4 fixed -- PASS [V]** (committed c5d06ab)
- Added "imports of <file.py>" to _PATTERNS in agent_resolver.py -> list_import_deps
- Added special-case handler in resolve_need() for list_import_deps multi-group match
- Added "NEED: imports of <file.py>" to DECOMPOSE_SYSTEM in local_agent.py with tip
- Answer now correctly says both local_agent and ui_server import from same llm_client

**Q1 fixed -- PASS [V]** (committed c5d06ab)
- Expanded orient_to_codebase regex in pattern_executor.py:
  "explain this codebase", "describe the system", "what does this tool do",
  "give me an overview" (bare), "I'm new here" etc. -- 16/16 adversarial cases fire
- Moved orient_to_codebase rule BEFORE understand_symbol/explain/describe rules in
  _DETECT_RULES so "explain this codebase" doesn't get captured as understand_symbol("this")
- Known misses (documented boundary, not bugs):
  "how does this work", "summarize the codebase", "tell me about this codebase",
  "help me understand this code" -- too ambiguous to fire orient safely

**Grounding pollution fixed [V]** (committed c5d06ab)
- agent_resolver.py ground_question(): test files and test symbols now filtered from
  phase0 grounding suggestions (WHERE file_path NOT LIKE '%test%')
- Prevents Q5-style poisoning where "pipeline" matched test fixture filenames

**Q5 still confabulating -- DEFERRED [V]**
- Question: "what is the path from a UI query to the database in the agent pipeline?"
- After grounding fix, model still invents query_router.py, query_session.py,
  QueryExecutor, persist_query_session -- none of which exist in Determined
- Root cause: model has no traction. It searches for "query" + "pipeline" + "database"
  symbols, finds nothing relevant (real path is handle_query -> _answer ->
  resolve_and_expand -> dispatch(TOOLS) -> oracle), invents a plausible pipeline instead
- The TOOLS dict dispatch is the structural dead end: dispatch() uses string-keyed
  TOOLS dict so static analysis can't trace dispatch -> specific tool -> oracle
- Grounding doesn't surface handle_query as the entry point for this question shape

**533 tests passed, 1 skipped [V]**

## Probe scorecard (Determined corpus, as of c5d06ab) [V]

- Q1 orient ("give me a quick overview"): PASS -- orient_to_codebase fires, structural answer
- Q2 blast-radius ("what would break if I changed resolve_and_expand"): PASS
- Q3 name-search ("what does ground_question do"): PASS
- Q4 comparative ("does local_agent use the same LLM client as ui_server"): PASS
- Q5 traversal ("path from UI query to database"): FAIL -- confabulates pipeline
- Q6 method-confab ("what methods does DBOracle have"): PASS

## Known issues (carried forward)

**Q5 confabulation root cause [V]:**
The real path is handle_query (ui_server) -> _answer (local_agent) ->
resolve_and_expand (agent_resolver) -> dispatch(TOOLS dict) -> tool functions -> oracle.
The TOOLS dict is the dead end: dispatch calls functions by string key, static analysis
sees "dispatch -> agent_tools.fn" (generic) not "dispatch -> search_symbols" etc.
Two angles for next session:
1. Add design_note knowledge artifact documenting the actual pipeline path -- surfaces
   via _get_design_frame on architecture questions without touching the call graph
2. Add a detect_pattern rule for "UI to DB path" / "pipeline path" questions that
   explicitly runs handle_query -> _answer -> resolve_and_expand as a known traversal

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and inline GUIDE_DATA in
console.html are separate stores -- both must be updated together. No auto-sync.
Same applies to guide_general.json vs inline GUIDE_GENERAL.

**ingest_design_docs project root mismatch [?]:** Must call with explicit path.

**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.

**Complete corpus DB path [V]:**
C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db

## NEXT SESSION -- start here

**First task: Q5 -- path from UI query to database**

Two concrete approaches to try (pick one or both):

Option A (data, no code change):
  Add a design_note to the Determined corpus DB documenting the pipeline:
  "The path from a UI query to the database is: handle_query (ui_server.py) calls
  _answer (local_agent.py) which calls resolve_and_expand (agent_resolver.py) which
  calls dispatch() (agent_tools.py) using the TOOLS dict to route to specific tool
  functions that call oracle methods on the DBOracle instance (db_oracle.py)."
  Then re-run Q5 to see if _get_design_frame surfaces it.

Option B (detect rule, code change):
  Add a detect_pattern rule for "path from UI" / "pipeline from query" / "how does a
  query flow" that fires a named pattern (similar to orient_to_codebase) running:
  1. callers of handle_query
  2. callees of _answer
  3. callees of resolve_and_expand
  Then synthesize with the TOOLS dict explanation as a known-architecture note.

After Q5: run full adversarial probe again to confirm stable. Then move to dj2 or
next real failure mode.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
Started via UI (port 5050) or manually.
