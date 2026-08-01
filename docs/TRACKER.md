tools/analysis - TRACKER (consolidated)
=========================================

This file is the canonical open-items list for the Determined analysis tool.
Active open items only. Closed items are deleted — for historical context use git log.
For architecture/intent, see DESIGN.md. For doc structure, see docs/README.md.

Per CLAUDE.md's working agreement: update this file in place as work completes
(checkboxes, dated notes) so Bart can see what changed via `git diff`.

---

## DESIGN PRINCIPLES

These are standing architectural commitments, not tasks. Apply when making
implementation decisions, not scheduled as work items.

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
| Determined (Python) | Full convergence | probe 2026-07-31 (self-model check): 12 stubs total — 2 real gaps (pattern_executor.__init__, contract_drift_classifier.__init__), 1 known accepted (suggest_tags), 9 test mocks; 0 false positives; 95.6% unresolved edges (external-lib ceiling, accepted); 1426/2147 inferred EPs (framework-caller ceiling, accepted); docstring health 62.1% missing (test files dominant; assessor.py notable) |
| dj2 (Python+JS) | Full convergence | probe 2026-07-31 (post re-ingest): 25 stubs; 12 FSM stubs (encounter/trade/barter JSON, 0 callers — design-complete islands); 5 subrace stubs (dnd_data.py, delete when dj2 coding starts, accepted); 4 real gaps with callers (_get_encounter_context, _get_combat_context, _register_world_tools, on_arc_completed — each 1 caller); process_consequences now 0 callers (orphaned, not a blocker); 3 test stubs (check_parley, get_player_by_session×4, test_encounter_parley_failure — accepted); unresolved edge ratio 87.6% (world/ ceiling, accepted); 66 JS cross-boundary edges (33 http_fetch + 33 cross_language); 594 design_notes; 9 decisions; docstring health 56.7% (804/1419 missing) |
| Commonplace (Python) | Full convergence | 1 stub (suggest_tags); classified: frontier stub, waits for LLM_ENDPOINT design decision |
| rotjs (TS) | Probe-passes | 6 stubs; lib/src dual-rep known |
| dungeoncrawler (TS) | Probe-passes | 0 stubs; clean |
| dnd-dungeon-gen (JS) | Probe-passes | 6 stubs; JS callee resolution gap known |
| end-of-eden (Go) | Probe-passes | 0 stubs; 15% unresolved (external libs, correct) |
| ruggrogue (Rust) | Probe-passes | 0 stubs; normalize_symbol strip known |
| slater (Rust) | Probe-passes | 195 files, 0 stubs, 1985 inferred EPs (tests/benchmarks, correct); async boundary blind |
| brogue-ce (C) | Probe-passes | 977 symbols, 7233 edges; 30 true stubs; cellHasTerrainFlag HOT (96 callers) |
| llm.c (C+Python+CUDA) | Probe-passes | 729 symbols / 2960 edges; 148 CUDA kernels; 22 stubs (mostly false-positives) |
| mach (Zig) | Probe-passes | 3425 symbols / 9359 edges; 80 stubs all correct (C FFI + ObjC); 14% resolution (expected ceiling) |
| clx (Lua) | Probe-passes | 529 symbols / 996 edges; 2 Lua stubs correct; 46% resolution |
| LearnWebGPU (C++) | Probe-passes | 656 symbols / 1730 edges; 3 true stubs; macro-hidden STRUCT/END bug fixed |
| raylib (C++) | Probe-passes | 13280 symbols / 59435 edges; 3485 stubs = header-only libs (raygui.h) + GPU API bindings (gl.h, vulkan.h) — accepted ceiling; no dedup applicable |
| zig-gamedev (Zig) | Probe-passes | 4999 symbols / 20682 edges; 668 stubs after dedup (was 1787); remaining = C FFI to Dear ImGui — accepted ceiling |
| ebiten (Go) | Probe-passes | 6367 symbols / 45073 edges; 50 stubs = proprietary platform SDK stubs (Nintendo/PS5) — correctly unimplementable; 82% unresolved = Go interface dispatch ceiling (RM73) |
| batteries (Lua) | Probe-passes | 451 symbols / 706 edges; 0 stubs; clean; 79% unresolved = Lua stdlib alias ceiling (RM73) |

