Written at commit: b708f33 (2026-07-22)

# SESSION STATE — session 234

## Active branch: main [V]

## What happened this session

**Housekeeping / orientation (session 234):**
- Drift from s233 handoff: 2 commits had already landed (1f41cfa capn fix, 066e252
  return_type + import signals) — both from s233's next list, both now done.
- Committed `.claude/hooks/validate_shell.py` + updated `.claude/settings.json` [V]
  (140f7ac) — PreToolUse hook blocks Bash-isms in PowerShell and Windows paths in Bash.
- Verified `python3 == python` (both 3.11.9) in this environment. Memory updated.
- Closed untapped signals #4: `behavioral_contracts` / `contract_violations` tables
  do not exist in dj2 DB schema. Marked all 4 untapped signals done in TRACKER.md.
- Wrote `docs/VISUAL_PROJECTION.md` — full implementation spec for Phases 1–3 of the
  visual projection work (all gates cleared). No code written yet.

## Signal fusion state [V]

All signals wired end-to-end:
- Convention (family, size, is_outlier)
- Chain (position, bonus)
- Artifact (dead, inline_notes, design_note)
- return_type existence check
- Import concept cross-check
- Breadth view: signal table (Shape tab "Signal table ↵" button)
- Depth view: spotlight SIGNAL CONVERGENCE table

## NEXT SESSION — start here

Read `docs/VISUAL_PROJECTION.md` first. Full Phase 1–3 spec is there, ready to implement.
No questions outstanding. No backend changes needed for any phase.

**Phase 1 first** (~30 min, 2 lines of new code + 1 data attribute):

File: `determined/ui/templates/console.html`

1. Add `data-family="${escHtml(r.convention_family || '')}"` to `.fusion-row` TR element
   (currently at ~line 4508, inside `data.rows.map(...)` in `stub_fusion_table_result` handler).

2. Extend the click handler (~line 4519–4522):
   ```javascript
   document.getElementById("fusion-table-wrap").addEventListener("click", e => {
     const row = e.target.closest(".fusion-row");
     if (!row) return;
     const sym = row.dataset.sym;
     openSpotlight(sym);
     gxInput.value = sym;   // NEW
     gxMap(sym);            // NEW
   });
   ```

Validate: click table row → spotlight opens → switch to Map tab → graph shows that symbol.

**Phase 2** (~1 session): family grouping. Extract row rendering into `fusionRowHtml()`,
add `fusionTableRender()`, family header rows with click-to-filter. All in spec.

**Phase 3** (~30 min): `fusionConvergenceRender()` — signal frequency summary line above table.

## Known issues [V = verified, ? = recalled]

**dead artifact LIKE over-match [V]:** `WHERE kind='dead' AND subject LIKE '%{name}'`
over-matches when name is a suffix of another symbol. Documented in test. Fix if noisy.

**load_db auto-orient blocks screenshot [V]:** background LLM thread on corpus load
causes screenshot tool to hang. Workaround: DOM reads via javascript_tool.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Server start command [V]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.
