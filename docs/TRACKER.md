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

## RM67 — Convergence protocol (COMPLETE — maintenance mode)

Determined is done. RM67 is the standing regression check: when running
Determined against dj2 or any other corpus, if the tool gets something wrong,
fix it here. No scheduled development. Fix regressions when they appear.

### Language scope

| Corpus | Target | Status |
|--------|--------|--------|
| Determined (Python) | Full convergence | probe 2026-08-05 (fresh re-ingest): 1 real stub (suggest_tags, known accepted), 9 test mocks, 0 false positives; ABC gaps: clean; 95.4% unresolved edges (external-lib ceiling, accepted); 587 EPs in determined/ (0 stubs); all 3 convergence criteria met |
| dj2 (Python+JS) | Full convergence | probe 2026-08-06: 25 stubs — 12 FSM (accepted), 3 test (accepted), 5 subrace/RM68 delete candidates, 5 production gaps (_get_combat_context, _get_encounter_context, on_arc_completed, process_consequences, _register_world_tools); all 3 convergence criteria met; EP and CrossEdges now meaningfully distinct columns |
| Commonplace (Python) | Full convergence | 1 stub (suggest_tags); frontier stub, waits for LLM_ENDPOINT design decision |
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
| raylib (C++) | Probe-passes | 13280 symbols / 59435 edges; 3485 stubs = header-only libs + GPU API bindings — accepted ceiling |
| zig-gamedev (Zig) | Probe-passes | 4999 symbols / 20682 edges; 668 stubs after dedup; remaining = C FFI to Dear ImGui — accepted ceiling |
| ebiten (Go) | Probe-passes | 6367 symbols / 45073 edges; 50 stubs = proprietary platform SDK stubs (Nintendo/PS5) — correctly unimplementable |
| batteries (Lua) | Probe-passes | 451 symbols / 706 edges; 0 stubs; clean |

HTML: best-effort. Capture js_event_binding edges; don't model HTML structure.

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

## RM69 -- Corpus age timestamp on every query result (Cook CSF-1)

Cook: a query against a 3-day-old corpus emits the same confidence as one against
a 5-minute-old corpus. Stale-corpus failure is silent and confident -- the most
dangerous failure mode.

**What to do:**
- `assessor/epistemic_policy.py` is the enforcement point.
- Add a `corpus_age_seconds()` helper that reads `MAX(ingested_at)` from `files`
  and computes elapsed time since now.
- Add a configurable staleness threshold (default: 24h); expose it in `project_meta`
  or a config key so corpora with different churn rates can tune it.
- Every query result that exits through `assessor/assessor.py` or `oracle/db_oracle.py`
  should include a one-line staleness note when the threshold is exceeded:
  `[corpus last ingested Xh ago -- results may be stale]`.
- `find_interplay_gaps` and `list_stubs` are the highest-value targets since they
  inform implementation decisions.

**Gate:** Determined session only.

---

## RM70 -- Wire pipeline_dependency_tracer into diff pipeline (Cook CSF-2)

Cook: a diff that reports "function A changed" and "function B changed" separately
may not surface that A and B together break an invariant that neither breaks alone.
Compound failures require cross-file awareness.

**What to do:**
- Locate `engine/pipeline_dependency_tracer.py` and verify it exists and is functional.
- Check whether `engine/engine_snapshot_diff.py` and `engine/structural_parity_diff.py`
  currently call it or just run independently.
- If not wired: after the diff computes changed files, pass them through
  `pipeline_dependency_tracer` to surface files that import from any changed file
  and flag them as "potentially affected even if unchanged."
- The output should be a distinct section: "Potentially affected by these changes"
  separate from "directly changed."

**Gate:** Determined session only. Verify pipeline_dependency_tracer.py exists before
planning implementation.

---

## RM71 -- epistemic_policy.py as mandatory query gate (Cook CSF-4)

Cook: "providing calibrated views of the hazards" requires the epistemic policy to
run on every query response, not just on queries that explicitly ask for it.

**What to do:**
- Read `assessor/epistemic_policy.py` (183L) to understand what it currently checks.
- Audit `assessor/assessor.py` and `oracle/db_oracle.py` call sites: does every
  response path pass through epistemic_policy?
- If not: add a wrapper or decorator so every outbound result gets a confidence check.
- A low-confidence result should include the reason inline, not suppress it.
- Do NOT make this a hard gate that blocks results -- callers must still get an answer,
  just a qualified one.

**Gate:** Determined session only.

---

## RM72 -- Mark agent_tools.py as high-blast-radius in responsibility_map (Cook CSF-5)

Cook: one component that accounts for the majority of system behavior is a hazard --
its failure modes are hardest to see and its changes have the broadest blast radius.
`agent_tools.py` at 12,705 lines is 5x the next-largest module.

**What to do:**
- Read `engine/responsibility_map.py` to understand how modules are currently classified.
- Add an explicit `HIGH_BLAST_RADIUS` marking for `agent_tools.py` (and any other
  module above a size/centrality threshold -- check by fan-in from the corpus).
- Surface this marking in `analyze_corpus` output so it appears whenever someone
  is about to reason about a change to that file.
- Standing rule: any change to `agent_tools.py` triggers full regression
  (`tools/run_regression.py`), not just targeted tests.

**Gate:** Determined session only.

---

## RM73 -- Grow or explicitly scope the observability layer (Cook CSF-6)

Cook: "people continuously create safety." The observability layer IS the mechanism
by which safety is created at runtime. At ~135 lines (fault_injector.py 26L,
signals.py 20L, instruments.py 89L) covering a 369-file system, it monitors a
small fraction of potential failure modes.

**What to do (choose one or both):**
- Option A (grow): add monitors for the major failure paths not currently covered:
  ingest failure, corpus returning empty on a non-empty corpus, query returning
  no results when results are expected, staleness (overlaps RM69).
- Option B (scope explicitly): document in `observability/README.md` or a docstring
  which failure modes ARE monitored, which are NOT, and why. An explicitly scoped
  monitor is safer than an implicitly incomplete one -- the gap is visible.
- At minimum, do Option B first. Option A is follow-on work.

**Gate:** Determined session only.
