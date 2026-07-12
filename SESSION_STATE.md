Written at commit: 70bd9b4
# SESSION STATE - session 156 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 156, 2026-07-12)

**RM52 done [V]:** Multi-method ingestion pre-pass implemented.
- New module `determined/ingestion/structure_induction.py`
- Four methods: `fca_pass` (FCA/Wille), `mdl_pass` (MDL/Rissanen),
  `wrapper_pass` (LP2/Kushmerick), `grammar_pass` (L*/Angluin)
- `combine()` applies set ops and Dempster-Shafer gate -> tiers:
  convergent (existing extractor + 2+ methods) / discriminant (2+ methods,
  extractor missed, stored with found_by/missed_by tag) / review (1 method,
  held)
- `run(text, seeds)` is the top-level entry; seeds come from existing
  extractor's constraint sentence output
- Wired into `ingest_design_docs` in `agent_tools.py` after existing
  extraction; result logged in output as "Structure induction (RM52): N
  additional candidates"
- 28 new regression tests, all passing
- **672 passed, 1 skipped [V]** (full suite, pytest tests/regression/ -m "not slow")

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
| MMP | Multi-method ingestion pre-pass | DONE (RM52) |
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
below default min_score=0.05. Needs min_score=0.01 to pick it up.

**design_note content format [V]:** Pre-existing rows have no [KIND|...] prefix.
Requirements found via _MUST_RE over content at query time. ~74 such rows in dj2 DB.

**RM52 discriminant seeds extraction [?]:** The seeds fed to structure_induction.run()
are extracted by splitting rule.rule on " | " and stripping the heading prefix. This is
a heuristic that matches _compress_constraints output but is not robust to all edge cases.
Worth monitoring when running against real docs.

## NEXT SESSION -- start here

**Recommended order:**

1. **RM48 (1 day) -- design-to-code delta:**
   RM52 is done -- RM48's prerequisite is satisfied.
   Step 0 (ingest) partially done from session 155 (135 notes added, 00E still missing).
   First: run `ingest_design_docs(min_score=0.01)` against dj2 to pick up 00E.
   Then: implement `design_gaps()` tool in agent_tools.py.
   See TRACKER.md RM48 for full spec (Level A/B/C matching, output shape).

2. **RM39 / RM41 / RM42 / RM43** -- defer unless Bart explicitly wants them.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
