# UI Navigation Experiments (archived 2026-06-27 - all trials concluded)

Purpose: the tool's job is making an unfamiliar codebase navigable through its
code graph. These are **time-boxed spikes**, not features -- and more than UI
taste tests, they are **probes**. Each way of interfacing with the graph
stresses a different part of the engine (edge resolution, ranking, subgraph
extraction, query routing) and tends to flush out core issues the way the
call-edge bug surfaced. We build only enough to run ONE fixed task, gather
evidence, and kill or flag. We do NOT polish. We stop at the first decisive
signal.

Every verdict records a **root cause**, not just a thumbs up/down:
- worked, or
- failed because of a fixable engine bug (-> log it below as a lighthouse), or
- untenable as an idea, and why.

The point is to harden the engine by exercising it from many angles, and to
leave lighthouses so future work doesn't re-walk dead ends.

## Lighthouses (issues surfaced, kept for the future)

- **Call-graph dropped method calls** (FIXED 2026-06-24). `obj.method()`,
  `self.x.method()` (scrambled), and `grid[i].method()` receivers were dropped
  or mangled in `parse_ast._extract_symbol_references`, plus `extract_design_facts`
  counted in_degree by exact bare name. Combined effect: 184 false dead-code
  candidates on dj2 (-> 78 real after fix). Underlies dead code, hot symbols,
  impact analysis. Tests: `test_call_edge_extraction.py`.
- **Remaining edge gap** (OPEN, low priority): calls whose receiver root can't be
  labeled at all still fall back to a bare method name; cross-file/duck-typed
  dispatch is matched only by name (conflates same-named methods). Acceptable for
  now; revisit if ranking accuracy demands type inference.

## Fixed evaluation task (same for every experiment)

> Starting cold from `process_message`, trace how a player action flows through
> dj2 -- through the intent -> adjudication -> action chain to a state mutation --
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
4. **3-fix budget:** you get up to 3 fixes to prove the paradigm. If it isn't
   working after the third, stop -- that IS the verdict (untenable, or sitting on
   a deeper engine problem worth a lighthouse). Do not spend fix #4.
5. Kill or mark PROMISING. Do not refine. Return to `main`.
6. Hard stop at the first decisive signal, win or lose.

After all four: compare verdicts, decide what (if anything) graduates to `main`.

## Experiments

### 1. Spotlight panel  -- branch `exp/spotlight` (already prototyped)
Click a symbol -> side panel with its facts + related symbols; breadcrumb trail.
- Kill if: clicks hit dead ends, or the panel adds nothing over inline text.
- Keep if: you can follow a thread symbol->symbol without losing your place.
- **Verdict: PROMISING** (2026-06-24). The panel is genuinely strong -- click
  `process_message` and you get risk profile (WARM, in=4/out=36), intent, callers,
  calls, findings: exactly the graph-neighbor data needed to walk the chain.
  3 fixes spent, each surfaced a real bug:
    1. Symbol detection tagged prose words ("Key", "The") as clickable and missed
       backticked identifiers. Switched to backtick-based detection -> only real
       symbols are navigable.
    2. Panel section symbols were dead text. Linkified `<name> in <file> line N`
       lines -> callers/calls now clickable to re-center.
    3. `list_callees` was flooded by `print` xN under a SQL LIMIT 30, burying real
       next-hops. Filter builtins + dedupe + count -> revealed the true spine
       (`adjudication_engine.process`, `IntentParser`, `IntentFrame`). Engine win,
       graduates to main regardless of UI outcome.
  Bare-name hops work (process_player_input, test fns). Tenable and valuable.
- **Lighthouse (CLOSED 2026-06-25):** dotted callee linkification fixed.
  Regex extended to capture full dotted names; `attachSymbolHandlers` resolves
  to last segment for navigation. `self.adjudication_engine.process` now
  displays the full chain and navigates to `process`.

