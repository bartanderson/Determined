Written at commit: f316d50 (2026-07-21)

# SESSION STATE — session 232

## Active branch: main [V]

## What happened this session

**TRACKER audit via git log [V]**

Discovered that RM69, RM70, RM71 were all shipped in prior sessions but their
TRACKER entries were never deleted. Cleaned all three:
- RM70 detect_conventions — deleted (done session 225)
- RM71 shape scanner + normalizer — deleted (done session 224)
- RM69 judgment layer / classify_stub — deleted (done session 229)

Root cause: SESSION_STATE was not being used to drive TRACKER cleanup.
Fix going forward: check git log at session start, delete done items immediately.

**FUTURE gates — all met [V]**

All items that were gating the FUTURE sections are now shipped:
- classify_stub calibration stable (RM69 done)
- detect_conventions sort=established|emerging shipped (RM70 done)
- rank_stubs with outlier_bonus wired (session 226)
- FSM/structured data ingestor (RM71 done)

Signal fusion (FUTURE — Signal fusion + multi-modal visual projection) is now
fully actionable. All three gates in that section are met.

## Known issues [V = verified, ? = recalled]

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs; tool queries bare names. Workaround: use graph_path.

**Server start command [V]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

Run: `git log --oneline -10` first. Delete any done TRACKER items before anything else.

Next work: **FUTURE — Signal fusion + multi-modal visual projection** in TRACKER.md.
Read that section. All gates are met. Design the fusion layer shape first (per the
section's own instructions), then visual projection surface, then wire.

The key design question: given a concept, what is the compositor that reads
classify_stub output + detect_conventions family membership + rank_stubs priority
+ graph centrality and surfaces a combined picture? That's the first design choice.
