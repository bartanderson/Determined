Written at commit: 57c380e
# SESSION STATE - session 147 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 147, 2026-07-11)

### Commits this session [V]

- `57c380e` File RM49-RM51: corpus enrichment arc to fix annotation sparsity

### Changes made [V]

**No code written this session.** Two pure design/planning passes.

**Pass 1 -- Devil's advocate on RM44-RM48 [V]**
Three failure modes that would cause the analysis-to-action arc to produce empty/wrong output:
1. `param_types_json` <1% populated in dj2 (11 annotated fns out of 1321) -- RM45 completion
   contract's core value (signature block) would be empty for almost every query.
2. Stubs have no docstrings -- RM46 scaffold's embedding match degrades to name-only signal,
   finds structurally unrelated functions.
3. Design notes absent in fresh corpus -- RM47 Tier 4 (design violation check) silently passes,
   giving READY when it simply didn't check.
Additional issues: RM40 improvement is opt-in (downstream tools won't use it unless explicitly
wired), RM48 schema is a blocking unknown, RM43 lenses operate on empty clue board by default,
implement_stub TASK_PATTERN will collide with existing project_stub routing.

**Pass 2 -- Corpus enrichment arc (RM49-RM51) filed [V]**
Three new items close the annotation sparsity gap:

- **RM50** (0.5 days): Inline comment extraction in parse_ast.py. Scan function body
  line range for `#` comments, store as kind='inline_note' in knowledge_artifacts. No LLM.
  Feeds RM49's context assembly. Full regression suite required before commit.

- **RM49** (1.5 days): annotate_function tool. Context assembly (source + callers + callees
  + inline notes + design notes) + LLM inference of param types, return type, behavioral
  contract. Stores as kind='inferred_annotation' with inference_basis evidence trail.
  RM45 and RM47 get a second read path, labeled (inferred). Integration test: run on
  process() (30 callers) and verify inferred types match actual PlayerAction/DungeonStateNeo.

- **RM51** (1 day): Annotation pass driver. Priority queue via workflow_items by caller count
  descending. Propagates upward after each annotation. Convergence stop when delta < N.

**Step 0 action added to RM48 [V]:** Run ingest_design_docs on dj2's 4 design docs before
implementing RM48. Zero code. Immediately populates requirement store and resolves the schema
unknown (SELECT to verify how 'kind' is stored in knowledge_artifacts).

**Strategic direction clarified [V]**
- Commonplace is now a regression corpus only -- too clean to stress new capabilities.
- dj2 is the primary validation target from here forward.
- Two reference tools identified for ground-truth measurement:
  - **pyan3** (pip install pyan3): independent call graph generator. Compare its edge set
    against Determined's graph_edges to get precision/recall for call graph completeness.
    Run against dj2 BEFORE RM40 to establish baseline, then after to measure delta.
  - **pyright** (pyright --outputjson): type inference ground truth. Compare against
    Determined's param_types_json and RM49's inferred_annotation store.
- Endgame metric: Determined can answer "what should I implement next in dj2, and what do
  I need to know before I start?" without the user already knowing the answer.

### Tests [V]
545 passed, 1 skipped -- no code changed, count unchanged.

## Gap taxonomy (cumulative) [V]

| Gap | Pattern | Status |
|-----|---------|--------|
| 1-4,7,8 | Various call graph gaps | FIXED |
| JS | DOM->socket.emit | REVISED: no emit in dj2 |
| DF | Data flow edges | OPEN (RM39) |
| TR | Target resolution collision | OPEN (RM40) |
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

**RM48 schema check needed [V]:** Step 0 resolves this -- run before implementing RM48.

**RM40 opt-in trap [V]:** resolved_only defaults False. RM44 and RM47 must explicitly
pass resolved_only=True or they silently use the polluted graph. Wire it explicitly.

**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board. RM42 must
ship and user must have pinned cards before lenses are useful.

## NEXT SESSION -- start here

**Recommended order:**

1. **Step 0 (0 days, do first):** Run ingest_design_docs on dj2's 4 design docs against
   C_Users_bartl_dev_dj2.db. Validate with SELECT COUNT(*) before/after. Run schema check:
   `SELECT content FROM knowledge_artifacts WHERE kind='design_note' LIMIT 5`
   Docs: docs/design/00A, 00B, 00E, 00F in dj2 repo.

2. **pyan3 baseline (0.5 days):** pip install pyan3, run against dj2, compare edge count
   against Determined's graph_edges. Establishes call graph precision/recall baseline BEFORE
   RM40 lands. Command: `pyan3 C:\Users\bartl\dev\dj2\**\*.py --dot > dj2_pyan3.dot`

3. **RM40 (0.5 days) -- HIGHEST PRIORITY code item:**
   Add resolved_only=False to bfs_callees/subgraph_around in graph_utils.py.
   Filter WHERE resolved=1 when True. Expose in agent_tools.py bfs_callees args.
   Regression test: BFS from handle_connect with resolved_only=True excludes bestiary.get().
   After: re-run pyan3 comparison to measure delta.

4. **RM50 (0.5 days):** Inline comment extraction in parse_ast.py _extract_functions.
   Scan raw source lines [lineno:end_lineno] for # comments. Store as kind='inline_note'.
   Run full 545-test suite before commit (parse_ast.py is high blast-radius).

5. **RM49 (1.5 days):** annotate_function in agent_tools.py after docstring_health.
   Extend RM45 + RM47 to read inferred store when param_types_json is empty.
   Manual integration test: annotate process() in adjudication_engine.py.

6. **RM51 (1 day):** run_annotation_pass driver in agent_tools.py after annotate_function.

7. **RM44 (0.5 days):** implementation_order topo sort. Needs RM40 first for accuracy.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
