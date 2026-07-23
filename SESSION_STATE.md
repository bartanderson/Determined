Written at commit: df8c585

# SESSION STATE — session 245

## Active branch: main [V]

## What happened this session

**Four commits landed:**

### Commit 3a57b6b — G7 slowness fix [V]
- `test_local_agent.py`: `test_answer_history_grows_across_questions` was taking
  ~90s because "how does it connect?" matched a named pattern and routed to
  `PatternExecutor.run()`, which has its own `_call_ollama` import not covered by
  the local_agent patch. Added `patch("determined.agent.local_agent.detect_pattern",
  return_value=(None, None))` to keep the test focused on history accumulation.
- G7 group: 3:42 → 9s [V]

### Commit 2d38c0c — kernel_launch edge_type fix [V]
- `language_walker.py`: `_cuda_kernel_launches()` was storing `edge_type="static"`
  instead of `"kernel_launch"` — fixed to `"kernel_launch"`.
- `persistence_engine.py`: cross-file resolution post-pass was gated to
  `edge_type = 'static'` — changed to `IN ('static', 'kernel_launch')` so kernel
  callee FQNs get upgraded alongside static edges.
- `test_language_walker_persist.py`: test updated to query `kernel_launch` instead
  of `static` for kernel launch edge assertion.
- 106 walker tests pass [V]

### Commit 0c457f1 — walk_call_chain bare-name fallback for C/CUDA [V]
- `agent_tools.py`: `walk_call_chain` with bare name (e.g. "gpt2_forward") was
  returning empty for C/CUDA corpora because the DB stores names as FQNs
  (`train_gpt2::gpt2_forward`). Added `LIKE '%::' || ?` fallback after the
  existing `.` suffix match for JS/TS. Bare names now resolve correctly. [V]
- 79/80 agent_tools tests pass (pre-existing `test_tool_registry_covers_all_tools`
  failure is unrelated to this change) [V]

### Commit 3204437 — llm.c six-probe DONE [V]

**llm.c six-probe findings:**
- 72 files: 20 .c/.h, 38 .cu/.cuh, 14 .py
- 729 symbols, 2960 edges, 148 `__global__` kernels (is_tool=1)
- 151 kernel_launch edges (correct after fix; were 0 before)
- 22 stubs: classification —
  - 8 CUDA false-positives: `block_dim`, `grid_dim`, `blockDim`, `gridDim`
    (dim3 variables captured as function stubs — known C walker limitation)
  - 2 CUDA utility false-positives: `Packed128`, `cast_value` (template stubs)
  - 2 external API stubs: `memcpy` (stdlib), `nvtxRangePush` (NVIDIA profiling)
  - 4 cuDNN conditional-compile stubs: `cudnn_att::*` — only built with
    `-DUSE_CUDNN`; acceptable known ceiling
  - 2 device_file_io stubs: `cmp`, `random_data` — may be real gaps
  - 4 `make_random_float` variants — test utility functions, acceptable
- Python (14 files): separate PyTorch implementations of the C training loop.
  NOT ctypes wrappers. 0 ctypes edges (correct). No cross-language connection.
- Blast radius: `gpt2_build_from_checkpoint` → 131 extended symbols (correct)
- Call chain: `gpt2_forward` traces to encoder→layernorm→matmul→attention→
  residual→gelu→softmax→crossentropy (correct GPT-2 forward pass) [V]

---

## Known issues [V = verified, ? = carried]

**Pre-existing: knowledge_for_file missing from REGISTRY [V]** — `test_tool_registry_covers_all_tools`
fails. Not caused by this session's changes. All other tests pass.

**CUDA stubs: dim3 vars captured as stubs [V]** — `block_dim`, `grid_dim`, `blockDim`,
`gridDim` appear as function stubs in CUDA files. Low-priority false-positive;
acceptable known ceiling.

**dead artifact LIKE over-match [V prior]:** documented in test, fix if noisy.

**load_db auto-orient blocks screenshot [V prior]:** workaround: DOM reads via javascript_tool.

**walk_call_chain broken for TS/JS corpora [?]:** The `.` suffix match handles some cases
but may have edge cases. C/CUDA :: suffix match is now fixed. Workaround: use graph_path.

**C walker: 9 unmatched header stubs in brogue-ce [V prior]** — platform-conditional.
Acceptable ceiling.

---

## NEXT SESSION — start here

**Option 1: Zig walker (mach engine corpus)** [recommended]
Next NOT YET INGESTED language in RM67 language scope table.
Zig has ast-grep support. Same LanguageWalker extension pattern as Go/Rust.
Find Zig corpus (Mach Engine: github.com/hexops/mach).
Target file: `determined/ingestion/language_walker.py`.

**Option 2: Lua walker (clx corpus)**
Same pattern. `clx` is the Lua corpus in the language scope table.

**Option 3: llm.c stub deeper triage**
22 stubs identified; `device_file_io::cmp` and `device_file_io::random_data`
may be real gaps worth classifying. Low priority.

**Verify G7 is still fast (sanity check before any work):**
```
.venv\Scripts\python.exe tools/run_regression.py --group G7
```
Expected: < 15s.

**Verify walk_call_chain fix works after re-ingest:**
```
.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.')
from determined.oracle.db_oracle import DBOracle
from determined.agent.agent_tools import walk_call_chain
oracle = DBOracle('C_Users_bartl_dev_corpora_llm_c.db')
chain = walk_call_chain('gpt2_forward', oracle, max_depth=1)
print(chain[0]['symbol'] if chain else 'BROKEN')
"
```
Expected: `train_gpt2::gpt2_forward`
