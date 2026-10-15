# Verification for 001

Base SHA: 598ed551d0538c1129c75aec0f708b20205c80af
Clone: C:\Users\bartl\dev\_scratch\dj2-verify

## Commands

- `git apply --check change.patch` -> OK
- `git apply change.patch` -> OK

## Tests

(no tests named in MANIFEST.tests_run)

## Not run

(list any named test that could not be run, with the reason)

## Determined-side coverage check (task 3.1)

Command:
  python tools/query.py check_event_coverage {"directory": "C:\\Users\\bartl\\dev\\_scratch\\dj2-verify"}

Summary (full output held in the session log, not committed):
  taxonomy:        55 declared types
  emitted:         21 unique types across 37 call sites
  consumed:        2 unique types across 5 call sites
  on_any present:  8 files (wildcard listener)

  emitted-but-undeclared:   20 types
  declared-but-never-emitted: 54 types
  emitted-but-never-consumed: 0 types
  consumed-but-never-emitted: 1 type (reputation.modify_requested)

Initial-set filter (7 types):
  encounter.started             emitted=no  consumed=yes  FAIL
  encounter.updated             emitted=no  consumed=yes  FAIL
  encounter.ended               emitted=no  consumed=yes  FAIL
  combat.initiation.triggered   emitted=no  consumed=yes  FAIL
  interaction.trade.offer_made  emitted=no  consumed=yes  FAIL
  interaction.trade.completed   emitted=no  consumed=yes  FAIL
  state.resource.changed        emitted=no  consumed=yes  FAIL

Interpretation: all 7 initial types are declared by this bundle's
config/events/initial_events.json and recognized by the taxonomy, but none
is emitted anywhere in dj2 at base_sha. This is expected for a contract-only
bundle. Bundles 002-005 introduce the emitters. The consumed=yes column is
driven by on_any wildcard listeners in 8 files, which treat every declared
type as subscribable; this is not the same as a typed subscriber and will
tighten when bundles 002-005 register typed on() handlers.

verified_at: 2026-10-14T01:18:35.829808+00:00
