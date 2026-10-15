# Rationale - bundle 002, Encounter FSM

Derived from the OpenSpec change dj2-state-machine-handoff, specs
dj2-fsm-completion and dj2-handoff-sync, and design D3 ("events are the only
coupling between machines and the rest of the game").

## Scope correction vs task 3.2's text

Task 3.2 said to "implement flee_possible, parley_possible, resolve_flee,
resolve_parley, start_combat to the committed JSON." Reading the base tree at
598ed55 showed the situation is different:

  - flee_possible and parley_possible already had real bodies in
    world/fsm/builtins.py, delegating to engine._check_flee / _check_parley.
  - start_combat had a body calling engine._start_combat, but that method is
    not defined on AdjudicationEngine, so the call was a silent no-op.
  - resolve_flee and resolve_parley returned context unchanged - genuine
    stubs.

Additionally, config/fsms/encounter.json referenced cond "fight_possible" on
the "fight" transition without defining that guard, which is the exact defect
spec dj2-fsm-completion was written to catch. The FSM could not enter
resolving_fight because no such guard was registered.

This bundle therefore does three things, not the five the task text imagined:

  1. Adds the missing fight_possible guard to encounter.json and its
     registration in AdjudicationEngine.start_encounter.
  2. Wires the four encounter actions to emit events through the EventLog
     instead of calling the engine directly, per design D3. Emitted types:
       begin_encounter -> encounter.started
       start_combat    -> combat.initiation.triggered (no combat rules)
       resolve_flee    -> encounter.updated, encounter.ended (outcome=fled)
       resolve_parley  -> encounter.updated, encounter.ended (outcome=parleyed)
     All four types are declared in config/events/initial_events.json, which
     was added by bundle 001.
  3. Adds tests/unit/test_encounter_fsm.py, walking every transition through
     the GenericFSM runner and checking both guard paths.

## Why this shape

The spec's D3 principle is "actions emit events; they do not call escalation,
context, dialogue or UI." The base tree violated that for start_combat (called
into the engine) and for the two resolve_* stubs (did nothing). Making them
emit is the minimum change that satisfies the principle without redesigning
the engine's public API.

start_combat emitting combat.initiation.triggered and nothing else is the
"combat is not implemented here" requirement from spec dj2-fsm-completion.
Combat resolution is a later phase (00C); bundle 002 does not touch it.

## Not included

  - No change to AdjudicationEngine's public interface beyond adding the two
    new registry entries (fight_possible, begin_encounter) in
    start_encounter.
  - No change to the two existing _check_flee / _check_parley engine methods.
  - No change to test_economy.py's encounter tests; they were already
    exercising the runner through the engine and remain the integration-level
    regression guard.

## Verification

Applied to a fresh clone at 598ed55 (see verify.md). Test file:
tests/unit/test_encounter_fsm.py, 8 tests, all pass.
