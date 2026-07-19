Written at commit: 28571da

# SESSION STATE — session 215
Written at commit: 28571da (2026-07-19)

## Active branch: main [V]

## What happened this session

**Design Oracle socket fix [V — 28571da]**
- `oracle_run` background thread now wrapped in `app.app_context()`
- Without it, `socketio.emit(..., to=sid)` silently dropped from background threads
- Fix: `with app.app_context():` around the try/except in `handle_oracle_run`
- Root cause of prior session's debugging spiral — noted in memory as verification stopping rule

**Design Oracle verified live against dj2 [V]**
- Loaded dj2 corpus (158 files · 55 hot · 13 stubs) via DB picker
- Clicked Run in Navigate sidebar — oracle_result arrived immediately
- CRITICAL: `_register_world_tools` [ai_integration.py, 1 caller] — real signal, highest-fanout blocked stub
- OPPORTUNITY: `_get_combat_context`, `_get_encounter_context` [context_builder.py]
- Panel colorization confirmed working in browser

**Memory saved [V]**
- `feedback_verification_stopping_rule.md` — 2 failed checks = name blocker and ask, never escalate; session 214 cautionary example

## Tests [V = verified this session, ? = recalled]

No Python logic changed (ui_server.py threading fix only). Prior suite results carry [?].

## Known issues [V = verified, ? = recalled]

**RM68 subrace dead code [?]:** dj2 game work, deferred by policy.
**design_oracle FOREWARNING [?]:** not exercised yet — needs context= symbol to trigger.
**Shape index symbols [?]:** stub names only; prereq map concept names may not be clickable.
**Server start command [V]:** must use `.venv\Scripts\python.exe`, NOT system pyenv Python — wrong binary breaks all threaded socket handlers silently.

## NEXT SESSION — start here

1. Continue UI redesign arc per `docs/UI_VISION.md`:
   - Ask bar demotion: hide or deprioritize as primary interface
   - GOT model completeness: do other surfaces self-present on corpus load?

2. Exercise FOREWARNING signal: run oracle with `context=_register_world_tools` (or any symbol in the call chain ahead of a blocked stub) to confirm BFS works.

3. Check `docs/TRACKER.md` for RM59 or other open items.

**Server start (standing note):** always use `.venv\Scripts\python.exe -m determined.ui.ui_server` from `C:\Users\bartl\dev\Determined`. Never use pyenv/system Python.
