# Agent entry point (opencode)

Project instructions live in `CLAUDE.md` and are the single source of truth. Read it
in full before doing anything else, including its SESSION START CHECKLIST, then work
from `SESSION_STATE.md` and `docs/TRACKER.md`. Do not duplicate its rules here.

Differences when running under opencode instead of Claude Code:

- The shell is Windows PowerShell 5.1 (`&&` is invalid; chain with `;` or `if ($?)`).
  A guard blocks Bash-isms and wrong-interpreter commands and tells you why.
- Call Determined tools with the `determined_query` tool (`tool`, `args`, `db`), not
  `python tools/query.py` with JSON on the command line (PowerShell strips the quotes).
- A "Determined: next work items" brief is added to your context each prompt. Take
  the first card, run `readiness_check` then `completion_contract` before writing code.
- Tests: `.venv\Scripts\python tools\run_tests.py`; never the full suite, never in
  the background. Commit completed work; never push (Bart pushes).
- The session scratchpad and Claude-specific tools named in CLAUDE.md do not exist
  here; keep `session_arc.md` in a temp or scratch folder you create.
- Details of what each agent wires up: `docs/AGENT_PARITY.md`.
