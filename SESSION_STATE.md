Written at commit: 6f04a13
# SESSION STATE - session 126 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 126, 2026-07-09)

**Discovery narration persistence [V]**
- Each Discovery step's LLM narration now stored as artifact: `discovery_{id}_narration`
- Final synthesis stored as `discovery_synthesis`
- Previously both were ephemeral (socket-only, lost on reload)
- 506 tests passed, 1 skipped. Committed bdc2c09.

**pyproject.toml cleanup [V]**
- Removed stale `ollama>=0.5` dependency (replaced by llama-server in session 36)

**UI: no auto-load on startup [V]**
- Removed `_load_session()` fallback from startup
- UI now starts with no corpus loaded -- user always switches explicitly
- Committed 6f04a13

**docs/SETUP.md created [V]**
- Windows-only setup guide: Python 3.11.9, venv, install, llm config, start UI
- llama-server and model paths now documented as configurable in `llm_client.py` lines 34-35
- Committed 6f04a13

**GETTING_STARTED.md -- in progress, being rewritten collaboratively [?]**
- Prior version (session 125) was written at wrong altitude -- described tool output, not user experience
- Correct framing established: teaching doc, tool is the lens not the subject, reader learns to recognize patterns for their own project
- Walked through with Bart in browser: confirmed corpus panel output, Frontier Direct empty, Frontier Orphan shows validate_entry (blue circle, anticipatory)
- Draft content written in conversation but NOT yet written to file
- Key findings from walk:
  - Re-analyze button opens folder browser (not Switch corpus)
  - Mode change in Frontier dropdown auto-loads -- Load button redundant
  - Corpus panel starts open (should default closed -- noted, deferred)
  - Tab bar needs usability pass (grouping, selects) -- noted, deferred

## NEXT SESSION -- start here

**Primary task: finish rewriting GETTING_STARTED.md**

Content written so far (in conversation, not yet in file):
1. Opening orientation paragraph [done]
2. Loading the skeleton -- Re-analyze flow [done]
3. Corpus panel explanation: 17 files, hot, stubs, Roots, Gaps [done]
4. Frontier tab -- Direct mode (empty, 0 stubs, good news) [done]
5. Frontier tab -- Orphan mode (validate_entry, anticipatory vs stranded) [done]

Still to write:
- Frontier tab -- ABC mode
- Topology tab
- The seed files themselves: what each file is and why it exists
- Phase 2: complete corpus, stub closure arc (one function at a time, reingest cycle)
- Phase 3: enhanced corpus, one enhancement at a time

Rules established this session:
- Each section explains only what that control shows -- no forward references until the flow reaches it
- No algorithm names without plain-English explanation first
- Written for two attention levels: thorough readers get full explanations, skimmers hit each concept at least once
- Bart walks it in browser and reports what he sees; doc is written from actual observations

**Also deferred (do after GETTING_STARTED.md is done):**
- Corpus panel defaults to closed on startup
- Tab bar usability pass (grouping, selects, multiple windows)
- Test the install from scratch (pyproject.toml, SETUP.md) on a clean environment
- RM28 Stage 5: test Discovery on dj2

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [V]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**LLM restart required after ctx-size change [V]:** --ctx-size 32768 only takes effect after full UI restart.
**Corpus panel starts open [?]:** Should default to closed; deferred to after GETTING_STARTED.md done.
