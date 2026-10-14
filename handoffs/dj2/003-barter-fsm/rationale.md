# Rationale - bundle 003, Barter FSM

Derived from the OpenSpec change dj2-state-machine-handoff, spec
dj2-fsm-completion, and design D3 ("events are the only coupling between
machines and the rest of the game").

## Task 3.3's economy question, answered

Task 3.3 asked: "read tests/integration/test_economy.py first, record in
rationale whether Barter and Trade share logic."

Answer: they share the runner (GenericFSM) and the two guards
need_more_gold and price_too_low (same shape: offer vs threshold). They do
NOT share action bodies: barter's execute_barter calls
engine._execute_barter with give+receive items; trade's execute_buy calls
engine._execute_purchase with a single item. Different engine methods,
different context keys, different transactions. Bundle 003 therefore
treats Barter as its own machine with its own actions. If the two converge
further in later work, a shared refactor would be a separate change.

Note on the referenced test: tests/integration/test_economy.py was read
during task 3.1. Its live barter tests (test_barter_shortsword_for_potion_start)
exercise the same context keys this bundle emits, and its two
test_barter_..._offer_and_confirm tests are already marked skip with reason
"Barter FSM needs update; will be replaced by event-driven system". No
test changes are needed here.

## What was actually missing in barter

All three functions named in task 3.3 (add_gold, execute_barter,
need_more_gold) had bodies in world/fsm/builtins.py at base_sha, but none
of them emitted events - the same pattern found in bundle 002 for the
encounter machine. In addition, the barter context did not include
session_id, so even if they had emitted, the required field would have
been absent.

A third issue surfaced during testing: GenericFSM.send_event called the
underlying state machine method with **event_data (keyword expansion), but
python-statemachine 3.x forwards only positional args to guard/action
callbacks. Every callback was receiving None for event_data; the guard
need_more_gold always evaluated 0 < shortage and every offer transitioned.
The bundle fixes it in world/fsm/generic_fsm.py.

## Changes

  1. world/adjudication_engine.py - add 'session_id': session_id to the
     barter context dict so emitted events carry the required field.
  2. world/fsm/builtins.py - add _emit_event helper. add_gold now emits
     state.resource.changed with resource='gold' and delta=offer.
     execute_barter now emits interaction.trade.completed with merchant_id.
  3. world/fsm/generic_fsm.py - send_event passes event_data positionally
     so guards/actions actually receive it.
  4. tests/unit/test_barter_fsm.py - new; 8 tests covering both guard
     paths, offer -> countering, confirm -> completed, cancel -> completed,
     and both emitted event types.

Emitted types (both declared in config/events/initial_events.json from
bundle 001):
    state.resource.changed
    interaction.trade.completed

## Not included

  - No change to config/fsms/barter.json (already consistent).
  - No change to engine._execute_barter.
  - No change to tests/integration/test_economy.py.
  - No regression re-run of the encounter test file in the same work clone;
     that file lives only in bundle 002's patch and was not present in the
     work clone at the time of bundle 003. The prefix-application check
     (apply bundles 001, 002, 003 to a fresh clone and re-run encounter +
     barter tests together) is performed in task 4.1a. The bundle 003
     change to GenericFSM.send_event is a no-op for encounter: none of the
     encounter events carry event_args, so those callbacks receive no
     arguments either way.

## Verification

Applied to a fresh clone at 598ed55 (see verify.md). Test file:
tests/unit/test_barter_fsm.py, 8 tests, all pass.
