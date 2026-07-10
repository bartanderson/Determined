Written at commit: 6406dd6
# SESSION STATE - session 133 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 133, 2026-07-10)

**RM28 Stage 4: completion state -- DONE [V]**
- `COLORABLE_KEYS` const defined: `["rail:corpus", "rail:navigate", "rail:tools", "rail:ask"]`
- `guideAllGreen()`: returns true when all 4 keys visited
- `guideCheckCompletion()`: idempotent -- shows completion card every call while all-green;
  schedules `guidePermanentDismiss()` once after 4s via `_completionScheduled` flag
- `guideUpdateCard()` restructured: checks `!_guideOn` first, then `guideCheckCompletion()`,
  then `!_isCommonplace` guard -- completion fires regardless of corpus
- Verified in browser via Chrome MCP: card showed "You've explored everything. / The guide
  will step back.", auto-dismiss fired after 4s, toggle hidden, footer restore visible [V]
- Committed 6406dd6 [V]
- No Python files changed; tests not re-run (not needed)

## Current state of seed/ [V]
17 files, original baseline. No additions staged or tracked.

## Known issues (carried forward)

**GUIDE_DATA sync trap [V]:** `guide_commonplace.json` and inline `GUIDE_DATA` in console.html
are separate stores -- both must be updated together when adding card content. No auto-sync.
**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [?]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI for single file.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**LLM restart required after ctx-size change [V]:** --ctx-size 32768 only takes effect after full UI restart.

## NEXT SESSION -- start here

Active open items in TRACKER.md: RM28 Stage 5 (deferred), RM21, RM20, RM29, RM30.

**RM20** -- next thing to build (~1 hour).
- File: `determined/agent/doc_extractor.py` -- embed candidate rule at store time; skip INSERT
  if cosine similarity >= 0.85 to any existing design_note. Reuses `embed_text` from
  `determined/oracle/embedding_model.py`.
- Entry point: find the store step inside `ingest_design_docs` in doc_extractor.py.
  Check before INSERT. No schema change needed.

**RM28 Stage 5 (deferred)** -- general guide layer for non-Commonplace corpora.
- `guide_general.json` keyed to element only (no corpus phase). Build after Commonplace proves pattern.

**RM21** -- build only after Technique 1 proves insufficient on real multi-hop queries.
