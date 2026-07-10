Written at commit: 70bcbd3
# SESSION STATE - session 138 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 138, 2026-07-10)

**RM36: corpus index injection -- DONE [V]**
- Committed 435db10
- Added `_corpus_index(oracle)` helper to `local_agent.py`.
  Queries `files WHERE is_hot=1` (up to 8) and `files WHERE role='entry_point'` (up to 6).
  Builds a short "Corpus map" block and injects it into Phase 1 DECOMPOSE prompt
  when `ground_question()` returns empty string.
- Fixes Q1 "give me an overview" -- model now emits real filenames instead of `<file.py>` placeholders.
- 4 new regression tests in `test_local_agent.py`.

**RM37: traversal heuristic "path" false-fire -- DONE [V]**
- Committed 435db10 (same commit as RM36)
- Added negative lookahead `(?!(?:the\s+)?path\b)` to the `what\s+is\s+` branch of the
  survey heuristic in `agent_resolver.py`.
- Fixes Q5 "what is the path from..." -- no longer extracts "path" as a symbol name.

**blast_radius OperationalError fix -- DONE [V]**
- Committed 70bcbd3
- `agent_tools.py` line 143: `functions` table has no `symbol_type` column.
  Was querying `SELECT name, symbol_type FROM functions` -- column doesn't exist.
  Fixed to `SELECT name, 'function' AS symbol_type FROM functions` (literal string).
- Fixes Q2 blast-radius which was returning the DB error as its answer.

**RM21 probe -- ALL 6 PASS [V]**
- Q1 orient: real filenames in answer (RM36)
- Q2 blast-radius: actual caller trace (blast_radius fix)
- Q3 search centrality: correct (RM32, prior session)
- Q4 comparative: YES/NO first, named symbols (RM33, prior session)
- Q5 traversal: correct route-to-DB trace (RM37)
- Q6 Entry class methods: only real methods named (RM34, prior session)

**533 tests passed, 1 skipped [V]**

## Known issues (carried forward)

**GUIDE_DATA sync trap [V]:** `guide_commonplace.json` and inline `GUIDE_DATA` in console.html
are separate stores -- both must be updated together when adding card content. No auto-sync.
**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [?]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI for single file.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db

## NEXT SESSION -- start here

**RM21 Technique 1 arc is complete and validated.** All 6 probe queries pass cleanly.
Techniques 2-6 are on hold -- gated on Technique 1 proving insufficient on real queries.

**True open items:**
- RM28 Stage 5 (deferred): general guide layer for non-Commonplace corpora.
  guide_general.json keyed to element only (no corpus phase). Low urgency.
- RM10 (FUTURE): DeRe-CoT recomposition pass in goal_intake.
- RM13 (FUTURE): Self-Harness -- mine adversarial traces into routing heuristics.

**Best next move:** RM28 Stage 5, or run the Q&A pipeline against a fresh corpus
(dj2 or harrow) to surface the next real failure mode before building more.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
Started via UI (port 5050) or manually.
