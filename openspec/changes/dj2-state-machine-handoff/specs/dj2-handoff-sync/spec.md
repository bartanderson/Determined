## ADDED Requirements

### Requirement: dj2 is read-only to the Determined agent
The agent working in Determined SHALL NOT edit, stage, commit, stash, reset, or push in any
dj2 working copy or the dj2 remote. Every change destined for dj2 SHALL exist only as a handoff
bundle inside the Determined repo until the user applies it.

#### Scenario: agent needs to test a dj2 change
- **WHEN** a proposed change must be run against dj2 code
- **THEN** the agent applies it to a throwaway clone outside any dj2 working copy and discards the clone afterwards

#### Scenario: agent holds write access to a dj2 checkout
- **WHEN** the session has a dj2 checkout available for reading
- **THEN** no command run by the agent writes into it (no `git add/commit/checkout/reset/stash/push`, no file writes)

### Requirement: Every analysis and bundle is pinned to a dj2 commit
Each Determined analysis result, finding, and handoff bundle that concerns dj2 SHALL record the
full dj2 commit SHA it was derived from (`base_sha`). Analysis SHALL run only against a dj2 tree
that equals a commit: a clean checkout, or a clone at that SHA. Uncommitted dj2 state SHALL NOT
be a baseline.

#### Scenario: dj2 working copy has uncommitted edits
- **WHEN** the dj2 working tree is dirty
- **THEN** analysis runs on a fresh clone at the pinned commit, never on the dirty tree, and the report states that local uncommitted edits were excluded

#### Scenario: report cites its baseline
- **WHEN** any dj2 report or bundle is produced
- **THEN** it contains `base_sha` and the corpus ingest time for that SHA

### Requirement: Corpus is re-ingested at the pinned commit before querying
Before any dj2 query that informs a bundle, the corpus database SHALL be (re)built from the tree at
`base_sha`. A corpus whose recorded SHA differs from `base_sha` SHALL be treated as stale.

#### Scenario: stale corpus
- **WHEN** the recorded corpus SHA differs from the requested `base_sha`
- **THEN** the query is refused with a message to re-ingest, and no findings are produced from the stale data

### Requirement: Handoff bundle format
A handoff bundle SHALL be a directory `handoffs/dj2/<NNN>-<slug>/` in the Determined repo containing:
`MANIFEST.json` (`id`, `base_sha`, `files_touched`, `tests_run`, `finding_ids`, `openspec_task`, `verified_at`),
`change.patch` (unified diff relative to the dj2 repo root, applicable with `git apply`),
`rationale.md` (why, citing Determined findings and dj2 design docs), and
`verify.md` (exact commands run, in a clone at `base_sha`, with their output summary).
One bundle SHALL correspond to one dj2 commit.

#### Scenario: bundle is complete
- **WHEN** a bundle is marked ready
- **THEN** all four files exist and `change.patch` passes `git apply --check` against a clean clone at `base_sha`

#### Scenario: change has no finding
- **WHEN** a patch touches dj2 files but cites no Determined finding id or OpenSpec task
- **THEN** it is not accepted as a bundle

### Requirement: Bundles are verified in a clone before handoff
A bundle SHALL be marked verified only after `change.patch` has been applied to a fresh clone at
`base_sha` and the tests named in `MANIFEST.json` have been run there, with results recorded in `verify.md`.
Tests that cannot run in the environment SHALL be listed as not run, with the reason; they SHALL NOT be counted as passing.

#### Scenario: test needs Postgres
- **WHEN** a named test requires the database
- **THEN** `verify.md` lists it as "not run: requires Postgres" and the bundle does not claim it passed

### Requirement: Bundles are applied by the user, in order, against the recorded base
The user applies a bundle to dj2 on a feature branch with `git apply --check` then `git am`/`git apply`
and one commit. Bundles carry an order. A bundle whose `base_sha` is not an ancestor-or-equal of dj2's
current HEAD, or whose files changed upstream of `base_sha`, SHALL be re-based and re-verified before use.

