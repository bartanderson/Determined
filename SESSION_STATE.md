Written at commit: 62a1b11
# SESSION STATE - session 150 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 150, 2026-07-12)

### Commits this session [V]

- `62a1b11` RM49: annotate_function -- infer param types, return type, and behavioral contract

### Changes made [V]

**RM49 done [V]**
- `determined/agent/agent_tools.py`: added `annotate_function(assessor, args)` after
  `docstring_health`. Assembles: source code via `_get_source_lines`, callers via
  `_list_callers_raw`, callees with return types, inline_notes (kind='inline_note'),
  design_notes (kind in design_note/layer_rule). Calls `generate_quality()` from
  llm_client (local import inside function). Stores result as kind='inferred_annotation',
  provenance='llm-inferred', needs_review=1. Stale annotation for same subject deleted
  before insert. write_back=False by default -- never touches source files.
  `inference_basis` auto-filled from structural evidence if LLM omits it.
- `determined/agent/tool_registry.py`: added annotate_function entry, category='knowledge'.
- `tests/regression/test_agent_tools.py`: added 'annotate_function' to hardcoded TOOLS set.
- `tests/regression/test_annotate_function.py`: 15 new tests (14 fast, 1 slow).
- `docs/TRACKER.md`: RM49 marked DONE.

**Tests [V]:** 581 passed, 1 skipped (full suite run at commit).

**Key pattern [V]:** LLM import is local inside annotate_function (not module-level).
Monkeypatch target for tests: `determined.agent.llm_client.generate_quality`.
NOT `agent_tools._llm_generate` -- that doesn't exist at module scope.
Carry this forward for any test that exercises annotate_function indirectly (RM51).

## Gap taxonomy (cumulative) [V]

| Gap | Pattern | Status |
|-----|---------|--------|
| 1-4,7,8 | Various call graph gaps | FIXED |
| TR | Target resolution collision | DONE (RM40) |
| ICX | Inline comment extraction | DONE (RM50) |
| ANN | annotate_function tool | DONE (RM49) |
| DF | Data flow edges | OPEN (RM39) |
| HTTP | fetch/HTMX -> Flask route | OPEN (RM41) |
| INV | Investigation context panel | OPEN (RM42) |
| LNS | Canned reasoning lenses | OPEN (RM43) |
| ORD | Implementation ordering | OPEN (RM44) |
| CTR | Completion contract | OPEN (RM45) |
| SCF | Scaffold from pattern | OPEN (RM46) |
| RDY | Readiness gate | OPEN (RM47) |
| DGP | Design-to-code delta | OPEN (RM48) |
| APD | Annotation pass driver | OPEN (RM51) |

## Known issues (carried forward)

**RM21 probes not re-run [?]:** Live LLM probe not re-run.

**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA are
separate stores -- both must be updated together.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**RM40 opt-in trap [V]:** resolved_only defaults False. RM44 and RM47 must explicitly
pass resolved_only=True or they silently use the polluted graph.

**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.

**pyan3 post-RM40 delta not yet measured [?]:** Re-run after RM49 lands.

**inline_note content prefix is normalized path [V]:** Tests use suffix match.

## NEXT SESSION -- start here

**Recommended order:**

1. **RM51 (1 day) -- next code item:**
   `run_annotation_pass(assessor, args)` driver. Priority queue: functions ordered
   by caller count desc, filtered is_stub=0, param_types_json IS NULL or empty.
   Pops top item, calls `annotate_function` for each, stops when marginal gain drops
   below threshold or scope exhausted.
   Entry point: `determined/agent/agent_tools.py` -- add after `annotate_function`.
   Wire into TOOLS dict (hardcoded set in test_agent_tools.py needs update too).
   LLM monkeypatch pattern: `determined.agent.llm_client.generate_quality`.

2. **RM44 (0.5 days):** implementation_order topo sort. Needs RM40 (done).
   Remember: pass resolved_only=True explicitly (RM40 opt-in trap).

3. **Manual integration test (RM49 validation):** Run `annotate_function` on `process`
   in adjudication_engine.py with llama-server on port 8081. Expected: inferred params
   match PlayerAction/DungeonStateNeo, return=dict, confidence >= 0.6.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
