# docs/ — what lives where and why

One rule: if you're about to put something in a doc and you're not sure which one,
check this file first. If the right home isn't listed, add a new entry here at the
same time you create the new doc.

---

## Active work

| File | Purpose |
|------|---------|
| **TRACKER.md** | Open RMs with owners and gates. Nothing FUTURE, nothing DONE. If it's not being actively worked or gated on a near-term trigger, it doesn't live here. |
| **SESSION_STATE.md** (repo root) | Per-session handoff artifact. Overwritten each session end. |

---

## Architecture and decisions

| File | Purpose |
|------|---------|
| **DESIGN.md** | System shape, layer architecture, major future directions (MCTS, cross-language, knowledge layer). The structural "why." |
| **ANALYSIS_MODEL.md** | The investigation arc — SEE→RECOGNIZE→PROJECT→TEST. Conceptual model of what the tool does. Companion to DESIGN.md's technical architecture. |
| **HISTORY.md** | Non-obvious decisions, failed approaches, constraints with reasons. Pruned when stale. The "why we didn't do X" layer. |
| **PRACTICES.md** | Engineering standards: how we work, what to check before writing code. |
| **sots.md** | The 25 shape-of-the-system tenets. Ingested into corpus DB as design_notes. |

---

## UI

| File | Purpose |
|------|---------|
| **UI_VISION.md** | GOT model — the north star philosophy for the UI. What it's for and why it's shaped the way it is. |
| **UI_REDESIGN.md** | Future UI work phases and design specs. Specific planned changes, gates, implementation details. |
| **UI_EVAL.md** | UI capability evaluated against the 6 canonical probe questions. Update in place as gaps are resolved. |

---

## Design specs (active future arcs)

These are living docs for work arcs that have gates — not yet in TRACKER because
the gate hasn't cleared, but too detailed and specific to live in DESIGN.md.

| File | Purpose |
|------|---------|
| **VISUAL_PROJECTION.md** | Signal fusion + multi-modal visual projection design. Phases 1-3. |
| **SLATER.md** | Slater integration arc — graph DB, vector search, generation model, Cypher migration. |

---

## Operational reference

| File | Purpose |
|------|---------|
| **SETUP.md** | How to install and run the tool. |
| **GETTING_STARTED.md** | User-facing introduction — how to use Determined on your own codebase. |
| **TEST_MAP.md** | Source file → test file mapping. Keep in sync with FILE_MAP in tools/run_tests.py. |

---

## Corpus-specific

| File | Purpose |
|------|---------|
| **COMMONPLACE_VISION.md** | Commonplace as demo corpus and guided journey vehicle — dual role, design intent. |
| **COMMONPLACE_USER_JOURNEY.md** | The actual journey content — what a user sees when walking the Commonplace arc. |

---

## Changes to this structure

Log here when a doc is added, merged, or retired. One line per change.

| Date | Change |
|------|--------|
| 2026-07-25 | Initial structure established. TRACKER.md pruned to active items only. FUTURE blocks moved to DESIGN.md, SLATER.md, UI_REDESIGN.md, VISUAL_PROJECTION.md. archive/ deleted (superseded, git has it). |
