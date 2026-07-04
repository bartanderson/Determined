# SESSION STATE - session 72 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 72, 2026-07-04)

### Commonplace DESIGN.md written and verified

- **`examples/commonplace/docs/DESIGN.md`** created:
  - Four-layer architecture spec (routes / services / storage / utils)
  - Six authority rules in Determined-detectable language
  - Four open design questions promoted from code comments
  - Stub roadmap with LLM dependencies for all five stubs
- Ingested: `ingest_design_docs` extracted 10 rules
- Verified: `check_design_violations` correctly flags both known violations
  (searcher service-layer bypass 0.50, capture URL duplication 0.30)

### New TRACKER items filed

- **RM10** (FUTURE): DeRe-CoT recomposition pass in `goal_intake` -- after
  decomposing a goal into sub-queries, recompose and check semantic alignment
  with the original to verify coherence before committing. Paper: Lee & Lee,
  Engineering Applications of AI, Vol 181 Part 3, Oct 2026.
- **RM11** (MEDIUM): `edit_file` agent tool -- closes the read→reason→write
  loop. Write logic already exists in ui_server socket handlers; this is
  wiring it as an agent tool (read_file, write_file, replace_in_file).
- **RM12** (MEDIUM): SearXNG web search -- self-hosted, no API key, local-first.
  `search_web(assessor, args)` agent tool hitting configurable endpoint.
  Use cases: stub scorer ("what library implements X?"), goal_intake enrichment.

### Confirmed already present (no item needed)

- Complex task decomposition and resynthesis: `score_stub` chains
  gather_context → build_claim → evaluate_claim; `reason_about` does
  structural assembly + LLM synthesis; `goal_intake` does semantic
  decomposition. The deterministic skeleton is there.

## NEXT SESSION -- start here

**Commonplace step 2: add missing topology shapes**

Add to `examples/commonplace/`:
- An ABC with at least one abstract method and no override
  (exercises `find_abc_gaps`)
- A chain-middle stub (called by another stub, calls another stub --
  exercises chain topology)
- A conditional stub (`raise NotImplementedError` inside an if branch --
  exercises `find_conditional_stubs`)

These give Commonplace the topology variety to demo all Determined frontier
features against its own codebase.

Alternatively: pick up RM11 (edit_file agent tool) -- it's Low effort and
closes a meaningful capability gap.

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
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)
- RM11: edit_file agent tool -- closes read→reason→write loop (MEDIUM)
- RM12: SearXNG web search agent tool (MEDIUM)

### Commonplace status
- Working skeleton: capture, browse, search, storage, utils all functional
- 5 deliberate stubs: extract_full_content, semantic_search, find_connections,
  _similarity_score, suggest_tags
- DESIGN.md written and ingested -- 10 rules live in Commonplace DB
- Missing: ABC shape, chain-middle stub, conditional stub, seed state,
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
