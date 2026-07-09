Written at commit: 0418275
# SESSION STATE - session 124 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 124, 2026-07-09)

**Doc consolidation [V]**
- DESIGN_ARC.md + DISCOVERY_MODEL.md + REASONING_MODEL.md collapsed into docs/ANALYSIS_MODEL.md
- Three source docs deleted
- Two source-file references updated (reasoning_engine.py, agent_tools.py)
- step_queue.md updated (was stale, still showing Stage 4 as CURRENT)

**Commonplace terminal structure established [V]**
- examples/commonplace/seed/ = Terminal 1 (skeleton, 17 files, 2 stubs) -- unchanged
- examples/commonplace/ = Terminal 2 (complete, 25 files, stubs closed, pre-enhancement)
  - Rolled back: tagger.py (suggest_tags returns []), searcher.py (semantic_search delegates to text search),
    linker.py (_similarity_score Jaccard only), utils/text.py (no embed helpers)
- examples/enhanced/ = Terminal 3 (enhanced, Walk 4 extras wired in)
  - suggest_tags -> LLM endpoint, semantic_search -> embeddings, _similarity_score -> cosine
- Terminal 0 = empty directory user creates themselves

**Design conversation [?]**
- Bart pushed back on "done" declarations -- tool is not ready for real users
- No getting started doc exists; no user-facing instructions exist
- The tour forward through phases is the primary user experience
- Users need to be able to navigate to any point once they've completed the tour

## NEXT SESSION -- start here

**Getting started doc (primary task)**
- Four terminals, three phases, choose-your-own-adventure structure
- Terminal 0 lives at examples/commonplace/noseed/ (user creates it; name is the instruction)
  -- noseed sits parallel to seed/ so the relationship is explicit; seed is the answer key
- Phase 1: Empty -> Skeleton (Terminal 0 -> 1): user builds skeleton from scratch OR loads seed
- Phase 2: Skeleton -> Complete (Terminal 1 -> 2): close stubs, wire orphans
- Phase 3: Complete -> Enhanced (Terminal 2 -> 3): LLM tagging, semantic search, cosine similarity
- Forward tour by default; any point navigable once complete
- Every tool explained: what it is, what it needs, what it produces, what comes next
- Dependencies called out explicitly; no dead ends
- Two audiences: no experience (every concept defined) and experienced (concepts still Determined-specific)
- Doc is a map + tour guide, not a script; tool carries inline context, doc fills the big picture
- Lives at docs/GETTING_STARTED.md

**Before writing the doc:**
- Run tests to confirm nothing broken by the terminal restructure
- Verify COMMONPLACE_USER_JOURNEY.md is accurate for all three phases as they now exist
- The enhanced/ folder needs a .determinedignore to exclude seed/ if it exists (already removed)

**After getting started doc:**
- Discovery narration persistence (narrations not yet saved to DB)
- RM28 Stage 5: test Discovery on dj2

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [V]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**LLM restart required after ctx-size change [V]:** --ctx-size 32768 only takes effect after full UI restart.
**Getting started doc does not exist [V]:** No user-facing instructions for running the tool.
