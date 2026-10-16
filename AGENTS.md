# Agent entry point (opencode)

Project instructions live in `CLAUDE.md` and are the single source of truth. Read it
(about 4k tokens), then `SESSION_STATE.md` (about 3k). Do not duplicate its rules here.

## Context budget (read this: your window is 32k tokens)

CLAUDE.md's SESSION START CHECKLIST was written for a much larger context. Following it
literally reads about 33k tokens of files and overflows yours (HISTORY.md alone is ~18k).
So here, do steps 1 and 3 only, and treat the rest as lookups, not reading:

- `docs/TRACKER.md`, `docs/HISTORY.md`, `docs/UI_REDESIGN.md`, `docs/DESIGN.md`: do not read
  whole. `grep` for the item or keyword you need, or read a range with `offset` and `limit`.
- Skip step 5 (session arc file) unless asked.
- The plugin cuts an unbounded read of a large file to ~8 KB and tells you how to get the
  next part; that is a limit, not an error.
- The Determined brief below your instructions already says what is open and what a
  verified bundle covers. Start from it.

## Use these tools instead of the shell

Arguments are passed as data, so there is no quoting to get wrong:

| To do this | Call |
|---|---|
| Ask Determined anything (`work_session_primer`, `readiness_check`, `completion_contract`, ...) | `determined_query` {tool, args, db} |
| Run the targeted tests | `determined_tests` {files, full_files, slow, list} |
| git status, diff, log, add, commit, push | `determined_git` {action, paths, message} |
| Run a Python script with the venv | `determined_python` {script, args} |

The shell blocks commands these tools cover and tells you which tool to use. Push with
`determined_git` action `push`: it runs the pre-push check first and never forces. The
repo is public, so never name private projects in commits, docs or code. Never run the
full test suite or run tests in the background.

These tools never start a model server on their own. Determined tools that need the
analysis LLM (reason_about, infer_behavior, narration) return "unavailable" until one
is running. Start one with `determined_python` (script `tools/llm_server.py`, args
`["start", "--profile", "analysis"]`).

## Shell (Windows PowerShell 5.1) for everything else

- No `&&` / `||`: chain with `;` or `if ($?) { ... }`. No heredocs (`<<`), no `/dev/null`
  (use `$null`), no `export` (use `$env:NAME = 'value'`). `bash`, `sh` and `wsl` are blocked.
- Use single quotes for literal strings; use full paths with the venv interpreter
  `.venv\Scripts\python.exe`.
- JSON on a command line loses its double quotes. Use the tools above instead.

## Other differences from Claude Code

- A "Determined: next work items" brief is added to your context each prompt. Take the
  first card, run `readiness_check` then `completion_contract` before writing code.
- The session scratchpad and Claude-specific tools named in CLAUDE.md do not exist
  here. Do not create `session_arc.md` or any other file outside the repository; there
  is no scratch folder for you. If you need notes, put them in your reply or in a file
  inside the repo that you then commit.
- Where you may edit: this repository, and the work repositories in determined.cfg
  `[agent] work_repos` (dj2). Anything else is refused by the plugin. dj2 is your
  working target: build there. Rules, enforced by the plugin and `determined_git`:
  1. In dj2, create a feature branch first (`determined_git` action `switch`, `repo`
     = the dj2 path, `branch` = `feat/<name>`). Edits on main/master are refused.
  2. Use `determined_git` with `repo` for add, commit and push in dj2 (the shell
     blocks git). Push sends a feature branch only, after the pre-push check; a person
     merges it.
  3. Do not hand-write what a verified handoff bundle already contains. When the primer
     says a bundle is "pending apply", apply it: `determined_git` action `apply_bundle`
     with `repo` = the dj2 path and `bundle` = its 3-digit id, on your feature branch.
     One call per bundle, in ascending id order, reading each result first (bundles are
     cumulative; the tool refuses out-of-order, unverified, dirty-tree or main-branch
     applies, runs the bundle's tests, commits "bundle NNN", and restores the repo on
     any failure). Handlers listed as "not changed by the bundle" may already exist or
     be mapped in the registry: check with `completion_contract` first.
- What each agent wires up: `docs/AGENT_PARITY.md`.
