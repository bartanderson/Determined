Written at commit: 3b9c0d2

# SESSION STATE — session 238

## Active branch: main

## What happened this session

**Code-only session. Doc-only commits from prior session (237) are HEAD.**

**Idea 7 gate cleared [V]:**
- Qwen3-VL-8B-Instruct-Q4_K_M.gguf confirmed on machine (5GB, 2026-07-22)
- `determined/agent/context_compactor.py` written and manually tested
- OCR quality: 5/6 key terms at font size 14; `<transcript>` extraction working
- Vision server on port 8082; LLM server on 8081 (no conflict)
- TRACKER Idea 7 gate updated to CLEARED [V]
- HISTORY.md: two entries added (Instruct vs Thinking bug, font size rule) [V]

**context_compactor.py state [V — file read this session]:**
- File: `determined/agent/context_compactor.py` (untracked — not committed yet)
- Public API: `compress_context(text, threshold=6000)`, `render_to_png()`, `is_available()`
- Constants: CANVAS_W/H = 1568, FONT_SIZE = 14, COMPRESS_THRESHOLD = 6000, VISION_MAX_TOKENS = 8192
- VISION_BASE_URL = "http://localhost:8082"
- Uses `<transcript>...</transcript>` tag extraction; falls back to stripping `<think>` blocks

**Server start command (from file header) [V]:**
```
C:\Users\bartl\models\llama-server\llama-server.exe -m "C:\hf_cache\hub\models--Qwen--Qwen3-VL-8B-Instruct-GGUF\snapshots\f982a07559d4a2f6c8744d840bf6fccab30eea96\Qwen3VL-8B-Instruct-Q4_K_M.gguf" --mmproj "C:\hf_cache\hub\models--Qwen--Qwen3-VL-8B-Thinking-GGUF\snapshots\bca5838231f8cc1303cf8810afffcfbdc41bc75a\mmproj-Qwen3VL-8B-Thinking-Q8_0.gguf" --port 8082 --image-min-tokens 1024 --jinja
```
Note: mmproj lives in Thinking model dir -- cross-model compatible, this is correct.

---

## NEXT SESSION -- start here

**First action: commit context_compactor.py and write its tests.**

1. `git add determined/agent/context_compactor.py` and commit
2. Write `tests/regression/test_context_compactor.py` -- server-offline tests only:
   - `render_to_png()` returns valid PNG bytes
   - `is_available()` returns False when port 8082 not running
   - `compress_context()` returns None when text under threshold
   - `compress_context()` returns None when server unavailable
   - `<transcript>` extraction regex on known response strings
   - `<think>` block stripping fallback
   No live-server tests in the regression suite.
3. Add `context_compactor` to `docs/TEST_MAP.md`
4. Run `tests/regression/test_context_compactor.py` alone, then confirm full suite

**After tests pass:** decide whether to wire context_compactor into
`development_priorities` or `walk_call_chain` as the first real use.

**Design question: RM71 vs RM69.** Still the active arc question from s237.
- RM71 (FSM ingestor) -> RM69 (corpus aggregation) -> C/Zig/Lua walkers
- Quick win anytime: `knowledge_for_file(path)` (TRACKER Idea 5) -- ~30 lines SQL, no gate

---

## Known issues [V = verified, ? = carried]

**dead artifact LIKE over-match [V prior]:** `WHERE kind='dead' AND subject LIKE '%{name}'`
over-matches when name is a suffix of another symbol. Fix if noisy in real corpora.

**load_db auto-orient blocks screenshot [V prior]:** background LLM thread on corpus load
causes screenshot tool to hang. Workaround: DOM reads via javascript_tool.

**Corpus switch UI flow [V prior]:** emit `socket.emit("load_db", {path: <abs db path>})`
to load directly. Double-emitting `ingest` causes "database is locked."

**walk_call_chain blind for async Rust [V prior]:** tokio::spawn entry points return 0 nodes.
Documented in RM67 slater row. No fix planned until Rust walker arc.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Server start command [V prior]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.
