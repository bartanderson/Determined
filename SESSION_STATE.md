Written at commit: 8ec0b8c

# SESSION STATE — session 222
Written at commit: 8ec0b8c (2026-07-20)

## Active branch: main [V]

## What happened this session

**Exploratory analysis session — no engine code changed [V]**

Validated Phase D collapse behavior with dj2 corpus loaded [V]:
- Corpus map: OPEN, Analyze: closed, all others closed — correct.

Ran classify_stub probe against all dj2 stubs [V]. Key findings:
- 5 subrace stubs → [0.97] concept-not-applicable (explicit removal language + sibling cluster). Tool working correctly.
- 5 real-gap stubs: _get_encounter_context [0.70], process_consequences [0.40],
  on_arc_completed UNCERTAIN, _register_world_tools UNCERTAIN, _get_combat_context UNCERTAIN.
- 3 test stubs surfacing in list (known issue: list_stubs test-fixture filter).

**Design discussion — two new TRACKER items filed:**

**RM70 — Convention detector [?]** (TRACKER updated [V])
Bottom-up family clustering: extract naming patterns from corpus, cluster by
structural similarity (calls, returns, body weight), find canonical shape from
members with 3+ threshold, surface outliers by deviation. Three gates: existence
(3+), usefulness (feature agreement), confluence (independent dimensions).
Not a classify_stub signal — standalone tool producing family maps.

**RM71 — Structured data ingestor [V]** (TRACKER updated [V])
"Data as code" framing: FSM configs, build DAGs, OpenAPI specs, package manifests
all reduce to named nodes + directed edges. Normalize to existing graph schema.
Same reasoning layer (path finding, prerequisite chains, orphan detection) applies
without modification. Priority: FSM JSON → build files → package manifests → OpenAPI.
Unlocks: config-layer evidence for blocked-on-prerequisite; combat gated behind
encounter is visible in encounter.json fight→resolving_fight→start_combat transition.

**Key methodology note filed to memory and HISTORY:**
Domain knowledge from corpus designers goes into Claude's interpretation context only —
never into tool scoring. Tool earns conclusions from corpus signals. The flip (using
Determined to drive fixes in dj2) happens when the tool is sharp enough.

## Known issues [V = verified, ? = recalled]

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs; tool queries bare names. Workaround: use graph_path.

**list_stubs surfaces test fixtures [V]:** check_parley, get_player_by_session,
test_encounter_parley_failure appear in dj2 stub list. Filter needed in corpus_projections.

**classify_stub can't see support-structure depth [?]:** two stubs identical at call
site but completely different backing infrastructure look the same to the scorer.
_get_encounter_context vs _get_combat_context is the concrete example.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

No code changes this session. Pick up from RM69 implementation or RM70/RM71 design.

**Most actionable next step:** fix the test-fixture filter in corpus_projections.py
(list_stubs excluding test paths) — small, concrete, verified gap.

**Then:** look at classify_stub scoring for the "has callers, no other signal" case —
`on_arc_completed` and `_register_world_tools` both have live callers but score UNCERTAIN.
Caller-present with no doc and empty body should lean toward blocked-on-prerequisite.
Calibration question: what threshold nudge makes that correct without breaking other cases?

**Trap to watch:** domain knowledge goes into interpretation, not tool logic. Before
adding any new classify_stub signal, ask: is this derivable from corpus alone?
