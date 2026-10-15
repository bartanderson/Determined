## ADDED Requirements

### Requirement: The initial event set is derived, not invented
The initial event set SHALL be the subset of `docs/design1a_event_taxonomy.md` (type form `domain.entity.phase`)
that the wave-1 FSM actions and the context-builder stubs emit or consume. Any needed type absent from the
taxonomy SHALL be proposed to the user as a taxonomy addition in a bundle; it SHALL NOT be introduced silently.

#### Scenario: action needs an unlisted type
- **WHEN** an implementation would emit a type not present in the taxonomy
- **THEN** the bundle adds it to the taxonomy doc in the same patch with a one-line meaning, or does not emit it

### Requirement: Each initial event declares required data fields
Each type in the initial set SHALL list its required `data` fields in one machine-readable file in dj2
(`config/events/initial_events.json` or the location the user chooses in review). `EventLog.emit` callers
for these types SHALL supply those fields, including `session_id` (the Event Log already warns when it is missing).

#### Scenario: emit without a required field
- **WHEN** a test emits an initial-set type missing a required field
- **THEN** the check reports the type and field

### Requirement: Event coverage report
Determined SHALL provide a report over a dj2 clone that lists, per event type: declared in the taxonomy,
emitted (literal `emit("type", ...)` call sites), consumed (`on("type", ...)` / `on_any`), and the diff:
emitted-but-undeclared, declared-but-never-emitted, emitted-but-never-consumed, consumed-but-never-emitted.

#### Scenario: undeclared emission
- **WHEN** a dj2 module emits `encounter.resolved` which is not in the taxonomy
- **THEN** the report lists it under emitted-but-undeclared with file and line

#### Scenario: initial set is the focus
- **WHEN** the report is run with the initial-set filter
- **THEN** it shows one row per initial type with all four columns and a pass/fail against "emitted by at least one machine action and consumed by at least one listener or test"

### Requirement: Initial events flow through the Event Log only
Machine actions SHALL deliver their outcomes to the rest of the game by emitting events through the Event Log.
Actions SHALL NOT call escalation, context, dialogue, or UI code directly. Subscribers (`on`) SHALL be how those layers react.

#### Scenario: resolve_flee succeeds
- **WHEN** `resolve_flee` runs with `flee_possible` true
- **THEN** it emits `encounter.updated` then `encounter.ended` (with `outcome: fled`) and makes no direct call into the escalation engine

### Requirement: Event type literals are not hand-typed in many places
The initial event types SHALL be referenced through one definition (a constants module or the JSON from the data-fields requirement)
so that Determined's coverage report can resolve them.

#### Scenario: typo in event type string
- **WHEN** an action emits `"encounter.endd"`
- **THEN** the coverage report flags it as emitted-but-undeclared
