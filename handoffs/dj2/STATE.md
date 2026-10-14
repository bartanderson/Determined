# dj2 handoff state

Live record of what Determined has handed off to dj2 and what dj2 currently is.

## Last recorded dj2 SHA

base SHA: 598ed551d0538c1129c75aec0f708b20205c80af
recorded: 2026-10-04, Linux cloud session baseline
remote:   https://github.com/bartanderson/dj2.git
working:  C:\Users\bartl\dev\dj2
fixture:  C:\Users\bartl\dev\_scratch\dj2-598ed55 (read-only)

When you push new work to dj2, the next Determined session updates this SHA
and reports the drift (files changed between the old and new SHA).

## Bundle list

Bundles live as directories under handoffs/dj2/. Status meanings:

planned  - spec'd but not yet built
wip      - under construction (not ready, do not apply)
ready    - complete and verified; apply in id order
applied  - you committed it to dj2 (record the new SHA above)
stale    - base SHA is behind dj2 HEAD; ask for regeneration

Current bundles:

 001  events-foundation  ready    task 3.1
 002  encounter-fsm      ready    task 3.2
 003  barter-fsm         ready    task 3.3
 004  trade-fsm          planned  task 3.4
 005  context-builder    planned  task 3.5

All planned against base SHA 598ed55.

Order is taken from the OpenSpec change dj2-state-machine-handoff, design D5.
It may change after task 1.4's re-measurement or task 3.3's economy analysis;
changes are recorded in tasks.md and reflected here.

## Apply procedure

See README.md in this directory. Short form: on a dj2 feature branch, one
bundle at a time - git apply --check, then git apply, then one commit.

## Note on task 2.4 verification

Task 2.4 asks that the README procedure be exercised against a scratch clone
with a sample bundle. No bundle exists yet (the first is task 3.1), so the
end-to-end application test is deferred to task 4.1, when bundles 001-005 are
applied in order to a fresh clone. The mechanics of make, verify, and check
are already covered by tests/regression/test_handoff.py against fixture
mini-repos, so the commands the README documents are themselves tested.

## Reverse sync

When dj2 changes outside this workflow (your own commits), the next Determined
session does four things:

 1. compares dj2 origin/main against the SHA recorded above
 2. reports "recorded X, remote now Y" with the files changed
 3. re-ingests the corpus at the new SHA
 4. updates the base SHA line above

## Changelog

2026-10-14: bundle 001 change.patch regenerated with LF line endings (old
version had CRLF and would not apply on a LF clone). handoff.py fixed to
write patches in LF regardless of host OS.

2026-10-14: bundle 003 change.patch built. Also fixes a latent bug in
GenericFSM.send_event (python-statemachine 3.x does not forward kwargs to
guards/actions; callbacks were always receiving None as event_data).

2026-10-14: handoff.py verify now supports three-way apply. When a bundle
was generated against base_sha but the tree has earlier bundles applied,
git apply --check fails on context and verify falls back to git apply --3way.
The clone HEAD check is relaxed to accept base_sha as an ancestor of HEAD.
README documents the --3way form for bundles 002+.