Written at commit: b9fc4cf

# SESSION STATE — session 228
Written at commit: b9fc4cf (2026-07-20)

## Active branch: main [V]

## What happened this session

**find_orphaned_interfaces() shipped [V]**

Pattern 1 of the structural gap framework — the last unbuilt tool.
For each ABC, finds classes whose method name set overlaps >= threshold with
the ABC's abstract methods but don't declare inheritance.

Two tiers: `strong` (>= 60%), `possible` (>= threshold, default 40%).
`scope` and `threshold` args, consistent with other structural gap tools.

Smoke test on dj2: AuthoritySystem surfaces as `[possible]` orphan of
AuthorityPhase. overlap=40% (2/5). Matched: validate_action, roll_dice.
Missing: check_permissions, query_dungeon_constraints, query_world_constraints.

Note: session 227 handoff claimed "4/5 methods present" — actual DB shows 2/5
exact matches. The 40% default threshold was calibrated to catch it.

7 new tests, 20/20 passing in test_structural_gap_tools.py.
Committed b9fc4cf.

**TRACKER.md: API vs subscription evaluation item added [V]**

Prompted by stencil.so/blog/snapcompact (render context as pixel-font bitmap,
carry at 1/3 input token cost, near-verbatim recall). Key finding: prose
compaction shreds facts; SESSION_STATE.md approach is validated by the research.
We can't hook Claude Code's built-in compaction without API access.
TRACKER item documents the evaluation decision gate and links the article.

**Cap'n report run [V]**

0% hit rate across 6 sessions. Trap cache has 3 entries (1 stale). The misses
are real: graph_edges column names keep being re-derived. Chart on next hit.

## Known issues [V = verified, ? = recalled]

**find_abc_gaps scope param does nothing [?]:** All scopes return identical output.
Tool queries classes table without file_path filter. 2-line fix, low priority.

**find_isolated_modules — test files are noisy [V]:** 67/68 moderate isolations
in dj2 are test files. Correct signal but visually noisy. Future: test-path
suppression tier or `exclude_tests` arg.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs; tool queries bare names. Workaround: use graph_path.

**Prose false positives in shape scanner [?]:** SESSION_STATE.md and history.md
detected as directed_graph from -> arrows. Normalizer errors on these. Acceptable.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

**All 4 structural gap pattern tools are now complete [V].**
Pattern 1: find_orphaned_interfaces (s228)
Pattern 2: find_isolated_modules (s227)
Pattern 3: find_phantom_factories (s227)
Pattern 5: detect_doc_drift Check 4 (s227)

**find_abc_gaps scope fix (low effort, low urgency).**
Add `AND file_path LIKE ?` filter to the abc_classes query in find_abc_gaps
when scope arg is present. Currently scope is accepted but silently ignored.
Function is in determined/agent/agent_tools.py — search `find_abc_gaps`.

**RM69 open design questions (low urgency):**
- Hypothesis count cap (3? all above threshold?)
- Prerequisite map: match named concepts across blocked-on comments
- Ranking formula calibration needs more real cases

**Run capn report when session count reaches 5.**
Counter resets after report. Next auto-notice at session 15.
