# Determined - Project Context

## SESSION START CHECKLIST -- do this before anything else, every session

**Step 1 -- Read SESSION_STATE.md**
Read `SESSION_STATE.md` at the repo root. It is the handoff artifact from the
prior session: what was done, what is next, what is pinned. Do not answer
"what's next" or make any plan until you have read it.

**Step 1a -- Drift check (RESUME verification)**
After reading SESSION_STATE.md, run `git log --oneline -3` and compare the
"Written at commit" SHA in the header against current HEAD. If they differ,
run `git diff <handoff-SHA>..HEAD --stat` and report drift explicitly:
"Handoff said X, repo now shows Y." Resolve [?]-tagged claims if cheap.
If SESSION_STATE.md has no SHA (older format), skip this step.

**Step 2 -- Read TRACKER.md**
Read `docs/TRACKER.md` for the current open items and dashboard status.
Do not conflate with SESSION_STATE.md -- TRACKER.md is the authoritative
open-items list; SESSION_STATE.md is the most-recent-session snapshot.

**Step 2a -- Check UI_REDESIGN.md for current work priority**
Read `docs/UI_REDESIGN.md`. This is the primary work driver: the shape-first
UI redesign, phased A/B/C. CLOSURE.md's gate was fully checked 2026-07-18
and Phase A shipped 2026-07-19 (session 219). Pick up the next unshipped
phase; resolve the open questions listed in the doc with Bart before
starting the phase they gate.

**Step 3 -- Confirm memory is loaded**
Check that the MEMORY.md auto-index has loaded via system context. If Bart
asks about prior decisions, preferences, or constraints, check memory entries
before answering.

**Step 4 -- Skim HISTORY.md**
Read `docs/HISTORY.md` for recent non-obvious decisions, failed approaches, and
surprises that are still live. These are things that don't belong in memory files
yet (too recent or specific) but that a fresh session would otherwise re-derive
the hard way.

---

## Environment

