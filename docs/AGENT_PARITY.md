# Agent parity: Claude Code and opencode

Determined can be worked on from Claude Code or from opencode. The repo, not either
agent, owns the state: CLAUDE.md (rules), SESSION_STATE.md, docs/TRACKER.md, the
handoff bundles. Switching agents is safe as long as this file's table stays true.

Check it any time (exit 0 = in parity):

    .venv\Scripts\python tools\check_agent_parity.py

The machine-readable manifest is `docs/agent_parity.json`. When you wire a new hook
or change the model server, update the manifest and this table in the same commit.

## What each agent uses

| Capability | Claude Code | opencode |
|---|---|---|
| Instructions | `CLAUDE.md` | `AGENTS.md` -> says read `CLAUDE.md` (opencode v2 did not auto-load CLAUDE.md) |
| Shell guard (Bash-isms, wrong paths) | `.claude/hooks/validate_shell.py` | same script, run by the plugin before every `shell` call |
| Wrong-interpreter guard | `~/.claude/hooks/check_venv_python.py` (user level) | same script, if present |
| Session start context | `.claude/session_start_hook.py` | AGENTS.md checklist + `work_session_primer` brief added each prompt |
| Determined tools | `python tools/query.py` | `determined_query` tool (no JSON quoting through PowerShell 5.1) |
| Targeted tests | `python tools/run_tests.py` | `determined_tests` tool (shell route is redirected to it) |
| git add / commit | `git ...` via the shell | `determined_git` tool (message passed as data; no push/reset/amend) |
| Run a venv script | `.venv\Scripts\python.exe x.py` | `determined_python` tool |
| bash / sh / wsl from the shell | blocked by `validate_shell.py` | same script, plus `opencode.json` deny rules |
| Skills | `.claude/skills/` | same folder, read natively |
| Commands | `.claude/commands/` | `/next` registered by the plugin; others not ported |
| capn trap registry hook | `scripts/capn_hook.py` | **not ported** (listed `claude_only`) |
| Model | Claude | local llama-server `agent` profile (port 8083), `local/qwen36-35b` |
| Permissions | `.claude/settings.json` | `opencode.json` `permissions` (default there is allow-all) |

## Starting and stopping the local model

    .venv\Scripts\python tools\llm_server.py start --profile agent
    .venv\Scripts\python tools\llm_server.py stop  --profile agent

One server fits in VRAM at a time; `start` refuses to stack a second.

## Known differences and gaps

- opencode has no session-start or stop hook in v2.0.29, so grounding gates that run
  at stop time cannot be ported; the AGENTS.md checklist and the per-prompt brief
  stand in for the start-of-session behavior.
- The permission hook sees pieces of compound commands, so whole-command guards
  run in `tool.execute.before`, where the raw command is visible.
- The 8 GB card limits the local model; judgment-heavy work may belong in Claude.
- opencode v2.0.29 does not auto-load `CLAUDE.md`; `AGENTS.md` is the entry point.
  The v1 docs that search engines return first describe a different plugin API
  and config keys; use opencode.ai/v2/docs.
- Claude hook scripts block in two shapes (exit 2 with a deny decision, or exit 0
  with `{"decision": "block"}`); the plugin honors both. New guards should be added
  to `docs/agent_parity.json` so the parity check keeps both agents in step.
- Shell redirects point at opencode-only tools, so they live in the plugin, not in
  `validate_shell.py` (which Claude Code also runs).
- Guard hooks scan command text. A literal `&&`, bare `python`, or `rm -rf *` inside
  a commit message or prompt string trips them; pass such text in a file.
- Open parity items and follow-ups are tracked in `docs/TRACKER.md` (RM74-RM79).

## Switching back and forth

1. Finish the task and commit; update SESSION_STATE.md as usual (add a "last agent" line).
2. Next session, either agent: run the drift check (`git diff <handoff-SHA>..HEAD --stat`,
   including `.claude`, `.opencode`, `opencode.json`, `AGENTS.md`, `docs/agent_parity.json`)
   and `tools/check_agent_parity.py`.
3. If parity reports drift, fix the manifest or the missing side before real work.
