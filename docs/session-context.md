# Session Context

> Auto-loaded at session start via OpenCode instructions.
> Keep this current so every session begins with full orientation.

## Current work

<!-- What are we actively building? Be specific. -->
- Last merged: `feat/equip-agent-enhancements` (class-aware defaults, supplies, cost tracking, take defaults shortcut)
- All stale branches purged. Repo clean on main.
- Next: TBD — awaiting direction

## Recent decisions

<!-- Key choices and their rationale. Delete old entries that are no longer relevant. -->
- **Skip infrastructure improvements** (delegation, governance, isolation). Feature-branch pattern covers isolation; local models have no budget risk; already have the tools needed.
- **Durable execution** — only if a process-die scenario occurs in practice.
- **Branch management**: merge before accumulating, delete stale branches promptly.

## Open questions

<!-- Things to decide or investigate. -->
- N/A

## File map

<!-- Paths to files the agent should know about for this project. -->

### Core project (Determind analysis tool)
- `docs/DESIGN.md` — Architecture and design principles
- `docs/TRACKER.md` — Active open items
- `docs/HISTORY.md` — Historical decisions (grep, don't read whole)
- `docs/GETTING_STARTED.md` — Setup instructions
- `docs/PRACTICES.md` — Working agreements
- `docs/AGENT_PARITY.md` — What each agent wires up

### Work repository (dj2)
- `C:/Users/bartl/dev/dj2/` — Determined game work repo (edit on feature branches only)
- `C:/Users/bartl/dev/dj2/world/equip_agent.py` — Equip agent logic
- `C:/Users/bartl/dev/dj2/world/dm_chat_handler.py` — DM chat handler, equip wiring
- `C:/Users/bartl/dev/dj2/world/narrative_system.py` — Narrative system, character finalization

### Configuration
- `opencode.json` — OpenCode config (model, providers, permissions)
- `determined.cfg` — Determined tool config (LLM profiles, work repos)
- `CLAUDE.md` — Agent entry point (read on new sessions)
- `AGENTS.md` — Agent instructions for this workspace

## Next steps

<!-- What should happen next? Update at session start. -->

---
*Last updated: 2026-11-12*
