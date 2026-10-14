# Bundle workflow

Operational playbook for building the next dj2 handoff bundle. SESSION_STATE.md

gives current state; this gives the steps. Read this before starting bundle

work in a new session.

The bundle format itself is defined in the OpenSpec spec

openspec/changes/dj2-state-machine-handoff/specs/dj2-handoff-sync/spec.md.

This file is only about how to build one.

## Bundle index

001 events-foundation  config/events/initial_events.json, 7 event types

002 encounter-fsm      fight_possible guard; four encounter actions emit events

003 barter-fsm         session_id in barter context; add_gold and

                       execute_barter emit; generic_fsm.py send_event fix

004 trade-fsm          registry keys fixed; execute_purchase renamed

                       execute_buy and emits

005 context-builder    _get_encounter_context and _get_combat_context

                       implemented as EventLog readers

All five are ready and verified. None applied to dj2 yet.

## One-time setup

Three scratch clones outside the Determined repo:

    C:\Users\bartl\dev\_scratch\dj2-work      writable, for edits

    C:\Users\bartl\dev\_scratch\dj2-verify    cumulative, for verify runs

    C:\Users\bartl\dev\_scratch\dj2-598ed55   read-only fixture

Base SHA for all five bundles: 598ed551d0538c1129c75aec0f708b20205c80af

## Build loop

For bundle NNN, slug, base SHA 598ed55:

### Step 1 - Reset the work clone to base

    cd C:\Users\bartl\dev\_scratch\dj2-work

    git reset --hard 598ed551d0538c1129c75aec0f708b20205c80af

    git clean -fd

    git status --short

Use --hard, not plain git reset. Plain reset leaves the edits in the working

tree, and the next bundle's diff will include them. git clean -fd removes

files created by the previous bundle.

### Step 2 - Make the dj2 edits in the work clone

Edit .py and .json files as needed. Create new test files under tests/unit/.

Run them inside the work clone:

    cd C:\Users\bartl\dev\_scratch\dj2-work

    python -m pytest tests\unit\test_your_new_file.py -v

    cd C:\Users\bartl\dev\Determined

If they fail, fix and rerun. Do not proceed until they pass.

### Step 3 - Build the bundle

    python tools\handoff.py make --clone C:\Users\bartl\dev\_scratch\dj2-work --bundle-dir C:\Users\bartl\dev\Determined\handoffs\dj2\NNN-slug --id NNN --base-sha 598ed551d0538c1129c75aec0f708b20205c80af --openspec-task X.Y

Writes change.patch, MANIFEST.json, and (if not already present) stub

rationale.md and verify.md.

### Step 4 - Re-add tests_run to MANIFEST.json

make overwrites MANIFEST.json every time, so tests_run is lost on each

rebuild. Open it and fill in the tests:

    notepad handoffs\dj2\NNN-slug\MANIFEST.json

Change "tests_run": [], to:

    "tests_run": [

      "tests/unit/test_your_new_file.py"

    ],

Save. Then:

    python tools\handoff.py check handoffs\dj2\NNN-slug

Expect: PASS:

### Step 5 - Prepare the verify clone with earlier bundles applied

The verify clone should be at base SHA plus every bundle before NNN,

committed. Rebuild it cleanly:

    cd C:\Users\bartl\dev\_scratch\dj2-verify

    git reset --hard 598ed551d0538c1129c75aec0f708b20205c80af

    git clean -fd

    git apply C:\Users\bartl\dev\Determined\handoffs\dj2\001-events-foundation\change.patch

    git add -A

    git commit -m "bundle 001"

    git apply C:\Users\bartl\dev\Determined\handoffs\dj2\002-encounter-fsm\change.patch

    git add -A

    git commit -m "bundle 002"

    git apply --3way C:\Users\bartl\dev\Determined\handoffs\dj2\003-barter-fsm\change.patch

    git add -A

    git commit -m "bundle 003"

    ... (continue, --3way for 003 and later)

    git status --short

    git rev-parse HEAD

    cd C:\Users\bartl\dev\Determined

Status must be empty; HEAD must not be the base SHA (it is base + N commits).

### Step 6 - Verify bundle NNN

    python tools\handoff.py verify --bundle-dir C:\Users\bartl\dev\Determined\handoffs\dj2\NNN-slug --clone C:\Users\bartl\dev\_scratch\dj2-verify

    type handoffs\dj2\NNN-slug\verify.md

Expect: verify: wrote ... and the named test file listed as PASS.

If apply falls back to 3way, verify.md will say so; that is normal for

bundles 003+.

### Step 7 - Write the rationale

    notepad handoffs\dj2\NNN-slug\rationale.md

Replace the placeholder. Cover: what was actually missing, what shape the

fix takes and why, what was deliberately excluded, and the verification

result. Match the style of bundles 002-005.

### Step 8 - Update STATE.md and tick the task

    notepad handoffs\dj2\STATE.md

    notepad openspec\changes\dj2-state-machine-handoff\tasks.md

Change the bundle row from planned to ready. Tick the task.

### Step 9 - Commit and push

    git add handoffs/dj2/NNN-slug handoffs/dj2/STATE.md openspec/changes/dj2-state-machine-handoff/tasks.md

    git commit -m "openspec: task X.Y - bundle NNN short-description"

    git push

    git log origin/dj2-state-machines-openspec..HEAD

Log must be empty.

## Traps discovered this session (2026-10-13/14)

- python-statemachine 3.x: send_event callbacks receive only positional

  args, not kwargs. Pass event_data as a single positional argument.

- handoff.py writes patches with newline="\n" explicitly. Windows

  Path.write_text defaults to CRLF and breaks git apply.

- handoff.py verify tries direct apply first, then git apply --3way for

  cumulative bundles. Clone HEAD check allows base SHA as an ancestor

  rather than requiring equality.

- check_fsm_consistency handles 'from' as a string OR a list of names.

- make overwrites MANIFEST.json; tests_run is lost on every rebuild.

