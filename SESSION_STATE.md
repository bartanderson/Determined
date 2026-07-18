# SESSION STATE — session 208
Written at commit: 6688a84

## Active branch: main [V]

## What happened this session (2026-07-18)

### 1. Discovered all 4 UX gaps already fixed [V]

Session started with intent to fix 4 UX gaps from session 207. Git log
confirmed they were committed in ab082a3 last session:
1. Frontier auto-load on corpus_ready — fgLoad_() call in corpus_ready handler
2. Frontier ABC mode "No frontier edges" — @abstractmethod decorator check
3. Corpus map "0 files" bug — dupes query isolated (dj2 lacks class_name column)
4. development_priorities via Ask bar — heuristic + _PATTERNS + bypass added

All 4 were done. Tests confirmed: 1144 pass, 1 skip [V].

### 2. Full regression suite retired [V]

User: 6-minute full suite is too expensive per change.
Decision: match-first rule — run only the test file(s) from TEST_MAP.md for
the changed module. Full suite only if something looks broken.

- Created docs/TEST_MAP.md — source module → test file mapping for all 70+ test files
- Updated CLAUDE.md standing rule: no full suite after edits, ever
- Committed: 9e9b1f2

### 3. Work focus clarified [V]

Determined, not dj2. Saved to memory (feedback_work_focus.md). Do not suggest
dj2 work as next step unless Bart explicitly asks.

### 4. Shape tab shipped [V]

All CLOSURE.md phases complete — gate open. Surfaced RM69 corpus projections
in the UI as a new "Shape" tab in the More dropdown.

**What it does:**
- Auto-runs all 4 corpus-shape tools on first click
- Scope input (e.g. "world/") to restrict to a subsystem
- 2x2 grid: File shape, Subsystem shape, Prerequisite map, Concept ghost map
- Verdict keywords color-coded: design-skeleton (blue), dead-concept (orange),
  GHOST (red), live (green)

**Backend:** shape_run socket event in ui_server.py dispatches all 4 tools in
one thread, returns structured result.

**Verified live [V]:** dj2 corpus — CombatFSM [GHOST], world/ dead-concept
dominant, encounter prereq — all correct. 46 tests pass (test_corpus_projections
+ test_ui_surfaces).

Committed: 6688a84

## NEXT SESSION — start here

**CLOSURE.md gate is open. UI redesign is the active arc.**

Shape tab is the first new projection surface. What's still open:

### Priority 1: Context modes (UI_VISION.md item #7)
Design/Trace/Review mode buttons exist (banner, tab highlight) but are partial.
Full intent: each mode presents a curated set of surfaces, suppresses noise,
guides the user toward the right tools for that context. Read UI_VISION.md
item #7 before designing anything.

### Priority 2: Frontier ABC mode render (arch-void)
The ABC filter in Frontier shows the graph visualization. Arch-void ABCs
(0 subclasses, engine/phases.py 8 interfaces) have no graph edges so the
graph is empty. Need a separate render path: when mode=abc, show the
UNIMPLEMENTED INTERFACES text output instead of (or alongside) the graph.
The backend find_abc_gaps tool already returns the right data.

### Priority 3: Burnishing
Small improvements that surface naturally during use. See TRACKER.md
Deferred/Burnishing section. Log, don't fix mid-arc.

## Known issues [V = verified, ? = recalled]

**TEST_MAP.md [V]:** source -> test mapping built; CLAUDE.md updated.
**Shape tab [V]:** live, committed, 46 tests pass.
**CLOSURE.md gate [V]:** all 3 phases checked off.
**walk_call_chain TS/JS FQN [V]:** graph_edges stores FQN callers; tool
  queries bare names -> chain length 0/1. Workaround: use graph_path.
**classify_stub file_path_hint TS [V]:** path matching fails; omit file_path.
**graph_path FQN JS [V]:** some module.method pairs return no path despite edge.
**Frontier ABC UI [V]:** shows "No frontier edges" for arch-void — needs
  separate render path for zero-subclass ABCs.
**narrative_engine latent bug [?]:** on_arc_completed references self.active_quests
  but commented out — AttributeError at runtime if arc completes. (dj2, not Determined)
**engine/phases.py ABC void [V]:** 8 interfaces, 0 implementations (dj2).
**Corpus map dupes query [V]:** isolated from files/hot/stubs to handle DBs
  without class_name column (dj2 style).
