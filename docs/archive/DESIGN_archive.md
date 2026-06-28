# DESIGN archived sections (2026-06-27)

Sections moved from DESIGN.md during spring cleaning. These are kept for
historical reference, not active design. For the current active design, see
DESIGN.md.

---

## 4. Symbol classification & routing architecture (historical design record - marked stale)

This was originally a 4-iteration execution plan (Symbol Classification
Stabilization Plan.md). As of 2026-06-16, the target files largely exist
under their planned names (graph/symbol_classifier.py,
graph/symbol_router.py, graph/build_dependency_graph.py,
graph/module_resolution.py, ingestion/scan_project_files.py,
ingestion/extract_symbols.py) and most of the plan's intent has landed.
Two things in the original plan are now stale and should not be followed
literally: every "VALIDATION" step said to run
`python tools/analysis/run_analysis_pipeline.py`, which no longer exists
anywhere in the repo (deleted in the loose-script cleanup - see TRACKER.md;
the real entrypoints are `engine/run_engine.py` for ingestion and
`ask.py` for querying); and Iteration 3's target file
`persistence/persist_file_analysis.py` doesn't exist either - persistence
now lives in `persistence/persistence_engine.py`. Treat what follows as the
historical design record of the classifier/router/graph layer, not as
runnable instructions.

### Objective

Stabilize the analysis pipeline by separating symbol ingestion, symbol
normalization, symbol routing, symbol classification, and persistence
responsibilities into a deterministic pipeline with explicit authority
boundaries between stages. Deliberately avoids graph redesign, semantic
inference, or advanced runtime analysis.

### The problem this solved

The system used to mix multiple identity domains into a single classifier
path: static AST identities (`AIBoundary`, `world.map.generate_loot`),
runtime-derived access chains (`self.ai_system`, `ctx.session`,
`generate_structured_data.self.ai_system`), and language/builtin/external
symbols (`any`, `max`, `pathlib.Path`, `flask.jsonify`) - all run through
one comparison system. That caused false `external_unknown`
classifications, inconsistent project classification, debugging opacity,
unstable heuristics, namespace contamination, and persistence ambiguity.

### Target architecture (the part that's still the live mental model)

```
RAW SYMBOL -> NORMALIZATION -> ROUTER -> DOMAIN CLASSIFIER -> PERSISTENCE
```

Each layer has exactly one authority, and is explicitly never responsible
for the others' jobs:

1. **Ingestion authority** - extracts symbols from AST, preserves canonical
   identities, builds the project symbol universe. Never classifies, never
   does runtime inference, never persists, never touches graph semantics.
2. **Normalization authority** - canonical comparison identity, stable key
   extraction (e.g. `ai.ai_boundary.AIBoundary.classify_intent` ->
   `classify_intent`). Never classifies, routes, or persists.
3. **Routing authority** - decides symbol domain only: project / runtime /
   builtin / stdlib / external. Never persists, builds graph, or does
   semantic interpretation. Implemented as `route_symbol()`,
   `is_runtime_symbol()`, `is_builtin_symbol()`, `is_static_project_symbol()`
   in `graph/symbol_router.py`.
4. **Domain classification authority** - classifies only within an
   already-routed domain. Never routes, normalizes, or persists.
5. **Persistence authority** - deterministic storage only (insert rows,
   commit transactions, store already-classified entities). Never
   classifies, routes, normalizes, or does semantic interpretation - no
   project matching, bucket inference, classification heuristics,
   normalization logic, or fallback decisions belong here.

Final expected shape:

```
RAW SYMBOLS -> INGESTION -> NORMALIZATION -> ROUTING
                                                |
                       +------------------------+------------------------+
                       v                        v                        v
                  PROJECT                  RUNTIME                BUILTIN/EXT
                 CLASSIFIER               CLASSIFIER               CLASSIFIER
                       |                        |                        |
                       +------------------------+------------------------+
                                                v
                                          PERSISTENCE
                                                v
                                       DEPENDENCY GRAPH
```

### Success criteria (the bar this was measured against)

Symbol domains separated before classification; project identity
deterministic; runtime traces don't contaminate static analysis;
persistence performs storage only; graph relationships stay reproducible;
debugging localized by layer; each layer has exactly one authority;
classification behavior predictable and explainable.

