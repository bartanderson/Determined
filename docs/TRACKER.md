tools/analysis - TRACKER (consolidated)
=========================================

This file is the canonical open-items list and at-a-glance status for the
Determined analysis tool. Active open items only. Closed items are deleted â€”
for historical context use git log. For architecture/intent, see DESIGN.md.

Per CLAUDE.md's working agreement: update this file in place as part of
finishing work (checkboxes, dated notes) so Bart can see what changed via
`git diff`, and so a future session doesn't need conversation history to
know where things stand.

---

## DESIGN PRINCIPLES

These are standing architectural commitments, not tasks. They should be applied
when making implementation decisions, not scheduled as work items.

**UI-CLI parity (aspirational 100%):**
Every capability that produces a result a human would act on must be reachable
from the UI — not just the common-path workflows. The UI is the canonical map of
what the tool can do. Exceptions are internal plumbing only (schema helpers, debug
internals, emit machinery) — not "too advanced" judgments about user need.
The Workbench tab is the natural home for full tool coverage; it should be a
complete tool picker, not a demo surface.
Corollary: if I'm about to write a new socket handler, there should be a UI
affordance for it before the session ends. Capability without UI access is
a half-shipped feature.

**GOT model (navigation-first):**
The editor is the navigation hub. Every surface connects back to it.
Search is secondary to browsing. Panels expose what the corpus knows,
not what we decided to show. See docs/UI_VISION.md for full statement.

**Design oracle posture:**
Proposals are evidence of goals, not specs. Extract intent before building.
Apply pressure before improving. Disagree when warranted. Code follows
understanding, not the other way around.

---

## FUTURE — Determined as knowledge compiler + MCTS reasoning engine (2026-07-20)

### The synthesis

Determined is already an oracle (symbols, call graph, imports, FSM artifacts, dead
concepts). The knowledge compilation pattern says: use Claude to design the system
once, then let the system generate training data forever. Determined is uniquely
positioned to do this for code analysis.

### The architecture

```
Determined (oracle over real corpora)
    ↓
classify_stub UNCERTAIN  ←── MCTS root node
    ↓
MCTS explores signal space       ← actions = evidence-gathering queries (imports, callee chain, dead artifacts, design notes)
    ↓
score_hypotheses(accumulated)    ← evaluate() / rollout
    ↓
resolution path                  ← one training sample
    ↓
run over N repos                 ← generator that never stops
    ↓
small stub-classification model  ← trained on resolution paths, not answers
```

### Key ideas

**MCTS as evidence-gathering search:** Instead of pre-computing all signals
(current approach), MCTS gathers evidence on-demand when flat signals don't
converge. Actions = signal-gathering queries. Evaluate = score_hypotheses.
When the tree finds a path that lifts confidence past threshold, that path is a
resolution. The search trace is a training sample: not "here is the answer" but
"here is the sequence of evidence-gathering that resolves this uncertainty."

**Lazy evidence gathering:** Imports, callee-chain, dead artifacts, design notes
are expensive to check for every stub. In MCTS they're only gathered when the
cheap signals (body shape, caller count) leave confidence below threshold.
Better architecture than the current front-loading approach.

**Corpus as generator:** High-confidence MCTS resolutions from real repos are
ground truth. Run over 10,000 repos = millions of labeled resolution paths.
Claude designs the system once; Determined generates the data forever.

**Curriculum (Plan A):** Ask Claude once: "What evidence about a function would
an expert check, in what order, to determine why it's unimplemented?" That answer
is the MCTS action space. Claude leaves the loop.

**Judges (Plan C):** Each signal is already a deterministic judge. score_hypotheses
is already a judge compositor. The goal is to make these calibrated enough to be
a trustworthy rollout function — then MCTS can explore without LLM calls.

### Prerequisites (what must land first)

1. Signal weight calibration against dj2 known-answer stubs (threshold tuning)
2. UNCERTAIN resolution paths documented (what evidence resolves each case)
3. evaluate() stable enough to use as MCTS rollout function

### Gate

Don't build MCTS until the flat kernel (classify_stub) proves insufficient on
real corpora. If calibrated signals resolve 90%+ of stubs without LLM escalation,
MCTS is the path forward for the remaining 10%. If calibration stalls, MCTS
is the answer.

---

## FUTURE — Untapped classify_stub signals (2026-07-20) [ALL SHIPPED 2026-07-22]

1. imports table - DONE (066e252)
2. dead knowledge_artifacts - DONE (artifact signals, session 233)
3. return_type existence check - DONE (066e252)
4. behavioral_contracts / contract_violations - tables do not exist in dj2 schema; skip.

---

## FUTURE — Signal fusion + multi-modal visual projection (2026-07-20)

### The problem

Every tool in Determined produces a single-lens view: classify_stub sees body shape
and callers; detect_conventions sees naming families; rank_stubs sees priority order;
walk_call_chain sees graph paths. The interesting findings emerge where multiple lenses
converge on the same concept — a stub that is an outlier in a naming family AND has
no callers AND is referenced by an FSM action AND has no knowledge artifact is a much
stronger finding than any of those signals alone. Right now there is no place in the
architecture that combines signals across tools for a single concept.

### The design question

Build a per-concept signal aggregation layer: given a concept, collect all signals
that touch it (naming family membership/outlier status, call graph centrality,
config FSM references, knowledge artifact presence, classify_stub confidence,
rank_stubs priority), weight them, and produce a combined picture. This is signal
fusion, not a new tool — it is a compositor that reads what the existing tools
already produce.

The detect_conventions emerging/established sort (min_family=3, sort ascending for
emerging) is the first example of a signal that is interesting not just for its
value but for its *position in a web*: a small naming family is an emerging
convention; a stub that diverges from it is stranded mid-pattern. That positional
meaning only becomes visible when signals are combined.

### Visual projection paradigms to design for

The current graph view is a start but the design review should consider the full
space of visual projections for code analysis:

- **Venn / overlap diagrams**: concepts that appear in multiple signal domains
  simultaneously (naming family + FSM + no callers = high-confidence gap)
- **Layered tables with drill-through**: a top-level table of concepts; selecting
  one pulls a second table of all signals touching it; selecting a signal row
  pulls the supporting corpus evidence. Walking a path = pulling on threads.
- **Color encoding**: signal agreement depth as saturation; classification
  confidence as hue; outlier status as contrast. Consistent palette across views.
- **Thread-pulling in a large visual area**: not just a panel but a workspace
  where multiple tables/graphs are open simultaneously and selections in one
  propagate to others — a concept clicked in the naming-family view highlights
  it in the call graph and in the stub list.
- **Adjacency / convergence maps**: which concepts share the most signal
  co-occurrences? That map shows the architectural seams.
- **Time-axis projection** (future): how do signals change as stubs are resolved?
  The "emerging convention" signal should decay as the family grows — tracking
  that over time shows where the codebase is maturing. The *trajectory* of family
  growth is itself a signal: a family accelerating from 4 to 12 members across
  ingestion runs means the author was actively building toward that convention.
  Determined could surface "accelerating families" as a stub-prioritization signal
  stronger than raw size alone — not just where the gaps are, but where momentum
  was building when work stopped.

### Gate

Not actionable until:
1. classify_stub signal calibration is stable (current active work)
2. detect_conventions sort (emerging/established) is shipped
3. At least one more tool produces per-concept output that could be fused

This is a design review item, not a coding task. When the time comes: design the
fusion layer shape first, then the visual projection surface, then wire them.
The GOT model (navigation-first, surfaces connect naturally) is the guiding principle.

---

## FUTURE — Stub-targeted editing: solutions at the projection site (2026-07-20)

When classify_stub or a future solution-generator produces an attempted implementation,
the natural next step is to place it in source without leaving Determined. This is not
a general code editor — it is editing surfaced *at the stub*, as part of the stub
resolution workflow.

Shape: projection panel shows the candidate implementation; user accepts/edits inline;
Determined writes the file back and re-ingests the symbol. Monaco (single JS bundle,
all languages) is the right embed for the edit surface — read-only by default, write
mode activated from the stub projection result. The mode switch is stub-scoped, not
corpus-wide. No general node-graph editing until this narrower use case proves the
pattern.

Gate: not actionable until classify_stub produces solution candidates (post-MCTS or
post-calibration). Design the write-back + re-ingest path when that lands.

---

## FUTURE — Sidebar panel collapse (2026-07-20)

Left sidebar sections hide content but leave wasted space because `.sb-section` uses
`flex: 1`, claiming equal flex share regardless of content visibility.

**Fix:** change `.sb-section` to `flex: 0 0 auto` so sections shrink to content.
Add collapse-to-label-bar toggle: clicking the section label shows/hides the body,
collapsed state = 26px label bar only, no gap. Stable spatial order (nothing reorders).
Model: VS Code sidebar section collapse behavior.

Files: `determined/ui/static/style.css` (.sb-section rule), `determined/ui/templates/console.html`
(click handler on `.sidebar-label` elements, toggle a `.collapsed` class).

Deferred: not worth fixing now, do in next UI rework pass.

---

## FUTURE — Evaluate API access vs subscription (2026-07-20)

Current setup: Claude.ai subscription + Claude Code CLI. Limitation: no control over
context compaction (harness-level, not hookable). Custom harness (snapcompact-style or
otherwise) requires API access with per-token billing.

To evaluate:
- Pull 3 months of session patterns: how often does compaction fire mid-session?
- Estimate token volume from those sessions against current API pricing
- Compare to subscription cost + API overage risk
- Note: Anthropic API supports hard spend limits — "addict bills" scenario is preventable
- Read: https://stencil.so/blog/snapcompact for the compaction technique that prompted this

Decision gate: only worth switching if compaction is a frequent bottleneck AND estimated
API spend is competitive with subscription. No urgency — evaluate when a natural billing
cycle break comes up.

---

## FUTURE — icecream debug library (2026-07-20)

`pip install icecream` — drop-in replacement for debug prints. `ic(expr)` auto-labels
the expression and its value, includes file/line. Useful during signal extraction
and scoring work in classify_stub. No urgency; grab it when debug logging becomes
friction.

---

## FUTURE — Domain expert adapters from corpus (2026-07-20)

Long-term destination: once Determined can describe a corpus as a whole (post-aggregation),
that description is training signal for a domain adapter. The arc:

  corpus → classify_stub → aggregation → prerequisite map
    → corpus summary as training signal
    → fine-tuned adapter for that domain (architecture, reasoning, coding, etc.)

This is the "mine from your own work" approach — not extracting experts from an existing
MoE (Mixtral/DeepSeek), not training sparse MoE from scratch, but accumulating
domain knowledge from real corpora into small versioned adapters:

  Architecture Adapter  ← from design-intent stubs + prerequisite maps
  Reasoning Adapter     ← from reasoning traces across sessions
  Coding Adapter        ← from dj2 / Determined corpus shape
  DJ2 Expert            ← from full dj2 ingest once aggregation is sharp

The matmul C corpus (FUTURE cross-language) is the first non-behavioral target —
performance structure rather than design intent, stress-tests shape tools and is
a natural first "what does this expert know?" extraction candidate.

Gate: this is not actionable until corpus aggregation ships and Determined can
describe a corpus as a whole. Not a distraction from current work — a destination.

---

## FUTURE — Cross-language understanding (2026-07-18)

### The unified idea

Three things that appeared as separate proposals are actually one:

> **Determined should understand code shape across language boundaries** —
> ingesting corpora in any language, classifying and projecting stubs into
> the right target language for the job, and demonstrating the tool's own
> power by running it across a chain of real projects in the language family.

The three sub-ideas and how they fit:

**1. Cross-language ingestion** — Determined reads corpora in Python, Lua, Zig, C, C++.
Each language adds a parser/stub-detector; the rest of the pipeline (graph, judgment,
projection) is already language-agnostic. Languages to add, in priority order:
- C / C++ — core targets; Zig interops with both, Zig first
- Zig — systems language, clean syntax, strong stub detection story
- Lua / clx (https://github.com/samyeyo/clx) — scriptable, LuaJIT host, game-adjacent

**2. Multi-language emission** — `project_stub` emits in the right language for the job,
not always Python. `target_lang` becomes a first-class param. Classification drives routing:

| Stub role | Target |
|---|---|
| Pure computation, no I/O, hot path | Zig |
| Game logic, scriptable, LuaJIT host | Lua |
| Interop with existing C libs | C |
| Object-heavy, existing C++ codebase | C++ |
| Glue, analysis, default | Python |

Design pressure to apply before building: the classification hypothesis drives routing,
but routing should be a policy the user can override — don't hardcode the table above
into the prompt path. `target_lang` as an explicit param is the right level of control.

**3. Cross-language corpus chain** — run Determined against a curated chain of projects
in the language family and let the tool demonstrate its own invariants across them.
The chain shows where design patterns are universal vs. language-shaped.
Candidate chain: dj2 (Python) → clx (Lua) → Mach Engine (Zig) → Brogue CE (C).
This is also the strongest possible demo: same tool, same pipeline, different languages.

**Verify loop shim** (prerequisite for emission, Windows-native):
`determined/agent/runtime_locator.py` — `locate(lang)` finds or fetches a pinned binary
into `%LOCALAPPDATA%\determined\runtimes\<lang>\<version>\`; `verify_snippet(lang, code)`
compiles/runs, returns stdout+errors. ~200 lines, no symlinks, no POSIX assumptions.
Moonstone (https://github.com/moonstone-sh/moonstone) is the closest prior art but
POSIX-only and over-engineered for snippet verification — build the shim instead.

**Second-order effects worth tracking:**
- Once emission is multi-language, the UI needs a language selector or auto-routing display
- The corpus chain creates a natural test bed: same stub patterns should classify identically
  regardless of source language — a good regression harness for the judgment layer
- Cross-language graph edges (Python calling C via ctypes, Lua calling C via FFI) are
  not currently modeled; worth noting as a future graph layer, not blocking anything now

## RM71 -- FSM ingestor: "data as code" pipeline (DONE 2026-07-22)

**What:** Ingest FSM JSON files (e.g. `config/fsms/encounter.json`) as first-class symbols
in the corpus DB. States, events, actions, and guards become rows in the `functions` table;
transitions become `graph_edges`. FSM actions and guards are marked `is_stub=1` because
their implementations live in Python -- enabling `classify_stub` to ask whether the
implementation exists and `list_stubs` to surface them.

**Why this matters:**
- Proves the "data as code" pipeline: design intent captured in JSON becomes queryable
  alongside the code that implements it.
- Prerequisite for RM69 corpus aggregation: aggregation tools need FSM signals before
  the picture of a corpus is complete. Without this, dj2 produces flat stub lists with
  no connective tissue to the game loop.
- Cross-validates action implementation: `start_combat` appears as both an FSM action
  (is_stub=1) and a Python function. `blast_radius` and `list_callers` can surface both.

**Tenets most live:**
- **XIV (single source of truth):** The JSON is the authoritative FSM spec. Python
  `start_combat` is the derived implementation. The ingestor makes this explicit by
  storing FSM actions as stubs; implementation cross-links use the existing call graph.
- **III (parse, don't validate):** JSON -> dataclass at ingest time. Malformed FSM
  JSON (missing `states`, wrong type) is rejected at the door with a clear error.
  No downstream tool receives an unvalidated FSM shape.
- **XXI (simplicity):** Use the existing `functions` table (`is_stub` is there). No
  new schema. No new tool. Existing tools work once symbols are in the DB. Target ~100 LOC.

**Tension:** FSM actions name Python functions that may not exist yet. Resolution: store
FSM actions with `is_stub=1` and let `classify_stub` do the cross-check naturally. The
dynamic_edges pass already handles similar gaps for JS-to-Python links.

**Schema: use `functions` table** (confirmed: `is_stub` is here, not in `symbols`).
- FSM states   -> `is_stub=0`, `canonical_id='FsmName::state::statename'`
- FSM events   -> `is_stub=0`, `canonical_id='FsmName::event::eventname'`
- FSM actions  -> `is_stub=1`, `canonical_id='FsmName::action::actionname'`
- FSM guards   -> `is_stub=1`, `canonical_id='FsmName::guard::guardname'`
- Transitions  -> `graph_edges`: `source_id=event`, `target_id=state`, `edge_type='fsm_transition'`
- `file_path` = the JSON file (makes `symbols_in_file` and `knowledge_for_file` work).

**Implementation shape:**
- `determined/ingestion/fsm_walker.py` -- new, ~100 LOC
  - `ingest_fsm_file(path, conn, project_root) -> int`
  - `ingest_fsm_pass(conn, root)` -- discovery + ingestion wrapper
  - `discover_fsm_files(root)` -- `rglob("*.json")` filtered to paths containing `fsms/`
- **Hook:** `run_engine.py` line 153, after `persist_all()`:
  `from determined.ingestion.fsm_walker import ingest_fsm_pass; ingest_fsm_pass(connection, Path(corpus.root_path))`

**What this unlocks (no new tools needed):**
- `list_stubs` on dj2 returns FSM actions/guards alongside Python stubs
- `classify_stub(start_combat)` can cross-check if Python implementation exists
- `blast_radius(start_combat)` surfaces both the FSM node and Python callers
- `symbols_in_file('encounter.json')` lists all states, events, actions, guards

**Scope:** Phase 1: `encounter.json` only. `discover_fsm_files` applies corpus-wide.
**Tests:** `tests/regression/test_fsm_walker.py` -- offline, in-memory SQLite.
**Gate:** None. Implemented (2026-07-22, session 241). 16 tests pass. Hook wired in run_engine.py.

---

**Implementation sequencing — gates cleared, C shipped (2026-07-23):**
Both gates cleared:
1. RM69 corpus aggregation -- DONE (CLOSURE.md Phase 1, 2026-07-17)
2. RM71 FSM ingestor -- DONE (2026-07-22, session 241)

C walker shipped (session 243): `language_walker.py`, `scan_project_files.py`, header dedup
post-pass in `persistence_engine.py`. brogue-ce ingested, probed, convergence verified.

Remaining:
3. Ingestion parsers: Zig, Lua
4. `target_lang` param in `project_stub`
5. `runtime_locator.py` shim
6. Corpus chain: acquire projects, ingest, surface shape comparison in UI

### Corpora to acquire

- **Optimized matmul (C)** — houslast3/85.30-GFLOPS-Single-Core-FP32-Matrix-Multiplication-on-AMD-Zen-3
  Hand-optimized SIMD/AVX matmul kernel. Tiny call graph, no stubs, all structure is performance
  structure (loop tiling, register blocking). Stress test for corpus shape tools on non-behavioral
  C. Verify repo exists and has clean C source before ingesting. (Source URL was a Google Translate
  mirror — check original.)
  NOTE: this fills the "C walker validation / compute shape" slot only. It is NOT a behavioral
  corpus — no design-intent stubs. A separate behavioral C corpus is required (see Brogue CE below).

- **Brogue CE (C)** — https://github.com/tmewett/BrogueCE
  Actively maintained C roguelike. Fills the "behavioral C" slot that matmul cannot: real
  design-intent stubs, FSM-heavy dungeon generation, clear subsystem separation (dungeon/monster/
  item/display). Domain synergy with dj2, end-of-eden, ruggrogue. Clone to
  `C:\Users\bartl\dev\corpora\brogue-ce`. Ingest after C walker is built.
  Expected: moderate stub count (it is actively developed), strong FSM signal, C-specific patterns
  (function pointers as callbacks, struct-based OOP, preprocessor conditionals).

- **llm.c (C + Python)** — https://github.com/karpathy/llm.c
  Minimal LLM training loop: C kernel (CUDA/CPU matmul, attention) called from Python via ctypes.
  Fills TWO slots simultaneously: (1) ML trainer codebase with mathematical design intent, and
  (2) cross-language boundary pair (Python -> C via ctypes). The ctypes boundary is the primary
  test target for cross-language edge modeling. Clone to `C:\Users\bartl\dev\corpora\llm.c`.
  Ingest Python side and C side separately, then verify cross-language edges link them.
  Expected: Python side has clear entry points (train.py, test.py); C side has near-zero stubs
  (optimized kernels); the ctypes boundary is where the interesting cross-language signal lives.

- **Mach Engine (Zig)** — https://github.com/hexops/mach
  Zig game engine. Fills the Zig corpus slot with game-domain synergy matching the rest of the
  chain. Mach is actively developed and covers the full stack: windowing, audio, GPU via WebGPU.
  Clone to `C:\Users\bartl\dev\corpora\mach`. Ingest after Zig walker is built.
  Expected: high EP count (platform entry points per backend), trait-like Zig interfaces (comptime
  dispatch), backend-conditional modules (#if builtin.os similar patterns). Walker must handle
  Zig's comptime and anytype generics without treating them as unknown symbols.

- **clx (Lua)** — https://github.com/samyeyo/clx
  LuaJIT application framework. First Lua ingest — validates the walker before a larger Lua
  game target. Also directly relevant as the dj2 emission target: stubs classified as
  "game logic / scriptable" route to Lua, and clx is the runtime they'd land in. Clone to
  `C:\Users\bartl\dev\corpora\clx`. Ingest as soon as Lua walker is built.
  Expected: framework-style corpus (high public API surface, few stubs — intentional API, not
  gaps). Follow-on: a LOVE2D game written in Lua once the walker is validated here.

- **C/C++**: beyond matmul and Brogue CE, small embedded systems tools or CLI utilities if
  the C walker needs further validation across different C idioms.

- **Cross-language pair note**: llm.c IS the cross-language pair — its Python/C ctypes boundary
  is the primary test. No separate corpus needed unless ctypes edge modeling needs a simpler
  example first (in which case, find a 200-line ctypes wrapper to start).

---

## FUTURE — Slater integration arc (2026-07-22)

**Source:** https://github.com/Hikari-Systems/slater
Slater is a Rust graph database that serves graphs that don't fit in memory (hundreds
of millions of nodes, billions of edges) in low hundreds of MB of RAM, via the standard
Bolt protocol. Any neo4j driver (Python, JS, Go, Java) works unchanged. Disk-native
vector search (Vamana + PQ; cosine/L2/dot ANN) lives next to the graph. Written with
Claude Code by Hikari Systems. Open source, Apache-2.0.

Six distinct ideas follow in priority order. Read all of them before acting on any —
they compose, and the later ones build on decisions the earlier ones make.

---

### Idea 1 — Slater as a Rust corpus (READY NOW, no gates)

**What:** Clone and ingest Slater as the primary validation corpus for the Rust walker.
Better than ruggrogue (a game loop) because Slater has clean architectural separation
between build path (slater-build) and serve path (slater server), heavy trait usage,
and a clear module hierarchy in `crates/`. It is also Claude Code-generated Rust —
meta-interesting as a data point on how AI-assisted code organizes itself.

**Steps:**

1. Clone:
   ```
   git clone https://github.com/Hikari-Systems/slater C:\Users\bartl\dev\corpora\slater
   ```

2. Load via UI corpus switcher with absolute path to the cloned directory.

3. Immediately after ingest, run the canonical six-probe loop (RM67):
   - `list_entry_points` — expect Bolt handler traits, build CLI entry points
   - `list_stubs` — expect 0 or very few (it is complete server software); any stubs are
     probably interface methods or platform-conditional code (`#[cfg(...)]`)
   - `list_features` — expect features: bolt_server, slater_build, delta/LSM, vector_search,
     acl, storage_backends
   - `development_priorities` — use as Rust walker regression baseline
   - `walk_call_chain` on a known entry point (the Bolt handler accept loop)
   - `blast_radius` on a core struct (the cache LRU)

4. Known Rust walker edge cases to watch for:
   - `impl Trait for Type` blocks — methods go on the concrete type, not the trait
   - `#[cfg(feature = "...")]` / `#[cfg(test)]` — conditional code may produce false stubs
   - Crate-level re-exports (`pub use crate::foo::Bar`) — may produce duplicate symbols
   - `mod.rs` files and inline `mod foo { ... }` — both valid Rust module forms
   - Lifetimes in function signatures — should not break param_types_json extraction
   - Macros (`#[derive(...)]`, `vec![]`, `tokio::main`) — walker must not try to parse
     macro bodies as function bodies

5. Add a row to RM67 language scope table once probed:
   `| slater (Rust) | Probe-passes | <stub count>; <known issues> |`

6. File any Rust walker bugs found as sub-items here before closing.

**No gate. Clone and ingest in the session you read this.**

---

### Idea 2 — Build/serve split as corpus generation model (feeds RM69 design)

**What:** Slater's architecture is: `slater-build` compiles a graph offline into a
content-addressed immutable "generation" directory; `slater` serves from it with a
bounded cache. Swapping generations is atomic (one `current` pointer flip). This maps
cleanly onto what Determined already does — ingest (build) and query (serve) — but
Determined does not formalize the split or version the output.

**The steal:** When designing RM69 corpus aggregation, adopt the generation model:

- **Ingest = build pass.** Produces a frozen, content-identified corpus snapshot
  (the DB file, keyed by a hash or ingest timestamp).
- **Query layer serves from the frozen snapshot.** Never mutates it mid-query.
- **Re-ingest produces a new generation**, not an in-place mutation of the existing DB.
  The old generation stays accessible until explicitly pruned.
- **One "current" record** points to the active generation (could be a sidecar JSON
  or a symlink). Switching corpora = updating the current pointer.

**Why this matters for RM69:** aggregation tools (file shape, subsystem shape,
prerequisite map) produce corpus-wide summaries. Those summaries need to be stable
within a session — a re-ingest mid-session should not silently invalidate them. The
generation model makes this explicit: summaries are stamped against a generation ID;
stale summaries are detected, not silently served.

**Implementation shape when RM69 is being designed:**
- `ingestion/generation.py` — `GenerationManifest(corpus_path, ingest_sha, timestamp,
  symbol_count, edge_count)`; written as `generation_manifest.json` next to the DB
- Query tools read the manifest at startup; if manifest is absent or stale, warn before
  running aggregation
- `corpus_aggregation.py` stamps summaries with `generation_id`

**Gate: implement when RM69 architecture is being designed. Do not add generation.py
before RM69 is active — premature if aggregation doesn't exist yet.**

---

### Idea 3 — Vector + graph colocation (design principle for RM69)

**What:** Today Determined keeps embeddings in `semantic_summaries` and call edges in
`graph_edges` — joined in Python across two queries. Slater shows that vector KNN and
graph traversal can be one query:

```cypher
MATCH (n:Function)
WHERE db.idx.vector.queryNodes(n, $embedding, 10)
RETURN n, [(n)-[:CALLS]->(m) | m] AS callees
```

**The principle (apply now, not later):** When designing RM69's aggregation layer,
make the schema choice that keeps embeddings and their associated graph edges
co-queryable — either in the same table join with a covering index, or in a
single tool call that fetches both in one DB round-trip. Avoid a pattern where
"find semantically similar symbols" and "find their call context" are two
independently-coded Python steps with a Python merge in between.

Concrete RM69 implication: `subsystem_shape` and `prerequisite_map` will need both
semantic clustering (embedding similarity) and structural clustering (call graph
proximity). Design the query so those two signals are gathered together, not
separately.

**This is a design discipline, not a migration. No new code before RM69 is active.**

---

### Idea 4 — Cypher as graph query interface (migration path, future)

**What:** Determined's graph queries are raw SQL with Python BFS loops. Cypher (the
neo4j query language Slater speaks) is native to the questions Determined asks.

**Side-by-side comparison:**

| Question | Current (SQL + Python) | Cypher |
|---|---|---|
| Stubs and their caller counts | 2-table JOIN + GROUP BY | `MATCH (c)-[:CALLS]->(s {is_stub:1}) RETURN s.name, count(c)` |
| 5-hop call chain from a stub | BFS loop in Python, ~40 lines | `MATCH p=(s)-[:CALLS*..5]->(n) RETURN p` |
| Files by stub density | subquery + ORDER BY | `MATCH (f)-[:CONTAINS]->(s {is_stub:1}) RETURN f.path, count(s) ORDER BY count(s) DESC` |
| Sibling stubs (share a caller) | self-join SQL | `MATCH (c)-[:CALLS]->(s1 {is_stub:1}), (c)-[:CALLS]->(s2 {is_stub:1}) WHERE s1 <> s2 RETURN s1, s2` |

