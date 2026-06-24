# UI Navigation Experiments

Purpose: the tool's job is making an unfamiliar codebase navigable through its
code graph. These are **time-boxed spikes**, not features — and more than UI
taste tests, they are **probes**. Each way of interfacing with the graph
stresses a different part of the engine (edge resolution, ranking, subgraph
extraction, query routing) and tends to flush out core issues the way the
call-edge bug surfaced. We build only enough to run ONE fixed task, gather
evidence, and kill or flag. We do NOT polish. We stop at the first decisive
signal.

Every verdict records a **root cause**, not just a thumbs up/down:
- worked, or
- failed because of a fixable engine bug (→ log it below as a lighthouse), or
- untenable as an idea, and why.

The point is to harden the engine by exercising it from many angles, and to
leave lighthouses so future work doesn't re-walk dead ends.

## Lighthouses (issues surfaced, kept for the future)

- **Call-graph dropped method calls** (FIXED 2026-06-24). `obj.method()`,
  `self.x.method()` (scrambled), and `grid[i].method()` receivers were dropped
  or mangled in `parse_ast._extract_symbol_references`, plus `extract_design_facts`
  counted in_degree by exact bare name. Combined effect: 184 false dead-code
  candidates on dj2 (→ 78 real after fix). Underlies dead code, hot symbols,
  impact analysis. Tests: `test_call_edge_extraction.py`.
- **Remaining edge gap** (OPEN, low priority): calls whose receiver root can't be
  labeled at all still fall back to a bare method name; cross-file/duck-typed
  dispatch is matched only by name (conflates same-named methods). Acceptable for
  now; revisit if ranking accuracy demands type inference.

## Fixed evaluation task (same for every experiment)

> Starting cold from `process_message`, trace how a player action flows through
> dj2 — through the intent → adjudication → action chain to a state mutation —
> using only the UI, no prior knowledge of the file layout.

Ground-truth spine (Bart knows this, so verdicts are honest); spans world/,
ai/, engine/, so it stresses cross-module edge resolution:

    process_message        world/dm_chat_handler.py   (input intake)
      -> classify_intent   ai/ai_boundary.py
      -> interpret_intent  engine/phases.py
      -> handle_player_action  world/narrative_system.py  -> state mutation

Success for the task = surface this chain (or an equivalent true path) and land
on a state mutation, without already knowing the file layout.

## Trial protocol (per experiment)

1. Branch off `main`.
2. Build the minimum to exercise the paradigm on the fixed task.
3. Run the task once. Capture: 1 screenshot + a 3-line verdict below
   (worked / failed / friction).
4. Kill or mark PROMISING. Do not refine. Return to `main`.
5. Hard stop at the first decisive signal.

After all four: compare verdicts, decide what (if anything) graduates to `main`.

## Experiments

### 1. Spotlight panel  — branch `exp/spotlight` (already prototyped)
Click a symbol → side panel with its facts + related symbols; breadcrumb trail.
- Kill if: clicks hit dead ends, or the panel adds nothing over inline text.
- Keep if: you can follow a thread symbol→symbol without losing your place.
- Verdict: _pending_

### 2. Call-tree  — branch `exp/call-tree`
Pick a root symbol; lazily expandable caller/callee tree.
- Kill if: trees explode or cycle unmanageably.
- Keep if: expand/collapse reveals flow faster than typing queries.
- Verdict: _pending_

### 3. Graph view (cytoscape)  — branch `exp/graph`
Subgraph around a symbol; nodes clickable to re-center.
- Kill if: hairball / unreadable / slow at corpus scale.
- Keep if: spatial layout surfaces clusters or hotspots lists hide.
- Verdict: _pending_

### 4. Trail / notebook  — branch `exp/trail`
Investigation recorded as a replayable, deletable step sequence.
- Kill if: capture overhead exceeds its reuse value.
- Keep if: a saved investigation is genuinely worth replaying.
- Verdict: _pending_

## Outcome
_decided after all four trials_