The original plan broke this into 4 iterations (identity stabilization,
routing layer separation, persistence stabilization, graph consistency
stabilization), each with its own target files, required outcomes, and
non-goals. Per the status note above, that level of detail is now mostly
historical - the files and authority boundaries it specified are in place.
If the authority model above is ever violated by future changes, this
section is the reference for what "violated" means.

---

## 5. Contracts & governance - exploratory notes (superseded)

This section is a condensed version of `contracts  + visibility.md`, kept
for the conceptual framing even though its concrete proposal is moot. The
original read as an AI-assisted brainstorming transcript rather than a
committed plan; its concrete proposal - plugging a "safe evolution
protocol" into `run_analysis_pipeline` and `debug_run.py` - is moot because
both of those files were deleted in the loose-script cleanup (see
TRACKER.md; the pipeline module never existed, debug_run.py only imported
it). The conceptual framing below predates, and was effectively superseded
by, the Truth Kernel / oracle work in section 2 above, which is further
along and already running against real data.

**The observation that mattered:** the codebase already had (and may still
have) 4 overlapping contract systems, not one - a JSON contract registry
(`tool_system_contract.json`, classification boundary rules, CP0-CP1
pipeline rules), Python contract modules
(`semantic_pipeline_contract.py`, `classification_contract.py`,
`contract_validator.py`), embedded inline contracts (LOCKED-comment style
invariants in `evaluation_snapshot.py`/`symbol_classifier.py`/
`semantic_candidate_builder.py`), and structural contracts in the
ingestion/graph layer (`BehavioralContract`,
`_extract_behavioral_contracts`, `FileAnalysis.behavioral_contracts`). The
real problem identified wasn't "we need to design a contract system" - it
already existed, distributed and partially inconsistent - it was "there is
no single arbitration layer deciding which contract is authoritative when
they disagree."

**The 3-layer mental model proposed** (reality layer = the actual codebase;
truth-extraction layer = snapshots/metrics/classifier outputs;
constraint layer = contracts in all their forms) is still a reasonable way
to think about where a future "contract precedence" system would sit, if
one is ever built. It is not currently built, and nothing in section 2's
Truth Kernel design depends on it - the Truth Kernel's STABILITY view reads
real contract violation reports directly rather than going through any
arbitration layer. Worth a skim if this idea is revisited; don't treat any
file/entrypoint name in the original as current.

---

## 9. Developer intelligence interface (vision - 2026-06-21)

### Code-agnostic design (hard constraint)

The tool is corpus-agnostic by design. It has no knowledge of the game,
its domain, or its conventions. It works by ingesting any Python codebase
into a corpus DB and letting the agent query that DB. The game corpus is
the current test subject, but the tool should work identically on Flask,
SQLAlchemy, a medical records system, or anything else.

Consequences:
- Heuristics must be phrased in structural terms (callers, files, symbols,
  findings) not game terms.
- The knowledge.db findings layer is how domain knowledge enters the system -
  a human or prior session stores facts about THIS codebase, and future
  queries draw on them. That is the only domain-specific layer.
- The UI makes no assumptions about what the corpus contains. "Files",
  "symbols", "callers", "findings" are the universal vocabulary.
- When evaluating a new feature, ask: would this work on Flask too?
  If not, it belongs in the knowledge layer, not the tool itself.

### The primary interface

The analysis tool is headed toward becoming a standalone developer
workbench - the primary interface a developer uses to understand,
navigate, and plan work on ANY codebase. Everything built so far
(corpus ingestion, Truth Kernel, conversational agent, knowledge.db,
PICK validation, heuristics) is backend infrastructure that this
interface sits on top of.

"Primary interface" means: when Bart wants to know what to work on
next, how a system works, what calls what, what the findings say, or
how a pattern was implemented before - he opens this tool, not a
separate file browser or grep session.

### Separation from the game (hard boundary)

The tool is a separate application - separate process, separate UI,
no runtime dependency on the dungeon app. The game does not know the
tool exists. This boundary is permanent: the tool interrogates the
game's source as a corpus, it does not run inside the game or share
its runtime.

The only legitimate coupling points:
- The game may expose test hooks (inspection endpoints, state dumps)
  as part of its own testing infrastructure. The tool may query those
  hooks. The game exposes them for testing; the tool exploits them.
  The game never imports from tools/analysis/.
