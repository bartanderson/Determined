## Why

dj2 is a D&D-style AI dungeon-master game whose runtime is a deterministic event stack
(Event Log -> Escalation Engine -> ContextBuilder -> gameplay systems). Its own
`docs/design/00C IMPLEMENTATION_SEQUENCE.md` says nothing else matters until the Event Log
and the state machines built on it work together. Today they do not.

Determined, run against dj2 (corpus `C_Users_bartl_dev_dj2.db`, ingested 2026-08-27, stale),
reports exactly one implementation wave of 25 incomplete symbols. 12 of them are the
unimplemented guards and actions of the three FSM configs in `config/fsms/`:

- `barter.json`: `add_gold`, `execute_barter`, `need_more_gold`
- `encounter.json`: `resolve_flee`, `resolve_parley`, `start_combat`, `flee_possible`, `parley_possible`
- `trade.json`: `execute_buy`, `update_price`, `price_acceptable`, `price_too_low`

plus two blocked `world/context_builder.py` stubs (`_get_encounter_context`, `_get_combat_context`).
`docs/analyses/dj2_encounter_analysis_1.md` already found the encounter chain is a complete
island: every layer exists, none are connected, `start_combat` has no target.

The state machines are the first unfinished layer, and the events they emit and consume are
the seam the rest of the game (escalation, context, dialogue, quests, combat) plugs into.
dj2's event taxonomy (`docs/design1a_event_taxonomy.md`) names the event types but nothing
checks which are really emitted, consumed or declared.

The work has to be driven from Determined (analysis, specs, tests, patches) and applied to dj2
under strict control, because dj2 is a separate repo with its own in-flight local edits and
Determined's cloud session must never write to it.

## What Changes

- Establish a one-way, pinned, verifiable propagation path from Determined's analysis of dj2
  into dj2 changes: **handoff bundles** that live in Determined (`handoffs/dj2/`), are verified
  against a throwaway clone of dj2 at a recorded commit, and are applied to dj2 only by the user.
- Complete the wave-1 FSM stubs for Encounter, Barter and Trade as a series of bundles, one
  per machine, each implemented to the committed FSM JSON (JSON is the contract; code follows it).
- Define and check the **initial event set**: the subset of the dj2 event taxonomy that the
  three FSMs emit or consume, with required data fields, plus a Determined-side report that
  diffs taxonomy vs emitted vs consumed event types.
- Add the Determined-side checks that make the above mechanical rather than narrated:
  an FSM-consistency check (every `cond`/`actions` name is defined) and the event coverage report.

## Capabilities

### New Capabilities

- `dj2-handoff-sync`: the pinned, one-way propagation protocol and bundle format between Determined and dj2.
- `dj2-fsm-completion`: what "a completed FSM" means for the wave-1 machines and the consistency check that proves it.
- `dj2-initial-event-set`: the initial event types, their required fields, and the coverage report.

### Modified Capabilities

None. Determined has no OpenSpec specs yet; this change initialises `openspec/`.

## Impact

- **Determined repo (writes):** `openspec/`, `.claude/commands|skills/` (from `openspec init`),
  new `handoffs/dj2/`, new analysis tools registered in the TOOLS dict, tests under
  `tests/regression/`, `tools/run_tests.py` FILE_MAP and `docs/TEST_MAP.md` kept in sync.
- **dj2 repo (writes):** none by the agent. The user applies bundles.
- **Cloud constraints:** no Qwen3 / llama-server, no Chrome 9222 DeepSeek bridge,
  no Postgres+pgvector. dj2's `world/db.py` needs Postgres, so only dj2 tests that run without
  it are usable as verification; the set is discovered, not assumed (task 1.3).
- **Known dj2 working-tree state at proposal time (user's, untouched):** uncommitted edits to
  `config/fsms/encounter.json` (adds `cond: fight_possible` with no matching guard defined),
  `world/context_builder.py` (adds a Postgres `get_spell_from_db` helper), `TRACKER.md`,
  `create_tables.py`, `SESSION_STATE.md`; plus untracked files. These are not in any baseline.

## Non-goals

- No combat system. `start_combat` stays a stub that emits `combat.initiation.triggered`
  (matches `00C`: combat is last) and the encounter analysis's lowest-risk path.
- No G0 World Description Language, verb registry (G10), semantic sensors (G11), narrative
  service (G3), voice, UI, multiplayer or MCTS work.
- No direct edits, commits or pushes to the dj2 repo or its working copy by the agent.
- No redesign of dj2 architecture: this follows `00A`/`00B`/`00C` ("implementation stabilization,
  not architecture invention").
- No work on Determined's own backlog (RM67, UI redesign) except what the checks above require.
- No wave-1 stubs outside the three FSMs and the two context-builder stubs
  (`dnd_data.py`, `narrative_engine.py`, `ai_dungeon_master.py` stubs are out of scope).
