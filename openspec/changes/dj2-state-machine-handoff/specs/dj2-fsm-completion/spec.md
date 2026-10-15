## ADDED Requirements

### Requirement: The FSM JSON is the contract
For each machine in `config/fsms/*.json`, the committed JSON at `base_sha` SHALL be the contract.
Implementations SHALL follow its states, events, transitions, guards and actions. A bundle SHALL NOT
silently change the JSON to fit the code; JSON changes SHALL be separate, explained edits in the same bundle.

#### Scenario: code and JSON disagree
- **WHEN** an action's natural implementation conflicts with the JSON
- **THEN** the bundle's `rationale.md` states the conflict and proposes a JSON edit explicitly, or the code follows the JSON

### Requirement: FSM definitions are internally consistent
Determined SHALL provide a check over every `config/fsms/*.json` that fails when a transition's `cond`
names a guard not defined under `guards`, a transition's `actions` names an action not defined under
`actions`, a transition's `from`/`to` names a state not in `states`, or there is not exactly one `initial` state.

#### Scenario: undefined guard referenced
- **WHEN** a transition has `"cond": "fight_possible"` and `guards` has no `fight_possible`
- **THEN** the check reports file, event, and the missing guard name, and exits non-zero

#### Scenario: all references resolve
- **WHEN** every name resolves and exactly one initial state exists
- **THEN** the check exits zero and prints a per-machine table of states, events, guards, actions

### Requirement: Every guard and action has an implementation target
For each machine, each guard and action named in the JSON SHALL map to exactly one implemented callable
registered with the generic FSM runner, and no registered callable SHALL be a stub (`pass`, `raise NotImplementedError`,
or constant return) when its bundle is marked complete. Determined's stub report is the measuring instrument.

#### Scenario: machine complete
- **WHEN** a machine's bundle is applied to the clone at `base_sha`
- **THEN** `list_stubs` on the re-ingested clone reports none of that machine's guards or actions as stubs

### Requirement: Each machine has transition tests that drive it end to end
For each completed machine there SHALL be tests that walk every declared transition at least once,
including each guard's true and false path, through the FSM runner (not by calling actions directly).

#### Scenario: guard false path
- **WHEN** `flee_possible` evaluates false
- **THEN** a test shows the `flee` event leaves the machine in `awaiting_choice` or the declared alternative, with no `resolve_flee` side effect

### Requirement: Combat is not implemented here
The Encounter machine's `start_combat` action SHALL emit `combat.initiation.triggered` with the encounter data
and SHALL NOT implement combat resolution. `combat_ended` remains an externally delivered event.

#### Scenario: player chooses fight
- **WHEN** the `fight` event is processed in `awaiting_choice`
- **THEN** the machine enters `resolving_fight`, one `combat.initiation.triggered` event is emitted, and no combat rules run

### Requirement: Context-builder encounter and combat stubs are filled only to the contract
`_get_encounter_context` and `_get_combat_context` in `world/context_builder.py` SHALL be implemented as pure
read-side consumers of the Event Log (`encounter.*` and `combat.*` events), per `04 context builder v1.3.md`:
no mutation, no re-resolution of entities, no database access.

#### Scenario: encounter in progress
- **WHEN** the log contains `encounter.started` without `encounter.ended` for the session
- **THEN** `_get_encounter_context` returns a snapshot describing that encounter derived only from the log events
