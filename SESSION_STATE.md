Written at commit: 699530c
# SESSION STATE - session 157 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 157, 2026-07-12)

**RM52 done [V] (session 156, carried forward):** determined/ingestion/structure_induction.py.
Four methods + combine() D-S gate -> convergent/discriminant/review tiers. Wired into
ingest_design_docs. 28 tests. 672 passed.

**RM48 done [V]:** design_gaps() tool in agent_tools.py (~line 855).
- `_extract_design_requirements(conn)` -- pulls design_note artifacts with must/shall/
  required language (handles both [REQUIREMENT|...] prefix and old plain-text rows)
- `_match_level_a(oracle, req_text, threshold=0.45)` -- embedding similarity vs all
  functions + classes
- `_match_level_b(oracle, subject, req_text)` -- file path keyword match
- `_match_level_c(oracle, subject, req_text)` -- import graph edge keyword match
- `design_gaps(assessor, args)` -- orchestrates levels, outputs GAP/PARTIAL/SATISFIED
- Wired into TOOLS dict and tool_registry.py (category: knowledge)
- `import re` added to agent_tools.py top-level imports (was missing)
- 19 new regression tests + updated test_dispatch_all_tools_registered to include design_gaps
- **691 passed, 1 skipped [V]** (full suite, pytest tests/regression/ -m "not slow")

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
| DGP | Design-to-code delta | DONE (RM48) |
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

**readiness_check T4 off by default [V]:** include_design_check=true required for design tier.

**00E not ingested [V]:** docs/design/00E AI_LAYER_OPPORTUNITIES.md in dj2 scored 0.04,
below default min_score=0.05. Needs min_score=0.01 to pick it up.

**design_note content format [V]:** Pre-existing rows have no [KIND|...] prefix.
Requirements found via _MUST_RE over content at query time.

**design_gaps Level A embedding [?]:** Level A embedding match is embedding-intensive --
with a large corpus it will be slow (one embed call per function). No caching in current
implementation. Fine for now; revisit if dj2 with 1300+ functions is too slow.

## NEXT SESSION -- start here

All planned RM items (RM39-RM52) are now either DONE or explicitly deferred.
The remaining open items (RM39 data flow edges, RM41 HTTP, RM42 Investigation,
RM43 Lenses) are deferred unless Bart explicitly wants them.

**Recommended action:**
1. Ask Bart what he wants next. Options:
   a. Use the tool against dj2 (run ingest_design_docs at min_score=0.01 to pick up 00E,
      then run design_gaps to find real architectural gaps)
   b. Pick up RM39/RM41/RM42/RM43 (data flow, HTTP routes, investigation panel, lenses)
   c. New items Bart has in mind

2. If testing design_gaps against dj2 corpus:
   - Run `ingest_design_docs(min_score=0.01)` to pick up 00E (scored 0.04)
   - Run `design_gaps()` to see what gaps the tool surfaces
   - Corpus DB: C_Users_bartl_dev_dj2.db (session 155 showed ~1215 design_notes)

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
