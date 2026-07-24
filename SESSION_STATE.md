Written at commit: a9dc933 (SESSION_STATE and TRACKER uncommitted)

# SESSION STATE — session 249 (end)

## Active branch: main [V]

## This session (committed) [V]

- `c8d9831` — fix(walker/cpp): macro-hidden STRUCT/END bare-declaration skip. 71 false
  stubs eliminated from LearnWebGPU. 217/217 G7 pass.
- `a9dc933` — fix(registry): knowledge_for_file added to REGISTRY. Pre-existing failing
  test now passes.
- RM68 header updated: `[dj2 REPO ONLY — NOT A DETERMINED TASK — NEVER ACT ON THIS IN A
  DETERMINED SESSION]` — won't surface again in "what's next" scans.
- HISTORY.md: completion gate decision logged.

---

## COMPLETION GATE — the north star [V]

Bart's words: **"be able to determine the first 5 things that we need to do in dj2
and be able to do them from the tool."**

Two parts:
1. **Determination** — tool produces a confident, ranked top-5 work list from dj2
2. **Execution support** — each item has: what it is (file:line), why now, what it
   needs (prerequisites), first step (scaffold pointer)

UI redesign is "frosting." This gate is the real completion criterion.

---

## NEXT SESSION PLAN

### Step 1 — dj2 walkthrough: test the current "top 5" answer

Load dj2 in the browser. Run the best current proxy for the completion gate:

```
rank_stubs           → what rises to the top?
stub_prerequisite_map → which of those are actually unblocked?
design_oracle         → any CRITICAL flags that override rank?
classify_stub         → spot-check top 3 candidates
```

Synthesize manually: can you produce a confident top-5 from these four tools?
Note every place the answer feels weak, ambiguous, or requires too many steps to assemble.

### Step 2 — Gap assessment from walkthrough

After the manual synthesis, answer:
- Is the ranking confident, or does it require judgment calls that the tool should make?
- Is the context sufficient to act (file:line, what it's supposed to do, what it needs)?
- How many tool calls does it take to assemble one work item card?

If 3+ tool calls are needed to understand a single item → compositor gap confirmed.

### Step 3 — Build `work_session_primer`

New tool in `determined/agent/agent_tools.py`:

```python
def work_session_primer(assessor, args):
    """
    work_session_primer() — top 5 actionable work items for this corpus.
    Synthesizes rank_stubs + stub_prerequisite_map + classify_stub + design_oracle
    into a ranked list. Each item: name, file:line, why-now, dependencies, first-step.
    Deterministic (no LLM). Optional: top_n arg (default 5).
    """
```

Implementation shape:
1. Pull top-20 from `rank_stubs` (existing signal composite)
2. Filter to unblocked via `stub_prerequisite_map` (no unresolved hard deps)
3. Elevate any CRITICAL from `design_oracle` to position 1 regardless of rank
4. For each of top-5: fetch file:line, callers, classify_stub result, prereqs
5. Format as a self-contained work item card per entry

Register in REGISTRY, add to TOOLS, add to `test_dispatch_all_tools_registered`.

### Step 4 — UI surface (after tool works in CLI)

Where it lives: **Shape home**, below the verdict strip — a "WHERE TO START" section
that auto-populates alongside the four quadrants on corpus load.

Each of the 5 items is a clickable card:
- Stub name + file:line (click → opens editor at line)
- Why-now badge (CRITICAL / HIGH-CALLERS / PREREQ-CLEARED / etc.)
- One-line purpose (from docstring or classify_stub result)
- [→ Scaffold] button → calls scaffold_from_pattern, result opens in editor

This answers Q2 from the design conversation: clicking a verdict claim produces a
filtered work-item view, not a raw tool output.

### Step 5 — Trail bar (if time)

The "WHERE TO START" cards need a drill-down that doesn't strand the user. Implement
the trail bar from the UI_REDESIGN.md ASCII diagram:
`corpus ▸ world/ ▸ _get_combat_context`
Breadcrumb at top of main stage; each segment clickable back up the altitude chain.
HTML/JS only — no backend changes.

---

## Design questions to answer during the walkthrough (carry into next session)

Q1: When you open Determined on dj2, what's the first thing you actually do?
Q2: If the verdict strip shows "CombatFSM [GHOST]", clicking it should produce what?
Q3: After drilling to file/line, what's the natural "go back" gesture?
Q4: Stub in Frontier → want call graph: in-place Map switch, or manual open Map?

These answer themselves during the Step 1 walkthrough. Don't pre-answer; observe.

---

## G7 status [V]

217/217 pass (verified this session).

---

## Known issues (carried)

- CUDA stubs: dim3 vars (block_dim, grid_dim) [?] — accepted ceiling
- C++ pure virtual not captured [V] — deferred to RM73
- Walker dispatch resolution (RM73) — FUTURE, Go interface dispatch highest-value first
