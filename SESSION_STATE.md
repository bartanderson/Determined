Written at commit: 68044b2

# SESSION STATE — session 221
Written at commit: 68044b2 (2026-07-19)

## Active branch: main [V]

## What happened this session

**Phase D of UI redesign shipped [V — commit 68044b2]**

Sidebar collapsible sections. Each section in the structure column now has a
collapse chevron in its label row. State persisted per-section in localStorage.

| Section | Default on corpus load |
|---------|----------------------|
| Corpus map | expanded |
| Analyze | collapsed (collapses on `corpus_ready`) |
| Oracle | collapsed |
| Quick actions | collapsed |
| Tools | collapsed |
| Investigation | collapsed |

Analyze re-expands on `corpus_status` when no corpus loaded (so user can see
the path input). Oracle result gets its own pop-out button (⤢) separate from
section collapse — appears only when result is populated.

Also committed: CLAUDE.md step 2a updated from CLOSURE.md → UI_REDESIGN.md.

## Tests [V = verified, ? = recalled]

- UI-only change; no Python engine code touched [V]
- Page loads clean, no JS errors [V — read_console_messages returned none]
- Collapse toggle verified via JS eval: Quick actions starts closed, click opens,
  chevron updates to ▾ [V]
- All sidebar body IDs present in HTML [V — grepped corpus-map-inner, sb-analyze-body, etc.]

## Known issues [V = verified, ? = recalled]

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs (Class.method); tool queries bare names. Workaround: use graph_path.

**classify_stub file_path_hint [?]:** path matching fails for TS corpora when
file_path given. Workaround: omit file_path.

**list_stubs test fixtures [?]:** test stubs surface in stub list. Not yet fixed.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

**Phase D is done [V].** All four phases of UI_REDESIGN.md are now shipped.

**Next: read UI_REDESIGN.md in full** — check if there are any remaining open
items or follow-up work noted. Then check TRACKER.md for what comes after the
redesign (RM59 feature shape analysis is the active item).

**RM59 — Feature shape analysis:**
Three new tools: list_features (directory scan), feature_shape (path tracing),
development_priorities (completeness ranking). Corpus-agnostic, directory-first.
Phase 1 first: list_features + feature_shape. See TRACKER.md RM59 for full design.

**Trap to watch**: when removing HTML elements, grep for all JS references to
those element IDs before committing (see HISTORY.md entry 2026-07-19 s220).
