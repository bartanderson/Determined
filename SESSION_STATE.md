Written at commit: d9dbfda

# SESSION STATE — session 307 final handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION (full arc)

Short session. Two threads, one process change.

### Thread 1: Zero-Mem paper (arxiv 2607.29377)

Bart shared a paper on deterministic memory operations for LLM agents. Key finding:
Zero-Mem eliminates LLM calls from memory ops (entity-context graph + temporal
hierarchy + deterministic calibration); 57.6% latency reduction.

Assessment:
- Not useful for Determined (already does this -- deterministic layer, LLM only at narration)
- Relevant to the companion MoE framework: the calibration layer (filtering conflicting
  evidence from multiple memory structures) is a concrete worked solution to the
  combination problem in deterministic MoE. Worth reading full method section before
  designing the combination step.

### Thread 2: Companion MoE framework

Bart is planning a deterministic mixture-of-experts framework as a separate project.
Agreed: start it after a few real dj2 development sessions through Determined; real
failures will define what the experts need to be. Not a Determined task.

### Process change: session arc workflow (commit d9dbfda) [V]

Added to CLAUDE.md:
- Step 5 in session start checklist: create `session_arc.md` in scratchpad, seed with
  carried-forward traps
- Working agreement: append one line to arc after each commit
- Session end Step 1: read arc file as source, fall back to git log if missing

Memory saved: `feedback_session_arc.md`. MEMORY.md updated.

Motivation: SESSION_STATE reconstruction at end is expensive when context is full.
Arc file amortizes cost; wrap-up becomes verify + promote, not reconstruct.

---

## WHAT TO DO NEXT SESSION

**Step 0 — Arc file.** Create session_arc.md at session start (Step 5 is now in
CLAUDE.md). Seed from the KNOWN TRAPS block below.

**Option A: list_features vs feature_shape EP count discrepancy (Option D from s305).**
list_features shows world/ with 164 EntryPts; feature_shape('world') shows 39.
Different definitions, same label "Entry points", no explanation. Not logged yet.
Run both tools on dj2, compare definitions in agent_tools.py, log delta in DELTA_LOG,
decide if terminology should be unified.

**Option B: New corpus for RM67 probe loop.**
RM75 closed. Clone a new corpus into `C:\Users\bartl\dev\corpora\`, ingest with
`tools/ingest_lang_corpus.py`, run RM67 probe.

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
- dj2 "tail" stubs: prior session (298) concluded "phantom edges, lower priority" -- WRONG. [V s305]
- analyze_corpus connectivity-dominant threshold requires orphaned_impl >= 50. [V s299]
- New tools registered in TOOLS dict: add AFTER function def, not inside the dict literal. [V s299]
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes and smart quotes.
  Use Git Bash (Bash tool) for commit messages. [V s299]
- _get_abc_gap_set() excludes no-subclass ABCs by design -- they belong to find_abc_gaps. [V s300]
- Stale corpus DB produces phantom stubs. Re-ingest before trusting stub list. [V s301]
- DB forward-slash paths: when querying by file_path, use forward slashes not backslashes. [V s303]
- persist_file_analysis ingested_at fix: old DBs pre-d48836f have NULL ingested_at for Python files. [V s304]
- _ep_tier excludes .json/.yaml/.toml (protocol tier). FSM config symbols not inferred EPs. [V s305]
- _caller_names bare-name fallback: Class.method callers resolved via bare name + caller_file. [V s305]
- frontier_priority and _get_chain_positions: Class.method JOIN bug fixed; bare-name + caller_file
  fallback in all three SQL JOINs. [V s306]
- list_stubs LIMIT applies to non-FSM stubs only. FSM stubs always show in full. [V s306]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
- Determined corpus DB: re-ingest at session start if DB mtime > ~1 week old.
- reingest_changed is available as a tool: call it when corpus may be stale.
- Session arc: create session_arc.md in scratchpad at start; append per commit; promote at wrap.