HTML: best-effort. Capture js_event_binding edges; don't model HTML structure.

**Future additions:** bethechatbot.com — review site, determine what to pull in.

### Per-session probe loop (deterministic, no LLM)

Run before any other work. Surface findings + what needs human input.

1. **Stub sweep** — is_stub=1 across active corpora; classify: real gap / test mock / Protocol false positive / dead code.
2. **Unresolved edge ratio** — files with highest unresolved callee %; trust floor for call chain answers.
3. **ABC gaps** — find_abc_gaps on key subsystems; interface contract drift.
4. **EP inferred count** — inferred vs. explicit EPs; movement signals real graph improvement.
5. **Docstring health** — top-N missing + staleness; where is the knowledge layer thinnest?

Report: "here's what I found / here's what needs your input / here's what I can close."

---

## RM74 — Analyst-level workflow capability audit

**Origin:** 2026-07-30 walkthrough session — using Determined on dj2 as a live evaluation.
Every time Claude reaches for something outside the tool (raw SQL, file reads, mental synthesis)
that's a gap. Goal: systematically close those gaps so Determined does the analysis, not Claude.

**Constraint:** All new capabilities must be corpus-agnostic and language-agnostic.
They operate on graph structure, stub signals, call edges — never on domain knowledge baked in.
The corpus tells you what's important; the tool surfaces it.

**Approach:** As the walkthrough continues, log each gap below. Then build or wire the tool
to cover it. Expect to discover workflows that work for any corpus.

### Gaps found so far

**GAP-1: Island detection** (2026-07-30, FIXED 2026-07-31)
- Fix: find_stub_islands() in graph_utils.py — BFS upward through caller chain; stub is an
  island if no non-stub caller exists in transitive closure. Tool wrapper + resolver pattern
  "stub islands [in X]" / "unwired stubs". Upgraded existing find_stub_islands tool to use
  BFS logic (was direct-caller check only). Commit: 71a4b9b

