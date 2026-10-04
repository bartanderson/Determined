## Context

Determined (analysis engine, `C:\Users\bartl\dev\Determined`, github bartanderson/Determined) is run against dj2
(game, `C:\Users\bartl\dev\dj2`, github bartanderson/dj2). They have no runtime coupling. The work is to
finish dj2's wave-1 state machines and the initial events they use, with analysis, specs, tests and patches
authored in Determined and applied to dj2 by the user.

Facts this design rests on (measured 2026-10-04, dj2 corpus ingested 2026-08-27 so counts must be re-measured, task 1.4):

- `implementation_order` on dj2: 25 incomplete symbols in one wave; 12 are FSM guards/actions
  (Barter 3, Encounter 5, Trade 4), 2 are `context_builder.py` stubs.
- dj2 `config/fsms/*.json` use a generic FSM runner (`GenericFSM`); actions/guards are string-dispatched, so they
  have zero static callers (Determined KNOWN TRAP: "FSM stubs have 0 static callers - don't treat as low-priority").
- dj2 `world/event_log.py`: `Event`, `EventLog.emit(event_type, data, source_system, ...)`, `on`, `on_any`; `emit`
  prints a warning when `session_id` is missing. Taxonomy types are `domain.entity.phase`.
- dj2 `world/db.py` requires Postgres + pgvector (`psycopg2`, `pgvector`): not available in the cloud.
- dj2 local origin: `main` is 1 commit ahead of `origin/main` and has uncommitted edits (see proposal). Determined `main`
  is 27 commits ahead of `origin/main`.
- Determined rules (CLAUDE.md): targeted tests only via `tools/run_tests.py`, foreground, short timeout, never `pytest -m`,
  register new tools in `TOOLS` after the function definition, update the dispatch-test expected set, keep `FILE_MAP`
  and `docs/TEST_MAP.md` in sync, commit but do not push `main`.

## Goals / Non-Goals

**Goals:** a mechanically checkable path from "Determined found a gap in dj2" to "the user commits a verified
patch in dj2"; three FSMs complete to their JSON; an initial event set that is declared, checked and flows only
through the Event Log.

**Non-Goals:** see proposal. Notably: no combat, no G0/G10/G11, no direct dj2 writes, no LLM-dependent steps.

## Decisions

### D1. Propagation is by patch bundle, not by shared checkout
dj2 stays read-only to the agent (spec `dj2-handoff-sync`). The agent works in a throwaway clone at `base_sha`
(created outside any dj2 working copy), emits `change.patch`, and verifies it by applying to a second fresh clone.
The user applies with `git apply --check` then commits on a dj2 feature branch.
*Why:* the user's dj2 tree has in-flight edits; a shared checkout makes "who changed this?" unanswerable.
A patch against a pinned SHA is auditable, reversible (`git apply -R`), and re-basable by regeneration.
*Alternatives rejected:* (a) agent commits to a dj2 branch and pushes: violates the strictness requirement and
puts agent output on the same remote as user work; (b) git submodule/subtree of dj2 inside Determined: couples the
repos that CLAUDE.md says have "no runtime coupling" and breaks the corpus path assumptions.

### D2. The FSM JSON is the contract; code follows it
JSON is the only place the machine is declared (states, events, guards, actions). Implementation follows it.
Parse-don't-validate (SOTS III): the consistency check is the single chokepoint that turns a loose JSON file into a
verified machine description; downstream code assumes it. This also catches the user's in-flight
`cond: fight_possible` edit in `encounter.json`, which names a guard that is not defined.
*Tension:* locality of reasoning (I) vs single source of truth (XIV). Resolved by scope: the machine definition lives
once (JSON); each action keeps its own small, local implementation and tests, not a shared helper.

### D3. Events are the only coupling between machines and the rest of the game
Actions emit events through `EventLog`; they do not call escalation, context, dialogue or UI (explicit data flow, II).
The three machines therefore stay independently testable and the later layers subscribe via `on`.
Event type strings are defined once (a constants module or `initial_events.json`, XIV) so Determined's coverage
report can resolve them statically instead of regex-guessing.

### D4. Initial event set derived from the taxonomy
Start from `design1a_event_taxonomy.md`. Expected core, to be confirmed against the actual FSM needs in task 3.1
(this list is a starting hypothesis, not a decision): `encounter.started`, `encounter.updated`, `encounter.ended`,
`combat.initiation.triggered`, `interaction.trade.offer_made`, `interaction.trade.completed`,
`interaction.trade.rejected`, `state.resource.changed` (gold), `system.action.executed`.

