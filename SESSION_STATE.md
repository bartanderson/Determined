Written at commit: 89bc6d5
# SESSION STATE - session 134 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 134, 2026-07-10)

**RM20: design_note semantic dedup -- DONE [V]**
- `ingest_design_docs` in `agent_tools.py` now embeds each candidate rule before INSERT
- Cosine-compares against all existing design_notes in corpus (threshold 0.85); skips if dup
- Tracks within-run embeddings to catch back-to-back similar rules in one ingest pass
- Graceful degradation: falls back to prefix-match if embedding model unavailable
- 506 passed, 1 skipped. Committed 89bc6d5 [V]

**RM21 probe: 6 multi-hop queries against Commonplace complete corpus -- DONE [V]**
- Technique 1 (claim verifier) never fired across all 6 queries
- Probe script: scratchpad/rm21_probe.py (verbose output captured)
- Failures are upstream of reasoning -- filed as RM31-34 (see TRACKER.md)
- RM21 Techniques 2-6 deferred: not the right next move given what probe revealed

**New items filed in TRACKER.md [V]:**
- RM31: wrong pattern routing (blast-radius → corpus_synthesis; traversal → symbol search)
- RM32: name collision in fact assembly (same symbol name in multiple files collapsed to one)
- RM33: synthesis gap (model summarizes facts instead of answering boolean/cross questions)
- RM34: method confabulation (model invents plausible method names not in facts) -- deferred until RM31-33 done

## Known issues (carried forward)

**GUIDE_DATA sync trap [V]:** `guide_commonplace.json` and inline `GUIDE_DATA` in console.html
are separate stores -- both must be updated together when adding card content. No auto-sync.
**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [?]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI for single file.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**LLM restart required after ctx-size change [V]:** --ctx-size 32768 only takes effect after full UI restart.

## NEXT SESSION -- start here

Active open items in priority order: RM35 (design reconciliation), RM31, RM32, RM33, RM34 (deferred), RM28 Stage 5 (deferred), RM29, RM30.

**RM35** -- do this first. Design reconciliation pass before any RM31 code work.
- Read DESIGN.md, compare against current code architecture
- Key additions not in design: pattern executor, guide/training layer, claim verifier,
  semantic reconciliation arc, two-tier LLM, corpus phase injection
- Rewrite affected sections in place; flag implicit decisions made without design coverage

**RM31** -- next thing to build after RM35. Two routing fixes in `local_agent.py`:
1. Blast-radius pattern: "what would break if X were removed?" → list symbols in X → list_callers on each → assess criticality. Add as named pattern in pattern_executor or heuristic in _answer().
2. Traversal pattern: "path from A to B" → walk call edges from A's layer toward B's layer. May need a new tool or decomposition that hops edge by edge.

**RM32** -- fact assembly fix. In `resolve_and_expand` or the facts-text formatter in `local_agent.py`: tag every symbol with its file when assembling facts block. "search (api.py)" not "search". Grounding already finds the file -- just doesn't carry through to facts text.

**RM33** -- ASSEMBLE prompt fix. In `_assembly_hint()` in `local_agent.py`: detect comparative/boolean question shapes and inject a synthesis instruction ("compare symbol behaviors, don't summarize files").

**RM34** -- deferred. Extend claim_verifier for METHOD_EXISTS claims OR strengthen ASSEMBLE system prompt. Do after RM31-33.
