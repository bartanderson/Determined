RM70 — Stub Solution Synthesis
================================

_Written 2026-07-26. Follows sketch_stub (session 261), which established the
two-layer architecture (deterministic brief + LLM candidate) and revealed that
the LLM's output quality is bounded by the context it receives, not its capacity._

---

## Problem statement

`sketch_stub` produces a candidate implementation for classified stubs. The
current brief gives the model: caller names + docstrings, 30-line sibling
previews, and declared return type. That is enough to produce a typed placeholder
(`return {}`). It is not enough to produce a plausible implementation.

The gap is retrieval, not generation capacity. An 8B model given the full caller
body, a complete sibling implementation following the same pattern, and the
relevant type definitions can write a plausible body — not because it guesses
better, but because the answer is largely visible in the surrounding code.

Verification and iterative refinement close the remaining gap: generated code
that calls non-existent APIs is caught by the corpus call checker and fed back
as a constraint.

---

## Design in one sentence

Give the model what a human engineer would open before writing the function:
the caller (to see how the result is used), a working sibling following the
same pattern (to see the style and structure), and the relevant type definitions
(to know what it can call). Verify the output against the corpus. Retry with
feedback if the first attempt fails.

---

## SOTS grounding

- **I Locality of reasoning** — the retrieval layer assembles everything the
  model needs into the prompt; the model reasons locally, not globally. No
  corpus-wide reasoning during generation.
- **XIV One source of truth** — pattern sibling selection uses the DB as the
  canonical source of function signatures and call relationships; not duplicated
  in the prompt as re-derived facts.
- **XI Explicit structure over hidden smarts** — the pipeline's three layers
  (retrieve → generate → verify) are each independently testable. Retrieval
  quality can be measured without running the LLM. Verification runs without
  generation. No stage depends on another stage's internal logic.
- **XXI Simplicity is the budget** — the pipeline should be built in order of
  value: retrieval alone is shippable and the highest-value change. Generation
  improvements and iterative refinement are layered on top, not designed up front.
