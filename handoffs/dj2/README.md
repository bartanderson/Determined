# Applying a dj2 handoff bundle

This directory holds handoff bundles produced by Determined. Each bundle is a
self-contained change destined for the dj2 repo at C:\Users\bartl\dev\dj2
(https://github.com/bartanderson/dj2). The agent that works in Determined
never writes to dj2; you apply bundles yourself.

## Bundle layout

Each bundle is a directory handoffs/dj2/NNN-slug/ containing:

    MANIFEST.json    id, base_sha, files_touched, tests_run, finding_ids,
                     openspec_task, verified_at
    change.patch     unified diff relative to the dj2 repo root
    rationale.md     why this change exists, citing Determined findings and
                     dj2 design docs
    verify.md        the commands run in a clone at base_sha, with output

A bundle corresponds to exactly one dj2 commit.

## Before you apply

1. Check that dj2's current HEAD is at or ahead of the bundle's base_sha.
   If dj2 moved and touched any file in MANIFEST.files_touched, ask for the
   bundle to be regenerated against the new SHA. Do not hand-merge.

2. Confirm the bundle is complete and cites a finding or task:

       python tools/handoff.py check handoffs/dj2/NNN-slug

   Expected output begins with PASS:. If it says FAIL:, stop and report.

## Applying a bundle

Work in your dj2 working copy, on a feature branch. Never apply to main.

1. Create a feature branch if you do not already have one:

       cd C:\Users\bartl\dev\dj2
       git checkout -b dj2-state-machines

2. Dry run - verify the patch applies cleanly:

       git apply --check C:\Users\bartl\dev\Determined\handoffs\dj2\NNN-slug\change.patch

   No output and exit code 0 means the patch will apply.

3. Apply:

       git apply C:\Users\bartl\dev\Determined\handoffs\dj2\NNN-slug\change.patch

4. Run the dj2 tests named in the bundle's verify.md. Some require Postgres;
   those are marked "not run" there and are not claimed as passing.

5. Commit with a message that names the bundle:

       git add -A
       git commit -m "bundle NNN: short description"

6. Push the branch, or keep it local and stack the next bundle.

## Applying a series of bundles

Bundles are ordered by MANIFEST.id (001, 002, ...). Apply them in order.
Applying any prefix of the ordered list should leave dj2 in a working state
with its headless tests still passing. Do not skip a middle bundle and apply
a later one.

## Reverting a bundle

To undo a bundle already applied and committed:

    cd C:\Users\bartl\dev\dj2
    git revert COMMIT-SHA

To undo an applied-but-uncommitted patch:

    git apply -R C:\Users\bartl\dev\Determined\handoffs\dj2\NNN-slug\change.patch

## Recording the new state

After you push dj2, the next Determined session records the new dj2 SHA in
handoffs/dj2/STATE.md and re-ingests the corpus. Until that happens,
STATE.md keeps the previous SHA and lists the bundle you applied as
"applied - pending SHA update".

## If a bundle is marked stale

STATE.md marks a bundle "stale" when its base_sha is no longer an ancestor
of dj2 HEAD, or when dj2 changed a file the bundle touches. Stale bundles
are not to be applied. Ask for regeneration; the regenerated bundle gets a
new base_sha and fresh verify.md.


