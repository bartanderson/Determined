Written at commit: e28e55e

# SESSION STATE — session 299 handoff (continued)

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**Session goal: reconnect the tools to the teaching vehicle (GETTING_STARTED.md)**

Bart identified the drift: the delta loop work (sessions 296-299) made the tools
sophisticated for dj2-scale projects, but the teaching corpus (commonplace) was left
behind. The guided journey in GETTING_STARTED.md taught the visual UI but never
introduced the Ask bar tools. analyze_corpus on commonplace said "unclear" — useless
for teaching.

**Two fixes shipped (e28e55e):** [V]

1. **Low-pressure shape in analyze_corpus.** When total_stubs <= 5 and no wired/isolated
   patterns dominate, the tool now says "Low pressure - essentially complete" instead of
   "unclear." Commonplace complete now reads: shape, 1 deferred stub, 43 orphaned impls,
   nothing blocking. Seed reads: complete, 24 orphaned impls (Flask routes).

2. **Ask bar section in GETTING_STARTED.md.** Two insertions:
   - Brief pointer after "Loading the skeleton" — type analyze_corpus before exploring panels
   - Full section "The Ask bar: from structure to action" after Phase 3 — shows actual
     analyze_corpus output on complete corpus, explains each section (SHAPE/WHAT TO DO
     NOW/JUDGMENT CALLS/SUGGESTED NEXT TOOLS), shows follow-on tools, closes with
     "what this looks like on a real project" to bridge commonplace to dj2-scale work

The journey is now one continuous path: visual UI panels + Ask bar tools. analyze_corpus
is the handoff — it synthesizes what the panels show into a decision.

459 tests pass [V].

---

## CURRENT STATE

**analyze_corpus shapes:**
- Complete (0 stubs): "Complete - no stubs" + orphaned count [V]
- Low pressure (<=5 stubs, none wired/isolated): "Low pressure - essentially complete" [V]
- Connectivity-dominant (orphaned >= 50, >= 3x stubs, >= 50%): "Connectivity-dominant" [V]
- Stub-blocked (stubs with real callers): "Stub-blocked" [V]
- Unclear (stubs, none verified, corpus too large for low-pressure): "unclear" (rotjs) [V]

**GETTING_STARTED.md:** Complete through Ask bar section. Journey covers
skeleton -> growing -> complete -> Ask bar -> what to do next. [V]

---

## STILL OPEN

1. **static/ false positive in analyze_corpus.** `static/` (web assets) appears as
   "built-but-isolated" for dj2. Needs an `_is_test_feature`-style filter.
   File: `determined/agent/agent_tools.py`, `analyze_corpus`, `built_isolated` list.

2. **config/ missing from wired_incomplete in analyze_corpus.** config/ has 12 stubs and
   60 entry points in dj2 but doesn't appear in WHAT TO DO NOW step 1. Investigate by
   running `list_features()` and comparing dir_key mapping vs. analyze_corpus query.

3. **RM67 convergence assessment for dj2.** Read TRACKER.md RM67 criteria. dj2 output
   now matches Claude synthesis — does it meet the probe acceptance criteria?

4. **find_abc_gaps() on dj2.** analyze_corpus shows 39 ABC gaps. Does the output explain
   which are accepted scaffolds vs. real gaps?

---

## PROCESS RULE (standing) [V]

Every session: run Determined on dj2, compare tool output to what Claude would say,
log delta in DELTA_LOG.md, fix the tool. Never synthesize without fixing.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden`. [V s290]
- `llm_client.chat()` reasoning_content fallback removed -- don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains `\n`. [V s291]
- pytest `-m` on CLI REPLACES addopts -- never pass `-m` by hand. [V]
- Old corpus DBs may lack `http_route`/`is_tool`/`is_stub` columns -- handle gracefully. [V s293]
- FSM stubs have 0 static callers (string dispatch) -- don't treat as low-priority. [V s295]
- frontier_priority [test] tag uses _is_test_path() -- keep in sync with _is_test_feature(). [V s296]
- list_stubs caller count = ALL edges (resolved + unresolved); frontier_priority = resolved only. [V s297]
- dj2 "tail" stubs ALL have unresolved callers -- phantom edges, not real call paths. [V s298]
- analyze_corpus connectivity-dominant threshold requires orphaned_impl >= 50. [V s299]
- New tools added to TOOLS dict must be registered AFTER function def, not inside the dict
  literal -- forward references in dict literals cause NameError at import time. [V s299]
- git commit message: strip em-dashes and smart quotes; PowerShell here-strings fail on them.
  Use Git Bash for commit messages with special characters. [V s299]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
