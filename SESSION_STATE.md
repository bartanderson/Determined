Written at commit: deefae9 (2026-07-22)

# SESSION STATE — session 237

## Active branch: main [V]

## What happened this session

**Doc-only session. No code changed, no tests needed.** Three commits, all TRACKER/STATE docs.

**Ideas 6, 7, 8 added to TRACKER knowledge layer section (5506a4e, eb7d28a) [V]:**
- Idea 6 — token-budget-at-write-time: count tokens at `_store_knowledge_artifact`,
  reject over threshold, emit workflow_item for summarization. Gate: RM69.
  Cross-validated: omp ships this as 40-LOC Rust native module (pi-natives tokens crate).
- Idea 7 — snapcompact-style PNG context compression: render accumulated LLM context to
  pixel-font PNG (1568×1568 = ~40K chars = 3,279 image tokens vs ~10K text tokens).
  F1 benchmark: 0.88 PNG vs 0.90 raw text vs ~0 prose summary. Gate: verify Qwen3-8B
  vision support. Point of use shifted to front — applicable to any long LLM call chain now.
- Idea 8 — mnemopi as RM69 prior art: omp's production knowledge layer (SQLite + embeddings
  + graph). API: retain/recall/reflect/memory_edit. Scope: hierarchical (global/project/tagged).
  Read source before designing RM69. Gate: RM71 active.

**Slater ingested and probed (deefae9) [V]:**
- DB: `C_Users_bartl_dev_corpora_slater.db` at `C:\Users\bartl\dev\Determined\` (12MB)
- Source: `C:\Users\bartl\dev\corpora\slater`
- 195 files, 121 hot, 0 stubs, 78 duplicate names

Six-probe results:
- list_entry_points: 1985 inferred, 0 explicit — all tests/benchmarks, correct for library crate
- list_stubs: 0 — complete server software, as expected
- list_features: `crates` (4627 syms, 87% doc) and `perf` (58 syms, 81% doc) at depth=1;
  depth=2 needed to see subsystems (bolt, storage, vector, acl)
- development_priorities: crates 87% done, perf 81%; 0 stubs both; 730 doc gaps in crates
- walk_call_chain: **blind across async boundary** — serve_with_listener returns 0 nodes;
  BoltClient::run_pull / run_stream are the reachable Bolt client symbols
- blast_radius: ShardInner::evict_to_budget — 5 direct callers, 593 extended; WARM rating;
  block cache is foundational to entire codebase

Rust walker edge cases resolved:
- #[cfg(test)] → no false stubs [V]
- 78 dup names → normal module aliasing (blockcache:: vs decodedblockcache::) [V]
- impl Trait for Type → BoltClient::* stored on concrete type, appears correct [V]
- async boundary → walk_call_chain returns 0 nodes for async entry points [V NEW GAP]

---

## NEXT SESSION — start here

**Design question: RM71 vs RM69.** Read both TRACKER sections before deciding.
- RM71 (FSM ingestor) is the prerequisite for RM69
- RM69 is the prerequisite for C/Zig/Lua walkers and the full corpus chain
- No new corpus can be added until RM71 ships

**Quick win available any session:** `knowledge_for_file(path)` (TRACKER Knowledge layer
Idea 5) — ~30 lines SQL, no gate, no dependencies. Inverse of describe_file.

**Qwen vision check:** verify whether a quantized Qwen2.5-VL (7B or 3B) fits on Bart's
machine via Ollama. If yes, Idea 7 (snapcompact) moves from "verify first" to "build now."
Run: `ollama list` and check `qwen2.5vl:7b` or `qwen2.5vl:3b` availability.

---

## Known issues [V = verified, ? = carried]

**dead artifact LIKE over-match [V prior]:** `WHERE kind='dead' AND subject LIKE '%{name}'`
over-matches when name is a suffix of another symbol. Fix if noisy.

**load_db auto-orient blocks screenshot [V prior]:** background LLM thread on corpus load
causes screenshot tool to hang. Workaround: DOM reads via javascript_tool.

**Corpus switch UI flow [V this session]:** emit `socket.emit("load_db", {path: <abs db path>})`
to load directly. Double-emitting `ingest` causes "database is locked" — first ingest
completes but second races it. Emit once, wait for response. "Switch corpus" button
coordinates in browser may not register — use socket.emit directly.

**walk_call_chain blind for async Rust [V this session]:** serve_with_listener and any
tokio::spawn entry point returns 0 nodes. Walker does not trace async dispatch edges.
Documented in RM67 slater row. No fix planned until Rust walker arc.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Server start command [V prior]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

**matmul C source URL [?]:** TRACKER notes "Google Translate mirror — verify original."
Not re-verified. Check before cloning.
