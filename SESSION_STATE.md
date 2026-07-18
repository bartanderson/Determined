Written at commit: 3936d0c

# SESSION STATE — session 209
Written at commit: 3936d0c

## Active branch: main [V]

## What happened this session (2026-07-18)

### 1. Design review — context modes [V]

Read UI_VISION.md, sots.md, and current console.html implementation.
Found: Design/Trace/Review mode buttons exist and are wired (setMode, banner,
tab highlights) but are COSMETIC ONLY — no surface suppression, no auto-load,
no curated experience. Just decoration.

Agreed: start with stub classification in spotlight as foundation for the
full redesign arc. Modes will become meaningful entry points once the surfaces
they curate are actually live.

### 2. RM-UI-1: Stub classification in spotlight [V — committed 3936d0c]

Full detail in TRACKER.md RM-UI-1. Summary:

**What it does:**
Opening any stub in the spotlight panel auto-runs classify_stub and renders
a "Stub Judgment" section with colored hypothesis chips, confidence %, and
evidence sentences. A "propose (classification)" button appears once judgment
arrives.

**Backend — ui_server.py:**
- New socket event: classify_stub_spotlight
- Handler calls extract_signals(oracle, symbol) + score_hypotheses(signals)
  directly (not text formatter) — returns structured JSON
- Emits classify_stub_spotlight_result:
  { symbol, top_hypothesis, top_score, uncertain, hypotheses[], signals{} }

**Frontend — console.html:**
- SP_SECTIONS: added judgment (order 2, stubOnly: true) — hidden by default
- openSpotlight: builds judgment placeholder as display:none
- symbol_quick_result: when is_stub=true for current spotlight symbol —
  reveals judgment section, appends "propose impl" button (disabled),
  emits classify_stub_spotlight
- classify_stub_spotlight_result handler: renders signal summary + colored
  hypothesis chips (green=design-intent, orange=blocked, blue=concept-not-applicable,
  grey=unknown), enables propose button labeled "propose (design)" etc.
- stub_projection handler updated to find sp-propose-btn not old sp-fill-stub-btn

**Verified live [V]:** process_consequences in dj2: design-intent-stated
(40%, green) + genuinely-unknown (20%, grey), evidence from docstring,
propose button enabled labeled "propose (design)".

**Tests [V]:** 52 pass (test_classify_stub + test_ui_surfaces)

## NEXT SESSION — start here

**UI redesign arc is active. TRACKER.md RM-UI-1 through RM-UI-4 is the roadmap.**

### RM-UI-2: Propose -> fulfill loop (do this first)

When "propose (classification)" is clicked:
1. project_stub fires with { symbol, classification: top_hypothesis }
2. handle_project_stub in ui_server.py line ~919 currently ignores classification
   — needs to pass it through to stub_projector.project_stub()
3. stub_projector.py project_stub() function needs to accept classification arg
   and frame the LLM prompt accordingly:
   - design-intent-stated: "complete the stated intent: <intent_text>"
   - blocked-on-prerequisite: "sketch the interface for <blocking concept>"
   - concept-not-applicable: note concept is absent, propose removal/stub note
   - genuinely-unknown: open-ended sketch from caller/callee context
4. Result renders in spotlight source panel, file opens in editor to stub line
   (stub_projection socket handler in console.html already does this)

**Where to look:**
- determined/ui/ui_server.py ~919: handle_project_stub (add classification pass-through)
- determined/agent/stub_projector.py: project_stub() function
- determined/ui/templates/console.html: stub_projection handler (already correct)

### RM-UI-3: Shape tab -> editor navigation [after RM-UI-2]

Clicking a file row in Shape tab results opens it in the editor.
Clicking a symbol in Shape results opens its spotlight.

### RM-UI-4: Mode = curated entry point [after RM-UI-3]

- Design mode: auto-runs Shape tab on activate
- Trace mode: auto-loads Frontier stubs with judgment visible
- Review mode: stub sweep ranked by uncertainty (most uncertain first)

## Known issues [V = verified, ? = recalled]

**RM-UI-1 propose button [V]:** button sends classification in emit but
  handle_project_stub ignores it. Fix is RM-UI-2.
**walk_call_chain TS/JS FQN [V]:** graph_edges stores FQN callers; tool
  queries bare names -> chain length 0/1. Workaround: use graph_path.
**classify_stub file_path_hint TS [V]:** path matching fails; omit file_path.
**graph_path FQN JS [V]:** some module.method pairs return no path despite edge.
**Frontier ABC UI [V]:** empty graph for arch-void ABCs. Deferred behind RM-UI arc.
**list_stubs [?]:** test fixtures appear as stubs (test/ files not filtered).
