# SESSION STATE - session 31 handoff
_Overwrite completely each session. Not authoritative - see Determined/docs/TRACKER.md for truth._

## What happened this session (session 31)

**SOTS grounding gap identified and closed:**
SOTS tenets surface automatically for code Determined analyzes (via _get_design_frame),
but were not required reading when planning changes to Determined itself. Fixed by
strengthening CLAUDE.md: sots.md is now a mandatory read before presenting any plan
or design, same weight as the session start checklist. Committed 0ca6ba1.

**Active arc documented in CLAUDE.md:**
Items 9, 10, 19 (in order) with per-item SOTS grounding notes baked in. Self-audit
step added as the validation gate for item 19 -- Determined checks itself using
the SOTS tenets already in knowledge.db before item 19 is marked done.

## FIRST THING NEXT SESSION

**Read docs/sots.md before planning anything.** (Now mandatory per CLAUDE.md.)

Then build in order:

**Item 9 -- Distillation pass**
- distill_to_one_sentence(content, subject) helper, calls Ollama compression prompt
- Store as kind='distilled', subject='distilled::<original>' in knowledge_artifacts
- New tool distill_corpus() -- iterates semantic_summaries + file_purpose artifacts,
  distills each, skips cached, aborts gracefully if Ollama down (XIII)
- Wire into symbol_brief (distilled preamble before verbose brief)
- Wire into goal_intake step 1 (use distilled for quick symbol scan)
- SOTS watch: XIV (distilled is a declared derivation, not second truth),
  X (idempotent re-run), XIII (Ollama failure visible not swallowed)

**Item 10 -- Structured output (_raw)**
- Add _raw helpers: _list_callers_raw, _list_callees_raw, _search_symbols_raw,
  _graph_most_connected_raw, _graph_subgraph_raw -- each returns list[dict]
- Refactor string versions to derive from raw (XIV: one source of truth)
- Wire goal_intake to use _raw helpers instead of direct SQL
- SOTS watch: I (each raw helper locally correct), XIV (string derives from raw),
  XXI (only the five named tools, no expansion)

**Item 19 -- Design intent cross-reference**
- New tool check_design_violations(symbol)
- Embed symbol + docstring + callee names, cosine-search all design_notes,
  filter for constraint language ("must not", "never", "only", "forbidden")
- Wire into risk_profile (violations append after risk badge)
- SOTS watch: XI (pure analysis, returns plan never acts), XVIII (empty result
  explains why), XIII (embedding failure degrades gracefully)

**Self-audit (validation gate for item 19)**
- Run check_design_violations against Determined's own corpus
- knowledge.db already holds all 25 SOTS tenets as design_notes
- Produces real findings AND validates item 19 works correctly
- Do NOT mark item 19 done until self-audit runs and findings reviewed

## Current state

Branch: main (Determined), all committed and pushed
Tests: 297/297 regression passing
Items done: 22, 23, 24, 25, 8, 14, 15 (all closed in TRACKER)
Active: items 9, 10, 19 planned and grounded, not yet started

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, separate venv
UI: python -m determined.agent.local_agent --ui then http://127.0.0.1:5050
Use PowerShell tool (not Bash) for all server/Python commands.
Active branch: main (Determined)
