# Reasoning Model — AI-Assisted Decision Architecture

_Created session 63, 2026-07-03. Living document — update disposition fields in place._
_Companion to DISCOVERY_MODEL.md (navigation + analysis concepts) and DESIGN_ARC.md (investigation arc)._
_This document captures the architecture for making local models (3B/8B) produce reliable_
_architectural-level decisions through structured decomposition, not raw model capability._

---

## The Core Insight

The limitation is not model intelligence — it is context shape.

A small model given the whole codebase at once will fail to make reliable architectural decisions.
The same model given one focused, concrete sub-question with all relevant evidence already assembled
will answer correctly most of the time. The design job is to convert big questions into small ones
automatically, run each small one with high-quality context, and assemble the results deterministically.

No single model call needs to understand the whole system. The whole-system understanding lives in
the DB (call graph, contracts, design notes, topology). The models provide judgment on focused slices.

**What this is not:** a smarter LLM wrapper, prompt engineering, or RAG. It is a structured
pipeline where deterministic DB queries do the reasoning and models do the judgment.

---

## The Three Components

### 1. Decomposer

Takes a goal or architectural question and returns an ordered list of sub-questions — the questions
whose answers, taken together, determine the answer to the original question.

**Input:** a goal string ("should validate_action be a method on AuthoritySystem?")
**Output:** ordered list of sub-questions with routing hints (DB query vs. evaluate() call)

**Requirements for a good decomposer:**
- Sub-questions must be independently answerable
- Each sub-question must be small enough to fit in one evaluate() call or one DB query
- The list must be complete: if all sub-answers are known, the main question is answerable
- Order matters: dependency sub-questions come first

**Example decomposition** for "should validate_action be a method on AuthoritySystem?":
1. How many of validate_action's callers are inside AuthoritySystem? [DB query]
2. Does validate_action access AuthoritySystem instance state (self.*)?  [contract analysis]
3. What SOTS tenet(s) apply to this boundary decision? [embedding search + evaluate()]
4. Do validate_action's siblings follow a validator-on-class pattern? [DB query]
5. What is the coupling cost if it stays standalone (how many files import its module)? [DB query]

Three of five sub-questions are pure DB queries — deterministic, no LLM needed. The other two
are focused evaluate() calls with constrained, high-quality context. The synthesis reads five
concrete findings, not the whole codebase.

**Reuse path:**
- Decomposer is a single LLM call (8B preferred). Input: the question + a list of available
  query types. Output: structured sub-question list with routing annotation.
- `collect_symbol_context()` in evaluator.py already lists what evidence is available for
  a given symbol — feed this into the decomposer prompt so it knows what DB queries are possible.

---

### 2. Router

For each sub-question, decides whether it is answerable by a DB query (deterministic) or
requires an evaluate() call (LLM judgment). Routes accordingly and executes.

**Routing rules (in order — stop at first match):**

| Pattern | Route | Why |
|---|---|---|
| Count / frequency question | DB query | graph_edges, callers, symbol_occurrences |
| Existence question | DB query | symbol_definitions, class_attributes |
| Pattern matching (do siblings do X?) | DB query | group by file/class, count matching |
| Coupling / import question | DB query | import_graph, module membership |
| "Does tenet X apply?" | embedding search + evaluate() | requires semantic matching |
| "Is this a good decision?" | evaluate() | requires judgment |
| "What becomes possible if X?" | evaluate() with callers as evidence | requires reasoning |

The router is mostly deterministic code. Only the last three rows need LLM involvement,
and even those are constrained to a single focused question per call.

**Reuse path:**
- DB queries use existing helper functions: `list_stubs()`, `gather_context()`,
  `symbol_context()`, `collect_symbol_context()`, direct SQL via `db.execute()`
- evaluate() calls use the existing `evaluate_claim()` / `build_eval_request()` /
  `execute_eval_request()` pipeline — the kernel is already split for composability
- `retrieve_evidence()` already searches knowledge_artifacts by embedding — reuse as-is

---

### 3. Synthesizer

Takes all sub-answers (a structured list of findings) and produces a final recommendation
with confidence, reasoning, and provenance (which sub-answers drove the conclusion).

**Input:** the original question + list of (sub-question, answer, source) tuples
**Output:** recommendation + confidence + reasoning + provenance list

**The key constraint:** the synthesizer must NOT repeat the sub-question work. It reads
already-computed findings, it does not re-derive them. Its LLM call receives a tight,
structured context — not the codebase, not the call graph, just the assembled findings.

**Example synthesizer output** for validate_action placement question:
```
Recommendation: STANDALONE (moderate confidence)
Reasoning: 4 of 5 callers are outside AuthoritySystem, and the function accesses
no instance state. SOTS tenet [III] (single decision point) is consistent with
either placement. Sibling pattern argues for method, but external caller majority
argues against coupling. Recommendation stands until caller distribution shifts past 50%.
Provenance: driven by sub-answers 1 (4/5 external) and 2 (no state access). Sub-answers
3, 4, 5 were consistent but not decisive.
```

