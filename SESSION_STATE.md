Written at commit: d32aaf9
# SESSION STATE - session 153 handoff (updated: RM46 + RM47 both done)
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 153, 2026-07-12)

### Commits this session [V]

- `4aa4412` RM46: scaffold_from_pattern
- `ae1a8c4` TRACKER: mark RM46 DONE
- `d32aaf9` RM47: readiness_check

### Changes made [V]

**RM46 done [V]**
- `determined/agent/stub_projector.py`: `_extract_structural_skeleton(source, fn_name) -> dict`
  AST analysis: first_stmt_type, return_shape, error_handling, has_guard.
- `determined/agent/agent_tools.py`: `scaffold_from_pattern(assessor, args)` after project_stub.
  Module-family siblings (same file/dir, matching return_type) + embedding similarity at 0.50
  (gracefully skipped if unavailable). Canonical/variation-point synthesis. Fill-in-the-blanks template.
- `determined/agent/tool_registry.py`: entry, category='frontier'.
- `tests/regression/test_scaffold_from_pattern.py`: 16 tests (6 AST, 10 integration).

**RM47 done [V]**
- `determined/agent/agent_tools.py`: `readiness_check(assessor, args)` after completion_contract.
  5 tiers, all DB queries, no LLM:
    T1: symbol exists and is incomplete (stub or ABC gap)
    T2: stub callees (must be built first)
    T3: unknown type annotations (type not in functions or classes table)
    T4: design constraint flags >= 0.4 (opt-in: include_design_check=true, off by default)
    T5: cycle in stub dependency graph (BFS over stubs only)
  READY output: resolved types, available callees, next-step hint.
  BLOCKED output: numbered issues, implementation_order tip if stub callees found.
- `determined/agent/tool_registry.py`: entry, category='frontier'.
- `tests/regression/test_readiness_check.py`: 14 tests.
- `tests/regression/test_agent_tools.py`: both tools added to TOOLS set.

**Tests [V]:** 643 passed, 1 skipped (full suite run this session).

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
| DF | Data flow edges | OPEN (RM39) |
| HTTP | fetch/HTMX -> Flask route | OPEN (RM41) |
| INV | Investigation context panel | OPEN (RM42) |
| LNS | Canned reasoning lenses | OPEN (RM43) |
| DGP | Design-to-code delta | OPEN (RM48) |

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

## NEXT SESSION -- start here

**Recommended order:**

1. **RM48 (1 day) -- design-to-code delta:**
   `design_gaps(scope?)` -- which architectural requirements have no detectable
   implementation? Reads `kind='design_note'` artifacts, matches against corpus
   via embedding similarity (Level A), file path (Level B), import graph (Level C).
   **Step 0 first (no code):** ingest dj2 design docs via `ingest_design_docs`, then
   run `SELECT content FROM knowledge_artifacts WHERE kind='design_note' LIMIT 5`
   to confirm how 'requirement' kind is stored. See TRACKER.md RM48 spec for details.

2. **Manual integration test:** With dj2 corpus loaded, run the full frontier workflow:
   implementation_order -> readiness_check -> completion_contract -> scaffold_from_pattern
   on a real stub to validate the end-to-end arc.

3. **RM39 / RM41 / RM42 / RM43** -- defer unless Bart explicitly wants them.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
