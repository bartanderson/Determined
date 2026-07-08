Written at commit: (pending -- written before final commit)
# SESSION STATE - session 119 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 119, 2026-07-08)

**RM15 Phase 1 clean user walk -- DONE [V]**
- Seed evolved since Phase 1 was written: now 17 files, 0 stubs (Walk 4 extras)
- Cleared developer carry-over artifacts from seed DB (design notes, summaries)
- Walked orient → frontier (Direct/Orphan/ABC) → topology → tools → knowledge
- No broken tools found. Clean walk.
- Rewrote COMMONPLACE_USER_JOURNEY.md Phase 1 with verified current outputs
- Marked RM15 DONE in TRACKER.md (all 4 phases complete)
- 493 passed, 1 skipped

**RM28 filed -- Three-mode UX: Tour, Discovery, Workbench [V]**
- Designed in conversation with Bart
- Three modes: Unguided (current), Guided Tour (Commonplace), Discovery (own project)
- Workbench: Discovery tools available ad hoc, user chains manually
- Shared foundation: Artifact layer (named, persistent, staleness-tracked tool outputs)
- Full spec in TRACKER.md RM28
- Build order: Stage 1 artifact layer → Stage 2 Tour → Stage 3 Workbench → Stage 4 Discovery

## NEXT SESSION -- start here

**RM28 Stage 1: Artifact layer**

Build the artifact persistence and staleness foundation that all three modes share.

**What to build:**
- Extend workflow_items with artifact kind, staleness state, feeds-into metadata
- OR add a new artifacts table -- check workflow_items schema first to decide
- Staleness: compare artifact.created_at vs. reingest timestamps in files table
- Cascade: when artifact A goes stale, flag any artifact whose source lists A
- UI: extend Build queue tab into Artifacts panel showing name/status/age

**Where to start:**
1. Read TRACKER.md RM28 (full spec)
2. Read determined/intent/workflow_store.py (existing workflow_items table)
3. Read determined/ui/ui_server.py Build queue tab section
4. Design schema extension, then build

**Key constraint:** build on existing infrastructure (workflow_items, reingest_file
timestamps, Build queue tab) -- don't replace, extend.

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [V]:** Clear design_notes + semantic_summaries
  before a clean demo. Structural facts (entry, hot, dead) are valid, keep them.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