### D5. Encounter first, and combat stays a stub
Order bundles by what unblocks the most with the least dependency: events foundation, then Encounter (analysis
already designated flee + parley as the lowest-risk end-to-end path), then Barter, then Trade, then the
context-builder consumers that read what those emitted. `start_combat` only emits `combat.initiation.triggered`.
The order is re-derived from `implementation_order` at the pinned SHA in task 1.4 and may change; changes are recorded in `tasks.md`.

### D6. Verification is bounded by what runs headless
dj2 needs Postgres for anything touching `world/db.py`. Verification therefore uses (a) FSM transition tests through
the runner with in-memory `EventLog`, (b) Determined's own re-ingest + `list_stubs` + coverage report on the patched clone.
Anything needing Postgres is reported "not run", never claimed. Existing headless tests (`tests/integration/test_economy.py`,
`tests/unit/test_escalation_engine.py`, `test_trade_fsm.py`, ...) are classified in task 1.3 and used as regression guards.

### D7. Cloud session runs in Determined; it clones dj2 as a read-only fixture
Pushing: the cloud session pushes only the feature branch `dj2-state-machines-openspec` of Determined (needed for its
work to persist), never `main`; the user merges. This is the single exception to "Bart pushes".
The local-machine-only parts (Qwen3, Chrome 9222, Postgres) are out of scope in the cloud.

### D8. Placement by durability: repo versus cloud, and always-valid repos
Rule of thumb: if it must outlive the credits, it is a file in the Determined repo on the pushed feature branch; if it can be
rebuilt, it stays in the sandbox. Rebuildable: dj2 clones, corpus DBs, venv, test output. Durable: specs, tooling, tests,
bundles, STATE.md, SESSION_STATE.md.
Nothing destined for dj2 is ever pushed to dj2 by the agent. It is a bundle, and bundles are ordered so every prefix leaves
dj2 working (each bundle is self-contained and tested on top of its predecessors). That is what makes "the credits ended
mid-way" safe: the user can stop applying at any point and dj2 is a valid, working game state with fewer machines finished,
never a half-wired one.
Small increments: commit + push after every task. A bundle under construction lives in `handoffs/dj2/wip/` and is promoted to
`handoffs/dj2/<NNN>-<slug>/` only when verified.
Freshness check at close: re-check every ready bundle against current dj2 `origin/main`; regenerate or mark `stale`.
*Why:* the user's explicit requirement is that when cloud access ends there is valid work in dj2 and nothing broken.
Pushing only whole, verified, independently-revertible units, and never touching dj2 directly, is the structure that guarantees it
without relying on anyone's vigilance (SOTS: structure over vigilance).
Bootstrap precondition, done by the user before the move: the Determined branch will be pushed by the app and carries
Determined's 27 unpushed `main` commits with it; the user decides whether dj2's 1 unpushed commit and in-flight edits are
committed and pushed first (they are not baselines otherwise).

## Risks / Trade-offs

- **Determined is Windows-centred** (PowerShell instructions, absolute `C:/...` path prefixes in the corpus).
  Ingest under Linux may misbehave. -> Task 1.1/1.3 test this first. If it fails, report; do not patch around it
  inside this change (a separate change).
- **Stale local DB** (dj2 corpus ingested 2026-08-27). -> Spec requires re-ingest at `base_sha` before any finding.
- **dj2's baseline lags the user's work.** The user's dirty tree and 1 unpushed commit are not baselines. -> The user
  commits/pushes dj2 first if they want that work included; otherwise bundles may need regeneration (spec: re-base by regeneration).
- **Bundle drift**: dj2 moves while bundles wait. -> `MANIFEST.json` carries `base_sha`; stale bundles are regenerated, never hand-merged.
- **Over-testing the generic runner**: only transitions in the JSON are tested, not the runner internals.
- **Taxonomy debt**: the taxonomy is "examples, not exhaustive". Additions are proposed in-bundle and reviewed.

## Migration Plan

1. User pushes dj2 and Determined to the state they want the cloud to see (agent never does this for dj2).
2. Cloud session: tasks 1.x (bootstrap, baseline), 2.x (Determined tooling), 3.x (bundles), 4.x (close).
3. User pulls the Determined feature branch, applies bundles to dj2 one at a time, runs dj2's own tests locally
   (including Postgres-backed), commits, pushes; next Determined session records the new SHA (reverse sync).
4. Rollback: `git apply -R` of a bundle in dj2, or discard the dj2 feature branch. Determined changes revert with the branch.

## Open Questions

- Where should `initial_events.json` live in dj2 (`config/events/` vs next to `config/fsms/`)? The user decides in bundle 001 review.
- Do the user's in-flight `fight_possible` guard and the `get_spell_from_db` helper belong in this work, or are they separate?
  They are not in any baseline until committed.
- Trade vs Barter: are they one economy machine family (shared `add_gold`/price logic) or independent? Task 3.3 reads
  `test_economy.py` and `test_trade_fsm.py` first and records the answer in the bundle rationale.
