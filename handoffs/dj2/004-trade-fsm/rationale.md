# Rationale - bundle 004, Trade FSM

Derived from the OpenSpec change dj2-state-machine-handoff, spec
dj2-fsm-completion, and design D2 ("the FSM JSON is the contract; code
follows it") and D3 ("events are the only coupling between machines and
the rest of the game").

## What was actually missing in trade

The trade FSM (config/fsms/trade.json) referenced two action names -
update_price and execute_buy - but the registry built in
world/adjudication_engine.py named its entries store_offer and
execute_purchase. python-statemachine resolves action names by attribute
lookup, so neither match could run: the trade machine's offer and confirm
transitions were dead. This is the same class of defect the encounter
machine had (fight_possible), and it is why the FSM JSON is treated as the
contract: the JSON named the correct actions; the code did not.

Three related gaps:

  1. The action registry keys did not match trade.json's declared actions.
  2. The buy/sell FSM context did not include session_id, so any event
     emitted from an action would be missing a required field.
  3. execute_purchase (the function behind execute_buy) performed its
     engine call but emitted nothing, same shape as the encounter and
     barter actions before bundles 002 and 003.

## Changes

  1. world/fsm/builtins.py - rename execute_purchase to execute_buy (the
     name trade.json declares), and make it emit
     interaction.trade.completed with merchant_id after the engine call
     succeeds. The event type is declared in config/events/initial_events.json
     from bundle 001.

  2. world/adjudication_engine.py -
     a. In the trade registry (line ~54), replace the two keys so they
        match trade.json:
          'store_offer'      -> 'update_price'  (bound to builtins.update_price,
                                                which already wrapped store_offer)
          'execute_purchase' -> 'execute_buy'   (bound to builtins.execute_buy)
        The guard registry above it was already correct and is unchanged.
     b. Add 'session_id': session_id to the buy/sell context dict so the
        actions can emit events with the required field.

  3. tests/unit/test_trade_fsm.py - new; 8 tests walking both guard
     paths (offer below / at / above price), confirm-from-awaiting, and
     cancel, and checking the emitted event payload.

## Not included

  - No change to config/fsms/trade.json. The JSON already had the correct
    names; it was the code that had drifted.
  - No change to builtins.store_offer. It is shared with the sell registry
    (world/adjudication_engine.py line 62) and remains the sell-path action.
  - No change to builtins.execute_sell.
  - No change to tests/test_trade_fsm.py. That file imports
    world.fsm.trade_machine, a module that does not exist at base_sha; it
    was broken before this bundle and is broken after it. Deleting or
    rewriting it is out of scope for bundle 004. Flagged for later cleanup.

## Verification

Applied to the cumulative clone (bundles 001, 002, 003 already committed) at
HEAD aadc4f6 via git apply --3way. Test file: tests/unit/test_trade_fsm.py,
8 tests, all pass.

Prefix check (part of the verification this bundle enables): after applying
bundles 001, 002, 003 together, the barter tests (8) and encounter tests (8)
still pass - 16 passed. The cumulative tree is a working dj2.
