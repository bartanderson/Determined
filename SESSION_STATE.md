Written at commit: 3c81160
# SESSION STATE - session 137 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 137, 2026-07-10)

**RM33: comparative synthesis hint in _assembly_hint() -- DONE [V]**
- Committed fc0e843
- Added `_COMPARATIVE_RE` regex to `local_agent.py`. Detects multi-condition question shapes.
- Threaded `question` param into `_assembly_hint(needs, question="")` via `_assemble_prompt`.
- When matched, ASSEMBLE prompt says: answer YES/NO first, name symbols, cite facts.

**RM34: method confabulation detection -- DONE [V]**
- Committed da81931 (claim verifier) + 3c81160 (prompt hardening)
- Added `HAS_METHOD` claim kind to `claim_verifier.py`. 4 regex patterns.
- `verify_claim` queries `classes.methods_json`, emits correction if method absent.
- Also added "Do not name any method, attribute, or symbol not in facts" to `_ASSEMBLE_SYSTEM`.

**TRACKER cleanup -- DONE [V]**
- Committed 3704d69 + 209788a
- Pruned RM29-RM35 (all done) from open items. Updated RM21 Technique 1 status.
- Marked RM15 and RM20 done (both completed in earlier sessions, stale [ACTIVE] tags).

**529 tests passed, 1 skipped [V]**

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

**True open items as of this session:**
- RM21 Techniques 2-6 (gated: probe first to see if RM31-34 fixed the original failures)
- RM28 Stage 5 (deferred: general guide layer for non-Commonplace corpora)
- RM10 (FUTURE: DeRe-CoT recomposition pass)

**Best next move: run a live RM21 probe.**
Re-run the 6 queries from the original RM21 probe against the Commonplace complete corpus
to see if RM31-34 actually improved answers. If yes, close RM21 Technique 1 arc as validated.
If answers still fail on specific queries, those failures point to which Technique (2-6) to build.

Original probe queries (from session 134, HISTORY.md):
- Q1: orient (routed to corpus_synthesis -- was this fixed by RM31?)
- Q2: blast-radius (was incorrectly routed to corpus_synthesis -- RM31 fixed)
- Q3: name collision search (RM32 fixed)
- Q4: boolean/comparative (RM33 fixed)
- Q5: traversal (RM31 fixed)
- Q6: method confabulation Entry (RM34 fixed)

Requires: LLM server running (llama-server on port 8081 with Qwen3-8B or 27B model).
Start server: check docs/DESIGN.md or run `llama-server.exe -m models/gguf/... --port 8081`
