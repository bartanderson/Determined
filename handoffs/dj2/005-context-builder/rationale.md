# Rationale - bundle 005, Context Builder encounter and combat stubs

Derived from the OpenSpec change dj2-state-machine-handoff, spec
dj2-fsm-completion ("Context-builder encounter and combat stubs are filled
only to the contract") and dj2-initial-event-set ("Initial events flow
through the Event Log only").

## What was actually missing

The two methods in world/context_builder.py were literal stubs:

    def _get_encounter_context(self, session_id: str) -> dict:
        # This will be implemented when encounter system is built.
        return {}

    def _get_combat_context(self, session_id: str) -> dict:
        return {}

They are called from ContextBuilder.build() at lines 70-71. Returning {}
means the UnifiedContext always had empty encounter_context and
combat_context sections, regardless of what the FSM had emitted.

## Design constraint (docs/design/04 context builder v1.3.md)

Per that design doc and the OpenSpec spec:
  - no mutation of state
  - no re-resolution of entities
  - no database access

These are pure read-side consumers of the EventLog. The design doc's
section 5 pipeline description puts "FSM injection" after escalation
overlay and after knowledge gap construction; the encounter/combat
context is derived from the log, not from the FSM object or from the
world DB.

The two methods therefore do nothing but scan EventLog and derive a
snapshot from the emitted initial-set event types (added by bundle 001,
emitted by bundles 002 and 004):

  _get_encounter_context: reads encounter.started / encounter.updated /
                          encounter.ended for this session. Returns a
                          snapshot when the most recent started has no
                          matching ended, else {}.
  _get_combat_context:    reads combat.initiation.triggered and
                          encounter.ended. Returns a snapshot when an
                          initiation has not been closed by an
                          encounter.ended, else {}.

Both ignore events tagged with a different session_id.

## Changes

  1. world/context_builder.py - implement _get_encounter_context and
     _get_combat_context as EventLog readers (see above). No imports
     added; no database access; no mutation; no new dependencies.

  2. tests/unit/test_context_builder_encounter.py - new; 8 tests covering:
       - empty when no events
       - snapshot after encounter.started
       - empty after encounter.ended
       - ignores events for other sessions
       - reflects encounter.updated
       - empty combat when no initiation
       - combat snapshot after initiation
       - combat empty after encounter.ended
     The test module stubs sys.modules['world.db'] with a MagicMock before
     importing context_builder, because context_builder imports world.db
     (which needs psycopg2 + Postgres in production). The tests never
     exercise that path.

## Not included

  - No change to get_spell_from_db. It is a module-level helper that does
    require Postgres; it is not exercised headless and the proposal's
    non-goals explicitly leave it out of scope.
  - No change to ContextBuilder.build() or its other helper methods.
  - No change to world.event_log, world.db, or world.escalation_engine.

## Verification

Applied to the cumulative clone (bundles 001-004 already committed) at
HEAD c076fc6 via git apply direct - the files touched by this bundle were
not touched by earlier bundles, so no context mismatch occurred.

Full prefix check after bundle 005: applying bundles 001, 002, 003, 004,
005 in order to a fresh clone at base_sha leaves all four test files
passing together - 32 tests (8 encounter + 8 barter + 8 trade + 8
context-builder), 0 failures. This is the D8 property: every prefix of
the ordered bundle list leaves dj2 in a working state.