- **OS**: Windows 11 - use **PowerShell** tool for all server starts, Python runs, and any command with a `C:\` path. Bash tool uses Git Bash and fails on Windows paths.
- **`&&` chaining**: Not valid in PowerShell 5.1. Use `; if ($?) { cmd2 }` or just `;`.
- **Python**: No `python3` on Windows. Use `python` or the full venv path (`.venv\Scripts\python.exe`). Full path is safest.
- **`python -c`**: Only works cleanly for single-line one-liners. For anything multi-line, write a `.py` script to the scratchpad and run that instead.
- **`/dev/null`**: Use `$null` in PowerShell (`2>$null` to suppress stderr).
- **Env vars**: `$env:VAR` not `$VAR` in PowerShell.
- **Paths with `~`**: Use `$env:USERPROFILE` or full path when passing to scripts.
- **Git and PowerShell** work normally; `ls`/`cat`/`rm` are aliased in PS but take different flags than Linux.

---

## PRE-CODE CHECKLIST -- run before writing any new code

Before writing any code that queries, transforms, or computes data in Determined:

1. Grep for it in `determined/agent/graph_utils.py` and `determined/agent/agent_tools.py`
2. If it exists, use it
3. If it doesn't exist, state what you searched for and didn't find before writing

This is not optional. The most common failure mode in this codebase is writing
a new version of something that already exists authoritatively elsewhere.
See docs/PRACTICES.md for the full engineering standards.

---

## Identity

- Repo: https://github.com/bartanderson/Determined
- Local working copy (Bart's machine): `C:\Users\bartl\dev\Determined`
- This is the Determined code analysis engine -- a corpus-agnostic Python
  codebase analysis tool backed by SQLite and local Ollama models.
- The game code (dj2) lives in `C:\Users\bartl\dev\dj2` -- separate repo,
  separate process, no runtime coupling.

## Environment setup (two-terminal rule)

Always use two terminals:
- Terminal 1: venv activated, for Python/pytest commands
- Terminal 2: for git and file operations

Venv paths:
- Activate: `.venv\Scripts\activate` (Windows) or `.venv/bin/activate` (Unix)
- Python: `.venv\Scripts\python.exe`
- Pytest: `.venv\Scripts\pytest`

Common mistakes:
- Running pytest outside the venv (missing deps)
- Running LLM calls without llama-server running (started automatically by the UI; for CLI use, start manually on port 8081)
- Assuming corpus DBs exist -- they must be ingested first

## Where things live

- Engine code: `determined/` (agent/, assessor/, graph/, ingestion/, oracle/, etc.)
- Tests: `tests/regression/` -- 298+ tests, all must pass before commit
- Docs: `docs/` -- TRACKER.md (open items), DESIGN.md (architecture), HISTORY.md (log)
- Practices: `docs/PRACTICES.md` -- engineering standards, read before coding

## DB management (standing rule)

- `knowledge.db` was eliminated in session 33. All tables (knowledge_artifacts,
  workflow_items, bags, bag_items, semantic_summaries) now live in the corpus DB.
- Corpus DBs (e.g. `C_Users_bartl_dev_dj2.db`, `C_Users_bartl_dev_harrow.db`):
  expendable, rebuilt by re-ingesting. Can be deleted and rebuilt at any time.
- There is no separate shared knowledge overlay DB. Everything is scoped to the
  active corpus DB.

## TRACKER.md update rules

Two operation types, two strategies:

- **Status changes** (mark DONE, update dashboard line, add a dated note to an existing item):
  Use the `Edit` tool with exact-string replacement. Surgical, low blast radius.

- **New item blocks** (adding an RM* item or other multi-line block):
  Write the new block to the scratchpad first. Read it back to verify it looks right.
  Then append/insert into TRACKER.md with `Edit`. Never write a 200-line new block
  directly into a 2400-line file in one shot.

SESSION_STATE.md is always a complete overwrite -- the delta approach does not apply there.

---

## Working agreement

- Read/write access to this folder -- edit files in place, no patch files.
- Run `git add` and `git commit` for completed work. Do NOT push -- Bart pushes.
- Before any multi-step sequence, state in one short line what is about to happen
  so Bart can abort. Skip this only for single-step actions.
- **After a change**: run only the matching test file(s) from `docs/TEST_MAP.md`.
  Never run the full suite — it takes 6 minutes and regressions are caught when they matter.
- Run a single test file: `.venv\Scripts\pytest tests/regression/test_foo.py`
- Run a single test: `.venv\Scripts\pytest tests/regression/test_foo.py::test_bar`
- Look up related tests: `docs/TEST_MAP.md` — source module → test file mapping.
- Matching tests must pass before commit. Full suite only if something looks broken.
- Before ending any session that did substantive work, rewrite SESSION_STATE.md
  in full with current status and next steps. This is mandatory. Follow the
  SESSION END PROTOCOL below.
- At session end (or when Bart says "ready for new session"): scan HISTORY.md,
  add any non-obvious decisions or lessons from this session, prune stale entries.
  Do this BEFORE writing SESSION_STATE.md so the history is current.
- Proactive context flagging: when a session is running long (10+ tool calls,
  extended multi-step work), flag it -- "Session is getting long, want to wrap
  and hand off?" Let Bart switch sessions before compaction hits.
- Degradation detection: if you notice you contradicted an earlier decision,
  re-derived something already settled, or misremembered a file, say ONE sentence:
  "This session may be degrading (<specific symptom>). Want to wrap and hand off?"
  Then stop. Never write SESSION_STATE.md without confirmation.

## SESSION END PROTOCOL

Run this before writing SESSION_STATE.md. This runs when memory is least
reliable -- nothing goes in the file from memory alone.

**Step 1 -- Carry forward traps**
Read the existing SESSION_STATE.md (if any). Identify any still-relevant failed
approaches or traps and carry them forward into the new file -- re-tagged [?]
unless re-verified in Step 2. Then overwrite SESSION_STATE.md in place.
(Git history is the archive; no need to copy the old file elsewhere.)

**Step 2 -- Verify before writing (anti-hallucination protocol)**
A claim may be tagged [V] only if confirmed by a command or file read during
THIS session end run. What you merely remember is [?].

- Run `git log --oneline -5` and `git diff --stat HEAD~1` to reconstruct
  what actually changed vs. what you believe changed.
- Re-read any file the handoff will mention by name or line number. A quoted
  line must come from a fresh read, not recall. File not where memory says?
  Caught hallucination -- correct it.
- If `.py` files changed this session: re-run `pytest tests/regression/` and
  write "tests pass" only from output produced in this run. Otherwise tag [?].
- Can't verify it and don't clearly remember it? Omit it. Honest gap beats
  confident fiction.
- If many claims end up [?], add at the top: "Low-confidence handoff -- verify aggressively."

**Step 3 -- Write SESSION_STATE.md**
First line of the file must be:
`Written at commit: <SHA from git log>`

Tag every factual claim [V] (verified this run) or [?] (recalled from memory).
Length: target <=150 lines; hard ceiling 250 lines. Over budget: drop narrative
prose first, compress decisions to one line each. Never cut: failed approaches,
known traps, verified state, or next steps.

Quality gate for Next Steps entries: "Would a fresh session know exactly what
to run first without asking?" If not, add the file, the command, or the reason.

**Rationalizations -- these mean STOP and tag [?] instead:**
- "I remember the session clearly, no need to re-verify" -- verify or tag [?]
- "Tests were passing earlier" -- earlier is not now; re-run or tag [?]
- "Context is nearly full, skip verification" -- cut prose instead; verification is non-negotiable
- "The old SESSION_STATE is outdated, just delete it" -- archive it; its traps may be the only record
- "I'll pad thin sections so the file looks complete" -- write "not started, no design chosen" honestly

---

## UI verify rule (standing rule, added session 47)

No UI feature is done until clicked in browser. "DONE (unverified)" is not done.
Before committing any UI change: start the server, load a corpus, exercise the
changed interaction, confirm it works. Use /verify or the chrome MCP tools.
5 minutes of real use exposed multiple broken interactions that passed code review.

**UI testing constraint (standing rule)**: Never use JS eval to inject or manipulate
browser state as a test setup step. The only valid test sequence is:
1. Reload the page fresh
2. Switch corpus via the UI corpus switcher
3. Wait for corpus_ready
4. Then test the feature

Injecting state via eval produces false results and bypasses the actual user path.
This was explicitly corrected and still violated in the same session -- it belongs here.

## Design reference: The Shape of the System

`docs/sots.md` (source: https://shapeofthesystem.com/) is the authoritative
engineering philosophy for this project and any corpus it analyzes. The 25 tenets
are also ingested into `knowledge.db` as design_notes (provenance `sots`) so
`_get_design_frame` surfaces them automatically during code analysis.

**Read `docs/sots.md` before presenting any design or plan for non-trivial work.**
This is not optional. The tenets surface automatically for code Determined analyzes;
they must also surface for the people building Determined. Do not present a plan,
propose an approach, or start a multi-step implementation without first grounding
in the tenets most live for that decision.

How to use it:
- Identify the 2-3 tenets most live for this decision
- Name the tension if two tenets pull against each other
- Apply the resolution: cognitive load vs. blast radius, weighted by who controls the input
- State which tenets informed the decision and why -- as reasoning, not a checklist

Do not score designs numerically. The tension sections exist because the
interesting decisions are not binary.

## Active work arc: RM59

All prior numbered items (6, 20, 1, etc.) are done. See TRACKER.md for the full
history. Current active item:

**RM59 -- Feature shape analysis (ACTIVE)**
Three new tools: list_features (directory scan), feature_shape (path tracing),
development_priorities (completeness ranking). Corpus-agnostic, directory-first.
See TRACKER.md RM59 for full design. Phase 1 first: list_features + feature_shape.

## Coding guidelines

1. **Read before you write.** Search for existing implementations first.
2. **Simplicity first.** Minimum code that solves the problem.
3. **Surgical changes.** Touch only what the task requires.
4. **Goal-driven execution.** State a brief plan with a verify step for multi-step work.

Full guidelines: `docs/PRACTICES.md`.

## Encoding

Avoid em-dash corruption (ΓÇö = UTF-8 em-dash written through wrong codepage).
Use plain hyphens (-) in docs rather than em dashes when in doubt. If using
bash heredocs, always specify UTF-8 encoding explicitly.