#### Scenario: dj2 moved after the bundle was made
- **WHEN** dj2 HEAD is ahead of `base_sha` and touched a file in `files_touched`
- **THEN** the bundle is regenerated against the new SHA and re-verified, not hand-merged

### Requirement: Artifacts are placed by durability, repo versus cloud
Everything the cloud session produces SHALL be classified as repo-bound or cloud-only, and only repo-bound artifacts SHALL be committed.

Repo-bound (committed and pushed to the Determined feature branch `dj2-state-machines-openspec`): OpenSpec files,
Determined source changes (tools, checks), their tests, `FILE_MAP` / `docs/TEST_MAP.md` updates, handoff bundles under
`handoffs/dj2/`, `handoffs/dj2/STATE.md`, `BASELINE.md`, `SESSION_STATE.md`, and docs.

Cloud-only (never committed, discarded with the sandbox): the dj2 clone(s), corpus `*.db` files (already gitignored),
the virtualenv, pip caches, test output, scratch files, and any dj2 working tree with a patch applied for verification.

dj2-bound changes SHALL NOT be pushed by the agent in any form; they travel only as bundles in the Determined repo.

#### Scenario: corpus database appears in git status
- **WHEN** `git status` in the Determined clone lists a `*.db` file, a clone directory, or a virtualenv as untracked
- **THEN** the agent adds the missing ignore rule or moves the file outside the repo, and does not commit it

#### Scenario: a dj2 change is ready
- **WHEN** a dj2 change passes verification
- **THEN** it is committed in Determined as a bundle directory and pushed on the feature branch; no dj2 remote is contacted for writing

### Requirement: Both repos are valid at every stopping point
At the end of every task, and whenever the session may stop (credits exhausted, interruption, hand-off), the following SHALL hold:
(a) the Determined feature branch is pushed and its targeted tests pass; (b) every bundle marked ready applies cleanly
(`git apply --check`) to current dj2 `origin/main`, or is marked `stale` in `STATE.md`; (c) no bundle in a half-written state is marked ready;
(d) dj2 is unchanged by the agent, so it cannot be broken by the agent's work; (e) `main` of either repo is untouched.

Bundles SHALL be self-contained and ordered so that applying any prefix of the ordered list leaves dj2 in a working state:
each bundle's tests pass on the tree that results from applying the bundles before it, and no bundle depends on a later one.

#### Scenario: credits run out mid-bundle
- **WHEN** the session ends while a bundle is unfinished
- **THEN** it exists only under `handoffs/dj2/wip/` marked not ready, the pushed branch has all completed work, and `STATE.md` says which task was in progress

#### Scenario: user applies only the first two bundles
- **WHEN** bundles 001 and 002 are applied to dj2 and later ones are not
- **THEN** dj2's headless tests that passed at `base_sha` still pass, and no code references anything from an unapplied bundle

#### Scenario: dj2 moved while the cloud session worked
- **WHEN** dj2 `origin/main` is ahead of `base_sha` at the close checkpoint
- **THEN** each ready bundle is re-checked against the new HEAD; those that no longer apply cleanly are regenerated and re-verified or marked `stale`

### Requirement: Work is pushed in small increments
After each completed task the agent SHALL commit to the Determined feature branch and push it, so that an unexpected stop loses at most the task in progress.

#### Scenario: task completes
- **WHEN** a task's verification passes
- **THEN** its `tasks.md` checkbox is ticked in the same commit and the branch is pushed before the next task starts

### Requirement: Reverse sync is recorded
When dj2 changes (user commits, bundle application, or other work), the next Determined session SHALL
record the new dj2 SHA in `handoffs/dj2/STATE.md`, re-ingest, and report drift from the last recorded SHA.

#### Scenario: session start drift check
- **WHEN** a Determined session starts a dj2 task
- **THEN** it compares dj2 `origin/main` with the SHA recorded in `handoffs/dj2/STATE.md` and reports "recorded X, remote now Y" with the changed files
