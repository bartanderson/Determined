Written at commit: 883dec7

# SESSION STATE — session 212
Written at commit: 883dec7 (2026-07-18)

## Active branch: main [V]

## What happened this session

**_IMPL_WHEN_RE — SetFit false-positive fix [V — d8e9a63]**
- `determined/agent/stub_classifier.py`
- "will be implemented when X is built" was classified as concept-not-applicable (57%)
  by SetFit. The scoring suppresses intent when removal fires (`if has_intent and not
  has_removal`), so the classification compounded badly.
- Fix: `_IMPL_WHEN_RE` fast-path added. `has_removal()` returns False early when matched;
  `has_intent()` returns True early. Deterministic override of model.
- Verified: `has_removal(text) = False`, `has_intent(text) = True` on the actual stub text.
- 41 classify_stub tests pass [V].

**Live UI walkthrough — dj2 + dungeoncrawler [V]**
- Loaded dj2 corpus, exercised all three modes (Design/Trace/Review), spotlight,
  shape tab, call tree, frontier, ask bar, topology.
- Loaded dungeoncrawler (TS) corpus, confirmed call tree FQN bug live.

**Work queue filed in TRACKER.md [V — 883dec7]**
- 7 items, priority ordered, each with file + line number.
- See "Work queue — post-walkthrough" section at top of TRACKER.md.

## Tests [V]
41 passed (test_classify_stub.py). No other engine files changed this session.
Last known full suite: 1144 pass, 1 skip (session 209 / CLOSURE.md Phase 1c).

## NEXT SESSION — start here

**Pick up work queue item 1 from TRACKER.md:**

Test stubs filter in `_fetch_stubs()`:
- File: `determined/agent/corpus_projections.py:80`
- Problem: `_fetch_stubs()` has no test-path filter; test files appear in shape output.
- Fix: copy `NOT LIKE '%/test_%'` / `NOT LIKE '%\\test_%'` / `NOT LIKE '%/tests/%'` /
  `NOT LIKE '%\\tests\\%'` conditions from `agent_tools.py:1646` into the WHERE clause
  in `_fetch_stubs()`. One fix covers all four projection tools.
- Test file: `tests/regression/test_corpus_projections.py` (check TEST_MAP.md to confirm).

After that: item 2 (TS call tree FQN, `agent_tools.py:521`), then RM68.

## Known issues [V = verified, ? = recalled]

**Test stubs in shape output [V]:** `_fetch_stubs` in corpus_projections.py:80 has no
  test-path filter. test_encounter_fsm.py shows as 33% density at top of file shape.
  Fix described in TRACKER work queue item 1.
**walk_call_chain TS/JS FQN [V]:** agent_tools.py:521 queries bare name; TS stores FQNs.
  addLogMessage (dungeoncrawler, HOT) shows "(no callees)". Workaround: Graph tab.
  Fix described in TRACKER work queue item 2.
**classify_stub file_path_hint TS [V]:** agent_tools.py:4817 exact match fails for TS paths.
  Workaround: omit file_path arg. Fix described in TRACKER work queue item 4.
**Ask routing miss [V]:** "what should I work on next?" routes to prioritize_work, needs
  workflow items. Returns "No active work items" when none exist. Fix: TRACKER item 5.
**world/ verdict misleading [V]:** dead-concept dominant due to 5 subrace stubs (RM68).
  Clears after RM68 removes them. TRACKER item 3.
**_get_encounter_context misclassification [V — FIXED d8e9a63]:** was concept-not-applicable,
  now correctly blocked-on-prerequisite via _IMPL_WHEN_RE.
**Shape index symbols [?]:** only stub names in index; prereq map concept names may not
  be clickable if not function names.
**graph_path FQN inconsistency [V]:** some JS module.method pairs find path, others don't.
  TRACKER item 7 (polish).
**list_stubs [V]:** already filters test files correctly. The gap is corpus_projections.py only.
