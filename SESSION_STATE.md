Written at commit: 13d73bf
# SESSION STATE - session 106 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 106, 2026-07-07)

**RM18 Gap 10 [V]:** Auto-discover design docs on corpus load.
- `_check_design_doc_hint()` in `ui_server.py`: runs on `load_db`, scans for markdown
  with `constraint_score >= 0.3` not yet ingested as `design_note` artifacts, writes
  count+paths to `project_meta` as `design_doc_hint` (JSON).
- `_design_doc_hint()` reads it; `_emit_corpus_ready` includes it in payload.
- Frontend `corpus_ready` handler shows orange dismissible notice in header when present.
- Committed: bdef388 [V], 449 passed, 1 skipped [V]

**RM18 Gap 1 [V]:** Structured layer-rule violation detection.
- `layer_rule` kind added to `knowledge_artifact.py` VALID_KINDS [V]
- `_extract_layer_rules(text, source)` in `doc_extractor.py`: deterministic regex parser
  for "X must not import Y" / "X cannot depend on Y" patterns -> JSON dicts [V]
- `write_seed_layer_rules_doc(project_root)` writes `LAYER_RULES.md` with universal seed
  rules and plain-English onboarding message if file doesn't exist [V]
- `ingest_design_docs` in `agent_tools.py`: extracts layer_rule artifacts from all docs;
  writes seed doc + human-readable message when no rules found [V]
- `_check_import_layer_violations`: queries `kind='layer_rule'` artifacts directly via
  SQL+JSON; returns hint when no rules defined; handles absolute+relative paths [V]
- `check_design_violations`: renders hint and structured violation output [V]
- 15 new regression tests in `tests/regression/test_layer_rules.py` [V]
- Updated 2 stale tests in `test_agent_tools.py` (old design_note format -> layer_rule) [V]
- Committed: 13d73bf [V], 464 passed, 1 skipped [V]

**RM18 fully done [V]:** Gap 2 (Flask entry_point), Gap 10 (doc discovery), Gap 1 (layer rules).

## NEXT SESSION -- start here

1. **RM19 Pass 1 -- Duplicate Detection.**
   Embed all function docstrings+names via existing all-MiniLM-L6-v2 infrastructure.
   Cluster by cosine similarity above 0.85. Surface groups of near-identical symbols.
   Output: candidate pairs with similarity score. No LLM needed.
   Build on: `determined/oracle/embedding_model.py` (embed_text, cosine_similarity),
   `knowledge_artifacts` (kind=reconciliation_finding).

2. **RM19 Pass 2** (after Pass 1 proven): Intent Differencing -- classify WHY near-duplicates
   differ using Qwen3-8B. Fixed taxonomy: accidental copy, historical evolution, performance
   optimization, platform-specific behavior, security reason, genuinely different abstraction.

## Known issues (carried forward)

**ingest_design_docs project root mismatch [?]:** Uses `oracle.get_project_root()` which
returns seed/, not examples/commonplace/. Design docs not auto-discovered. Workaround:
call discover_docs + extract_rules directly.

**UI Re-analyze+ does NOT use reingest_file [V]:** Runs background discover_run thread.
Workaround: call reingest_file() from Python CLI directly.

**Test count: 464 passed, 1 skipped [V]**

## Seed corpus state [?]

DB not reingested this session. Last known: 16 files, 27 implemented, 0 ABC gaps.
