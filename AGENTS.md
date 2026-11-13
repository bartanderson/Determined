# Agent entry point (opencode)

This file is the single source of truth for agent behavior in this project. Ignore the
"SESSION START CHECKLIST" in CLAUDE.md — it tells you to read ~33k tokens of files and
will fill your context window before you can start working. Use this file instead.

## Context budget (read this: your window is 32k tokens)

CLAUDE.md's SESSION START CHECKLIST tells you to read many large files. **Do NOT follow it literally** — doing so loads ~33k tokens and fills your context window before you can start working.

**What to actually do at session start:**
1. Read `docs/session-context.md` — it summarizes current work, decisions, and next steps.
2. Read `docs/TRACKER.md` only if you need the open items list (grep first, read whole only if grep returns nothing useful).
3. Everything else (HISTORY.md, UI_REDESIGN.md, DESIGN.md): **do not read whole**. `grep` for what you need.

**Important limits:**
- The plugin cuts unbounded reads of large files to ~8 KB — that is a limit, not an error.
- The "Determined: next work items" brief is added each prompt. Don't read additional large files on top of it.
- Never read HISTORY.md (18k+ tokens) at session start.

## Use these tools instead of the shell

Arguments are passed as data, so there is no quoting to get wrong:

| To do this | Call |
|---|---|
| Ask Determined anything (`work_session_primer`, `readiness_check`, `completion_contract`, ...) | `determined_query` {tool, args, db} |
| Run the targeted tests | `determined_tests` {files, full_files, slow, list}; in a work repo (dj2): {repo, test_paths} with named test files, e.g. test_paths ["tests/unit/test_event_log.py"] |
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
- Throwaway debug scripts go in `.scratch/` in this repository (git-ignored), never in
  `tools/`, `tests/` or a work repo, and never named `test_*.py`. Delete them when done.
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