### 2. Call-tree  -- branch `exp/call-tree`
Pick a root symbol; lazily expandable caller/callee tree.
- Kill if: trees explode or cycle unmanageably.
- Keep if: expand/collapse reveals flow faster than typing queries.
- **Verdict: KILL** (2026-06-24). The tree degenerates into a clickable list --
  same information as `list_callees` in chat, just with expand arrows. It does
  not show shape, purpose, or how a symbol sits in the architecture. More clicks
  for identical data. Fix 1 spent on dotted-name re-rooting (bare-segment
  fallback), which works, but doesn't change the fundamental problem.
  Root cause: flat expansion can't reveal spatial position or inline annotation.
  Both are prerequisites for "terrain" -- which is the real ask.
- **Lighthouse:** what's missing is two things together: (1) spatial position
  (where does this symbol live relative to the rest of the graph), and (2) inline
  annotation (what does each node do). A tree can't provide either. Points at
  Trial 3 (graph) for spatial layout and spotlight for annotation; the combination
  may be the real answer.

### 3. Graph view (cytoscape)  -- branch `exp/graph`
Subgraph around a symbol; nodes clickable to re-center.
- Kill if: hairball / unreadable / slow at corpus scale.
- Keep if: spatial layout surfaces clusters or hotspots lists hide.
- **Verdict: PROMISING** (2026-06-25). The graph renders and the force-directed
  layout does show structure. 3 fixes spent:
    1. `body`->`content` column name in knowledge.db risk query.
    2. Last-segment name resolution: dotted callees (`self.foo`) now resolve to
       their bare function name if unambiguous in the DB. 5->24 nodes at 3 hops.
    3. `position:fixed` sizing workaround for broken flex/grid height chain.
  What works: spatial neighborhood, risk coloring, click-to-recenter.
  What's next: wire node tap -> spotlight panel so graph = terrain and
  spotlight = inspect; the two together answer "where is it + what is it."
- **Lighthouse (open):** flex/grid height chain broken in `.tab-content` --
  the `1fr` grid row gives the tab-content only 62px; root cause not yet
  found. Worked around with `position:fixed` on `#gx-cy`. Fix properly
  before shipping.

### 5. Inline viewer  -- branch `exp/editor-inline`
Read file + slice lines server-side; render in a panel below spotlight with line numbers.
- Kill if: adds friction vs. just opening the file; slow; hard to read in context.
- Keep if: quick "what does this function actually do" without leaving the tool.
- **Verdict: PROMISING** (2026-06-25). Zero external dependency. Server reads file,
  uses `ast.end_lineno` for accurate function boundaries, returns lines with metadata.
  Panel renders below spotlight with padded line numbers (`355 | def process_message...`).
  Tested on `process_message` (dm_chat_handler.py:355-570, 216 lines) -- correct boundary,
  scrollable, no performance issue. One fix: source button toggle/close UX.
  Fits the "quick inspection without breaking flow" use case well.

### 6. Sublime Text  -- branch `exp/editor-sublime`
"Open in Sublime" button in spotlight -> server shells `subl path:line`.
- **Verdict: KILL** (2026-06-25). `subl path:line` works from CLI and PATH
  was correctly set up. Socket event never reached the server handler -- root
  cause not fully diagnosed (likely a socket namespace or server restart
  issue). Scrapped before full diagnosis: decision made that external editors
  are out of scope. The tool does the examination; users open their own editor
  if they want to follow along.

### 7. Lite-XL  -- branch `exp/editor-litexl`
"Open in Lite-XL" button -> server shells Lite-XL CLI.
- **Verdict: KILL** (2026-06-25). Lite-XL has no CLI argument for line
  numbers -- it treats all arguments as file paths. Opens files fine but
  can't land at a specific line. Same scoping decision as Trial 6 applies.

### 4. Trail / notebook  -- branch `exp/trail`
Investigation recorded as a replayable, deletable step sequence.
- Kill if: capture overhead exceeds its reuse value.
- Keep if: a saved investigation is genuinely worth replaying.
- **Verdict: DEFERRED**. Not enough saved investigations yet to know if replay
  pays off. Revisit once the tool is in regular use and investigations accumulate.

## Outcome

Editor integration: **inline viewer graduates to main** (Trial 5). External
editor launch (Trials 6, 7) scrapped -- the tool is the examination surface,
not a launcher. Users open their own editor independently if needed.

Navigation experiments: spotlight (1) + graph (3) both PROMISING and on main.
Call-tree (2) killed. Trail (4) deferred.
