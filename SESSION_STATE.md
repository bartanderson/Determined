Written at commit: 2f2c5ce
# SESSION STATE - session 155 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 155, 2026-07-12)

**RM52 designed and filed [V]:** Multi-method ingestion pre-pass. Design discussion
produced a grounded architecture for richer design doc extraction:
- Four deterministic structure-induction methods (FCA/Wille 1982, MDL/Rissanen 1978,
  LP² Wrapper Induction/Kushmerick 1997, L*/Angluin 1987) run serially over each doc
- Existing `_MUST_RE` extractor runs first; its output seeds Wrapper Induction and L*
  (no cold-start problem)
- Set operations (∩ △ ∪) + Dempster-Shafer gate tier output into:
  convergent (high trust) / discriminant (medium trust + tag) / review queue
- Grounded in Campbell & Fiske 1959 (MTMM) and Kuncheva & Whitaker 2003
- Pre-pass prerequisite for RM48; filed before it in TRACKER.md

**RM48 Step 0 partially run [V]:** `ingest_design_docs` run against dj2 corpus --
135 new design_notes stored, 00A + 00F now represented. 00E (AI_LAYER_OPPORTUNITIES)
scored 0.04 (below default 0.05 threshold) and was NOT ingested. Interrupted before
lowering threshold. Current count: ~1215 design_notes in C_Users_bartl_dev_dj2.db.

**Schema finding [V]:** design_note content is stored as plain text -- no
`[REQUIREMENT|...]` prefix in current DB rows. The `[KIND|confidence|source]` prefix
format exists in code (agent_tools.py:2801) but the 1080 pre-existing rows predate it.
Requirements must be found via `_MUST_RE` over content at query time, not a kind= column
query. ~74 rows contain must/shall language.

## Gap taxonomy (cumulative) [V]

| Gap | Pattern | Status |
|-----|---------|--------|
| 1-4,7,8 | Various call graph gaps | FIXED |
| TR | Target resolution collision | DONE (RM40) |
| ICX | Inline comment extraction | DONE (RM50) |
| ANN | annotate_function tool | DONE (RM49) |
| APD | Annotation pass driver | DONE (RM51) |
| ORD | Implementation ordering | DONE (RM44) |
| CTR | Completion contract | DONE (RM45) |
| SFP | Scaffold from pattern | DONE (RM46) |
| RDY | Readiness gate | DONE (RM47) |
| MMP | Multi-method ingestion pre-pass | OPEN (RM52) |
| DGP | Design-to-code delta | OPEN (RM48) |
| DF | Data flow edges | OPEN (RM39) |
| HTTP | fetch/HTMX -> Flask route | OPEN (RM41) |
| INV | Investigation context panel | OPEN (RM42) |
| LNS | Canned reasoning lenses | OPEN (RM43) |

## Known issues (carried forward)

**RM21 probes not re-run [?]:** Live LLM probe not re-run.

**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**RM40 opt-in trap [V]:** resolved_only defaults False. readiness_check T2 uses
_list_callees_raw which does NOT filter to resolved_only -- may surface unresolved
edges as stub callees. Acceptable for the gate use case but worth noting.

**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.

**scaffold_from_pattern embedding path [V]:** Silently skipped if embedding unavailable.
Module-family siblings still returned. Tests don't cover embedding path.

**readiness_check T4 off by default [V]:** include_design_check=true required to enable
design constraint tier. Embedding-based, can be slow.

**00E not ingested [V]:** docs/design/00E AI_LAYER_OPPORTUNITIES.md scored 0.04,
below default min_score=0.05. Needs min_score=0.01 to pick it up, or RM52 pre-pass
will handle it more robustly anyway.

**design_note content format [V]:** Pre-existing rows have no [KIND|...] prefix.
Requirements found via _MUST_RE over content at query time. ~74 such rows in dj2 DB.

## NEXT SESSION -- start here

**Recommended order:**

1. **RM52 (2 days) -- multi-method ingestion pre-pass:**
   New module `determined/ingestion/structure_induction.py`. Four methods:
   `fca_pass`, `mdl_pass`, `wrapper_pass`, `grammar_pass` + `combine(results)`.
   Modify `ingest_design_docs` in agent_tools.py to call it after existing extraction.
   See TRACKER.md RM52 for full spec and pipeline topology ASCII.
   **Start here, before RM48** -- RM52 output enriches RM48's input.

2. **RM48 (1 day) -- design-to-code delta:**
   After RM52 ships. Step 0 (ingest) is partially done (135 notes added this session).
   Still need: 00E at min_score=0.01, then implement design_gaps() tool.
   See TRACKER.md RM48 for full spec.

3. **RM39 / RM41 / RM42 / RM43** -- defer unless Bart explicitly wants them.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
