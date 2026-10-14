# Rationale - bundle 001, events foundation

Derived from the OpenSpec change dj2-state-machine-handoff, spec
dj2-initial-event-set, requirement "The initial event set is derived, not
invented" and design D4.

The set is the subset of docs/design1a_event_taxonomy.md that the wave-1 FSM
actions and the context-builder stubs emit or consume. It is derived from the
three committed FSM JSONs (config/fsms/barter.json, encounter.json, trade.json)
and the EventLog API in world/event_log.py.

Events kept (7):

  encounter.started             EncounterFSM entry; emitted when the machine
                                leaves the initial state and enters
                                awaiting_choice.
  encounter.updated             resolve_flee / resolve_parley emit this before
                                the terminal transition.
  encounter.ended               Terminal event for EncounterFSM, carries an
                                outcome field (fled / parleyed / fought).
  combat.initiation.triggered   start_combat emits this and nothing else; no
                                combat rules run here (design D5).
  interaction.trade.offer_made  Emitted when a TradeFSM or BarterFSM offer
                                transitions from awaiting to countering.
  interaction.trade.completed   execute_buy / execute_barter emit on confirm.
  state.resource.changed        add_gold emits this; resource="gold" for wave-1.

Events dropped from D4's earlier hypothesis (2):

  interaction.trade.rejected    No terminal "rejected" state exists in either
                                economy FSM. A low offer stays in countering;
                                the only exits are confirm and cancel, and
                                cancel currently has no actions. Nothing would
                                emit this type without inventing a new
                                transition, which would be a redesign, not a
                                spec-confirmation (proposal non-goal: no
                                redesign of dj2 architecture).

  system.action.executed        No FSM action emits it and neither context
                                builder stub consumes it. It is a generic
                                meta-event with no load-bearing role in wave 1.
                                Adding it would be completeness for its own
                                sake.

Required fields: session_id is on every type because EventLog.emit warns when
it is missing and every downstream consumer filters by session. The remaining
fields are the minimum needed to identify the entity the event concerns
(encounter_id, merchant_id) or its payload semantics (description, outcome,
resource, delta).

Location: config/events/initial_events.json, alongside config/fsms/. Chosen so
the two contract files are visible together and so Determined's check_event_coverage
tool can read the set as structured data (spec: "one machine-readable file").

No code in this bundle. Bundle 001 establishes the contract that bundles 002-005
implement against. Downstream bundles SHALL emit only types from this file;
additions require a follow-up bundle that edits both this file and the taxonomy
doc together.