**Reuse path:**
- Synthesizer is a single LLM call (8B preferred for synthesis quality)
- 3B can be tried first; if confidence is low, escalate to 8B
- Format the sub-answers as a numbered list, not prose — structured input produces
  structured output reliably from small models

---

## The Full Pipeline

```
Goal / architectural question
        |
        v
[Decomposer] (8B, one call)
  "What sub-questions do I need to answer this?"
        |
        v
Ordered sub-question list + routing hints
        |
        v
For each sub-question:
  [Router] (deterministic code)
    ├─ DB query → answer (deterministic)
    └─ evaluate() call → verdict + confidence (LLM, focused)
        |
        v
Assembled findings: [(question, answer, source, confidence), ...]
        |
        v
[Synthesizer] (8B, one call)
  "Given these N concrete findings, what is the recommendation?"
        |
        v
Recommendation + confidence + reasoning + provenance
```

Most of the actual reasoning is done by deterministic DB queries. The models provide
judgment at two narrow points: decomposing the question and synthesizing the findings.
Neither requires understanding the whole codebase.

---

## Model Role Split

| Role | Model | Why |
|---|---|---|
| Decomposer | 8B | Needs to understand question types and available evidence well enough to partition correctly |
| DB-answerable sub-questions | None (code) | Deterministic; no model needed |
| Focused evaluate() calls | 3B | Small, constrained context; 3B handles well |
| Synthesizer | 8B | Needs to weigh multiple findings and produce a coherent recommendation |

The 3B handles all the micro-judgment calls (one claim, one piece of evidence).
The 8B handles structure: turning a question into sub-questions, turning sub-answers into a recommendation.

This is achievable with the current hardware. No API calls needed. No model that doesn't fit
in available VRAM. The design architect-es around the constraint rather than accepting it.

---

## Connection to DISCOVERY_MODEL

This is the missing piece between Q4 (MCTS tree search) and the rest of the Discovery Model:

```
DISCOVERY_MODEL.md
  Frontier → Implementation Queue → [Q4 MCTS tree search]
                                            |
                              ← REASONING_MODEL fills this ←
                                            |
                                   Decompose "which stub next?"
                                   into sub-questions answered by
                                   frontier data + evaluate() kernel
```

Q4 in DISCOVERY_MODEL is currently deferred (blocked on Q3 + F4). The Reasoning Model is
the design that makes Q4 concrete when Q3 and F4 are ready. The MCTS tree search IS the
decomposer/router/synthesizer running iteratively over the frontier graph.

---

## Composability Audit

What exists and what new code each piece needs.

### Already built — reuse as-is

| Existing piece | Role in Reasoning Model |
|---|---|
| `evaluate_claim()` | Executes one focused evaluate() call in the Router |
| `build_eval_request()` / `execute_eval_request()` | Composable kernel split — already ready for Router use |
| `retrieve_evidence()` | Finds relevant knowledge_artifacts by embedding — used by Router for semantic sub-questions |
| `gather_context()` (stub_projector.py) | Provides callers + contracts + siblings as context for Router queries |
| `collect_symbol_context()` (evaluator.py) | Builds the claim string for a symbol — feed to decomposer so it knows what evidence exists |
| `symbol_context()` | Full picture of a symbol for the decomposer's context |
| `list_stubs()` | One of the primary DB query routes in the Router |
| `store_finding()` + `knowledge_artifacts` | Persist sub-answers and final recommendations as artifacts |

### New code needed

**R1 — Decomposer function** (~40 lines)
- Input: question string + symbol name (optional) + available_queries list
- Calls `collect_symbol_context()` to see what evidence is available
- Calls 8B LLM with structured prompt: "given this question and these available query types, list the sub-questions"
- Output: list of `{question, route: 'db'|'evaluate', db_query_type: str|None}`
- This is the only genuinely new logic in the pipeline

**R2 — Router function** (~60 lines)
- Takes one sub-question + route annotation
- For `route='db'`: dispatches to the right existing query function based on `db_query_type`
- For `route='evaluate'`: builds an eval request using `gather_context()` + `build_eval_request()`
- Returns `{question, answer, source, confidence}`
- This is mostly a dispatch table over existing functions

**R3 — Synthesizer function** (~30 lines)
- Input: original question + list of (question, answer, source, confidence)
- Formats as numbered findings list
- Calls 8B LLM with structured prompt: "given these findings, what is the recommendation?"
- Parses output into recommendation + confidence + provenance
- Stores result via `store_finding()` with kind='reasoning_result'

**R4 — `reason_about` agent tool** (~20 lines)
- Wraps R1 → R2 (in loop) → R3 into one callable tool
- Signature: `reason_about(question: str, symbol: str = None) -> str`
- Registered in TOOLS as assessor-layer tool
- Returns formatted recommendation block

**R5 — UI: Reasoning panel** (~50 lines JS + template)
- A "Reason" button in the Frontier tab (appears when a stub node is selected, alongside "Project")
- Emits `reason_about_request` socket event with symbol name
- Server runs R4, emits `reason_about_result`
- Result renders in the same result panel below the Frontier graph as `project_stub` output
- Markdown fencing stripped before render (fix projection display bug at same time)

