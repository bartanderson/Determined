Written at commit: a0092b3 (2026-07-22)

# SESSION STATE — session 236

## Active branch: main [V]

## What happened this session

**Doc-only session. No code changed, no tests needed.**

**Session start revealed a stale handoff [V]:**
The session 235 addendum said "cross-language corpora ingestion is next" but TRACKER RM67
already shows all 8 original corpora as probe DONE (as of 2026-07-18). The addendum was
written confused. Actual state: corpora are ingested and probed; what's missing are the
NEW corpora for languages whose walkers don't exist yet (C, Zig, Lua). The one exception
is slater (Rust) — Rust walker exists, no gate.

**Slater integration arc documented (aadc2f5) [V]:**
Reviewed https://github.com/Hikari-Systems/slater — Rust graph DB, Bolt protocol, disk-native
vector search, written with Claude Code. Six ideas documented in TRACKER with explicit gates:

1. Slater as Rust corpus — READY NOW, no gate. Clone and ingest.
2. Build/serve split = corpus generation model — apply when designing RM69.
3. Vector + graph colocation — design principle for RM69 (embeddings + call edges in one query).
4. Cypher/Bolt migration — full DB schema + parallel-test gate documented; trigger: >5s queries
   or MCTS arc. Node types (:Function/:File/:Module), edge types (:CALLS/:IMPORTS/:CONTAINS/
   :DATA_FLOW/:HTTP_FETCH/:JS_EVENT_BINDING/:FUNCTION_REFERENCE) are written in TRACKER.
5. Scale path — observational tripwire (>5s on 100K-edge corpus = migrate, don't optimize).
6. MCTS over Bolt — Cypher queries pre-written for when MCTS arc starts.

**Four missing corpus slots filled (a0092b3) [V]:**
All four named in TRACKER with repo URLs, clone paths, expected stub profiles, and ingestion gates:

| Corpus | URL | Slot | Gate |
|--------|-----|------|------|
| Brogue CE (C) | github.com/tmewett/BrogueCE | Behavioral C, roguelike domain synergy | C walker |
| llm.c (C+Python) | github.com/karpathy/llm.c | ML trainer + Python→C ctypes boundary | C walker |
| Mach Engine (Zig) | github.com/hexops/mach | Zig game engine, corpus chain | Zig walker |
| clx (Lua) | github.com/samyeyo/clx | First Lua ingest, dj2 emission target | Lua walker |

matmul C corpus remains for "compute shape" walker stress test — explicitly NOT the behavioral
C slot. Brogue CE fills that.

Corpus chain is now fully named [V]:
  dj2 (Python) → clx (Lua) → Mach Engine (Zig) → Brogue CE (C)

RM67 language scope table updated: 13 corpora total, 8 probe DONE, 5 NOT YET INGESTED [V].

---

## NEXT SESSION — start here

**One ungated action: clone and ingest slater.**

```
git clone https://github.com/Hikari-Systems/slater C:\Users\bartl\dev\corpora\slater
```

Then load via UI corpus switcher (absolute path to cloned dir). Run the RM67 six-probe loop:
- list_entry_points — expect Bolt handler traits, build CLI entry points
- list_stubs — expect 0 or very few (complete server software)
- list_features — expect: bolt_server, slater_build, delta/LSM, vector_search, acl, storage_backends
- development_priorities — use as Rust walker regression baseline
- walk_call_chain — on the Bolt handler accept loop
- blast_radius — on the cache LRU struct

Watch for these Rust walker edge cases (documented in TRACKER Slater arc Idea 1):
- impl Trait for Type — methods on concrete type, not trait
- #[cfg(feature/test)] — may produce false stubs
- pub use re-exports — may produce duplicate symbols
- Lifetimes in signatures — must not break param_types_json
- Macros (#[derive], tokio::main) — must not be parsed as function bodies

After slater is probed: update RM67 table row, then decide next arc. The gate chain is:
- RM71 (FSM ingestor) unblocks RM69 (corpus aggregation)
- RM69 unblocks C/Zig/Lua walkers and new language parsers
- C walker unblocks brogue-ce, llm.c, matmul
- Zig walker unblocks mach
- Lua walker unblocks clx

So after slater: the next design question is RM71 vs RM69, not "which walker to build."
Read TRACKER sections for both before deciding — RM71 is the prerequisite so it likely goes first.

---

## Known issues [V = verified this session, ? = carried from prior]

**dead artifact LIKE over-match [V prior]:** `WHERE kind='dead' AND subject LIKE '%{name}'`
over-matches when name is a suffix of another symbol. Documented in test. Fix if noisy.

**load_db auto-orient blocks screenshot [V prior]:** background LLM thread on corpus load
causes screenshot tool to hang. Workaround: DOM reads via javascript_tool.

**Corpus switch UI flow [V prior]:** emit `load_db` with absolute .db path to load directly.
"Switch corpus" button only visible when corpus already loaded.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path. (Not re-verified this session.)

**Server start command [V prior]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

**matmul C source URL [?]:** original TRACKER note says "Google Translate mirror — verify
original." Has not been verified. Check before cloning.
