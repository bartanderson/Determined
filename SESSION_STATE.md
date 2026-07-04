# SESSION STATE - session 72 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 72, 2026-07-04)

### Commonplace DESIGN.md written and verified

- **`examples/commonplace/docs/DESIGN.md`** created:
  - Four-layer architecture spec (routes / services / storage / utils) with
    explicit responsibility rules for each layer
  - Six authority rules in Determined-detectable language:
    - "Only storage/ touches the DB directly"
    - "Routes delegate to services, never to storage directly"
    - "Tags are always lowercase"
    - "Connections are bidirectional -- both directions must be stored"
    - "Content is required for every entry"
    - "URL validation must occur before network fetch"
  - Four open design questions promoted from code comments (extractor split,
    tagger eager-vs-lazy, searcher boundary bypass, capture URL duplication)
  - Stub roadmap with LLM dependencies for all five stubs

- **Ingested and verified:**
  - `ingest_design_docs` extracted 10 rules from the doc
  - `check_design_violations('search')` flagged service-layer bypass (score 0.50)
  - `check_design_violations('capture')` flagged duplicate URL validation (score 0.30)
  - Both known violations detected correctly

## NEXT SESSION -- start here

**Pick up from Bart's additions below, then continue Commonplace step 2.**

After addressing anything Bart adds, the next COMMONPLACE_VISION step is:

**Step 2: Add missing topology shapes to Commonplace**

Add to `examples/commonplace/`:
- An ABC with at least one abstract method and no override (exercises `find_abc_gaps`)
- A chain-middle stub (called by another stub, calls another stub -- exercises chain topology)
- A conditional stub (`raise NotImplementedError` inside an if branch, exercises
  `find_conditional_stubs`)

These give the Commonplace corpus the topology variety needed to demo all Determined
frontier features against its own codebase.

## Current Determined status

### Test count: 414 passed, 1 skipped

### Open DISCOVERY_MODEL items
- F1: Validate direct-call query accuracy (false positive audit)
- F7: Frontier tab type selector (add Orphan mode to dropdown)
- A1: resolved flag + is_project_call column (no migration needed -- rebuild fresh)
- A2: access_paths(symbol) query
- A3: collapse duplicate graph edges
- A4: universal sub-menu popover (symbol_context rendered inline)
- A5: multi-hop type trace for chained attribute calls
- W4-W5: Trail rendering and export (UI polish)
- Q4: MCTS tree search (deferred, see RM9)
- T5: Topology drift (deferred until post-production)

### Open TRACKER items
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)

### Commonplace status
- Working skeleton exists: capture, browse, search, storage, utils all functional
- 5 deliberate stubs: extract_full_content, semantic_search, find_connections,
  _similarity_score, suggest_tags
- 4 deliberate design tensions in code comments (all promoted to DESIGN.md)
- DESIGN.md written and ingested -- 10 rules live in Commonplace DB
- Missing: ABC shape, chain-middle stub, conditional stub, seed state definition,
  guided UI highlighting

## Hardware facts
- llama-server-8b: NSSM auto service, port 8081 (8B on GPU, ~3s/call)

## Corpus state
- dj2 DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_dj2.db (47 stubs, 35 ABC gaps)
- Commonplace DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db (5 stubs, 10 design rules)
- Determined DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined.db

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, use python
Use PowerShell tool (not Bash). NEVER use python -c with inner quotes - write .py scripts.
