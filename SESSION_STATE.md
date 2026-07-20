Written at commit: 893f249

# SESSION STATE — session 227
Written at commit: 893f249 (2026-07-20)

## Active branch: main [V]

## What happened this session

**rank_stubs gains outlier_bonus from detect_conventions signal [V]**

`_compute_outlier_stub_set(conn, scope)` helper added before rank_stubs.
Runs the same three-gate naming-family clustering logic as detect_conventions,
returns set of stub names that diverge from their family's canon.
outlier_bonus=3 added to composite score in priority mode; tagged `+outlier(3)` in output.
All 5 dj2 priority stubs got the bonus — they're all convention outliers. Committed b6094c2.

**RM67 convergence probe run against dj2 [V]**

5-step probe results:
- Stubs: 10 total, split cleanly into 5 RM68 (subrace/dnd_data) + 5 AI-layer. No surprises.
- Unresolved edge ratio: probe script bug (grouping by FQN prefix); dj2 ceiling is accepted.
- ABC gaps: all scopes returned same 8 ABCs — scope param effectively ignored (see known issues).
- EPs: 351 no-inbound-edge functions (accepted ceiling, dynamic dispatch).
- Docstring health: 561/1119 (50%) missing — concentrated in dungeon_app.py and game_state.py.

**RM71 confirmed fully done [V]**

All three phases shipped in prior sessions (scanner s224, normalizer s224, classify_stub
FSM signal s225). TRACKER said phases 1+2 done but missed phase 3. SESSION_STATE handoff
had this wrong. RM71 is complete.

**Structural gap analysis — five corpus-agnostic patterns derived from dj2 phases.py [V]**

Deep investigation of phases.py ABC system revealed:
- 8 ABCs, 0 implementations via subclassing. AuthoritySystem exists in world/authority_system.py
  but has `class AuthoritySystem:` not `class AuthoritySystem(AuthorityPhase):`.
- phases.py imported by ZERO other files. Architecture doc sitting on disk.
- PhaseSystemFactory: 7 create_* abstract methods, 0 implementations. Wiring mechanism never built.
Five generalized patterns documented in HISTORY.md and TRACKER (see Signal Fusion section area).

**Three structural gap tools shipped [V]**

- `find_isolated_modules(oracle, args)` — files that define symbols but never appear in imports.
  Severity-tiered: critical (ABC/interface files), moderate (other). Confirmed on dj2:
  phases.py = [critical], 67 moderate (mostly tests).
- `find_phantom_factories(oracle, args)` — factory ABCs (all create_*/build_*/make_* methods)
  with no concrete subclass. Confirmed on dj2: PhaseSystemFactory flagged correctly.
- `detect_doc_drift` Check 4 added — class role-claim drift. Regex scans class docstrings
  for "Phase:/Layer:/Component:/implements" language, cross-refs against ABC inheritance.
  Gracefully skips if `classes` table absent (older fixture DBs).
13 new tests, 43 total passing. Committed 893f249.

**UI panel space bug filed to TRACKER [V]**

`.sb-section { flex: 1 }` leaves wasted space when child sections hidden. Fix documented:
change to `flex: 0 0 auto`, add collapse-to-label-bar toggle. Deferred to next UI rework pass.

## Known issues [V = verified, ? = recalled]

**find_abc_gaps scope param does nothing [V]:** All 5 probe scopes returned identical 8-ABC output.
The tool queries classes table without filtering by file_path. Not a regression — scope was never
implemented. Low priority fix; the full-corpus view is usually what you want anyway.

**find_isolated_modules — test files are noisy [V]:** 67 of 68 moderate isolations in dj2 are
test files and scripts. Correct signal (tests don't get imported by production) but visually noisy.
Future: add test-path suppression tier or `exclude_tests` arg.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Prose false positives in shape scanner [?]:** .recall/history.md and SESSION_STATE.md
detected as directed_graph from -> arrows in prose. Normalizer errors on these. Acceptable.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

**find_orphaned_interfaces() — Pattern 1, medium effort.**
The last unbuilt structural gap tool. For each ABC in corpus, find classes whose method
name set overlaps >=60% with the ABC's abstract methods but don't declare inheritance.
Query: method name set intersection across classes table. No LLM needed.
This would have caught AuthoritySystem directly: 4/5 AuthorityPhase method names present.

**find_abc_gaps scope fix (low effort, low urgency).**
Add `AND file_path LIKE ?` filter to the abc_classes query when scope arg is present.
Currently scope is accepted but silently ignored. 2-line fix.

**RM69 open design questions (low urgency):**
- Hypothesis count cap (3? all above threshold?)
- Prerequisite map: match named concepts across blocked-on comments
- Ranking formula calibration needs more real cases

**Run capn report when session count reaches 5.**
Counter is at ~2. Notice fires automatically. When it fires: `python scripts/capn.py report`.