- **XIII Visible failure** — LLM failure is marked in output. Verification
  failure is reported with the specific signal that failed (e.g., "called
  `EncounterFSM.get_context` — not in corpus"). Never silently return bad output.

---

## Architecture: four stages

### Stage 1 — Retrieval (deterministic, always runs)

The brief currently contains:
- Caller names + docstrings
- 30-line sibling body preview
- Declared return type

Replace with:

**1a. Full caller body**
Read the complete source body of each caller (not docstring — the actual code).
The caller's usage of the return value is the ground truth for what the function
must produce. A caller that does `ctx["encounter_state"] = self._get_encounter_context()`
tells us the return value slots into a specific key.

**1b. Return-shape inference**
Walk the caller body's AST for subscript access (`result["key"]`), attribute
access (`result.state`), and unpacking patterns on the stub's return value.
These are the keys/attributes the return value must have. Confidence is labeled:
- STRONG: direct subscript or attribute access found
- WEAK: result passed to another function without direct access (keys unknown)
- NONE: usage pattern not parseable

Return shape is presented in the brief as "inferred keys: [x, y, z]" with
confidence level. It is not asserted as ground truth.

**1c. Pattern sibling search (name-pattern primary, semantic secondary)**
Find implemented functions with similar naming patterns across the entire corpus,
not just the same file. Method: normalized Levenshtein distance on function name
after stripping common prefixes/suffixes (`_get_`, `_build_`, `_compute_`).
Secondary tiebreaker: SetFit cosine similarity on docstring.

`_get_encounter_context` → finds `_get_combat_context`, `_get_navigation_context`
(name-pattern), then orders by semantic similarity to intent text.

Pull the full implementation of the top 1-2 matches. These are the style
examples. The model mirrors them, not invents from scratch.

**1d. Referenced type definitions**
For each name in the stub's docstring or signature that resolves to a class in
the DB: pull that class's `__init__` signature and public methods (non-stub).
These are the APIs the body is allowed to call. Not hinted — retrieved.

Example: `_get_encounter_context` mentions `EncounterFSM` → pull
`EncounterFSM.__init__(self, ...)` and all non-stub methods → model knows it
can call `EncounterFSM.get_state()`, `EncounterFSM.participants`, etc.

---

### Stage 2 — Generation (LLM, 1–K samples)

**Two modes:**
- **Quick** (interactive, default): 1 sample, verify, return if it passes. If
  it fails verification, mark failure reason in output and return the best
  partial attempt. No retry in interactive mode.
- **Thorough** (batch, explicit): K=3 samples, all verified, ranked by score,
  top result returned with alternates listed. Appropriate for batch runs or when
  interactive latency is not a constraint.

The prompt format remains completion-mode (ends at the `def` line; model fills
the body). The richer retrieval context is inserted before the target def:
1. Pattern sibling full implementation (as style example)
2. Caller body with the usage site marked
3. Available type APIs (what the body may call)
4. Return shape inference (what the body must return)
5. Intent text as a comment
6. Target `def` line

---

### Stage 3 — Verification and scoring (deterministic)

Each generated candidate is scored on four signals. All four run regardless of
whether previous signals fail — the full score drives the feedback prompt.

**V1: Syntactic validity** — `ast.parse()`. Hard gate: syntactically invalid
candidates are not scored further and not returned. Error is fed back as
constraint in retry.

**V2: Corpus call validity** — For every function/method called in the body,
query `graph_edges` and `functions` tables: does this name exist in the corpus?
Score = fraction of called names that resolve. This is the primary quality
signal. A body that calls only real corpus functions is plausibly correct; one
that calls invented APIs is confabulated.

**V3: Return type compatibility** — If declared return type is `dict`, does at
least one return statement return a dict literal or a variable of dict type? If
`None` or no return type, pass. Best-effort via AST walk. Not a hard gate —
contributes to score.

**V4: Pattern similarity** — AST structural similarity to the best retrieved
sibling (same statement types in similar order). Normalized edit distance on
the AST node sequence. Rewards implementations that follow the established
pattern.

**Composite score** = `V2 * 0.6 + V3 * 0.2 + V4 * 0.2` (V1 is a hard gate,
not weighted). Weights are provisional — calibrate against real examples.

---

### Stage 4 — Iterative refinement (feedback loop)

When quick mode fails V1 or V2, or when thorough mode's best candidate scores
below threshold (0.5), run a feedback round:

1. Identify the lowest-scoring signal from Stage 3.
2. Construct a specific constraint from that signal:
   - V2 failure: "You called `X` — it is not in the codebase. Available on
     `EncounterFSM`: `get_state`, `participants`, `current_phase`."
   - V3 failure: "Return type is `dict` but you returned `None`."
3. Append the constraint to the prompt and generate again.
4. Repeat up to 3 iterations (hard ceiling — visible output if ceiling hit).
5. Return the highest-scoring candidate across all iterations.

This is iterative refinement with corpus-grounded feedback, not MCTS proper.
The distinction matters: MCTS builds a tree over partial implementations and
backpropagates scores. That is appropriate if implementations are built
statement-by-statement and partial states are scored. For complete function
bodies (the current scope), feedback-guided retry is the right mechanism and
substantially simpler.

Full MCTS (statement-level tree search) is a future extension gated on: (a)
the iterative refinement approach proving insufficient, and (b) a scoring
function that can meaningfully evaluate partial bodies.

---

## Scope boundaries (what this is not)

- **Not a general code generator.** Only operates on stubs already in the corpus
  using only code already in the corpus. Corpus-agnostic constraint holds.
- **Not authoritative.** Output is labeled "candidate — review before applying."
  The classify_stub verdict is ground truth; the sketch interprets it.
- **Not a replacement for the engineer.** The output is a starting point — a
  typed, corpus-grounded placeholder that saves the first 15 minutes of
  implementation, not the rest.
- **Not gated on LLM quality.** The retrieval layer (Stage 1) is independently
  valuable. Ship it first. Stages 2-4 are layered on top.

---

## Build order (each step independently shippable)

_Revised after adversarial review: verification ships first to establish a
baseline score on current output. Retrieval improvements are then measurable._

1. **V1+V2 verification baseline** — `ast.parse` (V1) + corpus call check (V2).
   Run against current sketch_stub output on all dj2 stubs. Establish baseline
   scores. This is the yardstick for everything that follows.

2. **Caller body reader** — `_read_function_body` already exists for non-stubs.
   Extend `build_brief` to pull full caller bodies instead of docstrings. Ship.
   Re-run V1+V2 scores; measure improvement.

3. **Pattern sibling search** — name-normalized Levenshtein + DB query.
   Replace `_style_siblings` (file-scoped) with `_pattern_siblings` (corpus-scoped).
   Ship. Verify correct siblings are found (e.g. `_get_combat_context` for
   `_get_encounter_context`).

4. **Return-shape inference** — AST walk of caller bodies. Confidence levels:
   STRONG (direct subscript/attribute access), WEAK (passed to another function —
   inferred keys shown with "(uncertain)" tag), NONE (omitted from brief).
   Ship.

5. **Type definition pull** — DB query for named classes → their methods.
   Add to brief. Ship.

6. **V3+V4 scoring** — return type compatibility (V3) and pattern similarity (V4).
   V4 is a ranking tiebreaker only — never a rejection criterion. A candidate
   passing V2 ≥ 0.8 is not rejected on V4 grounds.

7. **Multi-sample + feedback loop** — quick mode (1 sample, no retry unless V1
   fails) is the default. `mode=thorough` is an explicit opt-in: K=3 samples,
   ranked by composite score, top result returned with alternates listed.
   Feedback: lowest-scoring V2 signal → specific constraint appended to prompt
   → retry. 3-iteration ceiling, visible in output if hit.

---

## Acceptance criteria

- `_get_encounter_context` sketch calls only functions that exist in the corpus
- Pattern sibling search finds `_get_combat_context` as top match (not just
  file-level siblings)
- Return-shape inference correctly infers at least one key from the caller body
- V2 corpus call score ≥ 0.8 for passing candidates (80%+ of called names resolve)
- Iterative refinement converges in ≤ 3 rounds for dj2's real gaps
- sketch_stub still declines concept-not-applicable stubs correctly
- All existing tests pass after each stage lands
