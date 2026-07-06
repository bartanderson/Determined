Commonplace Guided Journey - Working Log
=========================================

Live document. Each walk adds to what's known. Only restart from scratch
when a fundamental break requires it. Look ahead 2-3 steps before walking.

---

## WHAT WORKS (verified, don't re-test)

- CSS fix: .tab-content grid-row 4->5 (commit pending). Frontier, Graph,
  Topology tabs now render at full height.
- Seed corpus loads correctly: 8 files, 0 hot, 2 stubs, Roots: capture/index
- Frontier Direct mode: shows extract_metadata + extract_full_content as red
  stubs, extract as orange caller. Correct.
- Topology tab: renders correctly, shows Total stubs:2, direct-call shape,
  action queue points at stubs. Correct.
- symbol_context on extract_metadata: correct output via UI spotlight trigger
  (declaration, docstring, SAFE risk, 1 caller). Spotlight code is correct;
  preview pane too narrow to show it (556px < 590px needed). Not a bug.

---

## KNOWN ISSUES / BLOCKERS

1. Spotlight panel invisible in preview pane (viewport too narrow). Works in
   real browser. Not fixing -- preview limitation.

2. "0 design notes" has no call-to-action. User sees it but can't act on it
   from the corpus panel. Needs a "Scan for design docs" button.
   Status: FILED, not yet fixed.

3. seed/ has no DESIGN.md. ingest_design_docs finds nothing. Intentional --
   user writes design doc as they build. But the UI needs to explain this,
   not just show 0.

4. CLI (local_agent REPL): no named pattern for topology/frontier queries.
   User types natural language, LLM answers from what's been explored.
   With 0% coverage the answer is always empty. Not a bug -- coverage 0
   means explore first. But REPL startup should say "run 'orient' to start."

---

## WALK 1 - First complete attempt

### Setup
- Corpus: C_Users_bartl_dev_Determined_examples_commonplace_seed.db
- Interface: web UI at localhost:5050
- Approach: user perspective, click-by-click

### Look ahead (steps 1-7 before walking)
1. Load corpus -> corpus panel shows shape. WORKS.
2. Frontier -> 2 stubs. WORKS. (need to set Direct mode, it may remember Orphan)
3. Click stub node -> spotlight. WORKS in real browser, invisible in preview.
4. Topology tab -> structure summary. WORKS.
5. Editor tab -> open extractor.py -> NOT YET VERIFIED.
6. Reingest after edit -> NOT YET VERIFIED.
7. Design notes -> 0, no action. KNOWN ISSUE #2.

### Steps walked

[Step 1] Switch corpus to seed.
  Result: 8 files · 0 hot · 2 stubs. Roots: capture, index. PASS.

[Step 2] Frontier tab -> set Direct mode -> Load.
  Result: extract_metadata, extract_full_content (red), extract (orange). PASS.
  Note: mode dropdown remembers last selection -- may be on Orphan after prior session.
  Fix needed: default to Direct on tab open, or remember per-corpus.

[Step 3] Click extract_metadata in graph.
  Result: spotlight fires (trail shows entry), panel invisible in preview.
  In real browser: declaration + STUB docstring + SAFE risk + 1 caller. PASS (real browser).

[Step 4] Topology tab -> Refresh.
  Result: Total stubs:2, Direct-call:2, action queue: implement direct-call stubs. PASS.

[Step 5] Editor tab -> type 'extractor.py' -> Open.
  Result: file loads, symbols panel shows extract_metadata/extract_full_content/extract,
  code visible with STUB docstrings. Edit button present. PASS.

[Step 6] Editor save + reingest verification (session 86).
  Opened extractor.py in Editor tab. extract_metadata already had real
  implementation (urllib/HTMLParser). Clicked Edit -> Save.
  Found bug: ui_server line 1538 called reingest_file(_assessor.oracle, fp)
  but reingest_file signature is (db_path: str, file_path: str). Oracle object
  was silently swallowed by bare `except Exception: pass`.
  Fix: changed to reingest_file(_db_path, str(fp)), also improved error to
  emit toast instead of silent pass.
  After fix + server restart + save: sidebar updated live from 2 stubs -> 1 stub
  without page reload. corpus_ready fires correctly after reingest. PASS.

[Step 7] Design notes -- 0 design notes, no action available.
  Root cause: ingest_design_docs was not in the post-ingest flow.
  Fix: wired ingest_design_docs into post-ingest pass (after discovery,
  before ingest_done), same pattern as distillation. Silently skips corpora
  with no design docs. seed/ has no design docs intentionally -- user writes
  them as they build. On re-ingest of a corpus with docs, count will populate.
  KNOWN ISSUE #2 resolved. KNOWN ISSUE #3 (seed has no docs, UI doesn't explain)
  remains -- low priority, tooltip or empty-state text could address it later.

---

## NEXT WALK - Steps 5-6 (Editor + Reingest)

Look ahead:
- Editor tab: user opens extractor.py, sees the stub, edits it, saves.
  Does the Editor tab load the file correctly for seed corpus?
  Does Save write to disk?
  Does Analyze/reingest update the stub count?
- After reingest: corpus panel should show 1 stub (not 2).
  Frontier should reload and show only extract_full_content.

Known risk: Editor tab path resolution -- seed corpus files are under
examples/commonplace/seed/. Does the editor resolve that correctly?

---

## FINDINGS TO FIX (in order of journey impact)

F1. [DONE] Frontier mode resets to Direct on tab open.
    Fix: reset fg-mode select to 'direct' on every tab click (commit 5c396b3).

F2. [DONE] ingest_design_docs wired into post-ingest pass.
    Fix: runs automatically after discovery, before ingest_done (commit a7dc167).

F3. [DONE] REPL startup hints when coverage < 10%.
    Fix: prints "run orient or discover" hint at startup (commit 5c396b3).

RM16. [FILED] UI concept documentation pass -- explain every panel/mode/concept
    in one line, always visible. Walk-driven, after F1/F3 resolved.
