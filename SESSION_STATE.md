Written at commit: 96158ae

# SESSION STATE — session 239

## Active branch: main [V]

## What happened this session

**Thin cleanup session.** Session 238 had already committed everything before compaction.

**Discovered at session start [V — git log]:**
- `determined/agent/context_compactor.py` committed in 3b9c0d2 (session 238)
- `tests/regression/test_context_compactor.py` committed in same commit — 14 offline tests
- HISTORY.md already updated (Instruct-vs-Thinking bug, font-size-14 rule)
- TRACKER Idea 7 gate already cleared in 340f941

**Actual new work this session:**
- `docs/TEST_MAP.md` — added `context_compactor.py | test_context_compactor.py` row (was missed in s238) [V]
- `docs/TRACKER.md` — updated Idea 7 "Remaining:" note to "DONE (session 238/239)" [V]
- Memory: `project_llm_services.md` — added vision server section (port 8082, Qwen3-VL-8B-Instruct) [V]

**context_compactor.py status [V]:**
- Committed, 14 tests pass, TEST_MAP wired
- API: `compress_context(text, threshold=6000)`, `render_to_png()`, `is_available()`
- Server: port 8082, `--jinja --image-min-tokens 1024`, Instruct model only
- NOT yet wired into any tool (development_priorities, walk_call_chain, etc.)

---

## NEXT SESSION -- start here

**Decide: wire context_compactor into a tool, or RM71 design, or knowledge_for_file quick win.**

Options ranked by effort:

1. **Quick win** — `knowledge_for_file(path)` (TRACKER Idea 5): ~30 lines SQL, inverse of
   `describe_file`, no gate, no dependencies. One PR. Good warmup.

2. **Wire context_compactor** — pick `development_priorities` or `walk_call_chain` as first
   call site. Look for where text accumulates and hits the 6K threshold. Small change, high
   signal — confirms the end-to-end path works.

3. **RM71 design** — FSM ingestor (prerequisite for RM69). Write the formal TRACKER section
   first, then begin. No code before the design is on paper.

All three are valid. If Bart has a preference, take it; otherwise suggest in that order.

---

## Known issues [V = verified, ? = carried]

**dead artifact LIKE over-match [V prior]:** `WHERE kind='dead' AND subject LIKE '%{name}'`
over-matches when name is a suffix of another symbol. Fix if noisy in real corpora.

**load_db auto-orient blocks screenshot [V prior]:** background LLM thread on corpus load
causes screenshot tool to hang. Workaround: DOM reads via javascript_tool.

**Corpus switch UI flow [V prior]:** emit `socket.emit("load_db", {path: <abs db path>})`
to load directly. Double-emitting ingest causes "database is locked."

**walk_call_chain blind for async Rust [V prior]:** tokio::spawn entry points return 0 nodes.
Documented in RM67 slater row. No fix planned until Rust walker arc.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Server start command [V prior]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.
