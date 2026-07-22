Written at commit: aa6ec6c (2026-07-22)

# SESSION STATE — session 236

## Active branch: main [V]

## What happened this session

**Doc-only session. No code changed, no tests needed.** Four commits, all TRACKER/STATE docs.

**Session start revealed a stale handoff [V]:**
Session 235 addendum said "cross-language ingestion is next" — wrong. TRACKER RM67 shows
all 8 original corpora probe DONE as of 2026-07-18. The stale framing confused ingest
(done) with new walkers (not built yet, gated). Corrected in this session.

**Slater integration arc documented (aadc2f5) [V]:**
Reviewed https://github.com/Hikari-Systems/slater — Rust graph DB, Bolt protocol, written
with Claude Code. Six ideas in TRACKER with explicit gates:
1. Slater as Rust corpus — READY NOW, no gate (first action next session)
2. Build/serve split → corpus generation model — apply at RM69 design
3. Vector+graph colocation — design principle for RM69
4. Cypher/Bolt migration — full node/edge schema + parallel-test gate in TRACKER
5. Scale path — tripwire: >5s on 100K-edge corpus = migrate, don't optimize SQLite
6. MCTS over Bolt — Cypher queries pre-written for when MCTS arc starts

**Four missing corpus slots named (a0092b3) [V]:**
Corpus chain is now fully named: dj2 (Python) → clx (Lua) → Mach Engine (Zig) → Brogue CE (C)

| Corpus | URL | Fills |
|--------|-----|-------|
| Brogue CE | github.com/tmewett/BrogueCE | Behavioral C (roguelike); matmul fills compute slot only |
| llm.c | github.com/karpathy/llm.c | ML trainer + Python→C ctypes boundary (two slots, one corpus) |
| Mach Engine | github.com/hexops/mach | Zig game engine, game domain synergy |
| clx | github.com/samyeyo/clx | First Lua ingest, dj2 emission target |

Clone paths, expected stub profiles, and walker prerequisites in TRACKER corpora-to-acquire.

**CodeAlmanac knowledge layer ideas documented (aa6ec6c) [V]:**
Reviewed https://github.com/AlmanacCode/codealmanac. Five ideas in TRACKER:
1. Transcript → knowledge_artifacts: scan Claude Code .jsonl session files, extract
   decisions/constraints/gotchas, store as design_notes. Gate: RM69.
   Transcript location: `%APPDATA%\Claude\projects\<project-id>\*.jsonl`
2. Garden pass: `garden_corpus` tool — docstring_health + detect_doc_drift + gap_analysis
   in sequence, dedup against existing workflow_items, queue new ones. No gate.
3. Upstream source: point ingest_design_docs at almanac/ if CodeAlmanac runs on same repo.
   Zero new code — same pattern as SOTS ingest.
4. Citation gate: LLM-generated artifacts must cite a source file/line before storage.
   Apply at RM69 design time. Gate: RM69.
5. knowledge_for_file(path): inverse of describe_file — what does the knowledge layer know
   about this file? ~30 lines SQL. No gate, can be added any time.

---

## NEXT SESSION — start here

**One ungated action: clone and ingest slater (Rust walker exists, no prerequisite).**

```
git clone https://github.com/Hikari-Systems/slater C:\Users\bartl\dev\corpora\slater
```

Load via UI corpus switcher (absolute path). Run RM67 six-probe loop:
- list_entry_points — expect Bolt handler traits, build CLI entry points
- list_stubs — expect 0 or very few (complete server software)
- list_features — expect: bolt_server, slater_build, delta/LSM, vector_search, acl, storage_backends
- development_priorities — Rust walker regression baseline
- walk_call_chain — Bolt handler accept loop
- blast_radius — cache LRU struct

Rust walker edge cases to watch (full list in TRACKER Slater arc Idea 1):
- impl Trait for Type — methods on concrete type, not the trait definition
- #[cfg(feature/test)] — may produce false stubs
- pub use re-exports — may produce duplicate symbols
- Macros (#[derive], tokio::main) — must not be parsed as function bodies

After slater: update RM67 table row. Then the design question is RM71 vs RM69 — read both
TRACKER sections before deciding. RM71 (FSM ingestor) is the prerequisite for RM69; RM69
is the prerequisite for C/Zig/Lua walkers and the full corpus chain.

`knowledge_for_file(path)` (Idea 5 above, ~30 lines SQL) is a quick win that can be added
in any session alongside other work — no gate, no dependencies.

---

## Known issues [V = verified, ? = carried]

**dead artifact LIKE over-match [V prior]:** `WHERE kind='dead' AND subject LIKE '%{name}'`
over-matches when name is a suffix of another symbol. Fix if noisy.

**load_db auto-orient blocks screenshot [V prior]:** background LLM thread on corpus load
causes screenshot tool to hang. Workaround: DOM reads via javascript_tool.

**Corpus switch UI flow [V prior]:** emit `load_db` with absolute .db path to load directly.
"Switch corpus" button only visible when corpus already loaded.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Server start command [V prior]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

**matmul C source URL [?]:** TRACKER notes "Google Translate mirror — verify original."
Not re-verified. Check before cloning.
