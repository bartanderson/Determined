Written at commit: 28a5a3c

# SESSION STATE — session 250 (end)

## Active branch: main [V]

## This session (committed) [V]

- `9718102` — feat(tools): add work_session_primer — completion gate compositor tool.
  FSM stubs detected by name pattern (::action:: / ::guard::), grouped by FSM name,
  ranked first (highest handler count wins). Python stubs ranked by existing composite
  score; dead code (concept-not-applicable) suppressed. _primer_items() extracted as
  shared helper. 63/63 test_agent_tools pass.

- `28a5a3c` — feat(ui): WHERE TO START primer section on Shape home. Auto-loads on
  corpus_ready (alongside shapeRun). 5 cards above the 2x2 shape grid. FSM cards have
  [Open spec] → edOpenFile; Python cards have [Classify] → openSpotlight. ↺ refresh.

---

## COMPLETION GATE STATUS [V]

Gate: "be able to determine the first 5 things to do in dj2 and be able to do them from the tool."

**Part 1 — Determination: DONE.**
`work_session_primer()` returns a confident top-5 in one call. Verified on dj2:
  1. [FSM-SPEC] EncounterFSM — 5 handlers (start_combat, resolve_flee, resolve_parley, flee_possible, parley_possible)
  2. [FSM-SPEC] TradeFSM — 4 handlers
  3. [FSM-SPEC] BarterFSM — 3 handlers
  4. [DESIGN-INTENT] _get_encounter_context — context_builder.py:167
  5. [BLOCKED] _get_combat_context or _register_world_tools (tie at 3.4 composite)

**Part 2 — Execution support: PARTIAL.**
Cards show: name, file:line, badge, purpose, action button (Open spec / Classify).
What's missing to fully close the gate:

  A. FSM → Python prereq link not surfaced. Item #4 (_get_encounter_context) is
     unblocked by item #1 (EncounterFSM actions), but the cards don't say so.
     The card for #4 should read: "blocked by: EncounterFSM actions (#1 above)".
     Implementation: after scoring, scan Python stub docstrings for FSM names
     that appear in items 1-N; if found, add a `blocked_by` field to the card.

  B. _register_world_tools is a false positive at #5 (intentional scaffold, not a
     gap). design_oracle marks it CRITICAL; classify_stub marks it blocked-on-prereq.
     Real classification: SCAFFOLD (empty_pass body + "# Add tools here" comment).
     Fix: add scaffold detection to classify_stub — body is empty_pass AND docstring/
     body contains "add" / "register" / "here" pattern → classify as scaffold, skip
     from primer. Or simply: filter stubs where body='empty_pass' AND caller_count=1
     AND concept presence = {} from the Python priority list.

  C. No scaffold generation from the primer cards. [Open spec] shows the FSM JSON
     (correct), but there's no "generate handler stub" button that produces the
     Python skeleton. Next step: add [Scaffold] button that emits project_stub_request
     for an FSM action name (e.g. EncounterFSM::action::start_combat) and renders
     result in fgProjection or a new primer detail area.

  D. "Do them from the tool" — after seeing the spec, user needs to write the Python
     handlers. The natural next tool is scaffold_from_pattern or project_stub. The
     primer should link to whichever the user chooses. Currently requires manual step.

---

## WHAT TO DO NEXT SESSION (priority order)

### Step 1 — Fix false positive at #5 (_register_world_tools)

In `_primer_items()` (`agent_tools.py:10538`), after scoring Python stubs, add a
scaffold detection filter. Check: does the DB docstring or the source body contain
scaffold language ("add", "register", "hook") AND body = empty_pass AND 0 concept
presence signals? If yes, skip from the list. This removes the false [BLOCKED] card.

Alternatively: query `functions` table for stubs where `body` (if stored) is trivially
empty AND name matches known hook patterns. Check how body_shape is stored — it may
be in classify_stub signals, not in the DB.

Quickest fix: in `_primer_items()`, add to the Python stub filter:
  `if top_cls == "blocked-on-prerequisite" and caller_count == 1 and top_score <= 0.40:`
  → check if the body is empty_pass via extract_signals; if yes and concept_presence
  is empty, classify as scaffold and skip.

