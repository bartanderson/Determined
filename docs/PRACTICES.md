# Determined -- Engineering Practices

## BE A GOOD ENGINEER

1. **Read before you write.** Before writing any function, query, or module - search for what already exists that does the same thing. If it exists, use it.
2. **Use the authoritative implementation.** If a function exists that does X correctly, call it. Don't write a new version of X that bypasses it.
3. **Don't duplicate logic.** Two places that do the same thing will diverge. One will be wrong. Find it before it hurts you.
4. **Test what you ship.** If you can't verify it works, you don't know it works.
5. **Handle failures at the boundary.** Anything that can fail - network, file, model, DB - gets a try/except at the call site.
6. **One thing owns each concern.** If two places both decide the same question, one of them is wrong.
7. **Don't leave broken windows.** Placeholder code, dead paths, and TODOs without owners become permanent. Gate them or delete them.
8. **Understand before you change.** If you don't know why code is the way it is, find out before touching it.
9. **Confidence is not a substitute for verification.** Feeling capable of doing something is not the same as knowing the right way to do it in this codebase. Stop and check first.

## PRE-CODE CHECKLIST (Determined-specific)
Before writing any code that queries, transforms, or computes data in Determined:
1. Grep for it in `determined/agent/graph_utils.py` and `determined/agent/agent_tools.py`
2. If it exists, use it
3. If it doesn't exist, state what you searched for and didn't find before writing

## DO THIS (specific to this system)

1. **Ground truth in queryable structure.** Every fact the system reports must trace to a DB row or AST node. If it can't be queried, it can't be trusted.
2. **Make assumptions falsifiable before building on them.** Run the minimum against real data and get a pass/fail. Don't build a second layer on an untested first layer.
3. **Lock constraints before adding flexibility.** Determinism first. Expressiveness second. Every time flexibility came first, something regressed.
4. **Design closed-world constraints into features.** Enumerate what's legal. Reject what isn't. Scope creep enters through undefined edges.
5. **One authority per layer, enforced structurally.** Ingestion creates. Routing decides. Classification labels. Persistence stores. Never backwards, never shared.
6. **Design for partial failure.** If one component can't answer, the rest should still fire. A gap in one dimension shouldn't crash the whole response.
7. **Publish schema in one place.** The compiler reads it, the executor validates against it, the UI renders from it. One source, multiple consumers.
8. **Invalidate derived state when source changes.** Hash the source, check the hash. Time-based expiry assumes the source didn't change.

## IMPROVEMENT METHODOLOGY -- How to grow the tool's capability

The goal is a tool with the analytical power of a large LLM but the bones of a
deterministic, auditable analyzer. The way you get there:

**Step 1 -- Run it on real code and watch what it misses.**
Don't invent hypothetical gaps. Ingest a real corpus, ask real questions, and
observe where the answers are wrong, shallow, or absent. Every gap found this
way is a real gap. Every gap invented is a distraction.

**Step 2 -- Classify the gap by layer.**
Before deciding how to fill a gap, identify which layer owns it:

- **Deterministic** -- the answer is structurally derivable from AST, call
  graph, schema, or DB state. If the gap is here, write the query or
  traversal. This is always the first choice: zero hallucination risk,
  fully testable, cheap to run.
