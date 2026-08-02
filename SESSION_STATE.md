Written at commit: 95c31b4

# SESSION STATE — session 286 (end)

## Active branch: main [V]

## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**RM74 probe — all 6 canonical questions ran on dj2** [V]
- Q1 (entry points): 385 EPs, top by fan-out correct. No gaps.
- Q2 (stubs): 20 stubs, 4 real gaps with callers, 12 FSM islands, 4 subrace dead code. No false positives.
- Q3 (stub islands): 24 islands. _get_encounter_context and _get_combat_context appear as islands
  because their callers are also stubs — correct, not a bug.
- Q4 (feature_shape): **GAP-7 found** — returns "No symbols found" because feature_path expects
  a file-path fragment (e.g. "encounter/"), not a keyword. No routing layer maps keyword → path.
- Q5 (ABC gaps): 8 ABCs in phases.py, all intentional scaffolds. GAP-6 still open.
- Q6 (graph_path): GAP-5 fix confirmed working — reports two unregistered Flask routes
  (/api/resolve-encounter, /api/travel-progress). [V]

**GAP-7 logged in TRACKER.md** [V]
- feature_shape keyword→path gap documented. Fix: heuristic in query router or clearer error message.

**RM76 analyst wire-in** [V] (commit 95c31b4)
- Discovered decisions.toml, decisions_ledger.py, and init() hook were all already implemented.
- The one missing piece: `_enrich_with_stub_status` in local_agent.py queried
  `kind IN ('design_note','finding','sots')` — 'decision' was absent.
- Fix: added 'decision' to the kind list. Decisions from decisions.toml now surface in
  Section 5 (DESIGN) of domain analysis output.
- Verified: encounter analyst returns 3 decision artifacts when queried.
- 21 tests pass (test_domain_analyst.py). [V]

---

## WHAT IS NOT YET DONE

- dj2 decisions.toml: still untracked in dj2 git (dj2-repo concern, not a Determined task).
- GAP-6 (ABC scaffold intent): deferred to decisions.toml annotation — decisions.toml now
  has `phases_abstract_methods` entry that covers this. Could close GAP-6 by wiring
  find_abc_gaps to check for a matching decision artifact before alarming.
- GAP-7 (feature_shape keyword routing): unaddressed.

---

## WHAT TO DO NEXT SESSION

1. **GAP-7** — fix feature_shape routing. Two options:
   (a) In the query router, when feature_shape returns "No symbols found", scan file paths
       for the keyword, pick the best matching prefix, retry. One function in local_agent.py.
   (b) Improve the error message to guide the LLM narrator to ask for a path.
   Option (a) is the right fix — it closes the gap rather than explaining it.
   First command: grep for where feature_shape is called in local_agent.py to find the
   routing hook.

2. **GAP-6 close** — find_abc_gaps could check for a matching 'decision' artifact on the ABC's
   file/subject before flagging as "architecture void." Small addition to find_abc_gaps().
   Low complexity, high signal quality improvement.

3. **RM73/RM21** — pick based on what next dj2 probe surfaces. No blocker yet.

---

## KNOWN ISSUES / TRAPS

- _wrap_body() must be used anywhere in sketch_stub.py that parses a body fragment. [V]
- line_number=0 trap: queries on functions table ordered by line_number must exclude
  line_number=0 to avoid config-declared entries crowding out Python functions. [V]
- _pull_type_defs has two paths: (1) classes table for Python types,
  (2) functions LIKE 'TypeName::%' for FSM/protocol entities. [V]
- export_context session is in-memory; resets on server restart. Intentional. [V]
- GAP-5 fix (fetch dead-end detection) only finds fetch() calls stored as raw callee
  strings in graph_edges. If JS walker improves and stores http_fetch edges instead,
  _explain_missing_path needs updating. [?]
- feature_shape requires feature_path argument as a file-path fragment, not a keyword.
  GAP-7 — not yet fixed. [V]
- Second query in local_agent.py ~line 813 already had 'decision' in its kind list.
  Only the _enrich_with_stub_status query (line ~488) was missing it. Both now correct. [V]

---

## RESOURCE / PROCESS RULES [V]

- llama-server: stateless, no reason to kill between UI restarts.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it.
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate.
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py` — llama-server must be up first.