**DB migration detail (when this becomes active):**

Node types to define:
- `:Function` — properties: name, fqdn, file_path, is_stub, is_tool, is_entry_point,
  body_shape, http_route, docstring, param_types_json, caller_count, language
- `:File` — properties: path, language, role (entry_point/config/test/module)
- `:Module` — properties: name, package

Edge types to define (map from graph_edges.edge_type):
- `:CALLS` (call edges, the primary graph)
- `:IMPORTS` (import edges)
- `:CONTAINS` (File -> Function)
- `:FUNCTION_REFERENCE` (callback/dict-registered references)
- `:DATA_FLOW` (data_flow edges)
- `:HTTP_FETCH` (JS fetch -> Flask route)
- `:JS_EVENT_BINDING` (socketio emit -> handler)

Migration steps:
1. Write `scripts/export_to_cypher.py` — reads corpus DB, emits a `.cypher` dump
   in Slater's primitive-Cypher format (`CREATE (n:Function {…})`, `MATCH … CREATE [:CALLS]`)
2. Run `slater-build --input dump.cypher --graph <corpus_name> --data-dir <data_dir>`
3. Start `slater` (Docker or binary) on port 7687
4. Install neo4j Python driver: `pip install neo4j`
5. Write `determined/graph/bolt_oracle.py` — wraps neo4j driver, exposes same interface
   as current SQLite graph queries in `agent_tools.py`
6. **Parallel-run test suite:** run every graph query (walk_call_chain, blast_radius,
   find_abc_gaps, list_callers, list_callees, list_entry_points, list_stubs) against
   both SQLite and Bolt paths; assert result sets identical for same corpus