- **Semantic** -- the answer requires understanding meaning across symbols,
  names, or patterns (e.g. "what role does this module play?", "are these
  two functions doing the same thing?"). Use embeddings and similarity here.
  Still local, still verifiable, but probabilistic -- always back it with
  a deterministic check where possible.
- **Narrative** -- the answer requires synthesizing a human-readable
  explanation, surfacing judgment, or bridging gaps the first two layers
  can't close. This is where llama-server comes in: a thin layer on top of
  solid structure. It reports, it does not decide. It narrates what the
  deterministic and semantic layers already know.

**Step 3 -- Fix in the right layer.**
Never fill a deterministic gap with narrative. Never use the LLM to answer
a question the DB can answer. The narrative layer's job is to make
structural facts readable -- not to substitute for them when they're missing.

**Step 4 -- Report gaps to Bart before building.**
When a gap is found, surface it: what the tool produced, what the right
answer is, which layer owns the fix, and a proposed approach. Bart decides
priority. This keeps scope from expanding silently and ensures every addition
solves a real observed problem.

## LANGUAGE ROUTING -- Which path handles which language

**Rule: update this table any time a new feature lands in any path.**
If a feature exists for one language but not another, that is a known gap — note it here.

### Ingest entry points

| Corpus type | Entry point | When to use |
|-------------|-------------|-------------|
| Python-only or Python+JS/TS/Go/Rust | `determined/engine/run_engine.py` (EngineRunner) | Normal ingestion via UI or CLI (`python -m determined.engine.run_engine <path>`) |
| Go/Rust/JS/TS only (no Python) | `tools/ingest_lang_corpus.py` | Non-Python corpora where EngineRunner would crash (requires ≥1 Python file) |

### File discovery

| Language | Discovery function | Key filters |
|----------|--------------------|-------------|
| Python | `scan_project_files.discover_python_files` | Skips `site-packages`, `__pycache__`, `.venv`, `Lib`; respects `.determinedignore` |
| JS/TS/Go/Rust | `scan_project_files.discover_js_ts_files` | Extensions: `.js .ts .jsx .tsx .mjs .cjs .go .rs`; skips `node_modules`, `dist`, `build`, `.venv`, `*.min.js/ts` |

### Symbol extraction

| Language | Extractor | Docstrings | Typed params |
|----------|-----------|------------|--------------|
| Python | `parse_ast.py` | Yes (triple-quoted) | Yes (annotations) |
| JS/TS | `LanguageWalker._js_symbols()` | Yes (JSDoc `/** */` above decl) | TS only (type annotations) |
| Go | `LanguageWalker._go_symbols()` | Yes (`//` lines above func) | Yes (receiver + param types) |
| Rust | `LanguageWalker._rust_symbols()` | Yes (`///` lines above fn) | Yes (param types) |

### Call-edge extraction

| Language | Extractor | Builtins filter | Resolved flag |
|----------|-----------|-----------------|---------------|
| Python | `parse_ast.py` symbol_references | `_PY_BUILTINS` (frozenset of `dir(builtins)`) | Yes (global symbol lookup) |
| JS/TS | `LanguageWalker._shared_call_edges` via JS LangSpec | `_JS_BUILTINS` | Yes (`compute_resolved=True`) |
| Go | `LanguageWalker._shared_call_edges` via Go LangSpec | `_GO_BUILTINS` | No |
| Rust | `LanguageWalker._shared_call_edges` via Rust LangSpec | `_RUST_BUILTINS` | No (:: resolution post-pass in `persistence_engine`) |

### Data-flow edge extraction

All data_flow edges land in `graph_edges` with `edge_type='data_flow'`. There is no separate table.

| Language | Extractor | Provenance tags |
|----------|-----------|-----------------|
| Python | `parse_ast.py` (4 levels: arg, var, for_iter, var_kwarg) | `data_flow_arg`, `data_flow_var`, `data_flow_for_iter`, `data_flow_var_kwarg` |
| JS/TS | `LanguageWalker._js_data_flow()` | `data_flow_arg`, `data_flow_var`, `data_flow_for_iter`, `data_flow_var_kwarg` |
| Go | `LanguageWalker._go_data_flow()` | same tags |
| Rust | `LanguageWalker._rust_data_flow()` | same tags |

### Dispatch post-passes (run after per-file walk)

| Language | Pass | What it adds |
|----------|------|--------------|
| Go | `_go_interface_dispatch_pass` | Synthetic edges: interface method → concrete implementors |
| Rust | `_rust_trait_dispatch_pass` | Synthetic edges: trait method → `impl Trait for Type` implementors |
| Python | `_persist_cross_boundary_edges` | HTTP fetch + socketio cross-language edges (RM57) |
| JS/TS | `run_cross_language_link` (RM57) | `cross_language` edges: JS fetch → Python Flask route, JS socket.emit → Python @socketio.on |

### Persist path per language

| Language | Persist function | Tables written |
|----------|------------------|----------------|
| Python | `persist_file_analysis` → `_persist_graph_edges` | `files`, `functions`, `classes`, `imports`, `symbol_references`, `graph_edges` (static + data_flow) |
| JS/TS/Go/Rust | `_persist_js_ts_files` | `files`, `functions`, `graph_edges` (static + data_flow + dispatch) |

### Adding a new language

1. Add extension → language string mapping in `detect_language()` (`language_walker.py`)
2. Add the extension to `_JS_TS_EXTENSIONS` in `scan_project_files.py`
3. Implement `_<lang>_symbols()`, `_<lang>_callee_name()`, `_<lang>_fn_ranges()`, `_<lang>_data_flow()` in `LanguageWalker`
4. Register a `LangSpec` in `_lang_spec()` — the shared walk loop handles the rest
5. Add a builtins frozenset `_<LANG>_BUILTINS`
6. Update this table

**The invariant:**
A small, deterministic, well-tested analyzer augmented by a thin semantic
and narrative layer will outperform a large LLM on this domain -- because
the structure is always true, the LLM is sometimes wrong, and the combination
lets you know which is which.

## DON'T DO THIS (anti-patterns earned the hard way)

1. **Don't let guesses become infrastructure.** An assumption that works once and never gets validated will eventually be load-bearing and wrong.
2. **Don't trust pattern matching for identity.** Substring and keyword matching feels cheap and clever. It produces false positives at scale and is hard to audit.
3. **Don't mix identity domains in one path.** Builtins, project symbols, and external calls are different things. Route them before classifying them.
4. **Don't design fallbacks without wrapping the primary.** A fallback that only catches ImportError while the actual call sits outside try/except is not a fallback.
5. **Don't ask a component to do what it reliably fails at.** If a model or layer can't reliably do X, redesign around what it actually does rather than forcing it.
6. **Don't make persistence boundaries ambiguous.** Know exactly what lives in which DB, why, and what happens to it when the corpus is rebuilt.
7. **Don't close a gap without a test that proves it stays closed.** A fix without a regression test is a patch. It will reopen.
8. **Don't omit the why from design decisions.** Future sessions will face the same temptations. The reasoning is what stops them from making the same mistake.
