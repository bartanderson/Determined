Written at commit: bf61aa7 (2026-07-22)

# SESSION STATE — session 235 (addendum)

## Active branch: main [V]

## What happened this session

**Visual projection — all three phases shipped** (1972baa, 81decfb):
- Phase 1: row click → spotlight + graph pre-loaded in Map tab. `data-family` on rows.
- Phase 2: family grouping with clickable headers, filter/clear.
- Phase 3: convergence summary line above table.
- All frontend-only. No backend changes.

**Direction clarified (end of session):**
- No dj2 modifications until Determined is complete (not just "no dj2 work" — the
  gate is using Determined fully on dj2 without going back and forth).
- Next arc: cross-language ingestion + new corpora. Already partially done (TS/JS/Go/Rust
  walkers exist). Need to actually ingest the reference corpora and verify they walk cleanly.
- Signal calibration is GATED on multi-corpus ingestion — dj2 alone is not a valid
  yardstick. Calibrate weights/thresholds after you have diverse ground truth:
  0-stub corpora (specificity), known-gap corpora (sensitivity), cross-language.

## NEXT SESSION — start here

**Cross-language corpora ingestion.** The walkers exist; the corpora are cloned.
Goal: ingest all reference corpora, verify they produce sensible output, surface any
walker bugs that only show up on real code at scale.

Reference corpora locations [?]:
```
C:\Users\bartl\dev\corpora\dnd-dungeon-gen    (JS)
C:\Users\bartl\dev\corpora\dungeoncrawler     (TS)
C:\Users\bartl\dev\corpora\rotjs              (TS)
C:\Users\bartl\dev\corpora\end-of-eden        (Go)
C:\Users\bartl\dev\corpora\ruggrogue          (Rust)
```

First command — check what's already ingested:
```
python scripts/capn.py ask "cross-language corpus ingestion status"
```
Then read TRACKER.md RM67 language scope table (shows probe status per corpus).
Then ingest any that are missing or stale, run `list_features` + `development_priorities`
on each, verify output makes sense against known ground truth.

## Known issues [V = verified, ? = recalled]

**dead artifact LIKE over-match [V]:** `WHERE kind='dead' AND subject LIKE '%{name}'`
over-matches when name is a suffix of another symbol. Documented in test. Fix if noisy.

**load_db auto-orient blocks screenshot [V]:** background LLM thread on corpus load
causes screenshot tool to hang. Workaround: DOM reads via javascript_tool.

**Corpus switch UI flow [V]:** emit `load_db` with absolute .db path to load directly.
"Switch corpus" button only visible when corpus already loaded.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Server start command [V]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.
