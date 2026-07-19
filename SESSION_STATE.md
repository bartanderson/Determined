Written at commit: 866eb4e

# SESSION STATE — session 218
Written at commit: 866eb4e (2026-07-19)

## Active branch: main [V]

## What happened this session

**Completed all remaining UI_EVAL.md items [V — all in commits]:**

| Fix | Commit | What |
|-----|--------|------|
| A3 | b1f193a | Module filter chips above Roots section |
| B3 | b2a2ee4 | Blast radius expandable extended impact |
| G1 | 866eb4e | Workbench promoted to primary tab bar + grouped tool forms |

**A3 details [V]:**
- Server: removed `eps[:8]` cap, sends all EPs with `module` field computed via
  `relative_to(oracle.get_project_root().resolve())` (absolute paths in DB required this).
- Client: chip row auto-generated from unique EP modules (filter(Boolean) excludes
  root-level files). Default "All" shows top 8; module chip shows all EPs in that module.
- dj2 chips: static/ world/ engine/ ai/ core/ dungeon_neo/

**B3 details [V]:**
- `blast_radius` tool output restructured: "Direct callers (N):" / "Extended impact (N):" /
  "Risk factors:" sections, one symbol per line.
- New `tryBlastRadiusRender()` parses sections, renders callers as clickable rows,
  extended impact as collapsible `<details>` element.
- New `blast_radius` socket event bypasses LLM for instant deterministic results.
  Client handler calls `activateTab("chat")` before `addResultBlock` (panel-chat is
  hidden when Graph/Frontier tab is active).
- Tools panel "Blast radius of" shortcut now emits socket directly, not tpQuery.

**G1 details [V]:**
- Workbench moved from More overflow to primary tab bar (7 primary tabs now).
- `_WORKBENCH_TOOLS` expanded: 12 to 16 tools, added category field.
- New tools: symbol_context, blast_radius, list_features, feature_shape.
- check_design_violations now has `symbol` param.
- `wbRender` rewritten: groups by category, two-row layout for tools with params.
- Categories: Orient / Frontier / Symbol / Design / Documentation / Search.

## Tests [V = verified, ? = recalled]

- UI changes only, no Python engine logic changed (blast_radius tool output format changed).
- 91 parse_ast regression tests still passing [?] -- not re-run, engine unchanged.
- blast_radius tool format change is backward-compatible for CLI use (still readable text).

## Known issues [V = verified, ? = recalled]

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs (Class.method); tool queries bare names, chain length 0/1. Workaround: use
graph_path. Not fixed (separate RM item).

**classify_stub file_path_hint [?]:** path matching fails for TS corpora when
file_path given. Workaround: omit file_path, rely on name-only lookup.

**list_stubs test fixtures [?]:** test stubs surface in stub list. Not yet fixed.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`. Never use pyenv/system Python.

## NEXT SESSION -- start here

**UI_EVAL.md is fully checked off [V].** All A1-A3, B1-B3, C1, D1, E1-E2, F1,
G1-G2 fixes are shipped.

**Next step:** Step back and assess the GOT model completeness question from
`docs/UI_VISION.md` -- do surfaces self-present on corpus load without any user
action? That is the redesign gate criterion. Read UI_VISION.md and evaluate
against dj2 -- which surfaces auto-populate on load, which require user action.

**Deferred (do not start):** G3 (corpus switch loses context), G4 (tool
transparency), L1-L4 (cloud model routing) -- architectural, not yet.

**Server start (standing note):** always use `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`. Never use pyenv/system Python.
