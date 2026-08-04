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
| dj2 (Python+JS) | Full convergence | probe 2026-08-02: 25 stubs; 12 FSM stubs (encounter/trade/barter JSON — design-complete islands, accepted); 3 test stubs (check_parley, get_player_by_session, test_encounter_parley_failure — accepted); 10 real gaps: _get_encounter_context, _get_combat_context, process_consequences, _register_world_tools, on_arc_completed, get_race_for_subrace, get_subraces_for_race, semantic_match_fighting_style, semantic_match_subrace, subraces (dnd_data.py stubs are delete candidates); 8 phases.py ABCs correctly classified as intentional scaffolds (GAP-6 fix — decision artifact matched); unresolved edge ratio 87.9% (accepted ceiling); 10 decisions; 594 design_notes; docstring health 56.0% (809/1444 missing) |
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


## RM77 — export_context back-channel (FUTURE)

When a future capability exists to monitor or intercept external LLM output
(sub-agent listening to web LLM, browser automation reading responses, or
equivalent), wire it into `export_context_append` as a third source path.

**Current state (RM71 session accumulator):**
- `export_context_append(symbol, tool, args)` — user-relayed: user reads external
  LLM request, calls Determined tool, relays result. Source: `"determined"`.
- `export_context_append(symbol, content, source="user")` — freetext: user pastes
  LLM response or manual note into session. Source: `"user_supplied"`.

**Back-channel would add:**
- Source: `"back_channel"` — external LLM output parsed and relayed automatically,
  either as tool dispatch (LLM says "run blast_radius on X") or raw text capture.

**Candidate mechanisms (evaluate when relevant):**
1. Sub-agent monitors external LLM tab output and calls append automatically.
2. Browser automation (claude-in-chrome) reads response text, extracts tool requests.
3. External LLM has a plugin/API that can call back to a local endpoint.

**Gate:** first evaluate whether the external LLM session can be observed at all
(browser MCP read access to the LLM tab). If yes, option 2 is likely cheapest.
If not, option 1 requires the external LLM to emit structured output.

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

**Status: all four ingested and probed 2026-07-28. RM67 probe table updated 2026-08-02.**

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
  **Static tier DONE 2026-08-04:** `find_pure_functions` (prior), `find_stable_layouts`,
  `find_dead_event_handlers` — all three shipped, registered in TOOL_REGISTRY, Workbench tiles added.
- **Profile-grounded:** hot-path dominance, repeated recomputation on hot edges.
  Requires instrumentation hook (cProfile injection) producing `call_samples` table.
  Static tier ships first.

**Fit:** `DBOracle` stays structural. `OptimizationOracle` wraps same DB + optional
profiling DB. Corpus-agnostic — normalization maps any profiler output to existing FQDNs.

**Prerequisite:** analysis/code-generation arc complete. Static purity sub-tier
could ship earlier as a standalone tool.

**Estimated effort:** static tier ~1 session; profile-grounded tier ~2-3 sessions.

---

## RM76 — Decision ledger for target projects (IMPLEMENTED 2026-07-31, analyst wire-in 2026-08-01)

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

- [x] `target_lang` param in `project_stub` — auto-detect from file ext; explicit override via `lang` arg (2026-08-03)
- [x] `runtime_locator.py` shim — check_snippet() / check_projection(); Python via ast.parse always; C/Zig/Lua via tool when on PATH else ok=None (2026-08-03)
- [x] Corpus chain UI — `survey_corpus_chain()` + `format_corpus_chain()` in graph_utils; Workbench "Cross-Corpus" tool, oracle-independent; 22 corpora surveyed, grouped by language family (2026-08-03)
