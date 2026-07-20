Written at commit: ba82a15

# SESSION STATE — session 225
Written at commit: ba82a15 (2026-07-20)

## Active branch: main [V]

## What happened this session

**`_get_combat_context` resolved — DONE [V]**

Added signal 10 to extract_signals: config-layer FSM presence.
- Direct: concept IS an FSM with config entries → mild design-intent-stated boost
- Indirect: concept appears in another FSM's action name (e.g. EncounterFSM.start_combat)
  but has no own config file → blocked-on-prerequisite +0.8
Result: _get_combat_context → blocked-on-prerequisite [0.43] with evidence
"concept referenced by config FSM action(s) (EncounterFSM.start_combat) but has
no config file — config-gated prerequisite". 42/42 tests passing. [V]

**Calibration run on known-answer stubs [V]**

- _get_combat_context → blocked-on-prerequisite [0.43] CORRECT
- _get_encounter_context → design-intent-stated [0.70] — arguably correct;
  EncounterFSM has config entries + Encounter classes exist + docstring states intent.
  Expected blocked-on-prerequisite was our assumption, not ground truth.
- Subraces excluded: RM68 DEFERRED, not classify_stub test cases.

**MCTS + knowledge-compiler synthesis captured in TRACKER [V]**

Detailed FUTURE section written: Determined as oracle → MCTS explores signal space
→ resolution paths as training data → small model. Untapped signals also captured:
imports table, dead artifacts, return_type existence, behavioral_contracts.

**RM70 detect_conventions shipped [V]**

determined/agent/agent_tools.py — bottom-up naming family discovery, three gates:
- Existence (3+ functions share naming prefix/suffix)
- Usefulness (2+ feature dims agree >=70%): callers, callees, return_type, param_count, body_weight
- Confluence (agreeing dims span 2+ feature categories)
Output: family canon, per-member match/diverge, outlier surface.
On dj2: 140 families. Stubs like _get_combat_context surface as outliers in `get` family.

**RM69 step 6 rank_stubs shipped [V]**

Three modes:
- priority: actionable stubs ranked by caller_count * confidence + chain_bonus
- gap: all stubs grouped by classification, sorted by confidence
- perusal: top 2-3 interesting stubs for a scope
Excludes test files. On dj2: 6 actionable stubs in priority mode; subraces at
concept-not-applicable [0.97] correctly buried.

Both registered in TOOLS, tool_registry, and test_agent_tools expected set.
11 new tests in test_conventions_and_ranking.py. 188 tests passing. [V]

## Known issues [V = verified, ? = recalled]

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Prose false positives in shape scanner [V]:** .recall/history.md (95%) and
SESSION_STATE.md (65%) detected as directed_graph from -> arrows in prose. Normalizer
correctly errors on these since it only handles structured formats. Acceptable for now.

**detect_conventions at corpus scope is noisy [V]:** 140 families on dj2 with no scope.
Scope param helps. Threshold tuning (min_family, agreement %) needs calibration against
real use cases before the output is agent-friendly at full corpus scale.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

**Calibrate detect_conventions output.** 140 families at full corpus is noisy.
Two levers:
1. Raise min_family (try 5) to filter small clusters
2. Raise agreement threshold (try 80%) to require tighter canons
Run against dj2 with different settings and find a threshold where output is
useful without being overwhelming. Target: <20 families at corpus scope.

Command:
```
.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.')
from determined.oracle.db_oracle import DBOracle
from determined.agent.agent_tools import detect_conventions
oracle = DBOracle('C_Users_bartl_dev_dj2.db')
print(detect_conventions(oracle, {'min_family': 5}))
" 2>$null
```

**Thread convention outlier score into rank_stubs composite (optional).**
Currently rank_stubs uses caller_count * confidence + chain_bonus. Convention
outlier status (stub that diverges from its naming family canon) is a natural
additional signal. Wire detect_conventions result into rank_stubs priority mode.

**Untapped signals (FUTURE, not urgent):**
- imports table: concept named in docstring but not imported anywhere → concept-not-applicable
- dead knowledge_artifacts matching concept: corpus-wide annotation, strong signal
- return_type existence: named type not in classes table → concept-not-applicable
See TRACKER FUTURE section for full design.

**RM69 open design questions remaining (from TRACKER):**
- Hypothesis count cap (3? all above threshold?)
- Prerequisite map: match named concepts across blocked-on comments
- UI/flow: how corpus-level projections surface (blocked on UI redesign)
- Ranking formula calibration needs more real cases