### Step 2 — Add FSM → Python prereq link to cards

In `_primer_items()`, after building all items, for each Python stub item:
  - extract FSM name mentions from its `purpose` (docstring first line)
  - scan the fsm_groups keys for a match (case-insensitive: "EncounterFSM" in purpose)
  - if match found, add `"blocked_by": {"rank": N, "name": fsm_name}` to the item dict

In `_buildPrimerCard()` (console.html ~line 4470), if `item.blocked_by` exists:
  - render a small "↑ blocked by #N (FSMName)" line below the purpose
  - make it a link that scrolls to card #N in the primer list

### Step 3 — Add [Scaffold] button for FSM action stubs

When user clicks [Scaffold] on an FSM-SPEC card:
  - Emit `project_stub_request` with the first action name
    (e.g. `EncounterFSM::action::start_combat`)
  - OR: emit a new `fsm_scaffold` event that generates all handlers for the FSM
    as a single Python module skeleton
  - Render result in the fgProjection area or a new primer-detail div below the card

The FSM JSON already has action names + docstrings, so a deterministic scaffold is
possible: for each action, generate `def action_name(context): """docstring""" pass`.
No LLM needed. Implement in agent_tools.py as `fsm_scaffold(assessor, args)`:
  args: fsm_name (e.g. "EncounterFSM")
  output: Python module text with stubs for all actions + guards

### Step 4 — Trail bar (if time, low priority)

The "WHERE TO START" cards need a drill-down breadcrumb. See UI_REDESIGN.md ASCII
diagram: `corpus ▸ world/ ▸ _get_combat_context`. HTML/JS only, no backend.
Low priority — the primer cards already give direction. Trail bar is polish.

---

## KEY DESIGN DISCOVERIES (carry into next session)

**FSM stub signal gap**: FSM stubs have docstrings IN THE DB (from fsm_walker ingest)
but classify_stub returns UNCERTAIN because it reads the source file (the JSON), not
the DB row. The DB docstring IS the spec. classify_stub should fall back to the DB
docstring for non-Python files. Fix location: `extract_signals()` in
`determined/agent/classify_stub.py` — when file_path ends in `.json`, read docstring
from the DB instead of parsing the file.

**rank_stubs priority mode excludes FSM stubs entirely**: mode='priority' filters to
`blocked-on-prerequisite` and `design-intent-stated` only. FSM stubs are UNCERTAIN
(0.00 score) → excluded. mode='gap' shows them as genuinely-unknown. This is correct
behavior for rank_stubs; _primer_items() is the right place to handle FSM stubs as
a category.

**design_oracle CRITICAL is not reliable**: marks `_register_world_tools` as CRITICAL
(highest-fanout blocked stub) but it's an intentional scaffold. Do not auto-elevate
CRITICAL from design_oracle in compositor work. The oracle is useful for OPPORTUNITY
signals but its CRITICAL detection is too broad.

**stub_prerequisite_map inverted prereq gap**: the map showed encounter→_get_encounter_context
but didn't surface that EncounterFSM ACTIONS are prerequisites for _get_encounter_context
to be implementable. This is a real gap in stub_prerequisite_map — it only tracks named
prereqs (docstring-stated), not structural FSM→context_builder links.

---

## G7 status [V]

217/217 pass (unchanged this session — no walker/ingestion changes).
63/63 test_agent_tools.py pass (verified this session end).

---

## Known issues (carried)

- CUDA stubs: dim3 vars (block_dim, grid_dim) [?] — accepted ceiling
- C++ pure virtual not captured [V] — deferred to RM73
- Walker dispatch resolution (RM73) — FUTURE, Go interface dispatch highest-value first
- _register_world_tools false positive in primer [V] — Step 1 fix above
- FSM stub classify_stub returns UNCERTAIN despite DB having docstrings [V] — Step 1+
  workaround exists in _primer_items(); deeper fix in classify_stub optional