---

## Exploration Checklist

- [x] **RM1** — Prototype the Decomposer (R1) on one real question. Test: "should validate_action
  be a method on AuthoritySystem?" — does the decomposer produce the expected sub-questions,
  or does it miss key ones? Adjust prompt until the partition is reliable.
  Disposition: `→ built and smoke-tested (session 63). DB routes verified against dj2 corpus:
  7 callers, is_stub=yes, standalone (not a method), 2 validate* siblings, 0 import coupling.
  Decomposer calls quality LLM with structured prompt; falls back to minimal partition.`

- [x] **RM2** — Audit Router coverage. List all sub-question types the Decomposer might produce.
  For each, confirm there is a DB query function or evaluate() path that handles it. Any gap
  in the Router is a gap in the whole pipeline.
  Disposition: `→ initial coverage built (session 63): caller_count, callee_count,
  class_membership, sibling_pattern, import_coupling, is_stub (all DB), plus sots_match and
  design_judgment (evaluate routes). Gaps will surface when Decomposer produces types not in
  _DB_ROUTES; Router falls through to evaluate() as a safe default.`

- [x] **RM3** — Implement R1 (Decomposer) + R2 (Router) + R3 (Synthesizer). Test end-to-end on
  validate_action placement question. Verify each sub-answer is reasonable before looking at
  the synthesis.
  Disposition: `→ all three built in reasoning_engine.py (session 63). DB routes verified.
  End-to-end test against live LLM on hardware is the remaining manual step (RM5 triggers this).`

- [x] **RM4** — Implement R4 (`reason_about` tool) and test via chat interface. Compare output
  to a human expert's reasoning about the same question on dj2.
  Disposition: `→ built and registered in TOOLS (session 63). Test via chat: reason_about
  question="should validate_action be a method?" symbol=validate_action`

- [ ] **RM5** — Implement R5 (Reasoning panel UI). Wire "Reason" button into Frontier tab.
  Fix markdown fence rendering in the result panel at the same time (affects project_stub output too).
  Disposition: `→ not explored`

- [ ] **RM6** — 3B vs 8B benchmark. Run R2 (focused evaluate() calls) on 3B vs 8B for the same
  sub-questions. Measure: does 8B produce noticeably better focused verdicts, or is 3B sufficient
  for micro-judgment? If 3B is sufficient for Router calls, 8B is only needed at Decomposer + Synthesizer
  (two calls total instead of N+2).
  Disposition: `→ not explored`

- [ ] **RM7** — Confidence aggregation. When multiple sub-answers have low confidence, does the
  Synthesizer correctly produce a low-confidence recommendation, or does it confidently synthesize
  uncertain inputs? Test: deliberately give the Synthesizer conflicting sub-answers and measure
  whether the output confidence reflects the conflict.
  Disposition: `→ not explored`

- [ ] **RM8** — Persistence and replay. Store each reasoning chain (question + sub-questions +
  answers + synthesis) as a knowledge_artifact with kind='reasoning_chain'. This enables:
  (a) reviewing prior decisions, (b) detecting when a prior reasoning chain is now stale (e.g.
  a new caller was added that changes a count sub-answer), (c) using prior chains as context
  for new decompositions.
  Disposition: `→ not explored`

- [ ] **RM9** — Connect to Q4 (MCTS). Once `reason_about` is proven on single questions, extend
  to iterative frontier decisions: "given the current frontier, which stub should be implemented
  next?" The sub-questions are the same ones as Q4's value function. R1-R3 is the implementation
  of Q4's evaluator node. DISCOVERY_MODEL.md Q4 should reference this doc when undeferred.
  Disposition: `→ not explored`

---

## Mining Priority

**Do first (prototype, no UI needed):**
1. RM1 — Decomposer prototype (validate the partition)
2. RM3 — End-to-end pipeline on one real question
3. RM4 — `reason_about` tool in chat

**Do second (UI + benchmarking):**
4. RM5 — Reasoning panel + fix markdown fence display
5. RM6 — 3B vs 8B benchmark on Router calls

**Do third (quality + persistence):**
6. RM7 — Confidence aggregation test
7. RM8 — Reasoning chain persistence
8. RM2 — Router coverage audit (do after seeing gaps in RM3)

**Do last (connects back to DISCOVERY_MODEL):**
9. RM9 — MCTS connection (undefers Q4)

---

## What This Is Not

- **Not RAG**: RAG retrieves similar documents. The Router executes specific structured queries
  against a known schema. The evidence is precise, not approximate.
- **Not a chain-of-thought prompt**: CoT happens inside one LLM call. This pipeline runs
  deterministic code between LLM calls. The reasoning is in the pipeline, not the prompt.
- **Not an agent loop**: there is no feedback between Synthesizer and Decomposer in the base
  design. The pipeline is a single pass. Iterative refinement (RM9/Q4) comes later.
- **Not dependent on model quality**: each component can be replaced independently.
  If 3B is insufficient for Router evaluate() calls, swap in 8B. If synthesis quality is poor,
  add a validation step. The architecture doesn't change when model capabilities change.
