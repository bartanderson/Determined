# SESSION STATE - session 71 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 71, 2026-07-04)

### Design documentation and housekeeping

- T5 (topology drift) disposition updated: deferred until Determined is actively
  driving design decisions and the codebase moves in response. No drift without
  Determined-guided changes. Revisit post-production.

- A1 (resolved flag migration) disposition updated: no migration needed. Corpus
  DBs are expendable and rebuilt from scratch. Schema changes go into CREATE TABLE.
  Memory and DISCOVERY_MODEL.md updated.

- **COMMONPLACE_VISION.md written** (`docs/COMMONPLACE_VISION.md`): authoritative
  design intent for the Commonplace sample program. Captures:
  - Dual role: canonical demo corpus + guided journey vehicle
  - Seed-to-complete arc (user builds Commonplace using Determined's tools)
  - Guided UI model: highlighted controls with pedagogical hover tooltips
  - Current status: what is implemented, what stubs exist, what design tensions
    are already in code comments
  - Gaps: no markdown design doc, no ABC/chain-middle/conditional-stub examples,
    seed state not defined, guided UI not built
  - Next steps in order

## NEXT SESSION -- start here

**Task: Write the Commonplace design doc**

File to create: `examples/commonplace/docs/DESIGN.md`

This is the highest-leverage next step because it immediately unlocks two
Determined features on the demo corpus:
- `ingest_design_docs` -- mines the doc for invariants and authority rules
- `check_design_violations` -- cross-references code against those rules

Read `docs/COMMONPLACE_VISION.md` section "Next steps -- 1. Design doc for
Commonplace itself" for the spec. Key content to include:

1. **Architecture** -- the intended layer structure:
   - routes/ -- HTTP boundary only, no business logic
   - services/ -- all business logic lives here
   - storage/ -- only layer that touches the DB
   - utils/ -- pure functions, no state

2. **Authority rules** (things Determined's violation detection can flag):
   - "Only storage/ touches the DB directly"
   - "Routes delegate to services, never to storage directly"
   - "Tags are always lowercase"
   - "Connections are bidirectional -- both directions must be stored"

3. **Open design questions** (promote from code comments to doc):
   - extractor: fetch + parse + metadata -- one module or three?
   - tagger: eager-on-capture vs lazy-on-view
   - searcher: bypasses service layer to call storage directly
   - capture route: URL validation in two places

4. **Stub roadmap** -- what each stub is waiting for and why it matters:
   - `extract_full_content` -- readability/trafilatura
   - `semantic_search` -- sentence-transformers or llama-server embeddings
   - `find_connections` / `_similarity_score` -- embedding cosine similarity
   - `suggest_tags` -- LLM endpoint (llama-server port 8081)

After writing the doc, ingest it against the Commonplace corpus DB and run
`check_design_violations` on `searcher.py` and `routes/capture.py` to verify
the violations Determined can now detect.

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
- 4 deliberate design tensions annotated in code comments
- Missing: markdown design doc, ABC shape, chain-middle stub, conditional stub,
  seed state definition, guided UI highlighting

## Hardware facts
- llama-server-8b: NSSM auto service, port 8081 (8B on GPU, ~3s/call)

## Corpus state
- dj2 DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_dj2.db (47 stubs, 35 ABC gaps)
- Commonplace DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db (5 stubs)
- Determined DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined.db

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, use python
Use PowerShell tool (not Bash). NEVER use python -c with inner quotes - write .py scripts.
