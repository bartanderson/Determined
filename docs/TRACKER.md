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
| Determined (Python) | Full convergence | probe DONE (2026-07-21); adversarial re-run DONE — 3 stubs clean, 0 false positives |
| dj2 (Python+JS) | Full convergence | probe 2026-07-25: 248 inferred EPs (down from 331, good movement); 12 FSM stubs (real work queue); 5 subrace stubs (delete when dj2 coding starts); 3 test mocks (accepted); 5 real gaps; phases.py 39 abstract methods = real ABC, unwired not abandoned — future implementation target; world/ 100% unresolved (accepted ceiling) |
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

## RM70 — Stub solution synthesis (ACTIVE DESIGN)

Enhance `sketch_stub` from typed-placeholder generator to corpus-grounded
solution candidate generator. Full design: `docs/RM70_DESIGN.md`.

**Problem:** current brief gives the LLM caller names + docstrings. Not enough
for anything beyond `return {}`. The model's capacity exceeds what the brief
lets it reach.

**Solution:** four-stage pipeline — retrieve → generate → verify → refine.

**Stage 1 — Retrieval (deterministic):**
- Full caller bodies (not docstrings) — shows how return value is used
- Return-shape inference via AST walk — STRONG/WEAK/NONE confidence; WEAK shown as "(uncertain)"
- Pattern sibling search: name-normalized Levenshtein corpus-wide (primary) + SetFit tiebreaker (secondary only)
- Referenced type definitions: named classes → their public methods (what the body may call)

**Stage 2 — Generation:** completion-mode prompt with full retrieval context.
Default: 1 sample (quick, interactive). `mode=thorough`: K=3 samples, ranked.

**Stage 3 — Verification (deterministic scoring):**
- V1: `ast.parse()` — hard gate
- V2: corpus call check — fraction of called names in DB; primary quality signal (weight 0.6)
- V3: return type compatibility — AST walk; soft signal (weight 0.2)
- V4: pattern similarity to best sibling — tiebreaker only, never a rejection criterion (weight 0.2)

**Stage 4 — Iterative refinement:** lowest-scoring V2 signal → specific constraint
("you called X — not in corpus; available: Y, Z") → retry. 3-iteration ceiling.
Visible in output if ceiling hit. Not MCTS — honest name: feedback-guided retry.

**Build order** (each step shippable independently):
1. V1+V2 baseline (measure current sketch_stub quality first)
2. Caller body reader
3. Pattern sibling search (corpus-scoped)
4. Return-shape inference
5. Type definition pull
6. V3+V4 scoring
7. Multi-sample + feedback loop

**Gate:** start with step 1 next session. Each step measured against baseline.

---

## RM72 — Determined graph explorer (desktop, WebGPU/C++) (FUTURE)

Standalone native desktop tool for visually navigating corpus call graphs. Reads
directly from corpus SQLite DB. Not a UI replacement — a large-graph companion.

**Core capabilities:** force-directed layout at corpus scale, smooth zoom/pan,
click to expand callers/callees, highlight call chains, blast radius visualization,
open any corpus .db file directly.

**Tech:** C++ desktop app, WebGPU via Dawn. LearnWebGPU is the reference tutorial
and also a natural C++ walker validation corpus for Determined once RM72 is active.

**Gate:** UI redesign (UI_REDESIGN.md) complete; C++ walker exists (done); Bart
explicitly opens a RM72 session. C++ walker and RM72 are mutually motivating —
LearnWebGPU validates the walker; the walker lets Determined analyze RM72's own code.

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

## Cross-language — remaining tasks

Walkers all done (C, C++, Zig, Lua, Rust). See DESIGN.md for rationale and design.

- [ ] `target_lang` param in `project_stub` — multi-language emission routing
- [ ] `runtime_locator.py` shim — snippet compilation/verification for Zig/Lua/C
- [ ] Corpus chain UI — surface shape comparison across language family in browser