- Shared utility code (pure functions, data structures) may be copied
  into both codebases, not imported across the boundary.

### Query taxonomy and coverage (as of 2026-06-21)

Ten categories of question the interface must answer well:

1. Identity/definition - "what is X", "where is X defined"
2. Structure/composition - "what files are in X/", "what classes in X.py"
3. Relationships/dependencies - "who calls X", "what imports X", "compare X and Y"
4. Behavioral/trace - "how does X work", "trace X", "show me how X is used"
5. Survey/landscape - "tell me about the quest system", "architecture of X"
6. Evolutionary/history - "what changed in X", "when was X last modified" (GAP)
7. Development planning - "what should I work on", "how was X done elsewhere" (partial)
8. Ranking/complexity - "most complex file", "most tightly coupled" (partial)
9. Quality/issues - "findings for X", "what has TODOs", "what has no docstrings" (partial)
10. Pattern/convention - "how is X typically done here", "find similar to X" (GAP)

Categories 6 and 10 are currently unaddressed. Category 7 (dev planning)
is the highest-value gap: "what should I work on next" and "how was this
pattern implemented elsewhere" are the questions a co-developer asks most.

### UI interaction model (decided 2026-06-21)

Default mode is chat: plain text in, text out. But answers are typed,
and the type determines the renderer automatically - the user never
chooses a display format, the answer chooses it:

- File list answer -> browsable list with drill-down buttons per file
- Call relationship answer -> two-column card or inline graph
- Findings answer -> card per finding, grouped by kind
- Count/ranking answer -> sorted table
- Survey answer -> structured sections with live symbol names

**The answer IS the navigation.** Every symbol name, file name, or
system name appearing in an answer is a live button. Clicking it fires
the next query without typing. The chat input handles open-ended
questions; buttons handle structured follow-through. The user never
retypes a name they just saw in output.

**Agent-suggested follow-ups.** Every answer ends with 2-3 suggested
next queries rendered as buttons (e.g. "callers of X", "findings for X",
"compare X and Y"). The user can click or ignore and type something else.
This makes structured navigation feel conversational.

**Proactive badges.** When a symbol or file is displayed anywhere, the
UI shows passive badges without asking: "4 callers", "2 findings",
"no docstring". Gaps are visible at a glance rather than discovered
by querying.

**Exploration breadcrumb.** Drill-down is a tree. The UI keeps the
full path visible (WorldController -> SessionSystem -> __init__) so
the user knows how they arrived and can navigate back up any branch,
not just linear back.

**Display modes (planned):**
- Call graph: nodes = symbols, edges = calls, immediate neighborhood
  of any chosen symbol. Clickable nodes fire identity queries.
- File dependency tree: collapsible, rooted at any chosen file.
- Findings dashboard: all knowledge_artifacts by category
  (design_note / known_issue / file_purpose / future_plan),
  sortable and filterable, each card with drill-down buttons.
- Diff absorption panel: accept a git diff, re-ingest changed files,
  surface what changed and what it may break. Closes the loop:
  edit code -> tool tells you the impact.

### Build order

Phase A (near-term, low effort):
- "What should I work on" heuristic: pulls workflow_items + findings
  to produce a prioritized answer.
- "How was X done elsewhere" heuristic: uses callers + examples to
  show prior implementations of a pattern.
- Impact analysis trigger: "if I change X what breaks" -> task_generator
  ripple query (already exists, just needs a heuristic entry point).

Phase B (medium-term):
- Drill-down structured responses with follow-up prompt suggestions.
- Quality sweep heuristics: TODOs, missing docstrings, unfinished items.
- Git history heuristic: thin wrapper over git log for evolutionary queries.

Phase C (longer-term):
- Standalone UI application (separate from the dungeon app).
- Call graph and dependency tree renderers.
- Findings dashboard.
- Diff absorption pipeline.

---

## 10. Code editing and refactoring capability (vision - 2026-06-21)

### Goal

The tool can suggest, preview, apply, and verify simple code edits -
docstring additions, new functions/classes following an existing pattern,
symbol renames with caller updates. It never produces broken code and
never applies anything without explicit approval.

### The safety model: suggest -> diff -> approve -> apply -> verify

Every edit follows this sequence without exception:

1. **Suggest**: tool proposes the change in plain English, names every
   file that will be touched and why.