7. Once parallel tests pass on dj2 + at least one non-Python corpus: drop SQLite graph
   query path, remove graph_edges queries from agent_tools.py, delete bolt_oracle.py
   bridge (now it's just the driver)

**Parallel test is the gate for dropping SQLite.** Do not drop until every graph tool
passes it on at least two corpora.

**Gate: not before SQLite becomes a query bottleneck OR MCTS arc (Idea 6) makes
multi-hop Cypher clearly worthwhile. Estimate: this becomes relevant after 2-3
large C/Zig corpora are ingested and query latency is measurable.**

---

### Idea 5 — Scale path for large corpora (observational, no action yet)

**What:** SQLite is fine for corpora up to ~50K edges. Slater's bounded-memory model
(3-pool LRU: decompressed-block, vector-index, result) keeps RSS flat regardless of
graph size — a 400 GB graph costs the same RAM as a 4 GB graph to serve.

**When this matters:** The C/Zig corpora planned in the cross-language arc are
structurally denser than Python/TS game code. A large C++ game engine or systems
project could have 200K-2M edges. If `list_callers` or `blast_radius` start
taking more than a few seconds, the graph layer is the bottleneck.

**Trigger to act:** ingest a C corpus and run `blast_radius` on a widely-called
symbol. If it takes > 5 seconds on a 100K-edge corpus, migrate to Idea 4 (Cypher/Bolt)
as the fix, not SQLite optimization.

**No action until triggered. Do not pre-optimize.**

---

### Idea 6 — MCTS evidence gathering over Bolt (downstream of MCTS arc)

**What:** The MCTS reasoning arc (TRACKER: FUTURE — MCTS reasoning engine) requires
iterative call graph traversal as the evidence-gathering step — gather evidence about
a stub by following its call chain, then score hypotheses, then branch. In Python+SQLite
this is recursive BFS: multiple DB round-trips, Python graph objects, manual dedup.

In Cypher over Bolt, the same traversal is:
```cypher
-- All paths from stub to depth 5, excluding builtins:
MATCH p = (stub {name: $name})-[:CALLS*..5]->(n)
WHERE NOT n.is_external
RETURN p

-- Sibling stubs (two stubs sharing a caller):
MATCH (c)-[:CALLS]->(s1 {is_stub:1}), (c)-[:CALLS]->(s2 {is_stub:1})
WHERE s1.fqdn <> s2.fqdn
RETURN c.name, s1.name, s2.name

-- Import evidence (what a stub's file imports):
MATCH (stub {name: $name})<-[:CONTAINS]-(f)-[:IMPORTS]->(dep)
RETURN dep.name
```

Each MCTS action = one Cypher query. The search tree does not need Python graph objects.
The evaluate() function reads the Bolt response directly.

**Gate: MCTS arc itself (gated on flat kernel proving insufficient post-calibration).
File this note here so when MCTS design starts, the team knows Bolt is the right
query surface, not a new Python BFS implementation.**

---

### Implementation order summary

| Idea | When | Gate |
|------|------|------|
| 1 — Slater as Rust corpus | Now | None — clone and ingest |
| 2 — Generation model for RM69 | When RM69 is designed | RM69 active |
| 3 — Vector+graph colocation principle | When RM69 is designed | RM69 active |
| 4 — Cypher/Bolt migration | After large C corpora, or MCTS | Scale trigger or MCTS arc |
| 5 — Scale path observation | Monitor | > 5s query on 100K-edge corpus |
| 6 — MCTS over Bolt | MCTS arc | Flat kernel insufficient |

---

## FUTURE — Design Oracle (2026-07-18)

A tool that reads across the already-ingested corpus and surfaces three signals at the
right moment — not a new data pipeline, a new query over what's already there.

**The problem it solves:** dj2's design docs, stubs, backlog items, and "I want to"
statements are all ingested and connected. But nothing joins them into actionable advice
about *what to work on next and why*. The pressure sits there disconnected from the
development moment where it would be useful.

**The three signals:**

- **CRITICAL** — "X is blocking Q, R, S, T downstream. It overrides everything else."
  Driven by: stub classified as blocked-on-prerequisite + high downstream dependency count.

- **OPPORTUNITY** — "While you're already in this area, Y is adjacent, cheap, and unblocks Z.
  Want to take it?" Triggered by: current working context + graph adjacency + readiness.

- **FOREWARNING** — "You'll need W before you can do V. V is coming up. Here's what W requires."
  Forward-looking, derived from the dependency chain ahead of current work.

**What it composes (all already exist):**
- `knowledge_artifacts` — design doc intent, "I want to" statements
- `workflow_items` (kind=backlog) — catalogued backlog from ingestion
- `classify_stub` — stub readiness and blockage reason
- graph edges — adjacency, what's cheap to reach from current context
- `_get_design_frame` — sots tenet alignment for the current area

**The join that's missing:** current working context → relevant intent → blockage state →
adjacency. That's the query. Output is ranked, scoped to current session context, at most
one CRITICAL + two OPPORTUNITYs + one FOREWARNING.

**When it runs:** Session start (broad read) and on-demand ("what should I work on next?").
Not automatic mid-session — that's noise. The valve opens when asked.

**Sensing model:** Claude holds the structural view and tracks gaps. Bart provides friction
from real use and occasional mock probes to test capability. Gaps surface through use,
not planning.

---

## FUTURE — Knowledge layer improvements (CodeAlmanac ideas, 2026-07-22)

**Source:** https://github.com/AlmanacCode/codealmanac
CodeAlmanac is a living wiki (committed markdown under `almanac/`) maintained by AI agents
that scan session transcripts, ingest PRs/diffs, and run periodic cleanup. Opposite direction
from Determined (they go transcripts→wiki→humans; we go code→graph→AI) but same problem space.
Five ideas worth stealing, each independent.

---

### Idea 1 — Transcript → knowledge_artifacts (session decisions enter the queryable layer)

**The gap:** Decisions made during Claude Code sessions live in SESSION_STATE.md for one
handoff, then effectively vanish from the knowledge layer. "Calibration gated on multi-corpus,"
"no dj2 work until Determined is complete," "dead artifact LIKE over-match" — these are real
constraints that `check_design_violations` and `knowledge_status` never see, because they're
only in markdown handoff files, not in `knowledge_artifacts`.

**The steal:** After a session, or on a periodic pass, scan recent Claude Code session
transcripts for extractable decisions and store them as `knowledge_artifacts` with
`kind='design_note'` and `provenance='session_transcript'`. The same LLM call that currently
drives `ingest_design_docs` can drive this — the input is just a transcript excerpt instead
of a design doc.

**What it enables:** `check_design_violations` surfaces session decisions when analyzing new
code ("this change conflicts with the constraint: calibration must follow multi-corpus ingest").
`knowledge_status` includes session-derived constraints alongside SOTS and design docs.

**Where transcripts live (Claude Code):** `%APPDATA%\Claude\projects\<project-id>\`
Each `.jsonl` file is one session. The sync job only needs to scan files newer than the last
run timestamp — same pattern as CodeAlmanac's sync.

**Implementation shape:**
- `scripts/sync_transcripts.py` — walks `%APPDATA%\Claude\projects\<project-id>\`, reads
  `.jsonl` files newer than a stored `last_sync` timestamp, extracts user+assistant turns,
  calls `ingest_design_docs`-style LLM prompt to extract decisions/constraints/gotchas,
  stores as `knowledge_artifacts` with `provenance='transcript:<session-id>'`
- Gate for extraction: only store claims that include a "why" (constraint, decision, or
  lesson) — skip task narration and code discussion
- Run manually first (`python scripts/sync_transcripts.py --corpus dj2`) before considering
  automation

**Gate: implement after RM69 corpus aggregation exists — the aggregation layer is what makes
the knowledge queryable in a useful way. Not before.**

---

### Idea 2 — Garden pass (scheduled knowledge maintenance)

**The gap:** We have `docstring_health` (finds stale/missing docstrings), `detect_doc_drift`
(finds design-note drift), and `gap_analysis` (brainstorms fills). But there is no pass that
runs these together on a cadence and queues the findings. Knowledge rot accumulates silently.

**The steal:** A `garden_corpus` tool that runs the three maintenance tools in sequence,
deduplicates findings against existing `workflow_items`, and queues new ones. Same concept
as CodeAlmanac's garden agent — periodic cleanup of the knowledge layer, not the code layer.

**Implementation shape:**
- `determined/agent/garden.py` — `garden_corpus(oracle)`:
  1. Run `docstring_health(oracle, top_n=20)` — queue stale docstrings as workflow_items kind='debt'
  2. Run `detect_doc_drift(oracle)` — queue drift findings as workflow_items kind='drift'
  3. Run `gap_analysis(oracle, scope='all')` — queue gap suggestions as workflow_items kind='opportunity'
  4. Dedup: skip items where identical subject+kind already exists in workflow_items
  5. Return summary: N new items queued, N already known
- Wired as agent tool `garden_corpus`, socket handler `garden`, UI button in Tools tab
- Run manually per session ("garden dj2") before considering any scheduling

**No automation until the manual tool proves its value. Don't schedule what you haven't
run by hand a few times.**

**Gate: no hard prerequisite, but more useful once more corpora are ingested — gardening
one Python corpus is thin; gardening dj2 + dungeoncrawler + end-of-eden is interesting.**

---

### Idea 3 — CodeAlmanac as upstream knowledge source (zero new code)

If you ever run CodeAlmanac alongside Determined on the same repo, point `ingest_design_docs`
at the `almanac/` folder. Their agents maintain architecture/, decisions/, guides/ in
human-readable markdown. Determined ingests it as `design_notes`. The two tools compose:
CodeAlmanac writes the "why" layer, Determined queries it during code analysis.

We already do this with SOTS (25 tenets ingested as design_notes from `docs/sots.md`).
`almanac/` is just the same pattern with agent-maintained content instead of hand-written docs.

**No code change. If a repo has an almanac/ folder, add it to the ingest_design_docs call.**

---

### Idea 4 — `sources:` citation gate on LLM-generated knowledge

**The gap:** LLM-generated `knowledge_artifacts` (from `annotate_function`, `ingest_design_docs`,
`gap_analysis`) can be vague or ungrounded. A design note that says "this module handles
persistence" with no source citation is hard to audit and rots silently.

**The steal:** Require every LLM-generated knowledge artifact to cite at least one source
(file path, line number, or commit SHA) before storage. Reject or flag uncited claims.

**Where to apply:**
- `ingest_design_docs`: already has `provenance` field; enforce that it points to a specific
  file, not just a corpus name
- `annotate_function`: annotation prompt should cite the call site or docstring it derived
  from; store as `source_ref` alongside the artifact
- `gap_analysis`: brainstorm outputs are generative and inherently uncited — tag them
  `kind='opportunity'` and `confidence='unverified'` to distinguish from cited facts

**Gate: RM69 design phase. Bake the citation requirement in at design time — retrofitting
it onto existing artifacts is harder than requiring it from the start.**

---

### Idea 5 — `knowledge_for_file(path)` tool (inverse lookup)

**The gap:** `describe_file(path)` goes file → symbols → structural analysis. But nothing
answers "what does the knowledge layer know about this file?" — design notes, inline notes,
semantic summaries, workflow items, and backlog entries whose content or provenance references
this path.

**The tool:** `knowledge_for_file(path)` — query across all knowledge_artifact kinds WHERE
content LIKE '%<path>%' OR provenance LIKE '%<path>%', plus semantic_summaries WHERE
file_path = path, plus workflow_items WHERE subject LIKE '%<path>%'. Return ranked by
relevance (exact file_path match > mention in content).

**Use case:** about to edit a file — "what do we know about it?" — surfaces constraints,
prior decisions, known gaps, and risk flags before touching the code. Natural two-step orient:
`describe_file` for structure, `knowledge_for_file` for what's known about it.

**Size:** ~30 lines of SQL + formatting. Can be added alongside any other task.

**Gate: none.**

---

### Idea 6 — Token-budget-at-write-time (context-window discipline for stored artifacts)

**The gap:** knowledge_artifacts and workflow_items are stored as raw text with no token
budget enforcement. At retrieval time, a bloated artifact consumes context window
silently — no warning, no truncation, no record of the cost.

**The principle:** count tokens *at write time*, not read time. A tokenizer call
(tiktoken or gigatoken) at `_store_knowledge_artifact` is cheap; LLM context wasted
on a 2000-token design note that could have been 200 is not.

**Concrete behavior:**
- Count tokens on every artifact before storing. Reject if over threshold (proposed:
  500 tokens for `design_note`, 200 for `inline_note`, 1000 for `doc_section`).
- If over threshold: do not store. Emit a `workflow_item` with
  `kind='backlog'` and subject `"summarize-before-store: <artifact subject>"`.
  The summarization pass (Idea 2's garden tool) picks it up.
- At retrieval time, rank candidates by token density (meaningful claims per token),
  not just recency or kind.

**Why this matters:** the knowledge layer's value is what the LLM can fit in context
during a query. A system that stores freely but retrieves selectively still wastes
tokens on storage — and selectively retrieving a bloated artifact is still expensive.
Enforce the budget at the point of entry, not the point of use.

**Implementation shape:** one helper `_count_tokens(text) -> int` using tiktoken
(no dependency on gigatoken; correctness over speed for single-artifact counting).
Called inside `_store_knowledge_artifact` before the INSERT.

**Cross-validation:** omp (oh-my-pi harness, MIT) ships exactly this as a 40-LOC Rust
native module (`pi-natives tokens` crate) with both O200k and Cl100k BPE tables embedded
in-process. They reach for it because it's cheap enough to call on every artifact; we
should too.

**Gate: RM69 design phase.** Bake in at schema design time alongside the citation gate
(Idea 4). Both are entry-point disciplines that are harder to retrofit than to build in.

---

### Idea 7 — snapcompact-style context compression (vision-based, zero-LLM compaction)

**Source:** omp harness (https://omp.sh, MIT). Technique: when context fills, render
history to pixel-font PNGs rather than calling a summarizer LLM. A 1568×1568 frame at
6×10 pixel font carries ~40K chars, billed as 3,279 image tokens vs ~10K text tokens —
about 1/3 the cost for near-verbatim read-back.

**The benchmark that matters:** on SQuAD v1.1 F1, prose-compacted context (both Gemini
and Opus summarizers) scored near zero — the summarizer shredded the facts it was supposed
to keep. PNG-compacted context scored 0.88 vs 0.90 for raw uncompacted text. The loss is
2 F1 points, not 90.

**Why this didn't fit before, why it fits now:** yesterday this was a curiosity. Today,
after the token-budget-at-write-time conversation, the shape is clear: Idea 6 disciplines
what goes IN; snapcompact disciplines what survives AFTER context accumulates. They're
complementary at different points in the pipeline.

**Point of use in Determined (shifted to the front):** any deep analysis chain that
accumulates LLM context across multiple tool calls — `development_priorities`,
`walk_call_chain` with context injection, future `corpus_aggregation`. Right now we
truncate or don't manage this at all. snapcompact is a better answer than truncation
because it preserves facts; prose summarization actively destroys them.

**What it requires:** the receiving model must support vision. Qwen3-8B status unknown —
verify before designing around this. If it doesn't support vision, the principle still
holds as a future-model target.

**Implementation shape (when the time comes):**
- `context_compactor.py` — renders accumulated context as PNG using pixel font
- Called by long-chain tools before pushing context to LLM if token count exceeds
  a threshold (e.g., 6K tokens)
- omp's snapcompact crate is 1,440 LOC Rust; a Python equivalent using PIL is viable
  if Rust is out of scope

**Gate: CLEARED (2026-07-22, session 238).** Qwen3-VL-8B-Instruct confirmed on Bart's
machine. `determined/agent/context_compactor.py` written and manually tested — OCR quality
5/6 key terms at font size 14, `<transcript>` extraction working, max_tokens 8192.
Server runs on port 8082. See HISTORY.md for llama.cpp Thinking-suppression workaround.
DONE (session 238/239): `context_compactor.py` written and committed; 14 offline tests pass.
No RM69 dependency — usable in any long LLM call chain now.

---

### Idea 8 — mnemopi as RM69 prior art (read before designing the knowledge layer)

**Source:** omp harness (https://omp.sh, MIT). mnemopi is their shipped, production
knowledge layer — local SQLite, vector embeddings, graph tools.

**Their API surface:**
- `retain` — queue durable facts into the active memory bank
- `recall` — search the bank
- `reflect` — synthesize an answer over the bank (LLM-driven)
- `memory_edit` — update, forget, or invalidate a recalled memory by id

**Their scope model:** global / per-project / per-project-tagged. Delegated subagents
inherit the parent's memory state — meaning memory scoping is hierarchical, not flat.

**Why this matters for RM69:** we're about to design a knowledge layer (knowledge_artifacts
+ RM69 aggregation) that covers the same ground. mnemopi is a shipped version of that
design by a team that has been running it in production. The schema decisions they made
under real load are more valuable than anything we can reason up from first principles.

**Pre-RM69 reading assignment:** before writing the first line of RM69 schema, read
mnemopi's source. Specifically: how they handle scope inheritance, how `reflect` is
implemented (LLM-over-bank vs retrieval-then-generate), and whether `memory_edit` by id
is preferable to our current update-by-subject approach.

**Gate: RM71 active (i.e., read during RM71 design, apply at RM69 design).** The reading
is ungated; the application is RM69.

---

## RM68 — Remove subrace concept from dj2 (DEFERRED)

**Context:** The OG system rewrite replaced the original D&D data model with a more
consistent system that has no subraces. The original D&D data had subraces; the OG
system intentionally dropped them. The current dnd_data.py stubs (subraces,
get_subraces_for_race, get_race_for_subrace, semantic_match_subrace,
semantic_match_fighting_style) are not compatibility shims waiting to be filled --
they are dead concept remnants. The concept should not exist, not be stubbed.

**Design decision:** Remove the subrace concept entirely from dj2. Do not implement.

**Scope (grep confirmed -- 3 files):**
- `world/dnd_data.py` -- 5 stub functions + subrace references in data structures
- `world/character_generator.py` -- subrace references (callers to remove)
- `world/authority_system.py` -- subrace references (callers to remove)

**Approach:**
1. Trace all callers of subrace functions via Determined (blast_radius on subrace stubs)
2. Remove subrace stubs from dnd_data.py
3. Remove callers in character_generator.py and authority_system.py
4. Verify no remaining references

**Why deferred:** Correct thing to do but not blocking anything. Low blast radius.
No other system depends on subraces returning real data (they already return []/None).

**Gate: do NOT do this work during Determined sessions.** This is a dj2-side task.
It will surface naturally from Determined's analysis of dj2 when the time comes.
Only execute when Bart explicitly says to work on it in a dj2 session.

---

## RM67 — Convergence protocol (ACTIVE)

Standing operating procedure. Not a feature — acceptance criteria and a per-session
probe loop. Goal: finish the tool cleanly enough to get back to building the game.

### Convergence definition

**Per corpus:**
1. Structural integrity — stub/is_tool/function_reference detection has no false positives;
   real gaps are found; entry point detection is trustworthy.
2. Probe passes — six canonical questions (entry points, blast radius, feature shape,
   stubs, design drift, call chains) answered without confabulation or misrouting.
3. Known gap ceiling — inferred EPs and open stubs are closed OR explicitly acknowledged
   as "not statically resolvable, acceptable." No open unknowns.

**Tool self-model:**
- Determined analyzing Determined finds no false positives in its own detection.
- Adversarial probe (session 140 pattern: 6 representative questions) passes.
- No TRACKER items that actively break the canonical questions.

### Language scope

| Corpus | Target | Status |
|--------|--------|--------|
| Determined (Python) | Full convergence | structural integrity done; probe DONE (2026-07-21) |
| dj2 (Python+JS) | Full convergence | 331 inferred EPs (accepted ceiling); 10 stubs split: 5 RM68-remove, 5 AI-layer (RM69 to classify) |
| Commonplace (Python) | Full convergence | 1 stub (suggest_tags); deferred to RM69 |
| rotjs (TS) | Probe-passes | 6 stubs; lib/src dual-rep known |
| dungeoncrawler (TS) | Probe-passes | 0 stubs; appears clean |
| dnd-dungeon-gen (JS) | Probe-passes | 6 stubs; JS callee resolution gap known |
| end-of-eden (Go) | Probe-passes | 0 stubs; 15% unresolved (external libs, correct) |
| ruggrogue (Rust) | Probe-passes | 0 stubs; normalize_symbol :: strip known |
| slater (Rust) | Probe-passes | probe DONE (2026-07-22) — 195 files, 0 stubs, 1985 inferred EPs (all tests/benchmarks, correct for library crate); walk_call_chain blind across async boundary (serve_with_listener = 0 nodes); blast_radius 593 for evict_to_budget (cache is foundational); 78 dup names = normal module aliasing |
| brogue-ce (C) | Probe-passes | probe DONE (2026-07-23) — 977 symbols, 7233 edges; C walker built (session 243); 30 true stubs (9 unmatched header decls + 21 empty-body); header dedup post-pass ships 542 false-positive header stubs; cellHasTerrainFlag HOT (96 callers = terrain query in dungeon gen); initializeLevel chain 189 nodes; 0 explicit EPs (correct for C game), 127 inferred EPs |
| llm.c (C+Python+CUDA) | Probe-passes | probe DONE (2026-07-23, session 245) — 729 symbols / 2960 edges; 148 CUDA kernels; 151 kernel_launch edges; 22 stubs (mostly false-positives); Python = parallel PyTorch impls, not ctypes |
| mach (Zig) | Probe-passes | NOT YET INGESTED — Zig walker not built |
| clx (Lua) | Probe-passes | NOT YET INGESTED — Lua walker not built; first Lua ingest |

HTML: best-effort. Capture js_event_binding edges; don't model HTML structure.

### Future additions

- **Zig** — language target; supports C and C++ interop; ast-grep has Zig support built in. Add when a suitable Zig corpus is available. Same LanguageWalker extension pattern as Go/Rust.
- **bethechatbot.com** — future corpus or reference addition. Review site for what specifically to pull in.

### Per-session probe loop (deterministic, no LLM)

Run before any other work. Surface findings + what needs human input.

1. **Stub sweep** — is_stub=1 across active corpora; classify: real gap / test mock /
   Protocol false positive / dead code.
2. **Unresolved edge ratio** — files with highest unresolved callee %; trust floor for
   call chain answers.
3. **ABC gaps** — find_abc_gaps on key subsystems; interface contract drift.
4. **EP inferred count** — inferred vs. explicit EPs; movement signals real graph improvement.
5. **Docstring health** — top-N missing + staleness; where is the knowledge layer thinnest?

Report: "here's what I found / here's what needs your input / here's what I can close."

### Open questions (need Bart's input)

- [x] dj2 331 inferred EPs: accepted as dynamic-dispatch ceiling (2026-07-17)
- [x] suggest_tags / Go/Rust/TS corpora / all deferred: answers may emerge from judgment layer (RM69) rather than requiring human input now (2026-07-17)

### Convergence status

- [x] Determined: probe DONE (2026-07-18, CLOSURE.md Phase 2); adversarial re-run DONE (2026-07-21, session 230) — 3 stubs clean, no false positives, 2 bugs fixed (blast_radius dedup, EP route path depth)
- [x] dj2: probe DONE (2026-07-18, CLOSURE.md Phase 2) — 5 RM68-remove stubs, 5 AI-layer gaps; judgment per RM69
- [x] Commonplace: probe DONE (2026-07-18, CLOSURE.md Phase 2) — 1 stub (suggest_tags), judgment per RM69
- [x] rotjs: probe DONE (2026-07-18, CLOSURE.md Phase 2)
- [x] dungeoncrawler: probe DONE (2026-07-18, CLOSURE.md Phase 2)
- [x] dnd-dungeon-gen: probe DONE (2026-07-18, CLOSURE.md Phase 2)
- [x] end-of-eden: probe DONE (2026-07-18, CLOSURE.md Phase 2)
- [x] ruggrogue: probe DONE (2026-07-18, CLOSURE.md Phase 2)
- [x] slater: probe DONE (2026-07-22, session 237) — 0 stubs (complete server software); 1985 inferred EPs all tests/benchmarks (correct for Rust library crate); #[cfg(test)] no false stubs confirmed; walk_call_chain blind across async boundary (serve_with_listener → 0 nodes, known Rust walker gap); blast_radius clean (593 extended for evict_to_budget); 78 dup names = normal module aliasing, not walker inflation
- [x] llm.c (C+Python+CUDA): probe DONE (2026-07-23, session 245) — 729 symbols / 2960 edges (20 .c/.h + 38 .cu/.cuh + 14 .py); 148 __global__ kernels as is_tool=1; 151 kernel_launch edges (bug fixed this session: was stored as "static"); 22 stubs: 8 CUDA dim3/template false-positives (block_dim, grid_dim, Packed128 etc), 4 cudnn_att conditional-compile stubs (correct, require -DUSE_CUDNN), 2 external API stubs (memcpy, nvtxRangePush), 8 possible real stubs; walk_call_chain FQN fallback fixed; Python (14 files) = separate PyTorch impls, not ctypes wrappers, 0 ctypes edges (correct); blast_radius gpt2_build_from_checkpoint shows 131 extended symbols (correct, whole model struct is impacted)

---

## Work queue — post-walkthrough (session 212, priority order)

Surfaced by live UI walkthrough of dj2 + dungeoncrawler corpora. Work these off in order
— big gains first, polish last.

1. **[x] Test stubs filter in corpus_projections.py** — shape output includes test files
   (test_encounter_fsm.py, test_economy.py) because `_fetch_stubs()` in
   `determined/agent/corpus_projections.py:80` has no test-path filter. `list_stubs` in
   `agent_tools.py:1646` already filters correctly — copy the same `NOT LIKE '%/test_%'`
   conditions into `_fetch_stubs`. All four projection tools (stub_file_shape,
   stub_subsystem_shape, stub_prerequisite_map, stub_concept_ghost_map) call `_fetch_stubs`
   so one fix covers all. ~30 min.

2. **[x] TS call tree FQN fix** — `walk_call_chain` in `agent_tools.py:521` queries
   `WHERE name = ?` with bare name. For TS, functions are stored as FQNs (UIManager.addLogMessage)
   not bare names — so lookup returns nothing and the tree shows "(no callees)".
   Fix: when bare-name row is None, retry with `WHERE name LIKE '%.?'` (FQN suffix match).
   Confirmed broken: addLogMessage (dungeoncrawler, HOT 8 callers) shows empty tree.
   Workaround: use the Graph tab. Affects rotjs, dungeoncrawler, dnd-dungeon-gen.

3. **[ ] RM68 — Remove subrace dead code from dj2** (full design in RM68 section below).
   world/ subsystem verdict is "dead-concept" because 5 subrace stubs dominate. Remove them
   and the real AI-layer signal surfaces. Game work guided by Determined: run
   blast_radius on each subrace stub to confirm low impact, then remove from
   world/dnd_data.py (5 stubs), world/character_generator.py, world/authority_system.py.

4. **[x] classify_stub file_path_hint TS fix** — `agent_tools.py:4817` uses
   `WHERE name = ? AND file_path = ?` with exact match. TS file paths may have separator
   or case mismatch vs what the caller passes. Fix: normalize both sides (replace \\ with /,
   lower) before compare, or use `LIKE` with normalized suffix. Workaround: omit file_path arg.

5. **[x] Ask routing baseline** — "what should I work on next?" hits `prioritize_work` which
   needs workflow items; returns "No active work items" when none exist. Fix: detect the empty
   case and fall back to querying stub shape data (stub_file_shape, stub_subsystem_shape) to
   synthesize an answer. Entry point for the Design Oracle concept.

6. **[x] Design Oracle** — full CRITICAL/OPPORTUNITY/FOREWARNING query over knowledge_artifacts
   + stubs + graph. See FUTURE — Design Oracle section below for full design.
   Do after #5 proves the routing concept.

7. **[x] Polish** — path input UX (show "enter a .db path" hint when directory entered),
   graph_path JS FQN inconsistency (some JS module.method pairs fail), threshold burnishing.

Also fixed this session (session 212):
- _IMPL_WHEN_RE: SetFit false-positive on "will be implemented when X" — classified as
  concept-not-applicable; fixed with deterministic fast-path in has_removal/has_intent (d8e9a63)
- _strip_fences prose preamble (4c77560, session 211)

---

## Dashboard - at a glance

**Last session (2026-07-18, session 212):** Live UI walkthrough (dj2 + dungeoncrawler). Fixed _IMPL_WHEN_RE SetFit false-positive. Work queue above filed from findings. Session 211: _strip_fences fix.

**Previous session (2026-07-18, session 210):** RM-UI-2, 3, 4 done. Full UI redesign arc complete (RM-UI-1 through 4).
RM-UI-2 (3f48c23): project_stub() takes classification kwarg; 4 prompt framings per hypothesis; handle_project_stub passes it through from socket data. Frontend was already correct.
RM-UI-3 (c6f76c2): Shape tab file paths clickable (blue, open editor); symbol names clickable (orange, open spotlight). Server emits navigation index (short_path→full_path, symbol list) alongside text. Delegated click on #shape-grid handles both.
RM-UI-4 (16698d3): Design mode → Shape tab + auto-runs shapeRun(). Trace mode → Frontier tab, filter=direct. Review mode → Frontier tab, filter=chain. Mode hints updated to describe actual surfaces.

**Previous session (2026-07-16, session 196):** Determined corpus re-ingested (functions: 1904->2160, edges: 16588->18693). Fixed 2 stub detection bugs: (1) Protocol method ... bodies were false-positive stubs -- _is_protocol_class() + in_protocol param added to _is_stub; (2) readiness_check ORDER BY is_stub DESC to prefer stub rows on name collision. 5 new tests, 1063 total pass. resolve/suggest_tags now correctly detected; structural_score is confirmed dead code (no callers).

**Previous (2026-07-16, session 195):** RM65 + RM66 done. is_tool column added to functions table (parse_ast.py detects @tool() at ingest; agent_tools._ep_tier now reads column, not decorators_json string). _extract_function_references(): 3 patterns (dict Attribute values, 2-arg register calls, callback kwargs); depth==1 + no-self/cls guard limits false positives. 140 function_reference edges on dj2. builtins.py: 17/18 fns now have callers (was 0). Inferred EPs world/: 185->170. 20 new tests. 1063 pass.

**Previous (2026-07-16, session 192):** RM10 done: goal_intake intent classifier (2A) + trace routing (2B). _classify_goal_type() detects investigate|trace|explain|implement. Investigate goals get READ + BLAST_RADIUS plan (no MODIFY/EXTEND). Trace goals call walk_call_chain() and surface the call path inline. 19 new tests. 1030 pass.

**Previous (2026-07-16, session 191):** RM63 signature fix (param_types_json={} shows () not (?), arguments_json fallback for bare names). RM64 explore_stub: design exploration for BLOCKED stubs -- callers+args, ghost/bridge analysis, sibling stubs, design questions. 12 new tests. All pass.

**Previous (2026-07-16, session 188):** Re-ingested Commonplace corpus (31 syms, 168 edges, http_route populated for 3 routes). Fixed walk_call_chain BFS depth bug: was queuing FQDN callees (services.extractor.extract) for WHERE name=? against functions table which stores bare names -- rsplit fix. Traversal probes: search->DB now 4 nodes deep, capture->storage 16 nodes (full pipeline). 999 tests pass.

**Previous (2026-07-16, session 187):** RM21 Technique 3 done: trace_call_chain pattern + heuristic bug fix. walk_call_chain BFS in agent_tools.py, trace_call_chain detect rule in pattern_executor.py, run_traversal() finds HTTP handlers via http_route col. 14 new regression tests. 999 passed.

**Previous (2026-07-15, session 181):** RM60 Phase 1 done: evaluated all 7 corpora. Key findings: (1) end-of-eden architecture correct, system/game most-connected; (2) dungeoncrawler clean; (3) dnd-dungeon-gen 0 EP bug confirmed - JS target_id is bare name not canonical_id, resolution info lost; (4) ruggrogue file-level grouping works; (5) rotjs lib/src dual-rep documented; (6) Determined depth=2 agent at 83%, structural_score blocking stub; (7) dj2 world/ 10 stubs real (AIDungeonMaster/AdjudicationEngine/ActionQueue). Two new bugs: RM61 (language builtins counted as local-missing), RM62 (JS callee file lost on resolution). Filed Phase 2 checkboxes.

**Previous (2026-07-15, session 178):** Go receiver types in param_types_json (88% typed for end-of-eden, up from 60%). Plain JS excluded from annotation queue. dungeoncrawler/rotjs confirmed TS not JS. RM59 filed: feature shape analysis (list_features, feature_shape, development_priorities). All corpora re-ingested. 892 passed, 1 skipped.

**Previous (2026-07-13, session 170):** LangSpec refactor (e939072): LangSpec dataclass + _shared_call_edges() replaces 3 duplicated walk loops. RM54 done: cross-file resolution post-pass, 2 new tests. dnd-dungeon-gen 974 edges, dungeoncrawler 163 edges. 816 passed, 1 skipped.

**Previous (2026-07-13, session 168):** RM56 done (cc45439: _last_call_fqdn.pop() fix, tuple-unpack comment, 26 data_flow tests pass). Starting RM53 Phase 1.

**Previous (2026-07-13, session 167):** RM39-L3 done (for-loop + kwarg data flow, 8 new tests, 770 passed). RM53-58 designed: LanguageWalker arc via ast-grep covering JS/TS/Go/Rust. JS/TS corpora cloned (dnd-dungeon-gen, dungeoncrawler, rotjs). RM56 Python cleanup started (partial).

**Previous (2026-07-13, session 163):** RM41 done + 16 tests. dj2 re-ingest: 153 files, 1321 fns, 93 http_route, 32 http_fetch, 18 js_event_binding edges. 754 passed, 1 skipped.

**Previous (2026-07-13, session 162):** RM42 Pass 2 done. Clue board now persists across page reloads. Three Flask routes (GET/POST /api/clues, DELETE /api/clues/<id>) store clues as workflow_items (kind='clue'). pinClue() POSTs on add; remove DELETEs; page load fetches and restores _clues. 738 passed, 1 skipped.

**Previous (2026-07-13, session 161):** TODO-1 + RM40 done. http_route TEXT column added to functions table (parse_ast.py extracts from @x.route AST, persistence_engine stores it, migration added). trace_http_chain uses http_route primary lookup with decorators_json fallback + http_fetch edge last-resort. 3 new tests. RM40: resolved_only on _list_callers_raw/_list_callees_raw, list_callers/list_callees/blast_radius. 4 tests. 738 passed, 1 skipped.

**Previous (2026-07-12, session 160):** RM43 done. 5 reasoning lenses (Next action, Blast radius, Open questions, Convergence check, Not ready) in determined/agent/reasoning_lenses.py. /api/reasoning_lenses Flask route. Lens buttons appear in Investigation panel when clues are pinned; each composes a structured prompt prefilling the Ask bar. 731 passed, 1 skipped.

**Previous (2026-07-12, session 159):** RM42 done + dj2 re-ingest. Investigation clue board: pin button on result blocks, clue cards, Ask/Clear actions. http_fetch/js_event_binding fix (read HTML/JS from disk). 731 passed, 1 skipped.

**Previous (session 156):** RM52 done. determined/ingestion/structure_induction.py: fca_pass (FCA/Wille), mdl_pass (MDL/Rissanen), wrapper_pass (LP2/Kushmerick), grammar_pass (L*/Angluin), combine() D-S gate -> convergent/discriminant/review tiers. 28 tests. 672 passed, 1 skipped.

**Previous session (2026-07-12, session 153+):** RM46 + RM47 done. scaffold_from_pattern: module-family + embedding siblings, AST skeleton extraction, canonical/variation-point synthesis, fill-in-the-blanks template, 16 tests. readiness_check: 5-tier pure-DB gate (stub callees, unknown types, design flags opt-in, cycle detection), READY/BLOCKED output with next-step hints, 14 tests. 643 passed, 1 skipped.

**Session 153 (2026-07-12):** RM46 done. scaffold_from_pattern: module-family + embedding-similarity sibling search (threshold 0.50), _extract_structural_skeleton (AST: first_stmt_type/return_shape/error_handling/has_guard), canonical vs variation-point synthesis, fill-in-the-blanks template. 16 tests. 629 passed, 1 skipped.

**Session 152 (2026-07-12):** RM44 + RM45 done. implementation_order: Kahn's BFS topo sort, wave plan, cycle detection, scope filter, 12 tests. completion_contract: one-call impl brief (signature, callers, callees split impl/stub, behavioral contracts w/ docstring fallback, design constraints, optional LLM gate), 11 tests. 613 passed, 1 skipped.

**Session 151 (2026-07-12):** RM51 done. run_annotation_pass driver: _build_annotation_queue (caller-count ordered, scope-filtered, excludes already-annotated) + run_annotation_pass (max_functions cap, convergence_threshold early stop on LLM failure). 9 regression tests. 590 passed, 1 skipped. RM50 tracker status corrected (was done session 149).

**Session 150 (2026-07-12):** RM49 done. annotate_function: LLM-inferred param types, return type, behavioral contract. 15 regression tests. 581 passed, 1 skipped.

**Session 149 (2026-07-12):** RM50 done. Inline comment extraction: tokenizer + regex markers in parse_ast.py, stored as kind=inline_note knowledge artifacts.

**Previously (2026-07-11, session 147):** Corpus enrichment arc filed. Devil's advocate analysis of RM44-RM48 exposed three failure modes: param_types_json sparsity (<1% annotated in dj2), stubs having no docstrings (undermines RM46 embedding), and design notes not existing for fresh corpus (RM47 Tier 4 false-READY). Three new items close these gaps: RM49 (annotate_function: infer types/contracts from call context + LLM), RM50 (inline comment extraction from parse_ast.py), RM51 (annotation pass driver: priority queue + convergence loop). Step 0 action added to RM48: run ingest_design_docs on dj2 design docs before implementing -- costs zero code. 545 passed, 1 skipped (no code changed this session).

**Session 140 (2026-07-10):** RM21 adversarial probe follow-up against Determined corpus. Corrected prior handoff (Q1/Q4/Q5 were partial, not all-pass). Fixed Q4 (imports of <file.py> NEED pattern + list_import_deps resolver + DECOMPOSE_SYSTEM tip) -- now PASS. Fixed Q1 (orient_to_codebase regex expanded to 16 phrasings, moved before understand_symbol in detect rules to prevent false capture) -- now PASS. Fixed grounding pollution (test files/symbols filtered from phase0 suggestions). Known orient misses documented: "how does this work", "summarize the codebase", "tell me about this codebase" -- boundary, not bugs. Q5 still confabulates (model invents query_router/query_session pipeline that doesn't exist); deferred to next session. 533 passed, 1 skipped.

**Session 139 (2026-07-10):** RM28 Stage 5 done. guide_general.json (13 entries keyed by tab/tab:mode) + guideUpdateCard() branch on _isCommonplace in console.html. Non-Commonplace path uses GUIDE_GENERAL with element-only keys and hides the phase picker row. Also ran RM21 6-question probe against Determined corpus: fixed Q6 method confabulation (DECOMPOSE_SYSTEM tip), Q2 blast-radius wrong symbol (pattern_executor detect rule + heuristic past-tense verbs), Q2 blast_radius TypeError (set() cast before subtraction), Q2 OperationalError (functions table literal). 533 passed, 1 skipped.

**Session 138 (2026-07-10):** RM36 + RM37 done. RM36: `_corpus_index()` injects hot files + entry points into Phase 1 DECOMPOSE prompt when grounding is empty -- eliminates `<file.py>` placeholder NEEDs. RM37: negative lookahead on survey heuristic's `what is` branch prevents "path" from being extracted as a symbol name. Also fixed `blast_radius` OperationalError (functions table has no `symbol_type` column -- queried as real column instead of literal). RM21 probe re-run: all 6 queries pass. 533 passed, 1 skipped.

**Session 117 (2026-07-08):** RM27 done. GRASP 9 principles baked as JSON (determined/data/grasp_principles.json + grasp_loader.py), wired into _check_design_violations_core alongside SOTS tenets. check_design_violations now surfaces named GRASP violations (e.g. GRASP-9 Protected Variations on check_design_violations itself). 481 passed, 1 skipped. RM23 also done this session: Phase 3 walk completed on complete Commonplace corpus (25 files, 64 functions). DB reingested 3 Walk 4 files (linker.py, searcher.py, search.py) before walking. Actuals: 0 stubs, 0 ABC gaps, 16 anticipatory orphans, knowledge layer empty (correct fresh-corpus state). Phase 3 section of COMMONPLACE_USER_JOURNEY.md updated with tool outputs. step_queue.md corrected (session 116 claimed advancement but didn't actually write it). No engine files changed; tests not re-run.

**Session 81 (2026-07-05):** Sidebar icon-nav shipped. 4-icon rail (Corpus/Navigate/Tools/Ask) replaces flat sidebar. Corpus panel: analyze + corpus map + gaps. Navigate panel: 6 start-here shortcuts only. Collapse to rail-only on active icon click. 436 passed, 1 skipped.

**Session 67 (2026-07-04):** Item 28 confirmed already done. RM6 + RM7 benchmarked with live 8B. ABC Frontier mode verified in browser (8 classes, 35 methods). reason_about full pipeline fired end-to-end (Decompose â†’ DB â†’ evaluate() â†’ Synthesize). launch.json fixed. 399 tests pass.

**Session 60 (2026-07-03):** Item 27 executed (self-review). Item 28 filed.
infer_behavior refactored to delegate to _infer_behavior_for_symbol (70 lines removed).
classify_references crash on --reingest-file fixed (project_symbols via ctx not analysis).
Determined corpus DB migrated (param_types_json column added); 9 files reingested.
Self-review findings: role inference accurate, match_structural_pattern limited at radius=2
with 3B model, SOTS XI on evaluate() filed as item 28. 372 tests pass.

**Before that (2026-07-01, session 50):** Items 25 + 26 + 14 closed.
Item 14: two-tier LLM in llm_client.py. generate_quality()/chat_quality()/is_available_quality()
target Qwen3.6-27B-Q4_K_M on port 8081, silent fallback to 3B if not running.
_synthesize_with_ollama and gap_analysis upgraded to quality tier; distillation stays 3B.
Start quality tier: llama-server.exe -m models/gguf/Qwen3.6-27B-Q4_K_M.gguf --port 8081
Items 25+26: llama-server migration complete, Ollama uninstalled, ~50GB freed. 335 passed, 1 skipped.

**Before that (2026-07-01, session 50 earlier):** Items 25 + 26 closed.
All Ollama call sites in Determined were already migrated to llm_client.py targeting
llama-server on port 8080. Fixed one broken import (OLLAMA_MODEL) in claude_eval.py
that would have crashed on import. Ollama uninstalled; ~50GB freed. No open numbered
items remain. 335 passed, 1 skipped.

**Before that (2026-06-30, session 43):** Items 23 + 24 done.
docstring_health tool: missing detection (SQL), staleness detection (cosine similarity vs
distilled summary, threshold 0.55), proposal storage in workflow queue. gap_analysis tool:
on-demand LLM brainstorm of typed fills (extend/bridge/mirror/consolidate) for a scoped
area, stores as backlog item, framed as generative/idea-mode. _gap_summary_block() fast
DB-only helper now embedded in knowledge_status as GAPS AT A GLANCE section. Both wired
into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern. 323 pass, 1 pre-existing flake, 1 skip.

**Before that (2026-06-30, session 42):** Items 21 + 22 done.
symbol_context tool: unified single-call view of everything known about a symbol
(declaration, docstring, risk, find-references, callers/callees, class attrs, design
frame, findings). concept_search tool: semantic + keyword search across all text
surfaces ranked by cosine similarity. Both wired into TOOLS, REGISTRY, TASK_PATTERNS,
detect_pattern. understand_symbol pattern now single step. 321 tests pass.

**Before that (2026-06-29, session 36):** Items 25/26 filed (llama-server migration).
llama-server b9842 downloaded to C:\Users\bartl\models\llama-server\llama-server.exe.
llama3.2-3b.gguf copied to C:\Users\bartl\models\gguf\. Health check passing.
Items 21-24 designed and filed (assistant arc). Items 1/2/3 closed.

**Before that (2026-06-29, session 36 earlier):** Items 1, 2, 3 closed. Items 21-24 designed and filed (assistant arc).
Items 2 and 3 superseded by 22 and 23 respectively. No code written for 21-24 yet.

**Before that (2026-06-29, session 36 earlier):** Items 1, 2, 3 closed.
Item 1: _classify_role() in parse_ast.py (test/entry_point/init/config/module heuristics).
Migration guards removed from persistence_engine; param_types_json moved into CREATE TABLE.
Items 2 and 3: explicitly deferred - no active need. No open numbered items remain.
323 pass, 1 pre-existing Windows file-handle flake.

**Before that (2026-06-29, session 35):** Items 6 and 20 done.
Item 6: reingest_file() incremental re-ingest, FileDelta scratchpad, INSERT OR IGNORE fix.
Item 20: param annotation capture (param_types_json), class attribute tracking
(class_attributes table), annotation-resolved call edges (SymbolReference.resolved,
GraphEdge.resolved, graph_edges.resolved), list_callers/callees tag, describe_file %
stat, DBOracle.get_class_attribute_type(). 19 new tests total. 296 pass.

**Before that (2026-06-29, session 35 earlier):** Item 6 done: incremental per-file re-ingest.
reingest_file() in determined/ingestion/reingest_file.py. FileDelta in-memory scratchpad
(old/new symbol state, added/updated/removed sets). apply_file_delta: insert new symbols
first, then persist_file_analysis, then delete stale old symbols, then rebuild outbound
edges. Inbound edges to removed symbols become honest dangling references. Fixed
_insert_symbol to INSERT OR IGNORE (was plain INSERT - latent re-ingest bug). Wired as
agent tool, CLI --reingest-file, REGISTRY. 6 new tests; 283 pass.

**Before that (2026-06-29, session 34):** Contracts fully reconciled and wired (item 7).
PyAnalyzer (ICSE 2024) reviewed; annotation-based call graph accuracy improvement
planned as item 20. SESSION_STATE updated.

**Before that (2026-06-28, session 33):** knowledge.db eliminated.
All tables (knowledge_artifacts, workflow_items, bags, bag_items) now live in corpus
DB. KnowledgeOracle deleted. Assessor._knowledge_conn returns oracle.conn. SOTS baked
as JSON (sots_tenets.json + sots_loader.py). semantic_summaries moved to corpus DB.
DB naming fixed (C_Users_bartl_dev_harrow.db). 304 regression tests pass.

**Before that (2026-06-28, session 32):** Items 9, 10, 19 done.
Item 9: distillation pass - distill_corpus() tool, distilled kind in knowledge_artifacts,
wired into symbol_brief (preamble) and goal_intake step 1 (enriched embedding). 301 tests.
Item 10: _raw helpers layer - 5 private raw helpers (_search_symbols_raw, _list_callers_raw,
_list_callees_raw, _graph_most_connected_raw, _graph_subgraph_raw), string tools now derive
from raw (XIV: one source of truth), goal_intake step 1 uses _search_symbols_raw. 303 tests.
Item 19: check_design_violations tool - semantic cosine-search against design_notes, constraint
language filter, wired into risk_profile, pure analysis only (SOTS XI). Self-audit ran against
Determined's own corpus (168 design_notes, 5 WARM symbols) - produced real findings, validated.

---

## UI Redesign Arc — running detail (session 209+)

Design north star: the UI proves the tool works. Every surface connects to
every other. Stubs, projections, judgment, proposals, and the editor are a
navigable pipeline — not isolated tabs you query separately.

### RM-UI-1: Stub classification in spotlight [DONE 2026-07-18]

**What it does:**
When any stub is opened in the spotlight panel, the backend runs
`classify_stub` and returns structured JSON. The spotlight renders a
"Stub Judgment" section with colored hypothesis chips, confidence %,
and evidence sentences. A "propose (classification)" button appears,
enabled once the judgment arrives.

**How it works — backend:**
- New socket event `classify_stub_spotlight` in `ui_server.py`
- Handler calls `extract_signals(oracle, symbol)` + `score_hypotheses(signals)`
  directly (not the text formatter) to get structured data
- Emits `classify_stub_spotlight_result` with:
  `{ symbol, top_hypothesis, top_score, uncertain, hypotheses, signals, file_path, line_number }`
- `hypotheses` is a list of `{ classification, score, evidence[] }`
- `signals` carries: caller_count, sibling_stub_count, body_shape,
  file_character, is_protocol_or_abc, is_lifecycle, intent_text

**How it works — frontend (console.html):**
- `SP_SECTIONS` gains a `judgment` entry (order 2, `stubOnly: true`)
  — hidden by default, only shown when `is_stub` confirmed
- `openSpotlight()` builds the judgment placeholder as `display:none`
- When `symbol_quick_result` fires with `is_stub: true` for the
  current spotlight symbol:
  - The judgment section is revealed (`display: ""`)
  - A "propose impl" button is appended to spotlight actions (disabled)
  - `classify_stub_spotlight` is emitted to the backend
- When `classify_stub_spotlight_result` arrives:
  - Signal summary line (body shape, caller count, sibling count, tags)
  - Each hypothesis renders as a colored chip with left border:
    - design-intent-stated → green
    - blocked-on-prerequisite → orange
    - concept-not-applicable → blue
    - genuinely-unknown → grey
  - Top hypothesis is bold; others are dimmed (opacity .75)
  - Confidence % shown top-right of each chip
  - Up to 2 evidence bullets per hypothesis
  - Low-confidence footer if `uncertain: true`
  - "propose impl" button enabled, relabeled "propose (design)" etc.
    using the first word of the top hypothesis classification
  - `dataset.classification` set on the button for downstream use

**Verified live (2026-07-18):**
- `process_consequences` in dj2: shows "design intent stated" (40%,
  green) + "genuinely unknown" (20%, grey). Evidence: docstring
  intent language. Propose button enabled labeled "propose (design)".
- 52 tests pass (test_classify_stub + test_ui_surfaces)

**Files changed:**
- `determined/ui/ui_server.py`: added `classify_stub_spotlight` handler
- `determined/ui/templates/console.html`: SP_SECTIONS, openSpotlight,
  symbol_quick_result handler, classify_stub_spotlight_result handler

### RM-UI-2: Propose → fulfill loop [DONE 2026-07-18]

`project_stub()` now accepts `classification` kwarg. Four prompt framings:
design-intent-stated / blocked-on-prerequisite / concept-not-applicable / genuinely-unknown.
`handle_project_stub` pulls classification from socket data and passes through.
Frontend was already correct (dataset.classification set by classify handler).
Commit: 3f48c23

### RM-UI-3: Shape tab → editor navigation [DONE 2026-07-18]

File paths in Shape tab render as blue clickable spans (open editor).
Symbol names render as orange clickable spans (open spotlight).
Server emits `index: {files, symbols}` alongside text on shape_result.
Delegated click on #shape-grid — no re-binding on re-run.
Commit: c6f76c2

### RM-UI-4: Mode = curated entry point [DONE 2026-07-18]

Design mode → Shape tab, auto-runs shapeRun() if not loaded.
Trace mode → Frontier tab, filter=direct (caller→stub), triggers fgLoad_().
Review mode → Frontier tab, filter=chain (stub chains), triggers fgLoad_().
Mode hints updated. CSS tab highlights updated for Design (shape/knowledge/editor).
Commit: 16698d3

---

**Before that (2026-06-28, session 30):** Mentor arc complete. Items 23/24/25 closed.
Item 23 rebuilt on embeddings (all-MiniLM-L6-v2, docstring-enriched queries, threshold 0.32).
SOTS (shapeofthesystem.com, 25 tenets) ingested into knowledge.db as design_notes -- surfaces
automatically via frame comparison. Item 24: goal_intake tool -- natural language goal ->
navigation plan (relevant symbols + risk badges + design rules + ordered approach). Item 25:
corpus map branch merged and deleted. Determined .claude/ added (same as dj2). 320/322 passing.

**Before that (2026-06-25/26, session 19):** Multiple bug fixes + corpus scoping + dj2 design docs.
Items 16/17/18 all fixed and closed. run_engine.py repo_root hardcoded to "." - fixed. scan_project_files.py:
3.10/3.11/3.12 venv dirs now excluded. knowledge.db corpus scoping complete (corpus column on knowledge_artifacts
+ semantic_summaries, scoped across all read/write paths: intent, oracle, assessor, agent layers). UI corpus
switch tab refresh fixed (_startupFiredFor tracks DB path). DB lock on re-analysis fixed (close oracle before
unlink). ingest_done now triggers corpus_status -> corpus_ready -> tab refresh. Regression fix: stale
test_list_callees_no_callees assertion. 298/298 passing. dj2 design docs written: 00E AI_LAYER_OPPORTUNITIES,
00F ASPIRATIONAL_DESIGN_INTENT (section H links back to item 19). Item 14 (validate small-model) is now
unblocked - all blockers resolved, harrow corpus clean and scoped.

**Before that (2026-06-24, session 17, continued):** Tool registry. New file:
determined/agent/tool_registry.py - REGISTRY (28 tools, full metadata: purpose/args/output/feeds/use_when/category),
TASK_PATTERNS (7 named workflows), describe_tool (callable from agent). agent_prompt.py now generates
TOOL_DESCRIPTIONS from the registry (all 28 tools, grouped by category). describe_tool wired into TOOLS.
2 new tests. 276/276 passing.

**Before that (2026-06-24, session 17, continued):** Knowledge layer additions.
extract_design_facts() - no-LLM structural extraction (entry points, dead code, hot symbols, stub files).
knowledge_status tool, get_findings expanded to semantic_summaries. 274/274 passing.

**Before that (2026-06-24, session 17):** Ran tool against dj2 corpus, found and fixed 5 real bugs.
is_hot was hardcoded False (now bool(mutations)); is_stub column missing from old DBs (migration added);
graph_most_connected returned builtins/externals (now project-only); find_todos only scanned docstrings
(now scans file content); task_generator had tools/analysis branding. Also fixed 2 stale regression tests.
274/274 passing. dj2 corpus re-ingested: 150 files, 132 hot, 47 stubs detected.

**Previously (2026-06-24, session 16):** Migration complete.
tools/analysis/ deleted from dj2. Engine now lives exclusively in Determined.
28 regression test files (279 tests) passing. knowledge.db intact (77KB).
dj2 is game code only. Both repos committed and pushed.

**Item 14 done (2026-06-27):** llama3.2:3b validated cold against harrow corpus.
All 7 orient_to_codebase steps fired in order. Model did not hallucinate tool names or skip steps.
Final synthesis correctly identified the key symbols. Pattern executor works. Item 14 closed.

**Item 15 done (session 18):** Pattern executor built and wired in. Model no longer picks
tools when a named pattern matches - executor drives the sequence, model only interprets
each step result. 293/293 tests passing.

**Full history:** `git log` (HISTORY.md is a decision log, not a session diary).

---

## Open items

---

RM65. **[DONE 2026-07-16] function_reference edge type in parse_ast.py**

   _extract_function_references() in parse_ast.py: 3 patterns (dict Attribute values
   depth==1 non-self/cls, 2-arg register calls, callback kwargs target=/key=/callback=).
   Wired into parse_ast() after dynamic edges. 140 edges on dj2. builtins.py 17/18
   fns gain callers. Inferred EPs world/ 185->170. 20 regression tests. 3 commits:
   91dc6e9 (is_tool layer fix), 9993e06 (function_reference), 6f6cd36 (fp tightening).

---

RM66. **[DONE 2026-07-16] Layer audit: move Python-specific detection out of tool layer**

   is_tool INTEGER DEFAULT 0 added to functions table. parse_ast.py detects @tool(...)
   via isinstance AST check at ingest time. _ep_tier() signature changed: takes is_tool
   bool instead of decorators_json. Both list_entry_points and detect_doc_drift SELECT
   is_tool; no more string matching in tool layer. Migration guard added for existing DBs.
   Commit: 91dc6e9.

---

RM-Perf. **[TODO] Optimization Oracle: static purity analysis + profiling overlay**

   **Origin:** Bart's idea (2026-07-15) — after the analysis/code-generation side is
   complete, build an `OptimizationOracle` alongside `DBOracle`. Instead of answering
   structural questions ("who references this?"), it answers performance questions:
   which functions dominate runtime, which values are repeatedly recomputed, which
   graph traversals could be cached, which semantic queries are duplicated, which
   events never influence observable state, which deterministic computations are pure
   and memoizable, which Python objects have stable layouts suitable for array-based
   storage.

   **Core insight:** the static call graph already has the symbol FQDNs and edge
   topology. Profiling data (Python cProfile, V8 flame graphs, etc.) maps back to
   the same FQDNs. A normalization layer that joins hot call-path data to existing
   `functions` and `graph_edges` rows is the main new piece; the rest is queries.

   **Two tiers — keep separate:**

   - **Statically inferable (no profiling needed):** pure/memoizable functions
     (no writes to shared state, no I/O, deterministic outputs), dead event handlers
     (js_event_binding edges whose source never influences observable state), stable
     object layouts (Python classes where `__init__` only assigns scalar attrs with
     no dynamic keys). These are answerable from the existing DB today.

   - **Profile-grounded (needs runtime traces):** hot-path dominance, repeated
     recomputation on hot edges, traversals that fire on every query, duplicate
     semantic queries. Requires an instrumentation hook (cProfile decorator injection
     or sampling profiler output) to produce a `call_samples` table keyed by FQDN.
     Static tier ships first; profile tier follows after instrumentation exists.

   **Fit with existing architecture:**
   - `DBOracle` stays structural. `OptimizationOracle` wraps the same DB + an optional
     profiling DB and answers perf questions.
   - Corpus-agnostic design holds: normalization maps any profiler's output to FQDNs
     already in the DB. Language-specific only at the profiler adapter layer.
   - The "make the engine observable so AI can continuously identify bottlenecks"
     principle (Bart, 2026-07-15) is the design philosophy here — raw model speed
     compounds less than persistent observability.

   **Prerequisite:** analysis/code-generation arc complete (RM21, RM39-L3 done).
   Static purity sub-tier could ship earlier as a standalone tool with no new infra.

   **Estimated effort:** static tier ~1 session (graph walk for purity classification).
   Profile-grounded tier: instrumentation adapter + query layer, ~2-3 sessions.

---

RM63. **[DONE 2026-07-15] feature_work_plan: ordered work plan for a feature from graph + contracts**

   **Goal:** given a feature path, produce a handoff-ready work plan that drives
   development without requiring the user to hold the whole project in their head.
   The tool that makes the invisible visible: what's incomplete, what order to tackle
   it, what each piece needs to do, and a scaffold to start from.

   **Output:** structured data formatted like a SESSION_STATE "NEXT SESSION" block --
   decisive, ordered, each item actionable. Ready to paste into a large LLM prompt
   for the narrow implementation step without reformatting.

   **Algorithm:**
   1. Find all stubs + missing functions in feature_path (deterministic, DB query)
   2. For each, look up outbound graph_edges callees -> group by destination directory = axes
   3. Sort axes by EP-weighted impact (how many entry points unblock when axis is complete)
   4. Within each axis, sort by implementation_order (topo sort, existing tool)
   5. For each function: emit completion_contract slot (grounded) + scaffold reference
      if a pattern match exists (scaffold_from_pattern, existing tool)
   6. Uncertain behavioral contracts flagged [infer: ...], not stated as fact

   **Loop:** user implements, re-ingests, re-runs feature_work_plan. Resolved stubs
   drop off; next item advances automatically.

   **Validation target:** dj2 world/ feature. Known ground truth: 10 real stubs,
   combat layer is the primary axis. Tool is working when it surfaces that axis
   clearly with correct order and grounded contracts.

   **New code:** axis-clustering step + composition wrapper. Everything else is calls
   to existing tools (implementation_order, completion_contract, scaffold_from_pattern,
   readiness_check).

   **Estimated effort:** 1 session.
   **Gate for RM64:** validate on dj2 before considering follow-ons.

---

RM64. **[DONE 2026-07-16] feature_work_plan follow-on considerations**

   Validated on dj2 world/ (session 191). 10 stubs, all BLOCKED, all land in
   world/placeholder axis (axis-grouping only differentiates when stubs have callees).

   **Done:**
   - RM63 signature fix: param_types_json={} shows () not (?); arguments_json fallback
     for bare param names when types absent.
   - explore_stub (Explore mode): surfaces callers+args, contract, ghost/bridge analysis,
     sibling stubs, design questions for BLOCKED stubs. 12 regression tests.

   **Remaining candidates:**
   - **Close-the-loop verification:** after re-ingest, check implemented fn resolves
     stub, satisfies callers, no new unresolved callees.
   - **Doc-drift detection:** design_note artifacts vs call graph -- new EPs with no
     design note, stub closed in way that changes expected callers.

---

RM65. **[DONE 2026-07-15] find_missing_bridges: detect when a stub's inputs cannot reach the data it needs**

   **Origin:** Surfaced 2026-07-15 while using feature_work_plan on dj2 world/.
   `_get_encounter_context(session_id)` could not be implemented because no function
   in the codebase maps session_id -> Encounter. That gap is invisible to readiness_check,
   which only checks whether callees are stubs -- not whether the input-to-output route
   exists at all.

   **The check (deterministic):**
   For each stub:
   1. Take its input types (from param_types_json)
   2. Take its return type (from return_type)
   3. Walk the call graph: does any chain exist from a function that takes the same
      input type to a function that returns or holds the needed output type?
   4. If no path exists: emit "missing bridge: <input_type> -> <output_type>,
      no path found -- add a function or field that connects them"

   **New blocker tier:** add to readiness_check as Tier 0 (prerequisite data bridge),
   or ship as a standalone tool first and integrate later.

   **Validation target:** dj2 world/_get_encounter_context. Should surface:
   "missing bridge: session_id -> Encounter, no path exists -- WorldController needs
   session_encounters: dict[str, str] or equivalent."

   **Estimated effort:** 1 session. Mostly graph traversal + type string matching.
   LLM not required.

---

RM66. **[DONE 2026-07-15] find_concept_ghosts: stubs that reference concepts with no symbol in the graph**

   **Origin:** Surfaced 2026-07-15. `_get_combat_context` says "Query active CombatFSM"
   in its docstring/contract, but CombatFSM does not exist as a class or symbol anywhere
   in the corpus. That gap is invisible to all current tools -- the stub looks like any
   other BLOCKED stub, with no signal that its entire prerequisite concept is absent.

   **The check (deterministic):**
   For each stub:
   1. Extract noun phrases from docstring + contract text (simple regex: capitalized
      runs, CamelCase tokens, words before "FSM"/"Manager"/"Engine"/"System")
   2. For each candidate concept name, check whether any symbol in functions or classes
      table matches or fuzzy-matches it
   3. If no match: emit "concept ghost: '<ConceptName>' referenced in contract but no
      symbol exists -- this stub may need a prerequisite class/module built first"

   **Why it matters:** a concept ghost means the stub is not just BLOCKED, it is
   UNGROUNDABLE -- you cannot implement it at all until the referenced concept exists.
   That is categorically different from a missing callee and should be surfaced before
   the user picks up the stub to implement.

   **Validation target:** dj2 world/_get_combat_context. Should surface:
   "concept ghost: 'CombatFSM' referenced in contract, no matching symbol found."

   **Estimated effort:** 1 session. Regex extraction + symbol lookup. LLM optional
   for fuzzy concept matching but not required for the core signal.

---

RM60. **[DONE 2026-07-15] Corpus analysis quality audit — evaluate what the tools see and miss across all 7 corpora**

   The goal: run the RM59 tools (and supporting tools) against every corpus DB,
   verify the output is accurate against ground truth, and file fix items for
   systematic gaps. Determined and dj2 are unknowns; the other 5 are known-complete
   projects that serve as ground truth.

   **Pre-audit finding (session 179, 2026-07-15):** Two structural problems found
   before the per-corpus work even starts:

   1. **Absolute path depth bug (P0):** All corpus DBs store Windows absolute paths.
      `depth=1` collapses everything under `C:` — useless. The correct depth per
      corpus is `common_prefix_depth + 1` (ranges from 6 to 8 across corpora). Fix:
      add `prefix` parameter to `list_features`, `feature_shape`, and
      `development_priorities` that strips the given path prefix before computing
      depth and display labels. Auto-detect if omitted (use common prefix of all paths).

   2. **"Missing" count inflation (P1):** Callees with no `functions` row include
      stdlib, pip packages, and all external library calls — not just unimplemented
      locals. This inflates the "missing" count and makes completeness% misleading
      (Determined shows 50% when it is effectively feature-complete). Fix: separate
      local-missing (callee not in functions AND its file would be under the corpus
      root) from external-missing (library call). Only local-missing counts toward
      completeness%.

   **Phase 0 - Fix structural problems first (prerequisite for accurate audit)**
   - [x] Add `prefix` param (auto-detected from common path prefix) to `list_features`,
         `feature_shape`, and `development_priorities`. Labels strip the prefix.
         Done 2026-07-15: _detect_prefix/_strip_prefix/_dir_key_fn helpers. 14 new tests.
   - [x] Fix "missing" inflation: _is_external_callee() filters dotted names (os.path.join
         etc.) as external; only bare names count as local-missing in completeness%.
         feature_shape distinguishes 'external' vs 'local-missing' in output.
         Done 2026-07-15: 931 tests pass.

   **Phase 1 - Per-corpus evaluation (run after Phase 0)**

   For each corpus: run `list_features` (correct depth), `development_priorities`,
   and `knowledge_status`. Verify against ground truth. Record findings in this item.

   Known-complete corpora (ground truth: should show 0 or near-0 stubs, meaningful
   features, reasonable entry point topology):

   - [x] **end-of-eden (Go)** - DONE 2026-07-15. system (270EP) and game (200EP) correctly
         most-connected. 0 stubs confirmed. Cross-feature calls (game/fs.Walk -> assets,
         system/audio -> assets) real and sensible. Finding: Go builtins (make, len,
         uint64, string) classified as local-missing - false positives, see RM61.

   - [x] **ruggrogue (Rust)** - DONE 2026-07-15. File-level grouping correct for Rust's
         one-concept-per-file layout. map.rs (31EP), experience.rs (28EP) correctly identify
         most-shared modules. gamekey.rs (1 sym, 17EP) = input key enum called everywhere.
         0 stubs confirmed. Finding: Rust local-missing also inflated by builtins, see RM61.

   - [x] **dungeoncrawler (TS)** - DONE 2026-07-15. rendering (9EP), entities (8EP), ui (8EP)
         correctly most-called. 0 stubs confirmed. core (5 local-missing, 0EP) is consumed
         internally. Architecture matches TS dungeon crawler structure.

   - [x] **dnd-dungeon-gen (JS)** - DONE 2026-07-15. 0 EP bug CONFIRMED. Root cause:
         JS ingester stores resolved=1 edges but target_id = bare callee name (e.g.
         'generateDungeon') not canonical_id. canonical_id format is
         'file:function:module.name:line'. These never match -> cross-feature edge
         computation returns 0. Suffix match (s.name LIKE '%.' || ge.callee) correctly
         resolves controller -> dungeon/generate.js. See RM62.

   - [x] **rotjs (TS library)** - DONE 2026-07-15. lib/ (290sy, 297EP) is compiled JS
         output; src/ (271sy, 0EP) is TS source. All imports point to lib/ -> lib/ gets
         all EP. Pattern documented: for TS libs that ship compiled output, analysis
         should target src/ for architecture; lib/ EP shows public API usage. 3 stubs in
         lib/ (Room.createRandomCenter, Room.createRandom, RNG.getItem) - real gaps in
         compiled output. Term.computeFontSize is src/ blocking stub.

   Unknown-completeness corpora (what we are actually trying to understand):

   - [x] **Determined (Python)** - DONE 2026-07-15. depth=2 run: determined/agent (173EP,
         83% complete, 1 stub), determined/ingestion (48EP, 72%), determined/graph (1 stub:
         structural_score blocking). determined/resolution at 20% with 1 stub is concerning.
         feature_shape completeness% (14%) inconsistent with dev_priorities% (83%) because
         feature_shape counts all edge instances, dev_priorities counts distinct callees.
         Python builtins (print, range, len, int, list) classified as local-missing - see RM61.

   - [x] **dj2 (Python+JS)** - DONE 2026-07-15. world/ 10 stubs are REAL: class methods
         called but not defined - AIDungeonMaster (dialog, narrative), ActionQueue (dequeue,
         is_empty), AdjudicationEngine (process, start_encounter, _handle_*). These are
         genuine implementation gaps in the combat/adjudication layer. Blocking stub:
         _get_combat_context. world_app.py (160EP) correctly identified as primary entry file.

   **Phase 2 - File gap items for confirmed problems**
   - [x] JS cross-file resolution gap - confirmed, filed as RM62
   - [x] Test-directory noise in development_priorities (filter option needed)
         Done 2026-07-15: exclude_tests=True default in list_features and development_priorities.
         _is_test_feature() matches tests/, test/, spec/, __tests__/, test_*.py etc. 5 new tests.
   - [x] Flat-layout usability (Rust src/ problem - auto-detect single-level flat?)
         Resolved by Phase 0 prefix auto-detect: depth=1 after prefix strip gives individual
         .rs files as features for ruggrogue, which is the correct Rust file-level granularity.
         No additional code needed.
   - [x] rotjs lib/src dual-representation confusion (document or auto-detect?)
         Done 2026-07-15: list_features detects compiled-output pattern (lib/dist/build/out
         EP >= 5x src/ EP, src/ has >10 syms) and appends a Note suggesting scope=src.
         Warning suppressed when scope= already active. 3 new regression tests.
   - [x] Language builtins as local-missing - confirmed, filed as RM61
   - [x] dj2 stubs identified: AIDungeonMaster/AdjudicationEngine/ActionQueue - real gaps

   **Depth reference (for future sessions):**
   | Corpus | Common prefix | Feature depth |
   |--------|--------------|---------------|
   | Determined | C:/Users/bartl/dev/Determined | 6 |
   | dj2 | C:/Users/bartl/dev/dj2 | 6 |
   | end-of-eden | C:/Users/bartl/dev/corpora/end-of-eden | 7 |
   | ruggrogue | C:/Users/bartl/dev/corpora/ruggrogue/src | 8 |
   | dnd-dungeon-gen | C:/Users/bartl/dev/corpora/dnd-dungeon-gen/app | 8 |
   | dungeoncrawler | C:/Users/bartl/dev/corpora/dungeoncrawler/src | 8 |
   | rotjs | C:/Users/bartl/dev/corpora/rotjs | 7 |

---

RM62. **[DONE 2026-07-15] JS ingester loses callee file on resolution - 0 entry points for all JS features**

   Fixed 2026-07-15 (8452d9d): resolution post-pass UPDATE now also sets
   callee and target_id to functions.name (qualified FQDN) in the same
   statement. Bare-suffix fallback in list_features/development_priorities
   (session 182, bc7ae69) was a tool-side workaround; this fixes the root
   cause in the ingester. 2 new tests + 2 updated. 948 passed.
   **TODO: re-ingest dnd-dungeon-gen** to pick up qualified callee names.

---

RM61. **[DONE 2026-07-15] Language builtins classified as local-missing, inflating miss counts**

   Fixed 2026-07-15 (15469fb): added _PY_BUILTINS, _GO_BUILTINS, _RUST_BUILTINS
   sets and _detect_corpus_lang() to identify dominant language from file extensions.
   _is_external_callee() now accepts optional builtins set; feature_shape and
   development_priorities detect corpus language once and pass it through.
   5 new regression tests. 938 passed.

---

RM59. **[DONE 2026-07-15] Feature shape analysis: directory-first feature grouping, path tracing, and completeness scoring**

   Adds a corpus-agnostic layer that answers "what features exist, which are complete,
   and what should be worked on next" — a synthesis level above individual symbol tools.

   **The gap:** all existing tools operate at symbol or file scope. No tool aggregates
   symbols into features, traces the end-to-end path a feature takes through the call
   graph, or scores path completeness. A human currently has to do that synthesis across
   blast_radius + readiness_check + stub detection. This RM makes it a single call.

   **Grouping strategy: directory-first**
   Each directory (at configurable depth, default 1) is a candidate feature.
   Directory name = feature label. Corpus-agnostic — works for Python, Go, Rust, JS/TS
   without language-specific logic. Phase 2 can layer semantic re-clustering on top.

   **Three new tools:**

   `list_features([depth=1][, scope])` — directory scan
   - Groups `files` table entries by first `depth` path segments
   - For each group: symbol count, stub count, entry points (symbols called from outside
     the directory), cross-feature dependency count
   - Returns ranked list: most entry points first (= most externally visible features)
   - Pure SQL, no LLM, fast

   `feature_shape(feature_path)` — path tracing
   - Takes a directory path (e.g. "combat/", "determined/agent/")
   - Gets all local symbols: `SELECT ... FROM functions WHERE file_path LIKE 'feature_path%'`
   - Entry points: local symbols with callers from outside the directory
   - Traces forward from each entry point via call graph (uses existing `subgraph_around`
     primitive, scoped to feature + one hop out)
   - Each node annotated: implemented / stub / missing (callee has no symbol row)
   - Each edge annotated: resolved / unresolved
   - Cross-feature edges flagged as dependencies (feature A calls into feature B)
   - Output: structured path DAG with per-node completeness status and blocking nodes

   `development_priorities([scope][, top_n=10])` — priority ranking
   - Runs list_features + feature_shape across all features (or scoped subset)
   - Completeness score per feature = implemented_nodes / (implemented + stub + missing)
   - Priority score = (1 - completeness) x entry_point_caller_count
     (incomplete features with many callers blocked on them rank highest)
   - Secondary sort: features whose stubs appear in other features' paths (cross-feature
     blockers rank above self-contained gaps)
   - Returns ranked table: feature, completeness%, blocking_node, priority_score
   - Optional: flag which features have design doc coverage (RM48 delta) vs none

   **Data already available (no new ingestion needed):**
   - `files.file_path` — directory derivable by splitting on `/`
   - `functions.is_stub`, `functions.docstring`, `functions.param_types_json`
   - `graph_edges.caller`, `graph_edges.callee`, `graph_edges.resolved`
   - `graph_edges.edge_type` — static vs data_flow, both count for path tracing
   - Entry points already determinable: callers from outside directory in graph_edges
   - `knowledge_artifacts` kind=design_note for design coverage signal

   **What "missing node" means:**
   A callee that appears in graph_edges but has no row in the functions table is an
   unresolved external. A callee that HAS a row but is_stub=1 is a local stub — the
   blocking kind. The distinction matters: external gaps are library calls (not actionable),
   local stubs are implementation gaps (actionable).

   **Cross-feature dependency graph:**
   When feature A has edges into feature B's symbols, A depends on B. This is derivable
   from the same data: graph_edges where caller_file_path prefix != callee_file_path prefix.
   `development_priorities` uses this to surface cross-feature blockers.

   **Implementation plan:**
   - Phase 1: `list_features` + `feature_shape` in agent_tools.py. Wire into tool_registry.
     Regression tests with in-memory DB seeded with multi-directory symbol sets.
   - Phase 2: `development_priorities` aggregation. Cross-feature dependency graph.
   - Phase 3 (future): semantic re-clustering as override for poorly-organized corpora.

   **Regression tests:**
   - list_features groups symbols by directory correctly
   - list_features depth=2 gives sub-feature granularity
   - feature_shape identifies entry points (external callers only)
   - feature_shape marks stub nodes correctly
   - feature_shape marks missing-callee nodes (not in functions table)
   - feature_shape emits cross-feature dependency edges
   - development_priorities ranks high-caller stubs above low-caller stubs
   - development_priorities ranks cross-feature blockers above self-contained gaps

   **Estimated effort:** Phase 1: 1 day. Phase 2: 0.5 day.

---

RM58. **[DONE 2026-07-13] Clone validation corpora for RM53-57 testing (JS/TS/Go/Rust)**

   Five reference corpora covering RM53-57 test surface across four languages.
   Together they validate the "corpus-agnostic" claim: one LanguageWalker abstraction
   handles Python, JS, TS, Go, and Rust without per-language plumbing changes.
   Clone into `C:\Users\bartl\dev\corpora\` (sibling to dj2).

   **Corpora:**

   | Repo | Language | Size | What it tests |
   |------|----------|------|---------------|
   | [GadgetBlaster/JavaScript-DnD-Dungeon-Generator](https://github.com/GadgetBlaster/JavaScript-DnD-Dungeon-Generator) | Vanilla JS, ES modules, zero deps | 112 JS files | fn→fn call chain: controller→dungeon→room→item→utility; vanilla JS data flow |
   | [HermannPR/DUNGEONCRAWLER](https://github.com/HermannPR/DUNGEONCRAWLER) | TypeScript | 14 TS files | Class method calls, Game.ts coordinator, entities/world/combat/ui hierarchy |
   | [ondras/rot.js](https://github.com/ondras/rot.js) | TypeScript library | 49 TS files | Library-scale: exported API, many cross-module callers; blast_radius |
   | [BigJk/end_of_eden](https://github.com/BigJk/end_of_eden) | Go (+ Lua content layer) | medium | Go package call graph: game/→ui/→system/; Go→Lua boundary mirrors dj2's Python→JS |
   | [tung/ruggrogue](https://github.com/tung/ruggrogue) | Rust (99.7%) | ~400 commits | Rust module + trait call graph; has 20-chapter architecture guide = ground-truth validation |

   **JS/TS corpora already cloned [V]** (session 167):
   ```
   C:\Users\bartl\dev\corpora\dnd-dungeon-gen
   C:\Users\bartl\dev\corpora\dungeoncrawler
   C:\Users\bartl\dev\corpora\rotjs
   ```

   **Go + Rust corpora (clone before implementing Go/Rust LanguageWalker):**
   ```
   git clone https://github.com/BigJk/end_of_eden corpora/end-of-eden
   git clone https://github.com/tung/ruggrogue corpora/ruggrogue
   ```

   **Validation targets by language:**
   - **JS** dnd-dungeon-gen: `controller → dungeon → room` call chain surfaces
   - **TS** dungeoncrawler: `Game → CombatSystem → Entity` with class-method fqdns
   - **TS** rot.js: blast_radius on a core export shows meaningful cross-module reach
   - **Go** end_of_eden: `game.* → ui.* → system.*` package call graph surfaces
   - **Rust** ruggrogue: call graph matches the documented architecture chapters

   **Estimated effort:** JS/TS already done. Go + Rust = 10 min clone, gate on RM53 Go/Rust phase.

---

RM53. **[DONE]** LanguageWalker: JS/TS (857fa6a), Go (36990d8), Rust (3480d20). All wired into persist_all. Session 169.

   Foundation for all non-Python graph work. Introduces `LanguageWalker`, the
   abstraction layer that RM54/55/57 and all future language extensions build on.

   **Parser backend: ast-grep (`pip install ast-grep-py`)**
   Rust-based, PyO3 bridge, tree-sitter underneath. 26+ languages built in — JS,
   TS, JSX, TSX, Go, Rust, Java, C, C#, Python, and more — with the same
   `SgRoot(src, language)` / `SgNode` API. No Node.js required, no per-language
   grammar installs. Pattern matching (`find_all("function $NAME($$$) { $$$ }")`)
   makes symbol and call extraction cleaner than raw CST walking.

   **Abstraction layer design (`determined/ingestion/language_walker.py`):**
   ```
   LanguageWalker(src: str, file_path: str, language: str)
       .symbols()       -> list[dict]   # functions table rows
       .call_edges()    -> list[tuple]  # (caller_fqdn, callee, 'static', resolved)
       .data_flow()     -> list[tuple]  # (caller_fqdn, callee, 'data_flow', prov)
   ```
   All downstream RMs import from `language_walker`, not from ast-grep directly.
   Swapping the backend (e.g. to Jelly for TS or a custom parser) touches only
   this file. `language` is a string passed through to `SgRoot` — adding a new
   language requires zero new plumbing, just a new pattern set.

   **Phase 1 — JS/TS (implement now, gates RM54/55):**
   - Named functions, arrow functions, class methods, object literal methods
   - `.js` and `.ts` files; HTML inline scripts deferred
   - fqdn convention: `<basename_no_ext>.<fn_name>`, class methods `<Class>.<method>`
   - TS type annotations captured in `param_types_json` if present
   - Wire into `persistence_engine.persist_all` after Python symbols

   **Phase 2 — Go (implement after Phase 1, gates Go corpus ingestion):**
   - Go functions and methods (`func $NAME(...)`, `func ($R $T) $NAME(...)`)
   - Package-qualified fqdn: `<package>.<FuncName>`
   - Validation corpus: end_of_eden (RM58)

   **Phase 3 — Rust (implement after Phase 2):**
   - `fn`, `pub fn`, `impl` block methods, trait impls
   - fqdn: `<module>::<fn>` or `<Struct>::<method>`
   - Validation corpus: ruggrogue — cross-check against its 20-chapter architecture guide
   - Rust trait dispatch adds a new edge type worth capturing: `trait_dispatch`

   **Language roadmap (ast-grep handles all of these, same API):**
   Go → Rust → Java → C# → Kotlin — each is a new pattern set, not new plumbing.

   **Validation (RM58 corpora):**
   - dnd-dungeon-gen: symbols from `app/dungeon/`, `app/room/`, `app/item/` appear
   - dungeoncrawler: `Game`, `Player`, `Enemy`, `CombatSystem` methods with correct fqdns
   - end_of_eden (Phase 2): Go package symbols appear, package call graph queryable
   - ruggrogue (Phase 3): Rust module symbols match documented architecture chapters

   **Regression tests:** `tests/regression/test_language_walker.py`
   - Phase 1: named fn, arrow fn, class method, object literal method, TS typed params,
     stub detection, fqdn convention, cross-file unresolved callee
   - Phase 2: Go func, Go method receiver, package fqdn
   - Phase 3: Rust fn, impl method, pub vs private, trait impl

   **Estimated effort:** Phase 1: 1 day. Phase 2: 0.5 day. Phase 3: 1 day.

---

RM54. **[DONE 2026-07-13]** JS static call graph: fn→fn call edges within JS/TS files.

   Core extraction was part of RM53 Phase 1 (LangSpec refactor unified the walk).
   This session added: cross-file resolution post-pass in _persist_js_ts_files
   (UPDATE graph_edges resolved=1 where callee matches any known JS/TS symbol suffix),
   2 missing regression tests (arrow fn caller, cross-file unresolved stub).
   Validated: dnd-dungeon-gen 974 edges (controller→generateDungeon chains surface);
   dungeoncrawler 163 edges (Game.constructor→handlePlayerInput, CombatSystem→takeDamage).
   816 passed, 1 skipped.

---

RM55. **[DONE 2026-07-13] JS data flow: variable binding and call-chain tracking (L1/L2/L3)**

   Depends on RM54. Mirrors the Python data_flow levels in JS/TS. Uses ast-grep
   via `LanguageWalker` — same backend as RM53/54, no new parser setup.

   - L1: `fnB(fnA())` → inline call arg → `data_flow` edge, provenance `data_flow_arg`
   - L2: `const x = fnA(); fnB(x)` → variable binding → `data_flow` edge, provenance `data_flow_var`
   - L3a: `for (const x of fnA())` → for-of over call → `data_flow_for_iter`; bind loop var
   - L3b: `fnB({key: x})` where x is bound → `data_flow_var_kwarg` (JS object literal
     named arg, the JS equivalent of Python keyword args)

   **Implementation (`language_walker.py` Phase 1 extension):**
   - `LanguageWalker.data_flow_edges()` → list of `(caller_fqdn, callee_fqdn, 'data_flow', provenance)`.
   - Per-function binding map scoped via CST function scope nodes (same invariant as
     Python: bindings don't cross function boundaries).
   - Provenance tags identical to Python side (`data_flow_arg`, `data_flow_var`,
     `data_flow_for_iter`, `data_flow_var_kwarg`) so `data_flow_edges` tool queries
     both Python and JS edges uniformly.
   - Wire into `persist_all` after RM54.

   **Validation (RM58 corpora):**
   - dnd-dungeon-gen: `const rooms = generateRooms(); placeItems(rooms)` type patterns
     surface as data_flow edges through the generation pipeline
   - dungeoncrawler: combat result flowing from `CombatSystem` into `UIManager` surfaces

   **Regression tests:** inline arg, const binding, let binding, for-of loop, object
   named arg, binding scoped to fn (no leak), module-level not tracked, TS typed var.

   **Estimated effort:** 1 day.

---

RM56. **[DONE 2026-07-13] Python AST cleanup: shared fqdn helper, binding reset, tuple unpack**

   Three known rough edges in parse_ast.py introduced across L1/L2/L3:

   1. **Duplicate `outer_fqdn` computation** — `visit_For` and `visit_Call` each
      independently compute `outer_fqdn` from `self.current_class` + `self.current_function`.
      Extract to a `@property` or inline helper so it's one place.

   2. **`_last_call_fqdn` accumulates without clearing** — the dict grows for the
      lifetime of a file visit and is never pruned. For large files with many calls
      this is a minor memory leak and could theoretically collide if `id()` is reused
      (CPython recycles node ids after GC). Clear the entry after consuming it in
      `visit_Assign`.

   3. **`visit_For` tuple unpack binds all elements to the same callee** — correct
      for tracking but misleading: `for k, v in fn()` binds both `k` and `v` to
      `fn`, which is the right provenance but could produce spurious downstream edges
      if `k` and `v` are structurally unrelated outputs. Document the known limitation
      in a comment; no behavior change needed unless a real false-positive surfaces.

   **No new tests required** — existing 26 data_flow tests are the regression suite.
   Verify all 26 still pass after refactor.

   **Estimated effort:** 1-2 hours.

---

RM57. **[DONE 2026-07-13] Cross-language data flow: Python response shape → JS consumer**

   Depends on RM54 + RM55. The "data to data" path across the language boundary.

   A Flask route returns `jsonify({"key": value})`. A JS `fetch()` call hits that
   route and destructures `const {key} = await resp.json()`. Today these are two
   disconnected facts. RM57 links them into a cross-language data_flow edge.

   **Three sub-problems:**
   1. **Python side — response shape extraction:** in `parse_ast.py` or a new pass,
      detect `jsonify(dict_literal)` or `return {"key": ...}` in a route handler and
      store the key names as a `knowledge_artifact` (`kind='response_shape'`).
   2. **JS side — response consumer extraction:** `JSWalker.response_consumers()`
      detects `await resp.json()` / `.then(data => ...)` / destructuring
      `const {key} = ...` patterns and extracts the key names being consumed.
   3. **Linking pass:** after RM54/55 emit http_fetch edges (JS fn → Flask handler),
      join response_shape artifacts to JS consumer key sets. Emit a `cross_language`
      data_flow edge annotated with matched/unmatched keys. Mismatches surface as gaps
      (design_gaps() can pick them up if stored as knowledge_artifacts).

   **Validation (RM58 corpora):**
   - dj2 is the primary target here (has real Flask + fetch chains).
   - dnd-dungeon-gen and dungeoncrawler are pure client-side so they won't exercise
     this path — that's fine, they cover RM53-55.

   **Gating condition:** implement after RM55 is working and at least one real
   fetch→handler chain exists in the active corpus (dj2 has several).

   **Estimated effort:** 1.5 days.

---


RM52. **[DONE] Multi-method ingestion pre-pass: structure-induction gate for design doc extraction**

   Implemented in determined/ingestion/structure_induction.py. Four methods
   (fca_pass, mdl_pass, wrapper_pass, grammar_pass) + combine() D-S gate.
   Wired into ingest_design_docs after existing extraction. 28 tests. 672 passed.

   **Pipeline topology (for reference):**

   ```
   INPUT DOC
       │
       ▼
   [EXISTING EXTRACTOR]  ← _MUST_RE regex + LLM pass
       │
       ├─ modal-verb requirements (seeds)
       │
       ▼
   ┌──────────────────────────────────────────────────────────┐
   │                   MULTI-METHOD PASS                      │
   │                                                          │
   │  seeds ──► [LP² WRAPPER INDUCTION]          → S_C       │
   │              Kushmerick et al. 1997                      │
   │            [FORMAL CONCEPT ANALYSIS]        → S_A       │
   │              Wille 1982                                  │
   │            [MINIMUM DESCRIPTION LENGTH]     → S_B       │
   │              Rissanen 1978                               │
   │  seeds ──► [GRAMMATICAL INFERENCE L*]       → S_D       │
   │              Angluin 1987                                │
   └──────────────────────────────────────────────────────────┘
       │
       ▼
   [SET OPERATIONS]                    Campbell & Fiske 1959 (MTMM)
     S_A ∩ S_B ∩ S_C ∩ S_D            Kuncheva & Whitaker 2003
     S_A △ S_B △ S_C △ S_D            (discriminant = signal, not noise)
     S_A ∪ S_B ∪ S_C ∪ S_D
       │
       ▼
   [DEMPSTER-SHAFER GATE]              Dempster 1967 / Shafer 1976
       │
       ├── existing agrees + convergent   → high trust  → store
       ├── 2+ methods, existing missed    → medium trust → store + tag
       └── 1 method only, existing missed → review queue
   ```

   **Execution model:** serial, not truly parallel. Methods run one after another, each
   result compared against the accumulating evidence set. Set operations and D-S combination
   are a single pass over the accumulated output. The existing extractor runs first and its
   output seeds Wrapper Induction and L* -- no labeled examples required from outside the
   system.

   **Why pre-pass, not replacement:** Replacement has a bootstrapping problem -- Wrapper
   Induction and L* need labeled seeds, and without the existing extractor there is no
   source for them. Pre-pass uses the existing extractor's output as seeds automatically.
   The existing extractor is the anchor: nothing clears the gate by beating it alone.

   **Determinism:** FCA (Wille), MDL given a fixed prior (Rissanen), LP² given fixed seeds
   (Kushmerick), and L* given an oracle (Angluin) are each deterministic. Set operations are
   exact. Dempster-Shafer combination is exact given fixed evidence. An optional LLM
   interpretation step may run after the deterministic core but is clearly separated and not
   required for the pipeline to produce a result.

   **What the gate produces (stored in knowledge_artifacts):**
   - `convergent`: existing extractor + 2+ methods agree → high trust, stored immediately
   - `discriminant`: 2+ methods found it, existing extractor missed → medium trust, stored
     with tag identifying which methods found it and which missed it
   - `review`: 1 method only, existing extractor missed → not stored until confirmed

   **The discriminant tag is the new information.** Which method found something that others
   missed tells you something structural about how the document expresses that requirement --
   a property invisible to any single-method pass.

   **Entry points for implementation:**
   - New module `determined/ingestion/structure_induction.py`: one function per method
     (`fca_pass`, `mdl_pass`, `wrapper_pass`, `grammar_pass`), plus `combine(results)`
     that runs set ops and D-S gate.
   - Modify `ingest_design_docs` in `agent_tools.py`: after existing extraction, call
     `structure_induction.run(doc, seeds=existing_rules)` and merge results through the gate.
   - Extend `knowledge_artifacts` content prefix: add `convergent` / `discriminant(methods)`
     / `review` alongside existing `[KIND|confidence|source]` prefix.
   - New regression tests: fixture doc with requirements in modal, bullet, and numbered forms.
     Verify that modal form is found by existing extractor AND at least one method; that
     bullet/numbered forms are found by multi-method pass but not existing extractor; that
     gate correctly tiers them.

   **Prerequisite for RM48:** RM52 should ship before RM48 (design-to-code delta) because
   RM48 queries `kind='design_note'` artifacts -- richer extraction here means richer input
   to RM48's gap analysis.

   **Estimated effort:** 2 days. FCA and MDL implementations are the core work (1 day).
   LP² and L* can be simplified for the restricted grammar class of design documents (0.5 day).
   Gate logic and storage integration (0.5 day).


RM48. **[DONE] Design-to-code delta: surface what the design says should exist that the code does not yet implement**

   Implemented design_gaps() in agent_tools.py. 3-level evidence matching:
   Level A (embedding >= 0.45), Level B (file path keyword), Level C (import
   graph keyword). GAP / PARTIAL / SATISFIED tiers. scope/threshold/show_satisfied
   args. Wired into TOOLS + tool_registry. 19 tests, 691 passed.

   **For reference -- original concept:** A `design_gaps(scope?)` tool that:
   1. Reads all `kind='requirement'` design_note artifacts from the corpus DB (these are
      the "MUST", "SHALL", "is required to" rules already extracted by doc_extractor.py)
   2. For each requirement, attempts to locate evidence of implementation in the corpus:
      named symbols, file patterns, import relationships
   3. Reports requirements with no detectable implementation as "design gaps" -- things
      the architecture commits to that the code doesn't appear to satisfy yet

   **What "evidence of implementation" means (in priority order):**
   - Level A: A function or class whose name or docstring semantically matches the
     requirement's subject (cosine similarity >= 0.45 against the requirement text).
     Use `embed_text` from `determined/oracle/embedding_model.py`.
   - Level B: A file path that matches the subject keyword (e.g., requirement about
     "auth boundary" → look for `auth*.py` or `*_auth.py`).
   - Level C: An import dependency that matches (e.g., requirement about "LLM must go
     through ai_boundary" → check whether llm_client.py imports from ai_boundary.py
     via `graph_edges`).
   - No match at any level → GAP.
   - Match at Level B or C only (not Level A) → PARTIAL (file exists but no clear
     implementing function found).

   **Output shape:**
   ```
   Design gaps for corpus: C_Users_bartl_dev_dj2.db
   (14 requirements extracted from 3 design docs)

   GAPS (no implementation found):
   1. [MUST] "The intent layer must classify player input before it reaches game state"
      Source: 00A ARCHITECTURAL_CONSTITUTION.md > Intent Layer
      No function or file matching 'intent classification' or 'IntentLayer' found.
      Suggested search: search_symbols('intent') / search_symbols('classify')

   2. [SHALL] "AI DM shall never write directly to DungeonStateNeo"
      Source: 00B SYSTEM_CONSTRAINTS.md > AI Boundary
      No enforcement mechanism (guard/assert/layer rule) found.
      Note: check_design_violations may catch violations but no enforcer detected.

   PARTIAL (file exists, no clear implementing function):
   3. [MUST] "Authority hierarchy must be enforced at mutation time"
      Source: 00A ARCHITECTURAL_CONSTITUTION.md > Authority
      File: mutation_runner.py exists. No function matching 'authority check' found.
      Check: symbols_in_file('mutation_runner.py')

   SATISFIED (skipped unless --show-all):
   4. [MUST] "Session state must persist across reconnects"
      Matched: get_session() in session_manager.py (similarity 0.61)
   ```

   **What already exists to build on:**
   - `kind='requirement'` design_note artifacts are already extracted and stored by
     `doc_extractor.py` (`_MUST_RE` at line 319 classifies "must/shall/required to" as
     `kind='requirement'`). Query: `SELECT content, source_file FROM knowledge_artifacts
     WHERE kind = 'design_note' AND content LIKE '%must%' OR content LIKE '%shall%'`
     -- but better: store `kind` in the JSON body at extract time and query on it.
     Alternatively, re-run `_MUST_RE` over the stored content at query time (no schema
     change needed).
   - `embed_text(text)` from `determined/oracle/embedding_model.py` -- already used
     by concept_search, find_duplicates, check_design_violations.
   - `_search_symbols_raw(oracle, query, limit)` at agent_tools.py:358 -- semantic
     symbol search. Use this for Level A matching.
   - `knowledge_artifacts` table already holds all ingested design rules. Design docs
     must be ingested first via `ingest_design_docs` -- the tool should check and warn
     if no design_note artifacts exist yet.

   **Schema note:** `knowledge_artifacts.content` stores the rule text. The `kind`
   field in the DesignRule dataclass (doc_extractor.py:66: constraint / requirement /
   permission / intent) is stored in `content` as a prefix or in the provenance string.
   Before implementing, verify exactly how `kind` is persisted: run
   `SELECT content FROM knowledge_artifacts WHERE kind='design_note' LIMIT 5` against
   a corpus with ingested design docs and inspect the format. If `kind` is not a
   separate column, add it to the JSON body or use regex over `content` at query time.

   **Entry points for implementation:**
   - New function `design_gaps(assessor, args)` in `determined/agent/agent_tools.py`.
     Takes optional `scope` arg (filename prefix or subject keyword to filter which
     requirements to check). Place after `check_design_violations` (~line 854).
   - Wire into `TOOLS` dict and `tool_registry.py` with category `"knowledge"`.
   - New regression test: `tests/regression/test_design_gaps.py`. Use a fixture DB
     with at least one ingested design_note of kind='requirement' and one stub that
     clearly does not match it. Verify the stub's subject appears in GAP output.
     Also test the SATISFIED case: a requirement whose subject matches an existing
     non-stub function.

   **Prerequisite:** Design docs must be ingested (`ingest_design_docs`) before
   `design_gaps` has anything to query. The tool should emit a clear message if
   `knowledge_artifacts WHERE kind='design_note'` returns zero rows:
   "No design notes found. Run ingest_design_docs first."

   **SOTS tensions:**
   - I (locality): the design-to-code gap is currently implicit and invisible. This
     makes it explicit and queryable on demand.
   - XI (separate decide from do): the tool surfaces gaps; it does not propose fixes.
     The developer decides whether a gap is real, already handled by untraceable code,
     or irrelevant to the current phase.
   - XIV (one source of truth): requirements come from knowledge_artifacts (ingested
     from design docs); implementation evidence comes from the call graph and functions
     table. The tool reads both sources but does not merge or modify them.
   - XXI (don't over-engineer): Level A (embedding similarity) is the main match
     mechanism. Levels B and C are fallbacks that add recall at low cost. Do not add
     a fourth level (e.g., full-text contract matching) until A/B/C prove insufficient
     on a real corpus query.

   **Estimated effort:** 1 day. Embedding similarity is already wired; the new code
   is the requirement-extraction query, the three-level match loop, and the output
   formatter. The schema note above must be resolved before starting -- budget 30
   minutes to inspect the live DB format.

   **Step 0 action (no code needed, do before implementing RM48):**
   Run `ingest_design_docs` on dj2's existing design docs:
   - `docs/design/00A ARCHITECTURAL_CONSTITUTION.md`
   - `docs/design/00B SYSTEM_CONSTRAINTS.md`
   - `docs/design/00E AI_LAYER_OPPORTUNITIES.md`
   - `docs/design/00F ASPIRATIONAL_DESIGN_INTENT.md`
   Validation: `SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='design_note'`
   before and after. Expect significant count increase. Also run the schema check:
   `SELECT content FROM knowledge_artifacts WHERE kind='design_note' LIMIT 5`
   to confirm whether 'requirement' kind is a top-level field or buried in content JSON.
   This unblocks RM48 query design and costs zero implementation time.

---

RM51. **[DONE] Annotation pass driver: prioritized queue and convergence loop for corpus enrichment**

   **The gap:** `annotate_function` (RM49) works on a single function. To enrich a
   corpus with 1300+ unannotated functions, there must be a driver that processes them
   in the right order, propagates improvements to callers after each annotation, and
   stops when the marginal gain drops below a threshold. Without this, RM49 is a
   one-off tool rather than a corpus enrichment loop.

   **The concept:** A `run_annotation_pass(scope=None)` tool that:
   1. Builds a priority queue of unannotated functions in `workflow_items`
      (kind='annotation_todo'), ordered by caller count descending (most-called first)
   2. Pops the top item, calls `annotate_function`, stores the result
   3. After each annotation, queues the annotated function's direct callers for
      re-annotation (they now have richer callee context)
   4. Tracks convergence: stops when a full pass produces fewer than N new inferences
      (default N=5) or the queue is empty
   5. Reports: functions annotated, types inferred, contracts stored, passes run

   **Why most-called first:** `process()` (30 callers), `execute()` (46 callers),
   `generate()` (21 callers) -- these have the richest call context for inference AND
   their annotations cascade to the largest number of downstream callers. Annotating
   them first gives the highest leverage per LLM call.

   **Propagation rule:** after annotating function A, query
   `graph_edges WHERE callee = A` to find A's callers. For each caller not yet in
   the queue (or whose last annotation predates A's), add to workflow_items with
   priority = caller's own caller count. This is a BFS-upward propagation, one hop
   at a time per pass.

   **Convergence check:** track `inferred_count` per pass. If pass N produces fewer
   new `knowledge_artifacts WHERE kind='inferred_annotation'` than pass N-1 by more
   than 50%, stop. The corpus has reached diminishing-returns state.

   **What already exists to build on:**
   - `workflow_items` table with `kind`, `priority`, `status` columns -- already the
     right queue structure
   - `annotate_function` (RM49) -- the per-function worker this driver calls
   - `_list_callers_raw(oracle, symbol)` at agent_tools.py:383 -- get callers for
     propagation step
   - `graph_edges` table with `resolved` column -- filter to project functions only

   **Entry points for implementation:**
   - New function `run_annotation_pass(assessor, args)` in `determined/agent/agent_tools.py`
     after `annotate_function` (RM49). Args: `scope` (optional file prefix to restrict
     the pass), `max_functions` (cap per run, default 50), `convergence_threshold` (default 5).
   - New function `_build_annotation_queue(oracle, scope=None)` -- populates workflow_items
     from functions WHERE `param_types_json IS NULL OR param_types_json = '{}'` AND
     `is_stub = 0` (stubs get annotated via RM49 directly; this pass covers complete functions).
   - Wire into TOOLS dict and tool_registry.py with category `"knowledge"`.

   **Validation (regression tests):**
   - Queue build: fixture DB with 3 unannotated functions at different caller counts.
     Verify queue order is by caller count descending.
   - Propagation: annotate function A in a 2-function chain (A calls B). Verify that after
     A is annotated, B appears in the queue (caller of A gets queued).
   - Convergence: fixture where all functions are already annotated. Verify pass exits
     after 1 pass with 0 new inferences.
   - Scope filter: verify `scope='world/'` restricts queue to world/ files only.
   - No LLM needed for queue/propagation/convergence tests; mark LLM inference tests --slow.

   **Dependencies:** RM49 (annotate_function) must ship first.

   **Estimated effort:** 1 day. Queue build is a simple query. Propagation is one
   _list_callers_raw call per annotated function. Convergence is a count comparison.
   The driver itself is glue around RM49.

---

RM50. **[DONE] Inline comment extraction: capture body comments as behavioral notes during parse**

   **The gap:** `parse_ast.py` reads function docstrings but ignores inline comments
   in function bodies. Comments like `# validates the move before applying`, `# state
   must be clean here`, `# only called from authenticated handlers` are behavioral
   notes written by the developer. They are the highest-quality documentation that
   exists for functions that have no docstring -- and for the dj2 corpus, that is the
   majority of functions. Currently this information is invisible to every Determined
   tool.

   **The concept:** Extend the AST visitor to capture inline comments (lines starting
   with `#` in the function body, excluding shebangs and encoding declarations) and
   store them as `knowledge_artifacts` with `kind='inline_note'`, `subject=function_name`,
   `source_file=file_path`. Each comment stored as one artifact. The `annotate_function`
   tool (RM49) reads these as part of its context assembly -- they are low-cost behavioral
   signal that costs zero LLM calls to extract.

   **What to capture:**
   - Inline comments attached to statements in the function body (via `ast.get_source_segment`
     or by scanning the raw source lines for the function's line range)
   - Exclude: module-level comments, class-level comments, shebang lines (`#!`), encoding
     declarations (`# -*- coding`), pure separator lines (`######`)
   - Include: any comment line within the function body's line range that has substantive
     content (len > 5 after stripping `# `)

   **Implementation note:** Python's `ast` module strips comments. Use the raw source line
   scan approach: for each function, get its line range from `lineno` and `end_lineno`
   (Python 3.8+ provides `end_lineno` on all AST nodes). Scan those lines directly in the
   source text for `#` prefixes. This avoids needing `libCST` or a separate tokenizer.

   **What already exists to build on:**
   - `parse_ast.py` `Visitor._extract_functions` -- already has `lineno` for each function;
     `end_lineno` is available on Python 3.8+ AST nodes
   - `persistence_engine.py` `_persist_knowledge_artifacts` -- already writes to
     `knowledge_artifacts`; add inline_note kind alongside design_note and distilled
   - `knowledge_artifacts` table -- no schema change needed; `kind`, `subject`,
     `source_file`, `content` columns already exist

   **Entry points for implementation:**
   - In `parse_ast.py` `Visitor._extract_functions` (or a new post-pass): after extracting
     each function, scan raw source lines `[lineno:end_lineno]` for comment lines.
     Attach to the function's data dict as `inline_notes: list[str]`.
   - In `persistence_engine.py` `_persist_functions` (or `_persist_knowledge_artifacts`):
     for each function with non-empty `inline_notes`, write one `knowledge_artifact`
     per comment, kind='inline_note'.
   - No new schema. No new table. No LLM.

   **Validation (regression tests):**
   - Fixture source file with one function containing 2 inline comments and no docstring.
     After ingest: verify 2 `knowledge_artifacts WHERE kind='inline_note' AND subject=fn_name`
     exist with correct content.
   - Fixture function with a docstring AND inline comments: verify both docstring (behavioral_contracts
     or functions.docstring) and inline_notes are captured independently, no duplication.
   - Fixture function with only separator comments (`######`): verify none stored (filtered out).
   - Fixture function with shebang-style comment: verify not stored.
   - Run full regression suite after change (parse_ast.py changes are high blast-radius;
     all 545+ tests must pass before commit).

   **Integration validation:**
   After implementing and reingesting dj2 corpus: run
   `SELECT COUNT(*), source_file FROM knowledge_artifacts WHERE kind='inline_note' GROUP BY source_file ORDER BY COUNT(*) DESC LIMIT 10`
   Report the top-10 files by inline note count. Spot-check 3-5 notes against source to
   confirm they are real behavioral comments, not noise.

   **Estimated effort:** 0.5 days. Source line scan is straightforward. Persistence
   is one new kind in an existing write path. Highest risk is blast-radius on parse_ast.py
   -- run full regression suite before committing.

---

RM49. **[DONE] annotate_function: infer and store docstrings, param types, and behavioral contracts for unannotated functions**

   **The gap:** RM45 (completion contract) and RM47 (readiness gate) depend on
   `param_types_json`, `return_type`, and `behavioral_contracts` being populated.
   In dj2, fewer than 1% of functions have type annotations. `behavioral_contracts`
   is empty for functions with no docstring. The tools ship but produce mostly-empty
   output on the corpus they were built to analyze.

   **The concept:** A `annotate_function(symbol)` tool that takes a single function,
   assembles all available context (source code, callers, callees, inline notes, design
   notes), runs LLM inference to produce: inferred param types, inferred return type,
   behavioral contract (pre/post/raises), and a one-sentence docstring. Stores inferences
   in `knowledge_artifacts` with `kind='inferred_annotation'` -- clearly labeled as
   inferred, never written to source files without explicit user confirmation.

   **RM45 and RM47 read from this store:** both tools should check
   `knowledge_artifacts WHERE kind='inferred_annotation' AND subject=symbol`
   when `param_types_json` is empty or `behavioral_contracts` has no rows for the symbol.
   Output is labeled `(inferred, confidence: 0.7)` to distinguish from real annotations.
   This makes the sparsity problem visible rather than silently producing empty output.

   **Context assembly for inference (what to pass the LLM):**
   1. Function source code (via `_get_source_lines` from stub_projector.py:100)
   2. Callers: what they pass as arguments (from `_list_callers_raw` + one extra query
      per caller: what literal or typed value do they pass?)
   3. Callees: what the function calls and what those return (from `_list_callees_raw`
      + `functions.return_type` for each callee)
   4. Inline notes: `knowledge_artifacts WHERE kind='inline_note' AND subject=symbol`
      (populated by RM50)
   5. Existing design notes mentioning the symbol or its file (from
      `knowledge_artifacts WHERE kind IN ('design_note','layer_rule') AND content LIKE '%symbol%'`)
   6. `gather_context(conn, symbol)` from stub_projector.py:110 -- already assembles
      callers + contracts + siblings; reuse rather than re-query

   **Inference output shape (stored as JSON in knowledge_artifacts.content):**
   ```json
   {
     "param_types": {"player_action": "PlayerAction", "state": "DungeonStateNeo"},
     "return_type": "Dict[str, Any]",
     "pre_conditions": ["player_action.type must be a valid ActionType"],
     "post_conditions": ["returns dict with keys: success, effects, message"],
     "raises": ["ValueError if player_action.type is unknown"],
     "docstring": "Process a player action against current dungeon state and return result dict.",
     "confidence": 0.72,
     "inference_basis": ["30 callers pass PlayerAction typed arg", "return value checked for ['success'] key by 12 callers"]
   }
   ```
   The `inference_basis` field is critical: it lets RM45 explain WHY the type was inferred,
   not just assert it. This grounds the output in evidence rather than hallucination.

   **What already exists to build on:**
   - `gather_context(conn, stub_name)` at stub_projector.py:110 -- callers + contracts + siblings
   - `_list_callers_raw`, `_list_callees_raw` at agent_tools.py:383, 426
   - `_get_source_lines` at stub_projector.py:100
   - `knowledge_artifacts` table -- kind='inferred_annotation' is a new kind, no schema change
   - `behavioral_contracts` table -- also write inferred contracts here so RM45 reads them
     from the existing path (subject=function_name, type='inferred')
   - LLM infrastructure: `generate_quality()` from llm_client.py -- use this, not the 3B fallback

   **Entry points for implementation:**
   - New function `annotate_function(assessor, args)` in `determined/agent/agent_tools.py`
     after `docstring_health` (~line 1700). Takes `symbol` arg; optional `write_back=False`
     (when True, proposes a docstring edit via `edit_file` -- requires user confirmation).
   - Extend `completion_contract` (RM45): after assembling param_types_json, if empty,
     query `knowledge_artifacts WHERE kind='inferred_annotation' AND subject=symbol`.
     If found, include with `(inferred)` label. Same for behavioral_contracts.
   - Extend `readiness_check` (RM47) Tier 3: if param type not in real annotation,
     check inferred_annotation store before reporting UNKNOWN TYPE.
   - Wire into TOOLS dict and tool_registry.py with category `"knowledge"`.

   **Validation (regression tests):**
   - Core storage: `annotate_function` on a known unannotated fixture function stores
     a `knowledge_artifacts` row with kind='inferred_annotation' and valid JSON content
     (all keys present, confidence is a float). Mark as --slow (requires LLM).
   - RM45 integration: after storing an inferred_annotation for a function, calling
     `completion_contract` on that function shows the inferred types with `(inferred)` label.
     Test this with a fixture annotation (no LLM needed for this assertion).
   - RM47 integration: after storing an inferred_annotation that resolves a formerly
     UNKNOWN TYPE, readiness_check no longer reports that type as unknown.
   - Confidence field: verify inference_basis is non-empty (at least one grounding reason).
   - write_back=False default: verify function source file is NOT modified when
     write_back is omitted.

   **Integration validation (manual, after RM50 ships):**
   Run `annotate_function` on `process` (adjudication_engine.py) -- the function with
   30 callers. Verify:
   - Inferred param types match PlayerAction and DungeonStateNeo (the actual types)
   - Return type correctly inferred as dict (30 callers check return['success'])
   - Confidence >= 0.6 (rich caller context should produce high confidence)
   - inference_basis lists the caller-count evidence

   **Estimated effort:** 1.5 days. Context assembly is the hard part (0.5d). LLM prompt
   design for structured JSON output (0.5d). RM45/RM47 integration reads (0.5d).

---

RM39. **[DONE 2026-07-13] Data flow tracking: parameter-passing and return-value edges**

   **The gap:** The graph tracks control flow (which function calls which) but not data
   flow (what values move between functions). We can say "handler A calls validate_move
   calls apply_move" but not "the player_action dict from the socket message reaches
   validate_move, and validate_move's bool return gates whether apply_move runs."
   For UI-to-output chain reasoning this is the missing half.

   **Design constraint (SOTS XXI):** Build Level 1 only after the prerequisite analysis
   identifies the specific patterns that matter in the real corpus. Do not build speculatively.

   ---

   **Prerequisite -- dj2 path analysis [DONE 2026-07-11]:**
   Re-ingested dj2 corpus (153 files, 1321 fns, 8199 edges). Full BFS from all socket handlers
   and HTTP route handlers. Findings in HISTORY.md 2026-07-11 entry. Key scoping results:
   - Level 1 priority targets: process()->Dict (adjudication_engine, 30 callers),
     execute()->Any (tool_system, 46 callers), generate()->str (llm_client, 21 callers),
     get_session()->SessionState (21 callers), move_party()->dict (21 callers).
   - fn_b(fn_a()) nested-call pattern is less common than result=fn(); use(result). Level 1
     captures some cases; Level 2 (variable binding) needed for full coverage.
   - State carriers: DungeonStateNeo, Character, PlayerAction (annotated params, 11 fns total).

   ---

   **Level 1 -- parameter-passing edges (~2 days after prerequisite):**
   In `parse_ast.py` `Visitor.visit_Call`, when a call argument is itself a call
   (`fn_b(fn_a())`), emit a `data_flow` edge: `fn_a -> fn_b`, via='return_value'.
   Also: when a param is annotated and the annotation matches a known function's
   return annotation, emit a typed data edge.

   Storage: extend `graph_edges` with `edge_type='data_flow'` (Option B -- traversal
   functions already handle all edge types; existing tools get data flow edges for free).
   Alternative Option A (new `data_edges` table) is cleaner for queries but splits the
   graph. Decide at implementation time based on query patterns needed.

   **Level 2 -- variable binding tracking (~2 weeks, defer):**
   Track `result = fn_a()` then `fn_b(result)` across statements within a function body.
   Requires per-function variable binding map in the AST visitor. Higher accuracy, much
   more complex. Build only after Level 1 proves insufficient on real queries.

   ---

   **Tooling to investigate before building:**
   - `libCST` (Meta): concrete syntax tree with better assignment tracking than stdlib ast
   - `astroid` (pylint's AST): has inference support, may give type-propagation for free
   - `pyright` type inference API: typed parameter->return chains without writing inference
   Grep existing Determined code first: `determined/ingestion/parse_ast.py` and
   `determined/agent/graph_utils.py` are the entry points.

   **Entry points for implementation:**
   - `determined/ingestion/parse_ast.py` -- `Visitor.visit_Call` (add data_flow emission)
     and new `visit_Assign` (for Level 2 variable tracking)
   - `determined/persistence/persistence_engine.py` -- store data_flow edges in graph_edges
     (extend `_persist_graph_edges` or add to `_persist_cross_boundary_edges`)

   **Estimated effort:** prerequisite 1 session; Level 1 2 days; Level 2 2 weeks (defer).

---

RM38. **[DONE 2026-07-14] JS/HTML event chain analysis: map DOM controls to HTTP routes**

   **Scope revision (2026-07-11):** dj2 has no client-side socket.emit calls. The socket.io
   connection is server-to-client push only. The @socketio.on handlers in world_app.py are
   unreachable from the current browser client. RM38's original framing (DOM controls ->
   socket.emit -> Python handler) has no current instances in dj2.
   The real gap is: DOM controls -> fetch()/HTMX -> HTTP route -> business logic.
   world.html and static/js/*.js use addEventListener + fetch() and HTMX hx-post/hx-get
   attributes. These chains are invisible to the static analyzer.
   Defer RM38 until: (a) dj2 adds client-side socket.emit, OR (b) we want to map HTTP
   route chains (fetch POST -> flask @route -> service call). File (b) as RM38b if needed.

   **Original gap (still valid for other corpora):** detect `socket.emit("event")` in
   HTML/JS and map to Python `@socketio.on("event")` handler via `cross_language` edges.
   This works correctly in Determined; dj2 just has no emit calls to detect.

   **Goal (revised):** map {DOM control -> event_type -> JS handler -> fetch(url, method)}
   and store as `js_event_binding` virtual edges. Then match fetch URL to Flask @route.
   This closes the actual chain in dj2: button_click -> fetchHandler -> HTTP route.

   ---

   **First: investigate existing JS analysis tools (0.5 days):**
   Before writing custom extraction, evaluate:
   - `js-callgraph` (npm): builds JS call graphs from source; may give handler->emit chains
   - `acorn` or `esprima` with Python subprocess: JS AST parsers, can find addEventListener
     and onclick patterns; subprocess call from Python is fine (no Python binding needed)
   - `CodeQL` for JS: GitHub semantic analysis, free for open source, queries for
     addEventListener patterns; overkill if the JS is simple but worth a look
   - `pyjsparser` / `calmjs.parse`: pure-Python JS parsers (no Node.js dependency)
   Decision criterion: if a tool can be called from Python and returns structured event
   binding data in under 1 day of integration work, use it. Otherwise write targeted
   regex/AST extraction -- the JS in dj2 is not complex.

   ---

   **What to extract (priority order):**
   1. HTML inline handlers: `<button onclick="fn()">`, `<form onsubmit="fn()">`
      -> extract element type, id/class, event_type, handler_name
   2. JS `addEventListener('click', fn)` and jQuery `.on('click', fn)` patterns
      -> extract selector, event_type, handler_name
   3. Within each JS handler function: trace calls until `socket.emit("event")` found
      -> gives handler_name -> emitted_event_name
   4. Combine: control -> event_type -> js_handler -> socket_event -> python_handler

   **Output schema** (extend `_persist_cross_boundary_edges` in persistence_engine.py):
   - Edge 1: `source_id = "<element_type>_<id_or_class>"`, `target_id = "js_handler_name"`,
     `edge_type = 'js_event_binding'`, `caller = element description`, `callee = handler`
   - Edge 2 (existing, improve): intermediate `js_handler_name -> socket_event_name` node
     so the full chain is traversable without special-casing `__js_client__`

   **Entry points:**
   - `determined/ingestion/dynamic_edges.py`: add `extract_js_event_bindings(html_src)` and
     `extract_js_call_chain(js_src, handler_name) -> socket_event` alongside existing
     `extract_socketio_handler_map` and `extract_cross_language_edges`
   - `determined/persistence/persistence_engine.py`: `_persist_cross_boundary_edges`,
     the Gap 7 block (~line 787) -- extend to also call the new extractor

   **What already exists to build on:**
   - `extract_socketio_handler_map(src)` in dynamic_edges.py: finds Python @socketio.on handlers
   - `extract_cross_language_edges(html_src, py_handler_map)`: finds socket.emit in HTML/JS
   - Both use regex over source text. Same approach works for addEventListener and onclick.

   **Estimated effort:**
   - Tool investigation: 0.5 days
   - Implementation (good external tool found): 1-2 days
   - Implementation (custom regex/AST): 2-3 days
   - New regression tests: 0.5 days

---

RM42. **[DONE 2026-07-12] Investigation context panel: accumulate query results as a clue board**

   **The gap:** Every tool query produces a result that disappears when the user moves to
   the next query. There is no way to accumulate findings across a session and reason about
   them together. Each query is a fresh window into one corner of the codebase; the user
   has to hold the emerging picture in their head. SOTS I (locality of reasoning) says the
   tool should carry that context, not the user.

   **The concept:** A persistent "investigation" panel that accumulates tool outputs as
   named clue cards. Cards from list_callers, bfs_callees, check_design_violations, etc.
   pile up. Then the user asks "what does this tell me?" and the AI reasons across the
   full board -- same pattern as a Cluedo investigation: gather clues independently, then
   fit the pattern together.

   **SOTS tensions:**
   - I (locality): accumulating context reduces cognitive load -- the point.
   - XXI (don't over-engineer): session-only storage (no DB write) is sufficient to start.
     If the pattern proves out, add workflow_items persistence in a second pass.
   - XI (separate decide from do): collecting clues and reasoning about them are two distinct
     steps. The panel holds collected evidence; the Ask bar reasons about it on demand.
   - XIV (one source of truth): the panel IS the context store; Ask bar reads from it,
     doesn't duplicate it.

   ---

   **Design (minimal first pass):**

   1. **Clue card model:** `{id, tool, subject, summary, timestamp, pinned}`.
      Summary is the first 200 chars of the tool result (truncated) plus subject name.
      Pin keeps it when "clear old" is triggered. Max 20 cards before oldest unpinned drops.

   2. **Collection:** every tool result panel gets a small "📌" pin button. Clicking it
      adds the result to the investigation. Auto-add option for starred tools (off by default).

   3. **Investigation panel:** 5th rail icon (🔍 or 🧩). Shows stacked cards, newest first.
      Each card: tool name badge, subject, summary, timestamp, X to remove.
      Collapse/expand each card. "Clear all unpinned" button.

   4. **Reason button:** "Ask about this" button at the bottom of the panel. Composes a
      pre-filled Ask bar query: "Given these findings: [card summaries]... what do they
      suggest?" User can edit before submitting.

   5. **Context injection:** When reasoning, the Ask bar receives the card summaries as
      prepended context. The agent sees them as additional facts alongside the normal DB
      query results. No new agent infrastructure needed -- just prepend to the query.

   ---

   **Storage (pass 1):** session-only JS (no DB write). Cards live in a JS array; they
   survive tab switches within the session but not page reload.

   **Entry points:**
   - `determined/ui/templates/console.html`: add rail icon, panel div, JS clue array,
     pin button injection into tool result panels, "Ask about this" composer
   - `determined/ui/ui_server.py`: no changes needed for pass 1

   **Estimated effort:** 1 day for pass 1 (rail icon + panel + pin buttons + reason button).

   ---

   **Pass 2 -- persistent investigation storage (file after pass 1 ships)**

   Investigations span sessions: a developer rarely closes a feature analysis in one
   sitting. Pass 1 cards are lost on page reload. Pass 2 persists them to the corpus DB
   so an investigation survives across days.

   **Schema extension:** add `kind='investigation_clue'` to `workflow_items`. The table
   already exists (created by `ensure_workflow_items_table` in
   `determined/intent/workflow_store.py`, called from `persistence_engine.py:291`).
   Extend with the clue card fields:

   ```sql
   -- workflow_items already has: id, corpus, kind, title, body, status, priority, created_at
   -- Pass 2 adds a JSON blob in body:
   --   { "tool": "bfs_callees", "subject": "handle_move", "summary": "...",
   --     "full_result": "...", "pinned": true, "session_id": "2026-07-12T14:30" }
   ```
   No schema migration needed: `body` is already TEXT; store the JSON there.
   `kind = 'investigation_clue'`, `status = 'active'` while pinned, `'archived'` when
   cleared.

   **Backend endpoints (new in `determined/ui/ui_server.py`):**
   - `POST /api/clue/save` -- receives `{tool, subject, summary, full_result, pinned}`,
     writes to `workflow_items`, returns `{id}`.
   - `GET /api/clue/list` -- returns all `kind='investigation_clue'` items for the active
     corpus, ordered by `created_at DESC`.
   - `POST /api/clue/delete` -- marks a card `status='archived'` (soft delete).
   - `POST /api/clue/clear` -- archives all unpinned cards.

   **Frontend changes (console.html):**
   - On panel open: call `GET /api/clue/list`, populate JS clue array from DB.
   - On pin: call `POST /api/clue/save` in addition to pushing to the JS array.
   - On X/remove: call `POST /api/clue/delete`.
   - "Clear unpinned": call `POST /api/clue/clear`, then reload list from DB.
   - Session ID: generated at page load (`new Date().toISOString()`), stored in a
     `const SESSION_ID` at top of the clue JS block. Included in every save call so
     you can filter to "this session's cards" vs. "prior session cards" in the UI.

   **Migration path:** pass 1 ships the JS-only panel. Pass 2 adds persistence by
   wiring the existing JS events to the new API calls. The panel UI does not change.

   **Estimated effort (pass 2):** 0.5 days. Three API endpoints + four frontend event
   hooks. No new schema migration (body column already TEXT).

---

---

RM41. **[DONE 2026-07-13] HTTP fetch/HTMX → Flask route cross-language edges**

   Implemented in dynamic_edges.py (extract_flask_route_map, extract_htmx_edges,
   extract_js_event_bindings, extract_fetch_edges) and wired into
   _persist_cross_boundary_edges in persistence_engine.py. URL normalization handles
   Jinja2 {{var}} ↔ Flask <type:var> matching. Falls back to reading HTML/JS from disk
   when scan_project_files skips them. dj2 after re-ingest: 32 http_fetch edges,
   18 js_event_binding edges. 16 new regression tests (27 total in test_dynamic_edges.py).
   738 passed, 1 skipped.

   ~~Original description below:~~

RM41. **HTTP fetch/HTMX → Flask route cross-language edges**

   **The gap:** Gap 7 wired JS socket.emit → Python @socketio.on via cross_language edges.
   The same pattern applies to the HTTP boundary: `fetch('/api/route', {method:'POST'})` in
   JS and `hx-post="/route"` HTMX attributes in HTML both call Python `@app.route('/route')`.
   These chains are invisible. dj2 uses fetch + HTMX exclusively (no socket.emit from client)
   so the entire client-to-server boundary is currently untracked.

   **What to detect (in priority order):**
   1. JS `fetch(url, {method:'POST'/'GET'})` and `fetch(url)` → extract url and method
   2. HTMX `hx-post="url"`, `hx-get="url"`, `hx-delete="url"` attributes → extract url, method
   3. Match extracted url+method to `@app.route(url, methods=[...])` in Python source
   4. Store as `cross_language` edge: `source_id='__js_client__'`, `target_id=handler_fn_name`,
      `edge_type='http_fetch'` (new subtype, or reuse 'cross_language' with callee='HTTP:url')

   **What already exists:**
   - `extract_socketio_handler_map(src)` pattern: already parses Python @decorator -> fn map.
      Extend to parse `@app.route(url, methods=[...])` with same approach.
   - `extract_cross_language_edges(html_src, handler_map)` pattern: regex over source text.
      Extend with `_FETCH_RE` and `_HTMX_RE` patterns alongside existing `_EMIT_RE`.
   - `_persist_cross_boundary_edges` in persistence_engine.py: already the right hook.

   **Entry points:**
   - `determined/ingestion/dynamic_edges.py`: add `extract_flask_route_map(py_src)`,
     `extract_http_fetch_edges(html_src, route_map)`, `extract_htmx_edges(html_src, route_map)`
   - `determined/persistence/persistence_engine.py`: extend Gap 7 block to also call new extractors

   **Estimated effort:** 1 day. Same regex/structural pattern as Gap 7 -- well-worn path.

---

## Baseline measurements (session 148, 2026-07-11)

Scope: 129 core dj2 source files (dungeon_neo, engine, routes, core, world, resolver + top-level .py).
Tools installed: pyan3, pyright (both via pip into Determined venv).

**pyan3 call graph baseline (BEFORE RM40):**
- Solid (call) edges: 1,701
- Dashed (use/defines) edges: 1,458
- Total: 3,159

**Determined graph_edges baseline (BEFORE RM40):**
- Total edges (all core dirs): 5,271
- Resolved (resolved=1): 1,087 (13%)
- Unresolved (resolved=0): 7,112 (87% -- bare name matches, stdlib collisions)
- Edge types: static=8,098, decorator=100, thread=1 (whole corpus)

**pyright baseline (dungeon_neo + engine + routes, 18 files):**
- Files analyzed: 18
- Errors: 213 (mostly unknown attributes -- dj2 has loose/missing type annotations)
- Warnings: 2
- Note: pyright has no "dump inferred types" mode; useful as error baseline and for
  spot-checking specific param types after RM49 inferred_annotation pass.

**Re-run after RM40:** compare resolved edge count (target: >13%) and check whether
pyan3 solid edges overlap better with Determined's resolved set.

---

---

RM37. **[DONE 2026-07-10] Traversal heuristic false-fires on "path" as symbol name**

   Discovered in RM21 probe re-run. Q5: "what is the path from the web route to the
   database for a new entry?" matches the traversal heuristic, but the heuristic
   extracts "path" as the symbol name and runs symbol/file/findings searches for "path".
   Nothing found, answer is empty.

   The RM31 traversal fix registered a heuristic for "path from X to Y" but the word
   "path" in other phrasings (route path, code path) also fires it, extracting the
   wrong noun.

   **Fix:** tighten the traversal regex so it requires "from <A> to <B>" structure and
   extracts A and B as the subject/target. If A and B aren't extractable, fall through
   to LLM decompose instead of running dead symbol searches.

   Entry point: `determined/agent/agent_resolver.py` -- traversal heuristic in
   `_HEURISTICS`.

---

RM36. **[DONE 2026-07-10] Orient/overview questions produce `<file.py>` placeholder NEEDs**

   Discovered in RM21 probe re-run. Q1: "give me a quick overview of what this codebase
   does" -- Phase 1 LLM emits `NEED: what does <file.py> do` with a literal angle-bracket
   placeholder. The resolver finds no match, zero facts retrieved, answer is empty.

   The model doesn't know which files to ask about, so it emits a template instead of
   real filenames. The grounding step doesn't fire for this question shape (no symbol or
   file name to extract).

   **Fix:** add a named heuristic for orient/overview questions that deterministically
   builds a NEED list from the corpus: top N files by call-edge count (hottest files),
   plus entry points. No LLM needed for decompose -- the corpus map IS the answer.

   Entry point: `determined/agent/agent_resolver.py` -- add to `_HEURISTICS`.
   Reference: `graph_most_connected` and `find_entry_points` tools already exist.

---

RM28. **[DONE 2026-07-10] Training mode: adaptive guided exploration**
   Replaces the three-mode UX concept (Tour/Discovery/Workbench) with a lighter,
   more elegant design that emerged from a full design discussion session 130.

   ---

   **Core concept: Training mode toggle**

   A small toggle in the header bar. Off by default for experienced users; on for
   new users discovering the tool. When off: today's UI, unchanged. When on: three
   things appear -- a corpus phase picker, a contextual guide card, and exploration
   color indicators on UI elements.

   **Permanent dismissal:** an X on the toggle stores `det_guide_dismissed=true` in
   localStorage. Toggle disappears permanently. A tiny "Guide" link in the footer
   restores it (no manual localStorage deletion required).

   ---

   **Adaptive guide -- no mode choice, no explicit steps**

   The guide watches what the user does and surfaces a contextual card for wherever
   they are. If they follow a logical order it feels like a tour. If they explore
   freely it still helps. No "next" button, no scripted sequence, no friction.

   The card is keyed to (active_tab + active_mode + corpus_phase). One card, always
   relevant, updates as the user moves. Card is visually neutral -- color lives on
   UI elements, not the card.

   **Content storage:** `determined/data/guide_commonplace.json`
   Shape: `{ "tab:frontier:orphan:skeleton": { "headline": "...", "body": "...",
   "what_to_notice": "..." }, ... }`

   General-layer guide (tool concepts independent of Commonplace) is deferred --
   RM16 one-liners already cover that floor. Build general layer as a second pass
   after Commonplace proves the pattern.

   ---

   **Exploration color grammar**

   Color indicators on the tab rail, sub-modes, corpus phases, and key tools.
   Tracks visited state in localStorage (`det:visited:tab:frontier` etc.).

   Rules:
   - **No color** -- unvisited. Not asking for attention.
   - **Red** -- visited, less than half the sub-elements explored.
   - **Amber** -- half or more explored, at least one remaining.
   - **Green** -- all sub-elements explored.
   - **One-action elements** -- skip red entirely, go straight to green on first visit.
     (A tab with no sub-modes, a tool with one action -- red would lie about there
     being more to do.)

   Color is a reward/progress indicator, not a to-do list. The game: find everything
   red and amber and turn it green. When everything is green, training mode has
   nothing left to offer.

   **Completion state:** all elements green â†’ guide card shows "You've explored
   everything. The guide will step back." â†’ toggle permanently auto-dismisses.

   ---

   **Corpus phase picker + code injection**

   Appears in training mode. Three phases: skeleton / complete / enhanced.
   Phase picker shows current phase and lets user jump between them.

   Implementation: start from skeleton (the existing seed/ files + seed DB).
   Injection is live -- "Add next piece" button writes the next implementation
   file to the corpus directory and calls reingest_file. The corpus panel updates
   in real time. The user watches metrics shift as code is added -- orphan count
   drops, hot symbols appear, stubs resolve. That IS the lesson.

   To jump ahead: inject all remaining pieces for a phase at once.
   Pre-built DBs for complete and enhanced are a fallback if injection proves
   fragile, but live injection is the preferred experience.

   Commonplace detection: key off `_db_path` containing "commonplace" (case-insensitive).
   Phase picker only appears when Commonplace is the loaded corpus.

   ---

   **Colorable element inventory (to finalize at build time)**

   Tab rail: Corpus, Navigate, Tools, Ask
   Frontier sub-modes: Direct, Orphan, ABC
   Corpus panel elements: Roots/Core toggle, corpus map expand, duplicate badge
   Corpus phases: skeleton, complete, enhanced (only when Commonplace loaded)
   Tools panel: each tool individually
   Ask bar: first query run

   Exact list locked in during Stage 1 build when the localStorage keys are defined.

   ---

   **Build order (each stage independently useful)**

   Stage 1: Toggle in header + permanent dismissal + localStorage scaffold +
            color indicators on tab rail (no content yet). Verify color grammar
            in browser before wiring anything else.

   Stage 2: Guide card panel + guide_commonplace.json content for all tab/mode
            combinations. Card updates as user navigates.

   Stage 3: Corpus phase picker + code injection. Skeleton â†’ complete â†’ enhanced
            live in the browser.

   Stage 4: Completion state. All green â†’ auto-dismiss message.

   Stage 5 **[DONE 2026-07-10]**: General guide layer for non-Commonplace corpora.
            guide_general.json keyed to element only (no corpus phase).

   ---

   **What already exists (build on, don't replace)**

   - COMMONPLACE_USER_JOURNEY.md -- content source for guide_commonplace.json
   - seed/ directory -- the skeleton state, 17 files, ready to inject from
   - reingest_file -- already works; injection calls this
   - RM16 one-liners -- the general-guide floor, already in place

---

RM23. **[DONE 2026-07-08] Commonplace Phase 3 extras arc: walk with Determined**

   Walk completed session 117. Phase 3 section of COMMONPLACE_USER_JOURNEY.md
   updated with actual tool outputs. All 3 extras were already implemented (Walk 4,
   session 115); this session was the documentation pass.

   **Actuals (complete corpus, 25 files, 64 functions):**
   - knowledge_status: 0 distilled, 42/64 missing docstrings, 0 design notes
   - find_abc_gaps: "All ABC stub methods have at least one non-stub override"
   - frontier_coverage: 0 stubs, 16 orphans (all anticipatory), LOW pressure
   - find_orphaned_impls: create_app possibly-stranded; 15 others anticipatory
   - check_design_violations: requires design notes first (0 in DB -- correct for fresh corpus)

   **DB reingested** 3 Walk 4 files before walking (linker.py, search.py, searcher.py
   were newer than DB). 1 updated in linker.py, 2 updated in searcher.py.

---

RM22. **[DONE 2026-07-08] Phase 0 bootstrap: new corpus from blank directory**

   UI guidance shipped (committed 0aaa111). Walk documented in
   COMMONPLACE_USER_JOURNEY.md Phase 0 section (committed this session).

   **What was built:**
   - 0-file scan: modal shows 3-step bootstrap guide (write first file, Analyze, then reingest_file)
   - Non-zero scan: modal shows "Analyze this project? N files Â· M MB Â· ~Xs" + confirm
   - Phase 0 walk: 17 seed files written to blank dir, Analyze produced DB in ~30s
   - Actuals: 17 files, 1 hot (storage/db.py), 0 stubs, 31 functions, 137 edges
   - Walk directory: C:\Users\bartl\dev\commonplace-walk (not in repo)

   **Key finding from walk:** 0 stubs in current seed (Walk 4 extras implemented
   extractor + processor functions). Phase 1 journey doc (which shows 2 stubs) was
   from an earlier seed state. Phase 0 â†’ seed shows a clean 0-stub codebase as
   starting point. ABC class hierarchy (EntryProcessor) surfaces immediately.

---

RM20. **[DONE 2026-07-10] design_note deduplication: LLM pass re-extracts rules the deterministic pass already stored**

   Done 2026-07-10 (session 134, commit 89bc6d5). Embed-at-store-time dedup wired into
   doc_extractor.py: each candidate rule embedded, cosine-compared against existing
   design_notes (threshold 0.85), skipped if duplicate. Also tracks within-run embeddings
   to catch back-to-back similar rules in one ingest pass.

   ~~Original description below (preserved for context):~~

   Discovered during RM15 Walk 2 Step 4 (Commonplace DESIGN.md ingest).

   **The problem:** `ingest_design_docs` runs two passes over a design doc:
   (1) a deterministic regex/keyword pass that extracts explicit constraint phrases, and
   (2) an LLM pass that extracts named invariants and authority rules.
   Both passes store their findings as `kind=design_note` artifacts. When the LLM
   rephrases a rule the deterministic pass already found, deduplication fails.

   **Current dedup:** compares the first 60 chars of the rule body at store time.
   Insufficient when LLM paraphrases: "PERMISSION: X must not Y" (deterministic) vs.
   "Only X is permitted to Y" (LLM) are the same rule but won't match.

   **Effect:** `check_design_violations` output shows the same rule 2-3x at nearly
   identical scores, inflating apparent violation count and obscuring signal.
   Observed: PERMISSION-prefixed duplicates appearing at 0.41 and 0.30 for a single
   query against a 10-rule corpus.

   **Fix options (in order of confidence):**
   1. Embed each candidate rule at store time; skip if cosine similarity to any
      existing design_note in the corpus exceeds 0.85. Reuses existing embedding
      infrastructure (`embed_text` from `determined/oracle/embedding_model.py`).
   2. Run dedup as a post-pass after all extraction: cluster all stored design_notes
      by embedding similarity, keep one canonical form per cluster.
   3. Skip the LLM extraction pass for rule types the deterministic pass already
      covers (PERMISSION, LAYER, MUST-NOT phrases). LLM pass restricted to rules
      the deterministic pass cannot find (e.g. implicit authority rules, named invariants
      phrased as prose without trigger words).

   **Recommended:** Option 1. One embedding call per candidate at ingest time.
   If similarity >= 0.85 to any stored rule, skip storage. Fast, local, uses
   existing infrastructure. No schema change needed.

   **Where to implement:** `determined/agent/doc_extractor.py` â€” the store step
   inside `ingest_design_docs`. Check before INSERT.

   **Estimated effort:** ~1 hour. Small, self-contained.

---

RM19. **[DONE 2026-07-07] Semantic Reconciliation Arc: duplicate detection, intent differencing, primitive discovery**

   All three passes implemented (confirmed session 118 â€” was marked FILED but code already exists):
   - Pass 1: `find_duplicates` â€” embed "{name}: {docstring}", pairwise cosine similarity matrix, pairs above threshold stored as `reconciliation_finding` artifacts.
   - Pass 2: `classify_duplicates` â€” feeds each stored pair to Qwen3-8B, classifies divergence from fixed taxonomy (accidental copy, historical evolution, performance optimization, platform-specific behavior, security reason, genuinely different abstraction). Stores classification as `reconciliation_finding`.
   - Pass 3: `find_primitive_gaps` â€” mines call graph for callee pairs that appear together across multiple callers; surfaces as `primitive_gap` artifacts.
   All three wired into TOOLS, tool_registry.py, and `list_reconciliation_findings`.

   Passes 4 (canonicalization) and 5 (architectural drift) deferred â€” require evidence from 1-3 first.



   Determined has shifted from static analyzer toward semantic maintenance system. This arc
   adds three reconciliation passes grounded in the call graph and embedding infrastructure
   that already exists.

   **Core design constraint:** every finding carries a reason classification, not just a
   similarity score. Goal is "explained differences" not "eliminated differences." The ideal
   output is not "these were merged" but "these differ by 7% due to platform-specific
   requirements -- divergence is intentional and documented."

   **Pass 1 -- Duplicate Detection (easy, do first)**
   Embed all function docstrings + names via existing all-MiniLM-L6-v2 infrastructure.
   Cluster by cosine similarity above threshold (0.85+). Surface groups of near-identical
   symbols. Output: candidate pairs with similarity score. No LLM needed.

   **Pass 2 -- Intent Differencing (medium, depends on Pass 1)**
   For each candidate pair from Pass 1: feed both docstrings + call graphs + file context
   to Qwen3-8B. Classify divergence reason from a fixed taxonomy:
   - accidental copy
   - historical evolution
   - performance optimization
   - platform-specific behavior
   - security reason
   - genuinely different abstraction
   Store classification as knowledge_artifact (kind=reconciliation_finding).

   **Pass 3 -- Primitive Discovery (novel, highest value)**
   Mine the call graph for repeated compositions: sequences Aâ†’Bâ†’Câ†’D that appear across
   multiple independent call chains. A composition appearing N times is evidence that a
   missing abstraction exists. Surface: "this 4-step pattern appears 12 times -- no shared
   primitive exists." Store as gap proposal in workflow_items.

   **Pass 4 -- Canonicalization (defer)**
   Propose structural consolidation (BaseParser hierarchy etc.). Downstream of 1+2+3
   being proven useful. High noise risk if run before evidence is established.

   **Pass 5 -- Architectural Drift (needs infrastructure)**
   Compare current dependency graph against a point-in-time snapshot to detect drift
   from intended architecture. Requires DB snapshot mechanism -- file as separate item
   when 1-3 are shipped.

   **Tractability order:** Pass 1 (one session) â†’ Pass 2 (one session) â†’ Pass 3 (two sessions).
   Passes 4 and 5 get their own items after the first three prove out.

   **What to build on:** `determined/oracle/embedding_model.py` (embed_text, cosine_similarity),
   `graph_edges` table, `knowledge_artifacts` (kind=reconciliation_finding),
   `workflow_items` (kind=backlog, provenance=llm-proposed).

---

RM18. **[DONE 2026-07-07] Act on RM17 gaps**

   Priority order from RM17 findings: Gap 2 â†’ Gap 10 â†’ Gap 1.

   **Gap 2 [DONE 2026-07-07]:** Flask @route decorator = entry point heuristic.
   `parse_ast._classify_role` now detects `@<name>.route(` pattern, classifies
   file as `entry_point`. Note: orphan count/list filtering via `_has_framework_decorator`
   was already in place. 9 regression tests added. Committed 0d9e0cc.

   **Gap 10 [DONE 2026-07-07]:** Auto-discover design docs on corpus load.
   `_check_design_doc_hint()` runs on `load_db`, scans for markdown with
   constraint_score >= 0.3 not yet ingested as design_notes, writes count+paths
   to `project_meta`. `_design_doc_hint()` reads it; `_emit_corpus_ready` includes
   it in payload. Frontend shows orange notice in header with dismiss button.

   **Gap 1 [DONE 2026-07-07]:** Structured layer-rule violation detection.
   `layer_rule` kind added to knowledge_artifacts (content = JSON {from_layer, to_layer,
   direction, source}). `_extract_layer_rules()` in doc_extractor.py parses design docs
   deterministically. `ingest_design_docs` stores layer_rule artifacts and writes
   LAYER_RULES.md seed doc with human-readable message if none found.
   `_check_import_layer_violations` now queries layer_rule artifacts directly; returns
   hint message when no rules defined. 15 new regression tests. 464 passed.

---

RM17. **[DONE 2026-07-05] Two-pass cold analysis of Commonplace: find tool blind spots**

   Findings filed in `docs/RM17_findings.md`. 10 gaps ranked. Top findings:
   - Gap 1 (HIGH): Layer-import violations invisible without design doc ingest + structured layer rules
   - Gap 2 (HIGH): Flask route handlers = 17 of 18 "orphans" are false positives; @route decorator = entry point
   - Gap 3 (MEDIUM): `_call_llm` ranked #2 root but is dead code; "ready but blocked" vs orphan distinction missing
   - Gap 4 (MEDIUM): `capture` role = INTERFACER (wrong, 95% confidence); should be COORDINATOR/CONTROLLER
   - Gap 10 (MEDIUM): DESIGN.md auto-discovery -- corpus has design constraints written for Determined, but no prompt to ingest them

   Root causes: (1) no auto-discovery/ingest of design docs; (2) Flask decorator pattern invisible to static analysis.

   **Next:** RM18 -- act on gaps. Priority order: Gap 2 (Flask entry-point heuristic, easy) â†’ Gap 10 (auto-discover design docs on corpus load) â†’ Gap 1 (structured layer-rule violations).

---

RM17_archive. **[ACTIVE text below, archived]** Two-pass cold analysis of Commonplace: find tool blind spots

   Two-pass examination of the Commonplace corpus to find what Determined gets
   right, wrong, and can't see at all. Output is a ranked list of gaps.

   **Pass 1 â€” cold read (tool output only):**
   Load Commonplace full corpus. Walk orient â†’ frontier â†’ topology â†’ spotlight
   queries â†’ knowledge. Write down exactly what Determined says the codebase is.
   No looking at source. Pure tool output.

   **Pass 2 â€” adversarial read (source truth):**
   Read the actual Commonplace source files directly. Independently form a picture
   of what the codebase is and does. Do not reference Pass 1 output while reading.

   **Compare â€” rub them together:**
   - False positives: tool reported X, X isn't real or isn't important
   - False negatives: code clearly does Y, tool never surfaced it
   - Blind spots: whole categories the tool has no way to see (design-level gaps)

   Blind spots are the highest-value output -- they point to missing tool
   capabilities, not just missed instances.

   **Rule:** complete Pass 1 and write it down before starting Pass 2.
   Once source is read, independence is lost.

   **Output:** ranked gap list. Each gap: what's missing, why the tool can't
   see it, how fixable it is (schema/query/LLM/structural limit).

   **Corpus:** Commonplace full (not seed) -- more signal.

---

RM16. **[DONE 2026-07-05] UI concept documentation: explain what each panel/mode/concept is and when to use it**

   Every panel, mode, and concept in Determined should have a one-line explanation
   visible in the UI at all times -- not triggered by emptiness or error, just
   always present as context. The goal is that a user who lands on any state
   (empty or populated, correct mode or wrong mode) still understands what they
   are looking at and why it exists.

   **The failure mode this addresses:**
   Reactive fixes (empty-state hints, error messages) unstick the user but don't
   build understanding. A user who hits Frontier in Direct mode with results never
   learns what Orphan mode is or when they'd want it. They got lucky, not informed.

   **What this means concretely:**
   - Frontier tab: one sentence on what Direct vs Orphan vs ABC means and when
     each applies. Not in a help doc -- in the tab itself, near the mode selector.
   - Corpus panel: one sentence on what "hot", "stubs", "design notes" mean.
   - Topology tab: one sentence on what the action queue is telling you.
   - REPL: startup message explains coverage and why low coverage = empty answers.
   - Each tool in the Tools panel: one line on what it does and when to reach for it.

   **Scope:** apply systematically across all journey steps in COMMONPLACE_JOURNEY.md.
   Walk each step, identify what a new user would not understand without prior
   knowledge, add the minimum text that closes that gap.

   **What this is not:** a tutorial, a help system, or a walkthrough. One sentence
   per concept, always visible, never modal. Experienced users ignore it; new users
   learn from it without having to ask.

   **When to work this:** after F1 and F3 are fixed. Walk the journey again with
   fresh eyes and file the missing explanations as a single pass.

---

RM21. **[ACTIVE] Small-model reasoning enhancement: push Qwen3-8B beyond its natural ceiling**

   **Technique 1 DONE (2026-07-08 + extended 2026-07-10 + Fix A 2026-07-15):** Verification loop wired into
   `_answer()` in `local_agent.py`. After ASSEMBLE, `claim_verifier.py` extracts structural
   claims (CALLS, NO_CALLERS, HAS_METHOD) via regex, checks each against `graph_edges` /
   `classes.methods_json`, and builds a correction block if any are wrong. One re-assembly
   pass with corrections prepended to facts. RM31-34 also done as part of this arc:
   blast-radius and traversal routing fixed (RM31), name-collision tagging in facts (RM32),
   comparative synthesis hint in ASSEMBLE (RM33), method confabulation detection (RM34).
   Fix A (2026-07-15): verify_claim now checks functions table when CALLS subject has no
   edges -- if symbol doesn't exist in corpus, emits correction. Same for HAS_METHOD.
   Catches Q5-style confabulation of symbols from training weights.

   **Technique 3 DONE (2026-07-16):** Traversal pattern (`trace_call_chain`) + heuristic bug fix.
   Probe results: 3 multi-hop queries run. Failures were (1) DECOMPOSE emitting template prose
   for traversal queries ("files in Key files"), (2) "each" extracted as a symbol name by the
   "what does X do" heuristic. Blast-radius + implementation-status query (probe 3) passed --
   DECOMPOSE was correct, impact bypass fired, answer was honest. General iterative DECOMPOSE
   loop has no evidence of being needed; gated on observing a non-traversal multi-hop failure.
   Fix: (a) negative lookahead in "what does X do" heuristic blocks common English words;
   (b) `walk_call_chain()` in agent_tools.py: deterministic BFS from start symbol, annotates
   stub/impl/missing per node; (c) `trace_call_chain` pattern in pattern_executor.py detects
   traversal intent, finds HTTP route handlers via `http_route` column, walks chain, one LLM
   synthesis call over the structured result.
   BFS depth fix (session 188, 2026-07-16): walk_call_chain was queuing FQDN callee names
   (e.g. services.extractor.extract) for WHERE name=? lookup; functions table stores bare names.
   Fixed with rsplit('.', 1)[-1] before queuing. Probes after Commonplace re-ingest: search->DB
   4 nodes deep, capture->storage 16 nodes (full pipeline end-to-end).

   **RM21-B [CLOSED 2026-07-16] Prose-style confabulation escape:**
   Gate probe run: Q5 against Commonplace. trace_call_chain pattern fired, found 0
   HTTP handlers (correct -- Commonplace has no web layer), returned honest "none found".
   No invented symbols, no prose confabulation. Fix A sufficient. Scan not needed.

   **RM21 probe re-run 2026-07-10 (after RM31-34):**
   - Q3 (name collision/search centrality): PASS -- RM32 tagging works, model answered correctly
   - Q4 (comparative boolean): PASS -- RM33 YES/NO hint fired, answer correct
   - Q6 (Entry class methods): PASS -- RM34 prompt hardening + verifier, no invented methods
   - Q1 (orient/overview): FAIL -- model emits `<file.py>` placeholder NEED, zero facts. Filed RM36.
   - Q2 (blast-radius linker.py): PASS -- blast_radius OperationalError fixed (symbol_type literal not column); answer now traces actual callers.
   - Q5 (traversal web-to-db): FAIL -- "path" word triggers traversal heuristic but extracts
     "path" as symbol name, runs dead searches. Filed RM37.

   **Remaining techniques (2-6):** Constrained decoding, prompt chaining, MCTS,
   speculative verification, large-model fallback. Build only after Technique 1
   proves insufficient on real multi-hop queries.



   The long-term goal: make Determined's local model reason reliably over multi-hop
   questions without requiring a larger model. Not a single feature -- a layered
   architecture built incrementally.

   **Why this matters:** Qwen3-8B can call one tool fine but degrades on multi-step
   reasoning chains (Aâ†’Bâ†’Câ†’D). Each technique below attacks a different part of that
   failure mode. Determined's deterministic fact layer is the key enabler -- the model
   doesn't need to *know* facts, it needs to *accept corrections* from the DB.

   **Technique 1 -- Verification loops (highest leverage, do first)**
   Model generates a claim â†’ Determined checks it against the DB â†’ if wrong, feed
   the correction back â†’ model revises. Pure tool-call pattern, no new infrastructure.
   Qwen3-8B is already good enough at accepting corrections. Start here.

   **Technique 2 -- Constrained decoding**
   Force model output to match a grammar or schema (e.g. `outlines` library).
   Model fills slots, can't hallucinate outside the schema. Dramatically reduces
   noise on structured queries. Pair with Technique 1.

   **Technique 3 -- Prompt chaining / decomposition**
   Break one hard question into N easy questions each within model capability.
   Determined answers each hop deterministically; model only plans the chain.
   This is the "lightly reasoned over" pattern already partially in place.

   **Technique 4 -- MCTS over reasoning (already in notes as future item)**
   Tree-search over evaluate() -- explore multiple reasoning paths, score them,
   pick the best. Expensive but effective for unfamiliar domains. Build after
   Techniques 1-3 prove insufficient for a real query.

   **Technique 5 -- Speculative verification**
   Model proposes, Determined's DB scores. No LLM judge needed -- the corpus IS
   the judge. Requires Technique 1 infrastructure to already exist.

   **Technique 6 -- Large-model fallback via browser bridge (already built)**
   When all local techniques fail, package the relevant context and send it to a
   large model (ChatGPT, Claude.ai, DeepSeek) via CDP browser automation. No API
   key required -- attaches to your running Chrome profile via CDP port 9222.
   Existing code: `C:\Users\bartl\dev\dj2\tools.old\bridge\`
   - `unified_core.py` -- BridgeCore: CDP attach, send, extract response (Selenium)
   - `deepseek_lib.py` -- DeepSeek-specific selectors and IOC context injection
   - `diagnostics/` -- test harness (test_full_consult.py, test_send.py, etc.)
   Determined already selects relevant context; bridge just needs a target URL and
   the packaged context string. Copy bridge/ into Determined when ready to wire.

   **Tractability order:** 1 â†’ 3 â†’ 2 â†’ 5 â†’ 4 â†’ 6. Each depends on the prior being
   proven on a real RM15-style query before adding the next layer. Technique 6 is
   the escape hatch -- available now, use only when local techniques are exhausted.

   **When to work this:** after RM15 Commonplace journey is complete and we have
   a baseline of what the model gets wrong on real multi-hop queries. The failures
   will tell us which technique to reach for first.

   **Note -- stealth browser option:** `https://github.com/tiliondev/fortress` is a
   Chromium fork patched at C++ level (V8/Blink/BoringSSL) that defeats bot detection.
   Not needed for the CDP-attach-to-real-profile approach above, but useful if a target
   site blocks even real Chrome profiles or if the bridge needs a fully headless setup
   (e.g. running on a server without a display).

---

RM15. **[DONE 2026-07-08] Commonplace guided journey: run it for real, fix Determined iteratively**

   The next active work arc. Full description in docs/COMMONPLACE_VISION.md.
   Synthesized user-facing journey (actuals from all walks): docs/COMMONPLACE_USER_JOURNEY.md

   **Four phases (0=scratch, 1=seed, 2=complete, 3=extras):**

   - Phase 0 (Scratch): DONE 2026-07-08 (RM22 resolved, walk recorded).
   - Phase 1 (Seed): DONE 2026-07-08 (session 119, clean user walk).
     Seed is now 17 files, 0 stubs (Walk 4 extras implemented). Journey doc updated.
     Key findings: 0 stubs in seed = no stub implementation story; 2 orphaned-impl
     (create_app false positive, validate_entry actionable); 0 design notes on clean start.
     COMMONPLACE_USER_JOURNEY.md Phase 1 section rewritten with actual current outputs.
   - Phase 2 (Complete): DONE (Walk 3). 0 broken stubs. Actuals recorded.
   - Phase 3 (Extras): DONE 2026-07-08 (RM23). Walk recorded in COMMONPLACE_USER_JOURNEY.md.

   **All four phases complete. RM15 DONE.**

   **Known issues (for future reference):**
   - ingest_design_docs path mismatch: DESIGN.md lives outside seed/ project root.
     Must call with explicit path, not auto-discovery.
   - Seed DB accumulates developer walk artifacts (design notes, distillation) across
     sessions. For a truly clean user demo, delete knowledge_artifacts (design_note,
     distilled) and semantic_summaries before loading the seed DB.

---

RM14. **[DONE 2026-07-05] Sidebar icon-nav**

   4-icon vertical rail (ðŸ—„ Corpus / ðŸ§­ Navigate / ðŸ”§ Tools / ðŸ’¬ Ask) replaces
   the flat 6-section sidebar. Corpus panel: analyze/switch + corpus map + gaps
   at a glance. Navigate panel: 6 start-here shortcuts only. Tools panel: query
   shortcuts. Ask icon toggles query bar independently. Clicking active icon
   collapses panel to 40px rail-only for max editor space. Shell grid updated
   to 40px + 210px + 1fr (was 210px + 1fr). Commit: 380814c.

---

RM13. **[DONE 2026-07-05] UI redesign pass: close remaining delta, fold DISCOVERY_MODEL**

   All sub-items completed across sessions 75-79:
   - A4: Universal symbol context popover (session 75)
   - F7: Frontier tab orphan/disconnected mode selector (session 75)
   - #1: Chat/ask bar hidden by default (session 76)
   - A3: Collapse duplicate Cytoscape edges with count badge (session 76)
   - W4-W5: Trail breadcrumb + export as session summary (session 78)
   - #7: Context mode switching (Design/Trace/Review) + call tree race fix (session 79)
   DISCOVERY_MODEL closed as tracking category.

---

29. **[DONE 2026-07-03] Frontier graph: ABC/unimplemented-interface shape**

   The current frontier graph query (functional caller -> stub callee, suffix-match join)
   finds direct call edges to unimplemented functions. It does NOT detect the ABC pattern:
   abstract methods defined on a base class that have no concrete override anywhere in the
   corpus.

   dj2's `engine/phases.py` is the canonical example: 47 `@abstractmethod` stubs on ABC
   classes (`InputPhase`, `IntentPhase`, etc.) that are completely disconnected from game
   code -- no class inherits from them yet. The call graph has no edges to these stubs
   because nothing calls an ABC method directly.

   **What a query for this shape needs:**
   - Detect which functions are abstract methods (body is stub AND decorated with
     `@abstractmethod`, OR parent class inherits ABC).
   - Find all classes in the corpus that inherit from the ABC (via class_attributes or
     a new class_hierarchy table).
   - For each abstract method, check whether any subclass overrides it.
   - Surface: abstract methods with zero overrides = true unimplemented frontier.

   **Implementation (session 66):** `find_abc_gaps()` in agent_tools.py â€” queries classes
   with base_classes_json containing 'ABC'/'Abstract', joins to functions to find stub methods,
   checks for non-stub overrides elsewhere. No new schema needed: existing `classes.base_classes_json`
   + `functions.is_stub` + `functions.file_path` are sufficient. Proxy heuristic (stub on ABC class
   = abstract) works well in practice. On dj2: 35 unimplemented abstract methods across 8 classes.
   Wired as agent tool `find_abc_gaps`, registry entry, test file (5 tests). Frontier tab gains
   "ABC (interface gaps)" mode â€” purple diamond nodes for abstract classes, red stubs for methods.
   Multi-level inheritance not handled (deferred â€” not needed for current corpora).

---

27. **[DONE 2026-07-08] Standards-grounded self-review: GRASP vocabulary wired into check_design_violations**

   As the tool matures, it should be capable of analyzing its own codebase and comparing
   its design decisions against documented, authoritative software design standards rather
   than ad-hoc patterns invented for the project.

   **The trigger for this item:** `infer_behavior`'s original 6 role patterns were invented
   from dj2's architecture rather than grounded in a published taxonomy. Wirfs-Brock RDD
   roles replaced them (session 56, 2026-07-02). This revealed a broader principle: any
   time Determined uses a classification scheme or taxonomy, that scheme should trace to
   a documented, general-purpose source rather than being project-specific.

   **What this item covers:**
   - When Determined is capable enough to analyze a moderately complex Python codebase,
     point it at `C:\Users\bartl\dev\Determined` itself as a corpus.
   - Ask it to identify places where design choices (tool names, category sets, scoring
     heuristics, pattern libraries) appear to be project-specific rather than grounded
     in general software engineering literature.
   - Compare findings against what the tool claims to support (general-purpose analysis
     of any repository) vs. what its internals assume.

   **Two standards with clear roles here (session 56 analysis):**

   Wirfs-Brock RDD -- already adopted for `infer_behavior`. Describes what a component
   IS (its role/character). Right for classification: "what is this function?"

   GRASP (Larman, "Applying UML and Patterns") -- describes WHERE to put responsibility.
   Not a classification taxonomy but a decision framework: "should this go here or there?"
   Two distinct uses:

   1. Determined violation detection (near-term): give findings design vocabulary.
      Current findings say "this symbol calls across a boundary." GRASP lets Determined
      say WHY that's wrong:
      - "Reaches across to get data it doesn't own -- violates Information Expert"
      - "Creates objects it has no business creating -- violates Creator"
      - "Boundary is reached around rather than through -- violates Protected Variations"
      This makes findings actionable, not just structural.

   2. dj2 design validation (longer term): dj2's Architectural Constitution already
      embodies GRASP without naming it. The mapping is near-perfect:
      - Protected Variations -> the AI boundary (LLM never touches game state directly)
      - Controller -> the adjudication engine (handles player action events)
      - Information Expert -> the authority hierarchy (only the owner mutates its data)
      - Indirection -> the Intent layer (input passes through classification before state)
      - Pure Fabrication -> ai_boundary.py itself (fabricated service, not a domain concept)
      Once Determined can reference GRASP explicitly, it can validate dj2's architecture
      with named principles rather than structural heuristics alone.

   **Other references to consider at review time:**
   - GoF design patterns -- structural/behavioral/creational
   - Clean Architecture layers (Martin) -- for layer-boundary detection
   - Any taxonomy currently hardcoded in Determined should cite its source or be replaced

   **Prerequisite:** Determined must be able to run corpus synthesis on a moderately
   large Python repo (itself) and have enough orientation capability to surface
   design decisions from its own knowledge_artifacts. Probably ready after phase 4
   (data flow tracing) is working.

   **Self-review run 2026-07-03 (session 60):** Item 27 executed. Determined's own corpus
   was ingested and the agent modules were analyzed. Key findings:
   - Role inference (infer_behavior_batch): COORDINATORs and CONTROLLERs correctly identified
     across agent_tools.py; INTERFACER for evaluate() accurate (thin LLM boundary).
   - match_structural_pattern: evaluator primitives return UNCERTAIN/STRUCTURER at radius=2;
     subgraphs too sparse for 3B model to reason about. agent_tools symbols had 1-node
     subgraphs due to stale inbound edges -- fixed by reingesting caller files.
   - check_design_violations: SOTS XI flagged on evaluate() (score 0.30) -- filed as item 28.
     SOTS XXIV on collect_symbol_context (reproducibility), XVI on check_design_violations
     (least privilege), XVIII on infer_behavior (observability) -- all borderline, low priority.

---

28. **[DONE â€” already implemented, confirmed session 67] SOTS XI: separate "decide to call LLM" from "call LLM" in evaluate()**

   **Source:** Self-review 2026-07-03. check_design_violations flagged SOTS XI on
   `determined.agent.evaluator.evaluate` (score 0.30).

   **What SOTS XI says:** "Separate the irreversible decision from its effect -- make
   'should we / which ones' a pure, exhaustively-testable function that returns a plan;
   make the doing a thin wrapper that only executes the plan."

   **The issue:** `evaluate()` currently does both: it builds the prompt, decides on
   the LLM call shape (question + evidence), and executes the LLM call in one step.
   The "decide" part (what to send, which evidence to include) is not separately testable
   without triggering an actual LLM call.

   **What to change:**
   - Extract a pure `build_eval_request(context, evidence, question) -> EvalRequest` that
     returns the prompt and parameters as a data structure (no LLM call).
   - `evaluate()` becomes: `build_eval_request(...)` then `_call_llm(request)` then
     `_parse_judgment(response)`.
   - Tests can exercise `build_eval_request` directly and verify prompt shape without
     mocking the LLM.

   **Priority:** Low. The current code is correct; this is a testability improvement.
   Worth doing before evaluate() grows more complexity.

---

19. **[DONE 2026-06-28] Design intent layer: check_design_violations + self-audit**

   The tool analyzes code structure but has no awareness of what the code is *supposed*
   to do. Design docs (architectural constitutions, subsystem specs, authority boundaries)
   are the authoritative intent for a project -- currently they live entirely outside
   the tool's knowledge layer.

   **The gap:** The tool can find that dm_chat_handler.py bypasses the authority layer,
   but cannot tell you *why* that's wrong or what the correct boundary is. Design intent
   has no representation in knowledge.db.

   **What this enables:**
   - Ingest design docs (markdown) as a separate artifact class alongside code
   - Extract aspirational constraints: authority boundaries, layer rules, forbidden patterns,
     named invariants, "must not" / "only X may" rules
   - Cross-reference code findings against design intent:
     "This symbol violates a documented boundary" not just "this symbol calls that one"
   - Surface drift: "ContextBuilder re-resolves entities -- constitution says it must not"
   - Inform every "where does this go" coding decision without dictating order

   **Nature of this item:** Living, aspirational, off-and-on. Not a one-time feature --
   a capability that deepens as the tool matures. Early stab: extract key constraints
   from design docs into knowledge_artifacts (kind=design_note, provenance=human-confirmed).
   Later: automated cross-reference against structural findings.

   **First concrete step:** Write a doc extractor that reads markdown design docs,
   pulls out named invariants and authority rules, and stores them as human-confirmed
   design_note artifacts scoped to the corpus. Then wire findings to check against them.

   **Primary target docs (dj2 corpus, all committed 2026-06-26):**
   - `docs/design/00A ARCHITECTURAL_CONSTITUTION.md` - the authority hierarchy and invariants
   - `docs/design/00B SYSTEM_CONSTRAINTS.md` - hard constraints
   - `docs/design/00F ASPIRATIONAL_DESIGN_INTENT.md` - authority boundaries (section B), AI DM
     vision (section C), world architecture (section D); section H explicitly describes what
     Determined should eventually extract and cross-reference from these docs
   - `docs/design/00E AI_LAYER_OPPORTUNITIES.md` - AI layer constraints and patterns

   When dj2 is the active corpus, these docs are the authoritative intent surface.
   The extractor should prioritize "must not", "only X may", "never", "must" phrases
   in these docs as the highest-signal invariants to store as design_note artifacts.

   **Why HIGH:** Without this, the tool cannot help maintain design integrity as code
   grows. It finds structural facts but misses the most important class of bugs:
   architectural violations.

1. **[DONE 2026-06-29] `files.role` classification** - `_classify_role()` added to
   `parse_ast.py`. Assigns "test", "entry_point", "init", "config", or "module"
   based on path/content heuristics. `find_files(role=...)` now works.
   Migration guards removed from persistence_engine (no persistent DBs - schema
   is the only authority; `param_types_json` moved into CREATE TABLE).

2. **[SUPERSEDED by item 22] `search_symbols` scope** - addressed by wide concept
   search design (item 22). Name-only match stays as the locator; concept search
   is a separate tool.

3. **[SUPERSEDED by item 23] `missing_docstrings` limit** - addressed by docstring
   health campaign design (item 23). Full coverage reporting + staleness detection
   + editor write-back replaces the capped list.

6. **[DONE 2026-06-29] Live sync loop: incremental per-file re-ingest** -
   reingest_file() in determined/ingestion/reingest_file.py. FileDelta scratchpad
   (in-memory), INSERT OR IGNORE fix in _insert_symbol, agent tool + CLI wired.
   6 regression tests.

7. **[DONE 2026-06-29] Contracts reconciliation and wiring** -
   Fixed "domains" vs "modules" key mismatch in scan_contract.py/parse_contract.py.
   Wired ContractRuntimeValidator (JSON stage invariants) into ingest post-pass.
   Completed drift pipeline: DriftClassifier -> HealthAggregator -> LifecycleController.
   violations -> contract_violations table; signals -> contract_drift_history on every
   ingest. stability_view now returns lifecycle states (ACTIVE/STABLE/DEGRADING/etc).

8. **[DONE 2026-06-28] Auto-populate semantic summaries at ingestion**

   `--summarize` flag added to `local_agent --source`. After ingestion and
   structural fact extraction, iterates all corpus files and calls
   semantic_summary() for each. Skips already-cached. Aborts gracefully on
   Ollama connection failure with count of summaries written. 297/297 passing.

9. **[DONE 2026-06-28] Distillation pass** -
   `semantic_summaries` and `file_purpose` artifacts store 3-4 paragraph LLM
   responses verbatim. Add a distillation step: pass each verbose blob back to
   Ollama with a compression prompt ("one sentence: what does this file/symbol
   do?") and store the result as a separate `distilled` kind in
   `knowledge_artifacts`. The distilled form is what `symbol_brief` and the
   agent resolver use as a quick-scan; the verbose form stays for full context.
   Subject naming convention: `distilled::<subject>`.

10. **[DONE 2026-06-28] Tool chaining: structured output mode** - every tool returns a
    string (right for LLM consumption). When one tool's output drives another
    programmatically (e.g. `list_callers` -> `risk_profile` for each caller,
    or `graph_subgraph` nodes -> `symbol_intent` for each node), the agent has
    to re-parse its own text. Add an internal `_raw` variant for key tools that
    returns structured data (list of dicts), used by agent_resolver's auto-
    expansion phase (phase 2b) instead of text-parsing. External API stays
    string-only. Affected tools: `list_callers`, `list_callees`,
    `graph_most_connected`, `graph_subgraph`, `search_symbols`.

20. **[DONE 2026-06-29] Call graph accuracy: type annotation exploitation + __init__ attribute tracking**

   Motivated by PyAnalyzer (ICSE 2024, Jin et al.) which achieves +24.7% F1 over
   comparable static analysis tools by modeling functions/classes/modules as heap
   objects. A full heap model is ~6-10 weeks and unnecessary given Determined's LLM
   reasoning layer. Two targeted improvements give 60-70% of the gain at ~5% cost.

   **Phase 1 -- Capture annotation data at parse time (schema + ingestion):**
   - `parse_ast.py` `_extract_functions`: capture `arg.annotation` for each parameter
     alongside `arg.arg`. Store as `param_types_json TEXT` column on `functions` table
     (JSON dict `{"param": "TypeStr"}`). Already captures `return_type`; this adds
     param types.
   - New `_extract_class_attributes` pass: for each `ClassDef`, find `__init__`,
     walk its body for `ast.Assign`/`ast.AnnAssign` where target is `self.x`.
     Extract inferred type from `Foo()` constructor calls or explicit annotations.
     Store in new `class_attributes` table:
     `(id, file_path, class_name, attribute, inferred_type)`
   - `persistence_engine.initialize_database`: add `class_attributes` table,
     ALTER TABLE guard for `functions.param_types_json`.

   **Phase 2 -- Use annotations in call edge resolution:**
   - In `parse_ast.py` `_extract_symbol_references` `Visitor.visit_Call`:
     when receiver is `obj.method()`, look up `obj` in current function's
     param annotation map. If `obj: Foo` is annotated, emit callee as `Foo.method`
     instead of bare `obj.method`.
   - If receiver is `self.attr`, look up `attr` in `class_attributes` for the
     current class. Emit `InferredType.method`.
   - Add `resolved INTEGER DEFAULT 0` to `graph_edges` (1 = annotation-derived,
     0 = heuristic name match).

   **Phase 3 -- Surface confidence in agent tools:**
   - `list_callers`/`list_callees`: tag edges with `(resolved)` vs `(inferred)`.
   - `describe_file`: report % of outbound edges that are annotation-resolved.
   - New DBOracle helper: `get_class_attribute_type(class_name, attr)`.

   **Why MEDIUM not HIGH:** LLM layer compensates for some graph inaccuracy.
   Highest value on dynamic-dispatch-heavy codebases; dj2/harrow are well-structured.
   Do after item 6 (live sync) since re-ingest is needed to populate new columns.

   **Estimated effort:** ~2 days. Order: schema (1c) -> param annotations (1a) ->
   __init__ attributes (1b) -> call resolution (2) -> agent tools (3).

11. **[FUTURE] Trace-weighted ranking** - replace heuristic scoring with
    trace-weighted ranking from expansion provenance. After real usage patterns
    are clear.

---

RM11. **[DONE 2026-07-05] edit_file agent tool: close the readâ†’reasonâ†’write loop**

   `edit_file(assessor, args)` in `agent_tools.py`. Three ops: `read_file`,
   `write_file`, `replace_in_file`. Path-boundary guard against project root.
   Wired into TOOLS dict and tool_registry.py. 12 regression tests pass.
   Full agentic loop now closed: goal_intake â†’ evaluate â†’ propose â†’ edit_file â†’
   reingest_file â†’ check_design_violations.

---

RM12. **[DONE 2026-07-05] Web search: SearXNG integration**

   `search_web(assessor, args)` in `agent_tools.py`. Hits SearXNG `/search?format=json`,
   returns top-N results as formatted title/URL/snippet text (snippet truncated at 200 chars).
   `SEARXNG_URL` config in `llm_client.py` (default `http://localhost:8888`; None = disabled).
   Graceful degradation on unreachable server. Wired into TOOLS and tool_registry.py
   (category: external). 10 regression tests pass. SearXNG is user-run (Docker or standalone);
   Determined just consumes the JSON API.

---

RM10. **[DONE 2026-07-16] goal_intake intent detection + trace routing**

   Probe run 2026-07-16 (session 191) against dj2. Embedding finds the RIGHT symbols.
   DeRe-CoT is the wrong fix -- the gap is in what goal_intake does with them.

   **Two confirmed failure modes:**
   1. Intent blindness: "find where AI boundary is violated" -> found AIBoundary correctly
      but plan says MODIFY it. Investigation goals need READ/BLAST_RADIUS, not EXTEND/MODIFY.
   2. Multi-hop gap: "trace player input to DB" -> got both endpoints but no path between
      them + noise. walk_call_chain already exists; goal_intake doesn't invoke it.
   Single-concept goals ("add consequence tracking") work fine -- no fix needed there.

   **Plan:**
   - 2A: Goal-type classifier -- keyword/embedding heuristic to detect intent as
     investigate | implement | trace | explain. Adjust action plan per type:
     investigate -> READ + blast_radius; implement -> EXTEND/MODIFY; trace -> 2B.
   - 2B: Trace routing -- extract two endpoint concepts from trace goals, invoke
     walk_call_chain between them, surface the path in the nav plan.

   **DeRe-CoT (original framing):** still valid if embedding starts finding wrong symbols,
   but not the current bottleneck. Keep in reserve.

   **Effort:** Small-medium. 2A is keyword matching + plan branch (~40 lines).
   2B reuses walk_call_chain; endpoint extraction is a regex/heuristic (~30 lines).

14. **[DONE 2026-07-01] Semantic speculative decoding** - once item 10 (structured output)
    is in place, explore using the 3B model as a reasoning-step predictor: 3B
    predicts which tools/symbols/docs are needed, Oracle fetches them, 8B reasons
    only over the pre-assembled result. Analogous to token-level speculative
    decoding but at the semantic level. Revisit after item 10 is shipped and
    real usage patterns show where the 8B is spending time unnecessarily.

13. **[FUTURE] Self-Harness pattern** - the corpus DB (knowledge_artifacts) is the
    natural store for harvested failure patterns. After ADVERSARIAL traces accumulate,
    mine them into `known_issue` artifacts keyed by failure category, then use those
    artifacts to tune agent_resolver heuristics. Loop: ADVERSARIAL run ->
    extract failure patterns -> store as known_issue -> harness reads on next
    run -> better routing. Closes the improvement loop without touching Ollama.

---

### LLAMA-SERVER MIGRATION (session 36, 2026-06-29)

Ollama is ethically compromised (early exploiter of llama.cpp open source project).
Replacing it with llama-server â€” the OpenAI-compatible server built directly into
llama.cpp itself. No wrapper, no company, pure llama.cpp output.

**Infrastructure already in place:**
- `llama-server.exe` (b9842, CPU): `C:\Users\bartl\models\llama-server\llama-server.exe`
- Model: `C:\Users\bartl\models\gguf\llama3.2-3b.gguf` (2.02 GB, extracted from Ollama blob,
  same GGUF format â€” no conversion needed)
- Start: `llama-server.exe -m C:\Users\bartl\models\gguf\llama3.2-3b.gguf --port 8080 --ctx-size 2048`
- Health: `http://localhost:8080/health` â†’ `{"status":"ok"}` (verified)
- API: `/v1/chat/completions` and `/v1/completions` (OpenAI-compatible)

**After item 25 is done and tested:** uninstall Ollama, delete `~/.ollama/models/blobs/` (~50GB).

---

25. **[DONE 2026-07-01] LLM backend: replace Ollama call sites with llama-server shim**

    All Ollama HTTP calls in Determined use one of two request shapes against
    `http://localhost:11434`. Replace with a thin `llm_client.py` module that
    targets `http://localhost:8080` (llama-server) and normalizes the response
    shape. Six call-site files updated to import from the shim instead.

    **Two Ollama API shapes in use (with their llama-server equivalents):**

    Shape 1 â€” `/api/generate` â†’ `/v1/completions`:
    ```python
    # OLD
    requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
    resp.json()["response"]
    # NEW
    requests.post(url, json={"model": MODEL, "prompt": prompt, "stream": False})
    resp.json()["choices"][0]["text"]
    ```

    Shape 2 â€” `/api/chat` â†’ `/v1/chat/completions`:
    ```python
    # OLD
    requests.post(OLLAMA_URL, json={"model": MODEL, "messages": [...], "stream": False})
    resp.json()["message"]["content"]
    # NEW
    requests.post(url, json={"model": MODEL, "messages": [...], "stream": False})
    resp.json()["choices"][0]["message"]["content"]
    ```

    **New file: `determined/agent/llm_client.py`**
    Two public functions, everything else stays the same:
    ```python
    LLM_URL   = "http://localhost:8080"
    LLM_MODEL = "llama3.2-3b"      # filename stem, no .gguf
    LLM_TIMEOUT = 60

    def generate(prompt: str, timeout: int = LLM_TIMEOUT) -> str | None:
        """Shape 1 â€” single prompt, returns text or None on failure."""

    def chat(messages: list[dict], timeout: int = LLM_TIMEOUT) -> str | None:
        """Shape 2 â€” message list, returns content string or None on failure."""
    ```

    **Six files to update (search-replace OLLAMA_URL/OLLAMA_MODEL/OLLAMA_TIMEOUT
    imports and response parsing):**
    - `determined/intent/semantic_summary.py` â€” Shape 1, `_generate()`
    - `determined/agent/agent_tools.py` â€” Shape 1, `_distill_one()` (line 372) and
      `_synthesize_with_ollama()` (line 1787)
    - `determined/agent/stub_projector.py` â€” Shape 1, `_call_ollama()` (line 179)
    - `determined/agent/doc_extractor.py` â€” Shape 2, line 370
    - `determined/agent/local_agent.py` â€” Shape 2, `_call_ollama()` (line 327);
      also update `PatternExecutor` init at line 371 and health/warmup refs
    - `determined/ui/ui_server.py` â€” Shape 2 (line 232), `_check_ollama()`,
      `_warmup_ollama()` â€” rename to `_check_llm()`, `_warmup_llm()`

    **Also update:** `determined/assessor/query_compiler.py` â€” Shape 1,
    `_compile_via_ollama()` (line 251) â†’ `_compile_via_llm()`.
    `determined/agent/pattern_executor.py` â€” remove `ollama_url/model/timeout`
    constructor args; import from `llm_client` instead.

    **Health check update in `ui_server.py`:** replace Ollama model-list check
    (`/api/tags`) with llama-server health check (`GET /health` â†’ `{"status":"ok"}`).

    **Test:** run full regression suite after swap. All 323 tests should still pass
    (most don't hit the LLM; the ones that mock it stay mocked). Manual smoke test:
    start llama-server, run `local_agent.py --ui`, ask a question.

---

26. **[DONE 2026-07-01] Model file management: document and maintain GGUF library**

    Ollama managed model downloads and storage. With llama-server we own the files
    directly. This item covers the transition and ongoing model management.

    **Immediate:** after item 25 verified working end-to-end â€” uninstall Ollama,
    delete `C:\Users\bartl\.ollama\` (reclaims ~50GB of blob storage).

    **Current GGUF library:** `C:\Users\bartl\models\gguf\`
    - `llama3.2-3b.gguf` â€” primary inference model (item 25)

    **Other models from Ollama library** (blobs exist, not yet extracted):
    Extract same way â€” read manifest, copy blob, rename `.gguf`.
    Manifests at `~/.ollama/models/manifests/registry.ollama.ai/library/`:
    - `llama3.2/latest` â€” same as 3b
    - `llama3.1/latest` â€” 8B model (~4.7GB blob)
    - `codellama/7b`, `codellama/13b`
    - `mistral/7b`
    - `qwen2.5/7b`, `qwen2.5-coder/1.5b`, `qwen2.5-coder/latest`
    - `qwen3.5/35b` â€” large model
    - `gemma3/4b`

    **Model management going forward:** download GGUF files directly from
    HuggingFace (TheBloke / bartowski quantizations are standard sources).
    No model manager needed â€” files are just files.

    **llm_client.py config:** `LLM_MODEL` should match the GGUF filename stem
    OR be ignored entirely (llama-server serves whichever model it was started
    with â€” the model param in the request is advisory, not a selector).
    Simplest: remove model name from request payload since llama-server ignores it.

---

### ASSISTANT ARC (session 36, 2026-06-29)

The tool has matured from an oracle (answer queries) to an assistant (surface gaps,
propose changes, support review). These four items build the assistant capability
layer on top of the existing structural knowledge foundation.

**What these build on (concrete infrastructure â€” read before building any of 21-24):**

Embedding: `determined/oracle/embedding_model.py` â€” `embed_text(str) -> np.ndarray`,
`cosine_similarity(a, b) -> float`. Lazy-loads `all-MiniLM-L6-v2` on first call.
In agent_tools.py the model is cached as `_get_embed_model()`; batch encode via
`model.encode([...], normalize_embeddings=True)`, dot product gives cosine similarity.

Design frame pattern: `_get_design_frame(assessor, symbol, file_path)` at
agent_tools.py:394 â€” builds query string from symbol+file stem+docstring, calls
`search_tenets(query, threshold=0.32, top_n=3)` from `determined/data/sots_loader.py`.
This is the reusable pattern for "embed context, cosine-search a knowledge surface."

Design violations pattern: `_check_design_violations_core(assessor, symbol, file_path)`
at agent_tools.py:504 â€” same embed+cosine-search pattern but richer query
(symbol+docstring+callee names+file stem) and searches `design_notes` at threshold 0.30.

Distilled summaries: stored in `semantic_summaries` table, `distilled` column.
Query: `SELECT distilled FROM semantic_summaries WHERE subject LIKE ? AND distilled IS NOT NULL`.
Subject is the file path. Also stored as `kind='distilled'` in `knowledge_artifacts`
with subject `distilled::<name>`. Both stores exist; `semantic_summaries.distilled`
is the primary one used by `symbol_brief` and `goal_intake`.

Goal intake semantic search pattern (agent_tools.py:1454-1484): loads all symbols
with docstrings via `_search_symbols_raw(oracle, "", limit=600)`, enriches each
with distilled file summary, batch-encodes all + the goal query together, ranks by
dot product. Threshold 0.28. This is the reusable pattern for conceptâ†’symbol matching.

Review queue: `determined/intent/workflow_store.py` â€” `add_item(conn, kind, subject,
content, provenance="human")`. Use `provenance="llm-proposed"` for machine-generated
proposals. `kind="next_up"` for actionable items. `update_item(conn, id, status="done")`
to accept. `status="deferred"` to dismiss. Table is `workflow_items` in the corpus DB.

Symbol references: `symbols` table has `symbol_type` values `function`/`class`
(declarations) and `caller`/`callee` (call-graph participants). `graph_edges` has
`caller`, `callee`, `caller_file`, `line_number`, `resolved`. `symbol_references`
table has `caller`, `callee`, `file_path`, `line_number`. All three needed for
find-references (item 21): declarations from `symbols`, usages from `symbol_references`.

Class attributes: `class_attributes` table â€” `(file_path, class_name, attribute,
inferred_type)`. Added in item 20. Used in item 21 for class attribute listing.

Risk scoring: `determined/agent/risk_annotator.py` â€” `score_risk(oracle, symbol)`
returns dict with `level` (HOT/WARM/SAFE), `reasons` list. Already used in `goal_intake`
and `risk_profile`. Import: `from determined.agent.risk_annotator import score_risk`.

---

21. **[DONE 2026-06-30] Symbol context view** â€” `symbol_context(assessor, args)` in agent_tools.py.
    Single call returns declaration, docstring, risk badge, find-references, callers/callees,
    class attributes, design frame, and stored findings. understand_symbol task pattern
    updated to single step. Wired into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern.

---

22. **[DONE 2026-06-30] Wide concept search** â€” `concept_search(assessor, args)` in agent_tools.py.
    Searches symbol names, docstrings, behavioral contracts, design notes, distilled summaries.
    Semantic re-ranking via all-MiniLM-L6-v2 at threshold 0.25. Grouped output by surface.
    Wired into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern.

---

23. **[DONE 2026-06-30] Docstring health â€” campaign tool** â€” surfaces missing and stale docstrings,
    proposes fills, supports editor write-back. New function `docstring_health(assessor, args)`
    in agent_tools.py. Optional args: `file` (scope to one file), `module` (scope to
    path prefix), `propose` (bool, default True â€” generate proposals and store in queue).

    **Missing detection:**
    ```sql
    SELECT name, file_path, line_number FROM functions
    WHERE (docstring IS NULL OR docstring = '')
    [AND file_path LIKE ? if scoped]
    ORDER BY file_path, line_number
    ```
    Same for `classes`. No limit. Always show total count.

    **Staleness detection:** for symbols WITH docstrings, retrieve `distilled` from
    `semantic_summaries` for their file. Embed both the existing docstring and the
    distilled summary using `embed_text()` from `determined/oracle/embedding_model.py`.
    `cosine_similarity(embed_text(docstring), embed_text(distilled))` â€” low score
    (< 0.55, tune empirically) = potentially stale. Report score alongside each flagged
    symbol so developer can judge. High distance = docstring and code diverged.

    **Proposal generation:** for each missing or stale symbol, look up distilled text:
    `SELECT distilled FROM semantic_summaries WHERE subject = ? AND distilled IS NOT NULL`
    (subject is file_path). If found, call `workflow_store.add_item(conn, kind="next_up",
    subject=f"docstring::{file_path}::{name}", content=distilled_text,
    provenance="llm-proposed")`. Store file_path and line_number in content as JSON
    so write-back knows where to go.

    **Editor-launch (UI layer):** `ui_server.py` â€” when user clicks a proposed docstring
    item in the work queue, open an inline editor pre-filled with the proposed text.
    On accept: write the text as a docstring to the source file at the stored line_number,
    call `workflow_store.update_item(conn, id, status="done")`. On reject: status="deferred".

    **Confidence display:** show cosine distance score alongside each stale flag.
    Score >= 0.80: likely fine. 0.55-0.80: review. < 0.55: flag as stale.
    Missing symbols get no score (N/A â€” no existing docstring to compare).

    **UI tab:** add `"docstring_health"` to `_TAB_TOOLS` in `ui_server.py` alongside
    the existing `"docstrings"` tab (which can be retired or repurposed as a summary).

---

24. **[DONE 2026-06-30] On-demand gap analysis with standing summary** â€” two-tier capability:
    a fast standing summary always available, and a deep on-demand analysis.

    **Gap summary (fast, DB-only, no LLM):** new section in `knowledge_status` output
    (agent_tools.py ~line 1023). Runs these heuristics via SQL:
    - Docstring coverage: `SELECT COUNT(*) FROM functions WHERE docstring IS NULL` /
      total. Per-module breakdown (group by first path segment).
    - Distillation coverage: `SELECT COUNT(*) FROM semantic_summaries WHERE distilled IS NOT NULL`
      / total files.
    - Design note coverage: count `knowledge_artifacts` where `kind='design_note'` per module.
      Modules with 0 design notes flagged as undocumented.
    - Pattern gaps (hardcoded heuristics for now): e.g. check if `files` table has any
      non-NULL `role` values (item 1 just landed â€” verify it's populating).
    Output: short text block "GAPS AT A GLANCE" with module-level counts and flags.
    No LLM. Fast enough to include in session startup output.

    **Full gap analysis (on-demand, LLM via Ollama):** new tool `gap_analysis(assessor, args)`
    in agent_tools.py. Optional args: `file`, `module`, `symbol` to scope. No args = uses
    gap summary to pick highest-signal area automatically.

    Scoped analysis steps:
    1. Collect what exists in the scoped area: symbols, their types, docstrings, design notes,
       behavioral contracts, risk scores.
    2. Collect what exists in analogous areas (same module pattern elsewhere in the corpus).
    3. Prompt Ollama (3B model via `assessor._ollama_generate()` or equivalent) with:
       "Here is what exists in [area]. Here is the pattern in analogous areas. What is
       missing, incomplete, or could bridge these areas? Propose typed fills: extend,
       bridge, mirror, consolidate."
    4. Parse response into a list of proposals. Store each as `workflow_store.add_item(
       conn, kind="backlog", subject=f"gap::{area}", content=proposal_text,
       provenance="llm-proposed")`.

    **Key constraints:**
    - NOT automatic. User-initiated. Menu option in UI sidebar or agent command.
    - Output is idea-mode â€” explicitly framed as possibilities, not prescriptions.
      Prefix output: "GAP ANALYSIS (generative â€” proposals may be off target):"
    - Ollama call uses 3B model (fast), not 8B. This is brainstorming, not reasoning.
    - Gap summary is the navigation layer: read it first to know where to focus the
      full analysis. Full analysis on a well-covered area will produce noise.

---

### MENTOR CAPABILITY ARC (session 26, 2026-06-27)

The goal of Determined is to approximate what Claude does when a developer brings
it an unfamiliar codebase: orient quickly, identify what is dangerous vs safe,
surface mismatches between design intent and code reality, and guide the developer
toward the right approach for their goal. Not answer queries - navigate.

This requires three capabilities that do not yet exist, plus one prerequisite.
All four build on existing infrastructure rather than replacing it.

**What the tool already has that these build on:**
- knowledge_artifacts (design_note kind) - foundation for design intent storage
- pattern_executor + orient_to_codebase - structured orientation, extendable
- risk_annotator - already scores hot/warm/safe per symbol
- stub detection - already knows what scaffolding exists but is unimplemented
- bag_store - already accumulates session context across queries
- mine_design_docs.py - hand-authored design notes in the right shape, wrong source

**The 3B model's role:** connector of pieces, not memory. DB holds structured
knowledge; the model reasons over what it is given. Architecture is: assemble
the right context for each step, let the model connect it.

---

22. **[DONE 2026-06-28] Design doc extraction: auto-mine markdown into design_note artifacts**

   Shipped as `ingest_design_docs` tool and `discover_docs` tool in agent_tools.py.
   discover_docs scans project for markdown with constraint density scoring.
   ingest_design_docs uses the 3B model (Ollama) to extract named invariants, authority
   rules, forbidden patterns from those docs and stores as design_note artifacts
   (provenance=llm-extracted). Re-running is idempotent. Wired into TOOLS and REGISTRY.

---

23. **[DONE 2026-06-28] Frame comparison: surface design intent automatically when code touches documented areas**

   Rebuilt session 30 on semantic embeddings (all-MiniLM-L6-v2). _get_design_frame()
   embeds symbol+docstring context, cosine-searches all design_notes in knowledge.db
   (threshold 0.32). Query enriched with docstring so abstract principle text (SOTS)
   surfaces alongside project-specific constraints. Replaces fragile string matching.
   320/322 passing (2 pre-existing failures, unrelated).

---

24. **[DONE 2026-06-28] Goal intake: developer states intent, tool assembles goal-directed context**

   goal_intake(goal) in agent_tools.py. Takes natural language goal, returns navigation plan:
   - Semantic search over symbol docstrings -> top 5 relevant symbols
   - HOT/WARM/SAFE risk badge for each
   - Design rules from knowledge.db (SOTS + project notes) semantically matched to goal
   - Uncalled functions near relevant files as safe insertion candidates
   - Ordered approach: READ (hot boundaries) -> REVIEW (warm) -> EXTEND (stubs) -> MODIFY (safe)

   Trigger phrase: "I want to add/build/implement/create/extend X"
   Wired into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern. 320/322 passing.

---

25. **[DONE 2026-06-28] Corpus map: merged and shipped**

   Branch ui/corpus-map merged to main and branch deleted. Corpus map panel
   (Roots/Core with risk badges, collapsible) is live in the UI.

---

## Chronological session log

See `git log` for full session history. HISTORY.md (docs/HISTORY.md) is a curated
decision log -- non-obvious choices, failed approaches, surprises still live.