**GAP-2: Cross-layer chain synthesis** (2026-07-30, FIXED 2026-07-31)
- Fix: chain_synthesis() in graph_utils.py — BFS upward from stub to nearest EP, annotates
  each hop as implemented/stub/EP, returns downstream callees and missing-link list.
  Wired to chain_context tool (already existed, now reachable via "chain for X" / "wiring
  chain for X" Ask bar patterns). Commit: 7db2691

**GAP-3: Route/boundary blind spot** (2026-07-30, FIXED 2026-07-31)
- What happened: Claude flagged `/api/resolve-encounter` as "unknown — check manually."
  JS fetch() calls to Flask routes don't produce Python graph edges, so the tool can't
  confirm whether the backend route exists.
- Gap: Cross-language boundary tracing (JS → HTTP → Python). The tool ingests both sides
  but doesn't join them on route strings.
- Fix (2026-07-31): Bug in _persist_cross_boundary_edges — HTML templates found in
  file_analyses prevented JS disk scan from running (single `not html_srcs and not js_srcs`
  guard). Decoupled with _need_html/_need_js flags. Re-ingest of dj2 now produces 21
  JS http_fetch/cross_language edges (e.g. dungeon.enterIntegratedMode → dungeon_enter).
  Commit: 9553e65

**GAP-4: Ask bar returns data, not analysis** — FIXED (2026-07-31, verified in UI)
- Fix (commit 8237b2f): _build_wiring_gaps reports isolated stubs as "unimplemented and not
  yet connected to any caller." Routing was already correct.
- Verified: "what is the state of the encounter subsystem?" on dj2 (post re-ingest) produces
  all 6 sections: COMPLETE (7 funcs), STUBS (_get_encounter_context w/ caller waiting),
  ORPHANED (7 funcs), WIRING GAPS (build → _get_encounter_context, unimplemented),
  DESIGN (3 design_notes from docs/design/), FIRST STEP (implement _get_encounter_context).
- Tiers 2-4: all shipped (see below).

### The larger arc (2026-07-30)

This is not just a fix — it's a capability tier upgrade. The current tool has:
  - Ingestion (structural facts into DB)
  - Retrieval (semantic search, call graph queries)
  - Display (UI surfaces — Frontier, Shape, Ask, etc.)

What it needs:

**Tier 1 — Analyst layer** DONE (2026-07-31, commit 8237b2f)
  - build_domain_analysis(): 6-section deterministic output from graph + knowledge artifacts.
  - Ask bar: "what is the state of X?" routes to analyst, no LLM call.

**Tier 2 — Plan layer** DONE (2026-07-31, commits abbf018 + 62e8050 + 0889c47)
  - generate_domain_plan(): "plan for X" → ranked workflow_items in Build Queue.
  - Stubs with callers → next_up #1,2,...; isolated → next_up after; orphaned → backlog.

**Tier 3 — Direction layer** DONE (2026-07-31, commit 1e32ee9)
  - generate_direction_update(): "I implemented X" → marks item done, reports callers
    now unblocked, surfaces remaining stubs in same file as new frontier.

**Tier 4 — Knowledge accumulation** DONE (2026-07-31, commit 71a4b9b)
  - build_domain_analysis() stores each run as analyst_run:{subsystem} artifact.
  - Second run diffs stub lists and prepends "[Since last analyst run]" delta.

All tiers corpus-agnostic. Same pipeline on dj2, Commonplace, rotjs, any language.

---

## RM68 — Remove subrace concept from dj2

**[dj2 REPO ONLY — NOT A DETERMINED TASK — NEVER ACT ON THIS IN A DETERMINED SESSION]**

The OG system rewrite dropped subraces. Current dnd_data.py stubs (subraces,
get_subraces_for_race, get_race_for_subrace, semantic_match_subrace,
semantic_match_fighting_style) are dead concept remnants — do not implement.

**Scope (3 files):** world/dnd_data.py (5 stubs), world/character_generator.py,
world/authority_system.py.

**Approach:** blast_radius each subrace stub to confirm low impact, then remove.

**Gate: dj2 session only. Surfaces naturally from Determined analysis of dj2.**

---

## RM71 — export_context: context packet for external LLM escalation (DESIGN DONE)

New tool. Assembles a clipboard-ready plain-text packet for a function when
the complexity signal exceeds the local LLM ceiling (or on explicit user request).

**Output sections:**
1. Function under analysis + corpus signals + classify_stub verdict
2. Neighbor context (caller bodies, callees, name-similar siblings)
3. Complexity score + which signals drove escalation (visible reasoning)
4. Tool API manifest — what Determined can answer if the external LLM asks

**Escalation ladder (three tiers):**
- Tier 1: local LLM (always tried first)
- Tier 2: web LLM (Deepseek, ChatGPT) — paste packet, interactive via tool manifest
- Tier 3: Claude — architectural arbitration; packet includes prior reasoning chain

**Complexity signal inputs:** caller body avg lines, referenced type count, pattern
sibling availability, classify_stub confidence, unresolved edge ratio (neighborhood).
Threshold calibrated against real examples; above threshold → escalate.

**Gate:** RM70 done 2026-08-01 — gate cleared. Build when RM72 Phase A ships.

Full design: `docs/RM70_DESIGN.md` (Tiered reasoning ladder section).

---

## RM72 — Graph explorer (pyray, integrated navigation hub) (ACTIVE)

Native desktop tool for visually navigating corpus call graphs. Reads directly
from corpus SQLite DB. Not a companion — a navigation hub: every node is a doorway
into the existing analysis surfaces (Workbench, Oracle, Map, Editor, Call tree).

**Tech:** Python + pyray (raylib). Already shipping as `determined/ui/graph_explorer.py`
and `tools/graph_explorer.py`. Launched as subprocess from Map tab.

**Implementation phases:**

Phase A — Socket bridge (ACTIVE)
- `_SocketBridge` class in graph_explorer.py: connects to UI server (localhost:5050)
  as a python-socketio client. Non-blocking; graceful if UI not running.
- Emits `gx_select` on node selection: `{symbol, file, node_id, is_stub, is_tool}`
- Emits `gx_navigate` on destination action: `{destination, symbol, file}`
  destinations: "workbench" | "oracle" | "map" | "call_tree" | "editor"
- Listens for `gx_highlight` from UI: `{symbol}` — highlights node in graph
- ui_server.py: `@socketio.on("gx_navigate")` — calls `activateTab` equivalent
  server-side and emits `gx_nav_ack` to browser; browser JS handles tab switch +
  symbol load via existing `activateTab(name)` + `gxMap(symbol)` / workbench dispatch.

Phase B — Context menu
- Right-click on node OR panel cluster row → popup overlay at cursor.
- Items: Workbench | Oracle/Ask | Map | Call tree | Editor | --- | Expand | Frame |
  Copy name | Copy file path
- All items call `_navigate_to(destination, node)` — same function as keyboard shortcuts.
- Escape or click-outside closes menu.

Phase C — Panel action buttons
- When a node is selected: "Go to" button row in panel below node name.
  [ Workbench ] [ Oracle ] [ Map ] [ Editor ]
- Buttons and context menu both call `_navigate_to` — one implementation.

Phase D — Reverse bridge (UI → graph)
- "Show in graph" link in Workbench + Oracle panels when graph explorer is open.
- Emits `gx_highlight` → graph explorer frames + selects that node.

Phase E — Cluster semantic summary
- When cluster hub selected: panel shows files in cluster, entry points,
  external callees, semantic_summaries pulled from corpus DB for top nodes.

**`_navigate_to(destination, node)` is the integration point.**
Every surface (keyboard, context menu, panel button) calls it. It emits the
right socket event or fires the local action (editor open, clipboard).

**Opened:** 2026-07-28. Phase A active as of 2026-08-01 (RM70 done, moving here).

---

## RM74 — Visual signal projection: Phases 1 & 2 (DONE 2026-07-28)

Both phases were already implemented in `console.html` — discovered during session 266.
Phase 3 (signal fusion compositor + multi-modal projection) is FUTURE — gate:
classify_stub calibration stable + detect_conventions sort shipped.

---

## RM75 — Corpus expansion: new language corpora (ACTIVE)

Add representative corpora for under-represented languages. Clone into `C:\Users\bartl\dev\corpora\`,
ingest with `tools/ingest_lang_corpus.py`, run RM67 probe after each.

| Corpus | Language | Source | Status |
|---|---|---|---|
| raylib | C++ | github.com/raylib-org/raylib | [x] clone [x] ingest [x] probe — 13280 sym / 59435 edges; 3485 stubs = header-only libs + GPU API bindings, accepted ceiling |
| zig-gamedev | Zig | github.com/zig-gamedev/zig-gamedev | [x] clone [x] ingest [x] probe — 4999 sym / 20682 edges; 668 stubs after dedup (was 1787); remaining = C FFI to Dear ImGui, accepted ceiling |
| ebiten | Go | github.com/hajimehoshi/ebiten | [x] clone [x] ingest [x] probe — 6367 sym / 45073 edges; 50 stubs = proprietary platform SDK stubs (Nintendo/PS5), correctly unimplementable |
| batteries | Lua | github.com/1bardesign/batteries | [x] clone [x] ingest [x] probe — 451 sym / 706 edges; 0 stubs; clean |

**Status: all four ingested and probed 2026-07-28. Update RM67 probe table next session.**

---

## RM73 — Walker dispatch resolution: lift the per-language edge ceilings (FUTURE)

Every walker has a class of call edges it cannot resolve — not impossible, but
requires type inference or cross-file analysis not yet built. Logged as "accepted
ceilings" during probe sessions. Deferred, not closed.

**Per-language inventory:**
- **Go**: interface dispatch — `obj.Method()` where obj is an interface type
- **Rust**: `dyn Trait` dispatch — same class; trait/impl shape already extracted
- **Zig**: struct method calls on pointer receivers — `self.method()`; 14% resolution on mach
- **Lua**: local stdlib aliases — `local sub = string.sub; sub(...)` unresolvable
- **C/CUDA**: function pointer calls; indirect dispatch through struct-of-function-pointers
- **C++**: virtual method dispatch; `class_hierarchy()` not yet implemented

**Approach:** per-language resolution passes, not a single unified pass.
1. Capture structural metadata enabling resolution (class hierarchy, interface-to-impl maps)
2. Post-walk resolution pass: match unresolved edges against metadata
3. Confidence scores / edge-type annotations (statically-resolved / structurally-inferred / unresolved)

**Gate:** no single language blocks any other. Go interface resolution is likely
highest-value first target given Go corpus usage.

---

## RM21 — Small-model reasoning enhancement (ACTIVE)

Goal: make Qwen3-8B reason reliably over multi-hop questions without a larger model.
Not a single feature — a layered architecture built incrementally.

**Done:** Technique 1 (verification loop — claim_verifier.py extracts structural claims,
checks against DB, feeds corrections back for one re-assembly pass). Technique 3
(trace_call_chain pattern + decomposition). RM21-B closed (prose confabulation escape
not needed — Fix A sufficient). RM31-34 done (blast-radius routing, name-collision
tagging, comparative synthesis hint, method confabulation detection).

**Remaining techniques:**
- **Technique 2** — constrained decoding (outlines library); force output to schema
- **Technique 4** — MCTS over reasoning; tree-search over evaluate(); expensive, build after 1-3 insufficient
- **Technique 5** — speculative verification; model proposes, DB scores
- **Technique 6** — large-model fallback via CDP browser bridge (code in dj2/tools.old/bridge/)

**Tractability order:** 1 (done) → 3 (done) → 2 → 5 → 4 → 6.

**When to work:** when a real multi-hop query fails and the failure points to a
specific technique. Don't build the next layer until the current one proves insufficient.

---

## RM-Perf — Optimization Oracle (TODO)

Build `OptimizationOracle` alongside `DBOracle` — answers performance questions
(hot paths, repeated recomputation, cacheable traversals, pure/memoizable functions)
rather than structural ones.

**Two tiers:**
- **Statically inferable:** pure/memoizable functions (no shared-state writes, no I/O),
  dead event handlers, stable object layouts. Answerable from existing DB today.
- **Profile-grounded:** hot-path dominance, repeated recomputation on hot edges.
  Requires instrumentation hook (cProfile injection) producing `call_samples` table.
  Static tier ships first.

**Fit:** `DBOracle` stays structural. `OptimizationOracle` wraps same DB + optional
profiling DB. Corpus-agnostic — normalization maps any profiler output to existing FQDNs.

**Prerequisite:** analysis/code-generation arc complete. Static purity sub-tier
could ship earlier as a standalone tool.

**Estimated effort:** static tier ~1 session; profile-grounded tier ~2-3 sessions.

---

## RM76 — Decision ledger for target projects (IMPLEMENTED 2026-07-31)

A persistent human layer for architectural commitments that survives corpus rebuilds.

### Problem

Corpus DBs are expendable — rebuilt on re-ingest, deletable at any time. Any
decision recorded in `knowledge_artifacts` is lost on rebuild. This is correct
for derived facts (graph edges, stubs) but wrong for human commitments ("this
stub must be implemented before encounter resolution can close").

When Determined development ends and dj2 development begins in earnest, the usage
mode shifts: analysis is no longer done to improve Determined, it's done to guide
game development. At that point, decisions need to persist across sessions and
rebuilds, owned by the project being built.

### Design

**Decisions live in the target project, not in Determined's DB.**

- File: `<target>/.determined/decisions.toml` (or `.json`), checked into the
  target repo and versioned with it
- On corpus load, Determined reads this file and materializes rows into
  `knowledge_artifacts` as `kind='decision'`
- Re-ingest rebuilds derived facts, then re-loads decisions as an overlay
- The file is the source of truth; the DB is always a derived view
- Decisions are diff-able in git: when committed, when changed, by whom

**Analyst integration:**
- Section 5 (DESIGN) already reads `knowledge_artifacts` — decisions surface there
  automatically
- Drift check: analyst compares committed stubs/interfaces against current graph
  state and flags overdue items ("you committed to _get_encounter_context being
  implemented; it is still a stub after N sessions")

**Precedent:** same pattern as `docs/sots.md` in Determined — authoritative content
lives as a file, gets ingested as `kind='design_note'` rows. Decisions are the same
pattern applied to the target project.

### Name resolutions

A second ledger entry type alongside architectural decisions: **canonical names for
opaque or misleading symbols**, derived from structural evidence and committed as
durable facts.

**Problem:** corpora with meaningless names (`f1`, `handle`, `process`, `do_thing`)
or obfuscated/minified names defeat fuzzy symbol resolution at query time. The
wiring_chain expansion heuristic (name-match + file-path match) works for clean
subsystem names but is fragile and re-derived on every query. Once you've determined
what `f1` means, that knowledge should survive re-ingest the same way an architectural
decision does.

**Inspiration:** Acoda (arxiv 2606.11755) — adversarial code obfuscation that defeats
LLM analysis by breaking token-level name signals. The structural evidence Determined
already holds (callers, callees, file path, inline notes, body shape) is exactly what
survives obfuscation. Name resolutions commit that inference as a first-class artifact.

**Schema addition to `decisions.toml`:**
```toml
[[name_resolutions]]
original = "f1"
canonical = "handle_encounter_flee"
confidence = "high"
evidence = ["callers: resolve_flee (adjudication_engine.py)", "file: encounter_resolver.py"]
```

**Integration points:**
- Graph query layer and wiring_chain fuzzy expansion check resolutions first; committed
  canonical name wins over heuristic
- Analyst narration (section 1-4) displays canonical name alongside original
- Section 5 (DESIGN) can surface the resolution evidence as a design note
- Future: auto-suggest resolutions when Determined detects opaque names + strong
  structural evidence; human confirms, gets written to `decisions.toml`

**Same gate as decisions:** corpus rebuilds re-materialize resolutions as
`kind='name_resolution'` in `knowledge_artifacts` on load.

**Variable resolutions — same ledger, different evidence model:**

Function resolutions use call graph evidence (callers, callees, file path). Variables
don't appear in the graph — they need AST-derived evidence instead. The schema handles
both via a `scope` field:

```toml
# Function-level resolution (graph evidence)
[[name_resolutions]]
original = "f1"
canonical = "handle_encounter_flee"
scope = "symbol"
confidence = "high"
evidence = ["callers: resolve_flee (adjudication_engine.py)", "file: encounter_resolver.py"]

# Parameter resolution (AST + usage evidence)
[[name_resolutions]]
original = "x"
canonical = "encounter_context"
scope = "parameter"
parent = "f1"
confidence = "medium"
evidence = ["passed to: get_encounter_data()", "type hint: dict", "usage: x['state']"]

# Local variable resolution (AST + assignment source evidence)
[[name_resolutions]]
original = "_d"
canonical = "encounter_db_row"
scope = "local"
parent = "f1"
confidence = "medium"
evidence = ["assigned from: db.fetchone()", "indexed as: _d['id'], _d['type']"]

# Module-level variable resolution
[[name_resolutions]]
original = "_cfg"
canonical = "encounter_config"
scope = "module"
parent = "encounter_resolver.py"
confidence = "high"
evidence = ["assigned from: load_config('encounter')", "read-only after init"]
```

**Evidence sources by scope:**

| Scope | Primary evidence | Secondary |
|-------|-----------------|-----------|
| symbol | callers, callees, file path | inline notes, body shape |
| parameter | how it's passed downstream, type hints, attribute access pattern | sibling function signatures |
| local | assignment source (RHS of `=`), keys/indices accessed, functions it's passed to | adjacent comments |
| module | assignment source, read-only vs mutated, import pattern | file name, usage sites |

**Resolution chain:** when a symbol is resolved, its parameter resolutions inherit
the canonical symbol name as context — `x` in `f1` becomes `encounter_context` in
`handle_encounter_flee`. The full chain is preserved so analyst output reads coherently
at every level, not just at the function boundary.

**Auto-suggest trigger:** Determined flags a resolution candidate when:
- A symbol/parameter/local name is ≤3 chars OR matches known opaque patterns (`tmp`, `x`, `v`, `_d`, `k`, `n`)
- AND structural evidence score exceeds threshold (strong assignment source, or ≥2 usage signals)
Human confirms → written to `decisions.toml`. No auto-write without confirmation.

### When to build

Before the shift from "using dj2 to test Determined" to "using Determined to build
dj2." That transition is the natural trigger — when analysis sessions start producing
decisions worth keeping rather than observations worth discarding.

**Gate:** RM67 convergence reached on dj2 corpus AND at least one session where
Bart says "I want to record this decision."

---

## Cross-language — remaining tasks

Walkers all done (C, C++, Zig, Lua, Rust). See DESIGN.md for rationale and design.

- [ ] `target_lang` param in `project_stub` — multi-language emission routing
- [ ] `runtime_locator.py` shim — snippet compilation/verification for Zig/Lua/C
- [ ] Corpus chain UI — surface shape comparison across language family in browser
