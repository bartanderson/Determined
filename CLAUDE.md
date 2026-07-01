# Determined - Project Context

## SESSION START CHECKLIST -- do this before anything else, every session

**Step 1 -- Read SESSION_STATE.md**
Read `SESSION_STATE.md` at the repo root. It is the handoff artifact from the
prior session: what was done, what is next, what is pinned. Do not answer
"what's next" or make any plan until you have read it.

**Step 2 -- Read TRACKER.md**
Read `docs/TRACKER.md` for the current open items and dashboard status.
Do not conflate with SESSION_STATE.md -- TRACKER.md is the authoritative
open-items list; SESSION_STATE.md is the most-recent-session snapshot.

**Step 3 -- Confirm memory is loaded**
Check that the MEMORY.md auto-index has loaded via system context. If Bart
asks about prior decisions, preferences, or constraints, check memory entries
before answering.

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
- Running Ollama queries without Ollama running (`ollama serve`)
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

## Working agreement

- Read/write access to this folder -- edit files in place, no patch files.
- Run `git add` and `git commit` for completed work. Do NOT push -- Bart pushes.
- Before any multi-step sequence, state in one short line what is about to happen
  so Bart can abort. Skip this only for single-step actions.
- Run regression tests before committing: `pytest tests/regression/`
- All 298+ tests must pass. A commit that breaks tests is not done.
- Before ending any session that did substantive work, rewrite SESSION_STATE.md
  in full with current status and next steps. This is mandatory.

## UI verify rule (standing rule, added session 47)

No UI feature is done until clicked in browser. "DONE (unverified)" is not done.
Before committing any UI change: start the server, load a corpus, exercise the
changed interaction, confirm it works. Use /verify or the chrome MCP tools.
5 minutes of real use exposed multiple broken interactions that passed code review.

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

## Active work arc: items 6, 20, 1

Items 9, 10, 19, 7, 22, 23, 24, 25 are all done (see TRACKER.md for details).
Current open items in recommended order:

**Item 6 -- Live sync loop (MEDIUM)**
Re-ingest a single changed file without full corpus re-run. Currently the only
option is full re-ingest (fast at 150 files, but won't scale). Requires:
incremental re-ingestion by file_path, edge delta propagation.
SOTS: XIV (one source of truth for each file's facts), X (idempotent per-file
re-ingest), XXI (don't add a watcher daemon if a simple on-demand call suffices).

**Item 20 -- Call graph accuracy (MEDIUM)**
Type annotation exploitation + __init__ attribute tracking. ~2 days.
Do after item 6 since re-ingest is needed to populate new columns.
See TRACKER.md for full 3-phase plan.

**Item 1 -- files.role (LOW)**
`parse_ast.py` sets role=None. Either implement role classification at ingestion
or remove the column and tool parameter.

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