2. **Diff**: tool shows the complete unified diff across all affected
   files before touching anything. Multi-file changes are shown together,
   not one at a time.
3. **Approve**: human explicitly confirms. No auto-apply, no "applying
   in 3 seconds unless you say no."
4. **Apply**: tool writes the change to disk.
5. **Verify**: immediately after apply -
   - ast.parse() on every changed file (syntax check, free, instant)
   - re-ingest changed files into corpus DB
   - compare symbol tables before/after: report any symbol that
     disappeared unexpectedly or any new symbol not in the plan
   - check all known callers of renamed/moved symbols are accounted for
6. **Report**: "these symbols changed, these callers were updated, corpus
   is consistent" - or "PROBLEM: X is now broken, here is why" with a
   rollback offer.

### What the corpus enables

The corpus DB is what makes this safer than a naive editor:
- Before renaming X, we know every caller of X across the whole codebase.
  The rename suggestion includes all of them. Nothing is missed.
- After editing, re-ingestion gives a symbol table diff. If a function
  that existed before is gone after, the tool flags it rather than
  silently succeeding.
- Pattern-following edits: "add a system like QuestManager" -> tool
  finds QuestManager in the corpus, extracts its structure (class shape,
  __init__ signature, method names, registration pattern), generates a
  template following those conventions, shows the diff.

### What it will and will not do

Safe operations (single-file or fully-enumerated multi-file):
- Add/update a docstring on a function or class that lacks one
- Insert a new function or class following a pattern found in corpus
- Rename a symbol with full caller update across all files shown upfront
- Extract a block into a named function within the same file
- Add a parameter to a function with all call sites updated

Will not attempt automatically:
- Moving code across files (import chain updates are too error-prone
  without a proper type-aware tool)
- Changes touching more than ~5 files without step-by-step approval
  for each file group
- Editing files not yet in the corpus (no symbol table = no safety net;
  ingest first)
- Any change where ast.parse() fails on the result (hard stop, no apply)
- Semantic correctness (the tool verifies structure, not behavior;
  tests are the human's responsibility)

### Code-agnostic constraint applies here too

The edit/refactor capability works on any ingested Python codebase.
Pattern discovery ("follow the shape of X") uses the corpus, not
hardcoded game knowledge. The only domain-specific input is what the
human types in the suggestion request.

---

## 11. Git access: current state and the credential boundary

### Today: local-read-only, zero secrets

The tool's only git capability is `git_log_for` (agent_tools.py), which
shells out to `git log` on the already-present local repo. This is a
local filesystem read of `.git` - no network, no credentials. The same
is true of any future `git diff` / `git show` / `git blame` and even
local `git commit`: none of these need a secret.

The credential question only becomes real the day a tool talks to a
**remote** (fetch / pull / push). That does not exist yet and should
not be added without revisiting this section.

### When remote access is added (the rules)

Two distinct properties to preserve, by different mechanisms:

1. **Secret away from the AI (by architecture, not hiding).** The tool
   must never *handle* the token. Let the OS credential layer hold it -
   on Windows, Git Credential Manager backs to Windows Credential Manager
   (DPAPI, tied to the user account). The tool runs `git push`; git
   supplies the credential at the network call. The token never enters
   the tool's memory, a constructed `https://token@host` URL, any log,
   knowledge.db, or the AI's context window. You cannot leak what you
   never hold.

2. **AI can trigger but not perform the privileged action.** Even with
   the token invisible, a misbehaving/injected AI could still *invoke*
   push (wrong branch, force-push, garbage). So:
   - `git_push` is NOT in the agent tool-dispatch table. Pushing is not
     an agent capability. The local Ollama agent never gets it.
   - Push lives only in the human-controlled UI action layer: the AI
     produces a push-request artifact (branch, commits, diff); the human
     approves; the tool (not the AI) executes. This is the section 10
     suggest -> diff -> approve -> apply -> verify model with push as the
     most-privileged "apply" step.
   - Guardrails: never `--force`, branch allowlist, refuse protected
     branches.

3. **Token hygiene.** Fine-grained PAT scoped to one repo, Contents
   read/write only, with expiry; or a per-repo SSH deploy key with a
   passphrase in ssh-agent. Optionally a dedicated bot account so
   tool-made pushes are independently revocable. Append-only audit log
   of every push the tool performs.
