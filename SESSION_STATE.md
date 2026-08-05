Written at commit: f9cff9a

# SESSION STATE — session 302 final handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION (full arc)

**1. Docstring health pass -- committed** [V]

Added one-line docstrings to 111 undocumented functions across the four worst files:
- `determined/assessor/assessor.py`      (37 added)
- `determined/ui/graph_explorer.py`      (40 added)
- `determined/oracle/db_oracle.py`       (17 added)
- `determined/agent/runtime_locator.py`  (17 added)

Method: queried the Determined corpus DB to get exact line numbers of all missing
docstrings, then wrote targeted one-liners per CLAUDE.md style rules.

123 tests pass post-change. [V]
Committed as f9cff9a. [V]

DB NOT yet re-ingested -- counts in DB still reflect pre-change state.
Session wrap requested before re-ingest could run.
Re-ingest pattern (from ui_server.py handle_ingest line 816):
  1. Clear all tables in the DB in-place
  2. `EngineRunner().run(corpus, project_prefixes=[], repo_root=target, connection=conn)`
  3. `conn.close()`

**2. Items 2 and 3 not started** [V]

- Incremental re-ingest file-watcher (new RM item) -- no design, no work started.
- Session-start DB freshness check -- not started; adjunct to item 2.

---

## WHAT TO DO NEXT SESSION

**Step 0 -- Re-ingest Determined DB and verify docstring count improvement.**

Session wrapped before re-ingest ran. Run it first thing:
```python
# Pattern from ui_server.py handle_ingest (line 816)
import sqlite3, sys
sys.path.insert(0, r"C:\Users\bartl\dev\Determined")
target = r"C:\Users\bartl\dev\Determined"
db_path = r"C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined.db"
# 1. Clear tables in-place (do NOT delete file -- avoids WinError 32)
c = sqlite3.connect(db_path)
for t in [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
    c.execute(f"DELETE FROM {t}")
c.commit(); c.close()
# 2. Re-ingest
from determined.engine.run_engine import EngineRunner
conn = sqlite3.connect(db_path)
corpus = type("Corpus", (), {"root_path": target})()
EngineRunner().run(corpus=corpus, project_prefixes=[], repo_root=target, connection=conn)
conn.close()
```
Then re-run the docstring health probe. Expected: assessor.py ~0 missing, runtime_locator.py 0,
db_oracle.py 0, graph_explorer.py 0. Overall core % should drop well below 20%.
Update TRACKER.md RM67 Determined row with new docstring health %.

**Step 1 -- Incremental re-ingest design.**

Surface as a new RM item in TRACKER.md. Design first:
- Which files changed? (git diff --name-only or file mtime vs DB mtime)
- Which tables to update? Check `determined/ingestion/reingest_file.py` -- it may already exist.
- Session-start freshness check is adjunct: if any .py mtime > DB mtime, run incremental.

---

## PROCESS RULE (standing) [V]

Every session: run Determined on dj2, compare tool output to what Claude would say,
log delta in DELTA_LOG.md, fix the tool. Never synthesize without fixing.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden`. [V s290]
- `llm_client.chat()` reasoning_content fallback removed -- don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains `\n`. [V s291]
- pytest `-m` on CLI REPLACES addopts -- never pass `-m` by hand. [V]
- Old corpus DBs may lack `http_route`/`is_tool`/`is_stub` columns -- handle gracefully. [V s293]
- FSM stubs have 0 static callers (string dispatch) -- don't treat as low-priority. [V s295]
- frontier_priority [test] tag uses _is_test_path() -- keep in sync with _is_test_feature(). [V s296]
- list_stubs caller count = ALL edges (resolved + unresolved); frontier_priority = resolved only. [V s297]
- dj2 "tail" stubs ALL have unresolved callers -- phantom edges, not real call paths. [V s298]
- analyze_corpus connectivity-dominant threshold requires orphaned_impl >= 50. [V s299]
- New tools registered in TOOLS dict: add AFTER function def, not inside the dict literal. [V s299]
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes and smart quotes.
  Use Git Bash (Bash tool) for commit messages containing special characters. [V s299]
- _get_abc_gap_set() excludes no-subclass ABCs by design -- they belong to find_abc_gaps.
  Re-adding the no-subclass block causes false JUDGMENT CALLs in analyze_corpus. [V s300]
- Stale corpus DB produces phantom stubs. Always re-ingest before trusting stub list
  if DB is more than one session old. See HISTORY.md 2026-08-05. [V s301]
- Docstring health counts in DB are stale until re-ingest runs. s302 committed 111 docstrings
  but wrapped before re-ingest -- DB still shows old zero counts. [V s302]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
- Determined corpus DB: re-ingest at session start if DB mtime > ~1 week old.
