Written at commit: 8384308
# SESSION STATE - session 129 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 129, 2026-07-09)

**RM29: duplicate symbol detection -- DONE [V]**
- Corpus panel shows "N duplicate names" in orange when names appear in >1 file
- Orphan mode annotates each orphan with "⚠ also in other_file.py"
- `dupes` query: `SELECT name FROM functions GROUP BY name HAVING COUNT(DISTINCT file_path) > 1`
- Bug found and fixed: `dupes` was computed in `_corpus_status()` but not passed through
  `_emit_corpus_ready()` -- badge never appeared until fixed
- Tooltip updated: warns "may be intentional (method names, route+query conventions)"
- RM30 filed: filter class methods from count so only module-level collisions trigger badge
- Committed 6cb645d, 8384308

**Fix Re-analyze UX [V]**
- `setCorpusLoaded` received `source_path` but never stored it -- Re-analyze always opened
  browse dialog. Now stored in `_currentSourcePath`, used directly on Re-analyze click.
- Committed 9812b13

**Gaps panel stops bouncing [V]**
- Gaps rendered before Roots/Core toggle so toggling doesn't shift it
- Committed b8d173c

**Roots vs Core explained:**
- Roots: entry points -- functions nothing else calls (route handlers, ABCs, main)
- Core: hot symbols -- functions many things depend on (high blast radius if changed)

**506 passed, 1 skipped [V]** (verified after each commit)

## Current state of seed/ [V]
17 files, original baseline. No additions staged or tracked.

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [?]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI for single file.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**LLM restart required after ctx-size change [V]:** --ctx-size 32768 only takes effect after full UI restart.
**RM30 duplicate name filtering [V]:** Tooltip warns but badge still fires on intentional patterns (class methods, route+query pairs). Fix: filter names where all occurrences have non-null class_name.

## NEXT SESSION -- start here

Active open items in TRACKER.md: RM30, RM28, RM21, RM20.

**RM30** (duplicate name filtering) -- small, self-contained. Filter `class_name IS NULL`
from the dupe count query so method names on multiple classes don't trigger the badge.
File: `determined/ui/ui_server.py` `_corpus_status()` -- the `dupes` query.

**RM28** (Three-mode UX: Tour/Discovery/Workbench) -- larger, design work needed first.
