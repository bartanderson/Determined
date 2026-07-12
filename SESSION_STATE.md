Written at commit: 7f7039b
# SESSION STATE - session 148 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 148, 2026-07-12)

### Commits this session [V]

- `a5aaa0c` RM40: add resolved_only filter to bfs_callees and subgraph_around
- `7f7039b` Improve doc_extractor to extract all sections, not just constraint-language lines

### Changes made [V]

**pyan3 + pyright baselines established [V]**
- pyan3 installed via pip. Run against 129 core dj2 files (dungeon_neo, engine, routes, core, world, resolver).
- pyan3: 1,701 solid (call) edges, 1,458 dashed (use) edges.
- Determined: 8,099 total edges, 1,087 resolved (13%), 7,112 unresolved (87%).
- pyright installed via pip. Run against dungeon_neo+engine+routes (18 files): 213 errors, 2 warnings.
- pyright has no "dump inferred types" mode -- useful for error baseline and spot-checking only.
- All baseline numbers recorded in docs/TRACKER.md under "Baseline measurements (session 148)". [V]

**RM40 done [V]**
- `bfs_callees` and `subgraph_around` in graph_utils.py: added `resolved_only=False` param.
- When True: filters `WHERE resolved=1` on all edge queries.
- `_graph_subgraph_raw` in agent_tools.py: exposes `resolved_only` passthrough.
- Two new regression tests: `test_bfs_callees_resolved_only_excludes_unresolved`,
  `test_subgraph_around_resolved_only`. Both pass. [V]
- 547 tests pass, 1 skipped. [V]

**doc_extractor.py overhauled [V]**
- Old behavior: silently dropped any section without "must/shall/never" vocabulary.
- New behavior: every headed section extracted. Constraint language -> confidence elevated.
  No constraint language -> body stored as kind=intent at downgraded confidence.
- Subject slugification fixed: strips articles/prepositions, handles plain English headings.
  "A. The Core Experience Goal" -> `core_experience_goal` (was `'The'`).
- `_downgrade_confidence` moved before `extract_rules` (was defined after, causing NameError).
- kind stays `'design_note'` everywhere for backward compat; rule subtype rides in provenance.
- 547 tests pass. [V]

**dj2 design docs ingested [V]**
- Ran extraction against all 52 docs in C:\Users\bartl\dev\dj2\docs (all generations, all dirs).
- 1,080 design_note entries written to C_Users_bartl_dev_dj2.db.
- Top sources: taxonomy runtime part2 (310), taxonomy plan part1 (270), design/00A-00F all present.
- Retrieval validated: query "process adjudication engine handles player action mutates world state"
  returns scores 0.54/0.53/0.52/0.51 hitting exactly the right design notes. [V]

### Tests [V]
547 passed, 1 skipped (confirmed from last full run this session).

## Gap taxonomy (cumulative) [V]

| Gap | Pattern | Status |
|-----|---------|--------|
| 1-4,7,8 | Various call graph gaps | FIXED |
| JS | DOM->socket.emit | REVISED: no emit in dj2 |
| DF | Data flow edges | OPEN (RM39) |
| TR | Target resolution collision | DONE (RM40) |
| HTTP | fetch/HTMX -> Flask route | OPEN (RM41) |
| INV | Investigation context panel | OPEN (RM42) |
| LNS | Canned reasoning lenses | OPEN (RM43) |
| ORD | Implementation ordering | OPEN (RM44) |
| CTR | Completion contract | OPEN (RM45) |
| SCF | Scaffold from pattern | OPEN (RM46) |
| RDY | Readiness gate | OPEN (RM47) |
| DGP | Design-to-code delta | OPEN (RM48) |
| ANN | Annotation sparsity | OPEN (RM49) |
| ICX | Inline comment extraction | OPEN (RM50) |
| APD | Annotation pass driver | OPEN (RM51) |

## Known issues (carried forward)

**RM21 probes not re-run [?]:** Live LLM probe not re-run.

**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA are
separate stores -- both must be updated together.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**RM40 opt-in trap [V]:** resolved_only defaults False. RM44 and RM47 must explicitly
pass resolved_only=True or they silently use the polluted graph. Wire it explicitly.

**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board. RM42 must
ship and user must have pinned cards before lenses are useful.

**pyan3 post-RM40 delta not yet measured [V]:** Re-run pyan3 comparison after RM49 lands
and dj2 is re-ingested. resolved edge count won't change from RM40 alone -- resolution
happens at ingest, not query time.

**doc_extractor prev-details not skipped [V]:** prev-details dir IS discovered and ingested.
Intentional -- take all data, organize it. Historical docs contribute lower-confidence entries.

## NEXT SESSION -- start here

**Recommended order:**

1. **RM50 (0.5 days) -- next code item:**
   Inline comment extraction in parse_ast.py `_extract_functions`.
   Scan raw source lines [lineno:end_lineno] for `#` comments.
   Store as kind='inline_note' in knowledge_artifacts.
   Entry point: `determined/ingestion/parse_ast.py` -- find `_extract_functions`.
   Run full 547-test suite before commit (parse_ast.py is high blast-radius).
   Feeds RM49's context assembly.

2. **RM49 (1.5 days):** annotate_function tool in agent_tools.py.
   Context: source + callers + callees + inline notes + design notes -> LLM infers
   param types, return type, behavioral contract. Stores as kind='inferred_annotation'.
   Manual integration test: annotate process() in adjudication_engine.py.
   Extends RM45 + RM47 to read inferred store when param_types_json is empty.

3. **RM51 (1 day):** run_annotation_pass driver. Priority queue by caller count desc.

4. **RM44 (0.5 days):** implementation_order topo sort. Needs RM40 (done) for accuracy.
   Remember: pass resolved_only=True explicitly (RM40 opt-in trap).

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
Started by UI automatically; for CLI use start manually.
