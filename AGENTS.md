# Agent entry point (opencode)

Project instructions live in `CLAUDE.md` and are the single source of truth. Read it
in full before doing anything else, including its SESSION START CHECKLIST, then work
from `SESSION_STATE.md` and `docs/TRACKER.md`. Do not duplicate its rules here.

## Use these tools instead of the shell

Arguments are passed as data, so there is no quoting to get wrong:

| To do this | Call |
|---|---|
| Ask Determined anything (`work_session_primer`, `readiness_check`, `completion_contract`, ...) | `determined_query` {tool, args, db} |
| Run the targeted tests | `determined_tests` {files, full_files, slow, list} |
| git status, diff, log, add, commit | `determined_git` {action, paths, message} |
| Run a Python script with the venv | `determined_python` {script, args} |

The shell blocks commands these tools cover and tells you which tool to use. Never
push; Bart pushes. Never run the full test suite or run tests in the background.

These tools never start a model server on their own. Determined tools that need the
analysis LLM (reason_about, infer_behavior, narration) return "unavailable" until one
is running: `tools/llm_server.py start --profile analysis` (via `determined_python`).

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
  here; keep `session_arc.md` in a temp or scratch folder you create.
- What each agent wires up: `docs/AGENT_PARITY.md`.
