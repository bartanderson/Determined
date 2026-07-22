# Visual Projection — Design Spec
_Written 2026-07-22. Covers Phases 1–3 of the signal fusion visual projection work
(TRACKER: FUTURE — Signal fusion + multi-modal visual projection). All gates cleared._

---

## What exists today (baseline)

**Signal table** (`stub_fusion_table_result` → `#fusion-table-body`, `console.html:4481–4522`):
- Rows are `<tr class="fusion-row" data-sym="{name}">` with 5 columns: symbol | file | classification+% | badges | score.
- Single click handler at `console.html:4519–4522`: `openSpotlight(row.dataset.sym)`.
- Each row object in `data.rows` carries: `name, file, classification, score, composite,
  convention_family, convention_size, convention_is_outlier, artifact_dead,
  artifact_inline_notes, chain_position, chain_bonus, return_type_name, return_type_exists,
  concept_in_imports`.

**Map tab / Cytoscape graph** (`console.html:1567–1649`):
- Tab: `data-tab="map"`, panel `#panel-map`. Default map view: `_mapView = "graph"`.
- `gxMap(symbol)` — destroys any existing `_cy`, clears `#gx-cy`, emits
  `socket.emit("graph_subgraph", { symbol, hops: parseInt(gxHops.value) })`.
  Renders result in `_cy` via `socket.on("graph_result", ...)`.
- `gxInput` (`#gx-input`) shows the currently graphed symbol.
- Node tap opens a popover; double-tap re-centers the graph on that node.

**Tab activation** (`console.html:1368–1388`):
- `activateTab("map")` switches to Map, sets `_mapView` visibility.

**Convention families**: each stub's `convention_family` is already returned in
`stub_fusion_table_result` rows. No new socket event is needed for Phases 1–2.

---

## Phase 1 — Table→Graph selection propagation

**Goal**: clicking a signal table row also loads that symbol's call graph in the Map tab
(background, no forced tab switch). When the user switches to Map, the graph is ready.

### Changes — `console.html` only

**1. Add `data-family` to `.fusion-row`** (`console.html:4508`, inside `data.rows.map`):

Current:
```html
<tr class="fusion-row" data-sym="${escHtml(r.name)}" style="...">
```

New:
```html
<tr class="fusion-row" data-sym="${escHtml(r.name)}" data-family="${escHtml(r.convention_family || '')}" style="...">
```

_(Needed for Phase 2; harmless to add now.)_

**2. Extend the click handler** (`console.html:4519–4522`):

Current:
```javascript
document.getElementById("fusion-table-wrap").addEventListener("click", e => {
  const row = e.target.closest(".fusion-row");
  if (row) openSpotlight(row.dataset.sym);
});
```

New:
```javascript
document.getElementById("fusion-table-wrap").addEventListener("click", e => {
  const row = e.target.closest(".fusion-row");
  if (!row) return;
  const sym = row.dataset.sym;
  openSpotlight(sym);
  gxInput.value = sym;
  gxMap(sym);
});
```

`gxMap` is already defined at `console.html:1605`. `gxInput` is already declared at `console.html:1568`.

### Behavior

- Row click → spotlight opens (existing).
- Row click → `#gx-input` fills with the symbol name.
- Row click → `graph_subgraph` socket event fires; `_cy` renders the subgraph in `#gx-cy`.
- No tab switch occurs. The user switches to Map when they want to see the graph.
- If Map tab is already active, the graph updates live.
- Map tab `gxHops` value (the existing hops selector) applies as-is.

### What does NOT change

- `openSpotlight` behavior — unchanged.
- Spotlight SIGNAL CONVERGENCE table — unchanged.
- The graph's node-tap/double-tap handlers — unchanged.
- No new socket events.

### Validation

1. Click a signal table row → spotlight opens for that symbol.
2. Switch to Map tab → graph shows that symbol's subgraph, `#gx-input` shows the symbol.
3. Click a different row → graph re-renders for the new symbol.
4. Double-tap a node in the graph → re-centers on that node (existing behavior, unbroken).

---

## Phase 2 — Naming family grouping in the signal table

**Goal**: stubs that share a convention family can be viewed as a group. Clicking a family
header filters the table to that family and highlights all members in the graph as a
multi-node subgraph.

### No new socket events needed

All data is already in the `stub_fusion_table_result` rows via `data-family` (added in
Phase 1). The family grouping is pure frontend.

### New state variables (add near `fusionTableRun`, `console.html:4472`)

```javascript
let _fusionRows  = [];          // raw data.rows from last stub_fusion_table_result
let _activeFamily = null;       // currently selected family name, or null = show all
```

### Changes to `stub_fusion_table_result` handler (`console.html:4481`)

At the start of the handler, after the error/empty guard, save the raw rows:
```javascript
_fusionRows = data.rows;
_activeFamily = null;
fusionTableRender();
```

Extract rendering into a new function `fusionTableRender()` (replaces the inline
`tbody.innerHTML = data.rows.map(...)` block):

```javascript
function fusionTableRender() {
  const tbody = document.getElementById("fusion-table-body");
  const rows  = _activeFamily
    ? _fusionRows.filter(r => r.convention_family === _activeFamily)
    : _fusionRows;

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--text3);padding:6px 0">No stubs</td></tr>`;
    return;
  }

  // Build family summary header rows if NOT filtered
  let html = "";
  if (!_activeFamily) {
    // Group by family
    const families = {};
    const ungrouped = [];
    rows.forEach(r => {
      if (r.convention_family) {
        (families[r.convention_family] = families[r.convention_family] || []).push(r);
      } else {
        ungrouped.push(r);
      }
    });
    // Families sorted by member count descending
    const sortedFamilies = Object.entries(families).sort((a, b) => b[1].length - a[1].length);
    sortedFamilies.forEach(([fam, members]) => {
      const outlierCount = members.filter(r => r.convention_is_outlier).length;
      const outlierNote  = outlierCount ? ` · <span style="color:var(--orange)">${outlierCount} ⚠</span>` : "";
      html += `<tr class="fusion-family-header" data-family="${escHtml(fam)}" style="cursor:pointer;background:var(--bg3);border-bottom:1px solid var(--border)">
        <td colspan="4" style="padding:3px 10px 3px 0;color:var(--text2);font-size:.88em">
          ▸ <strong>${escHtml(fam)}</strong> — ${members.length} stubs${outlierNote}
        </td>
        <td style="padding:3px 0;text-align:right;color:var(--text3);font-size:.82em">click to filter</td>
      </tr>`;
      members.forEach(r => { html += fusionRowHtml(r); });
    });
    ungrouped.forEach(r => { html += fusionRowHtml(r); });
  } else {
    rows.forEach(r => { html += fusionRowHtml(r); });
  }
  tbody.innerHTML = html;
}

function fusionRowHtml(r) {
  const clsColor = _CLS_COLORS[r.classification] || "var(--text3)";
  const clsLabel = _CLS_LABELS[r.classification] || r.classification;
  const badges = [];
  if (r.convention_is_outlier) badges.push(`<span style="color:var(--orange);margin-right:4px">⚠ outlier</span>`);
  if (r.artifact_dead)         badges.push(`<span style="color:var(--blue);margin-right:4px">dead</span>`);
  if (r.chain_bonus)           badges.push(`<span style="color:var(--text3);margin-right:4px">${r.chain_position}+${r.chain_bonus}</span>`);
  if (r.artifact_inline_notes) badges.push(`<span style="color:var(--text3);margin-right:4px">${r.artifact_inline_notes}n</span>`);
  const badgeStr = badges.join("") || `<span style="color:var(--text3)">—</span>`;
  return `<tr class="fusion-row" data-sym="${escHtml(r.name)}" data-family="${escHtml(r.convention_family || '')}" style="cursor:pointer;border-bottom:1px solid var(--border2)">
    <td style="padding:4px 10px 4px 0;color:var(--accent)">${escHtml(r.name)}</td>
    <td style="padding:4px 10px 4px 0;color:var(--text3)">${escHtml(r.file)}</td>
    <td style="padding:4px 10px 4px 0"><span style="color:${clsColor}">${clsLabel}</span> <span style="color:var(--text3);font-size:.88em">${Math.round(r.score * 100)}%</span></td>
    <td style="padding:4px 10px 4px 0">${badgeStr}</td>
    <td style="padding:4px 0;text-align:right;color:var(--text2)">${r.composite}</td>
  </tr>`;
}
```

_(The `_CLS_COLORS`/`_CLS_LABELS` constants at `console.html:4459–4470` are unchanged.)_

### Extend the click handler (Phase 1 handler, extended)

```javascript
document.getElementById("fusion-table-wrap").addEventListener("click", e => {
  // Family header click — filter table + graph all members
  const header = e.target.closest(".fusion-family-header");
  if (header) {
    const fam = header.dataset.family;
    if (_activeFamily === fam) {
      _activeFamily = null;   // second click clears filter
    } else {
      _activeFamily = fam;
      // Graph the first stub in this family
      const first = _fusionRows.find(r => r.convention_family === fam);
      if (first) { gxInput.value = first.name; gxMap(first.name); }
    }
    fusionTableRender();
    return;
  }

  // Stub row click — spotlight + graph
  const row = e.target.closest(".fusion-row");
  if (!row) return;
  const sym = row.dataset.sym;
  openSpotlight(sym);
  gxInput.value = sym;
  gxMap(sym);
});
```

### "Clear filter" affordance

Add a small `<span id="fusion-family-clear">` next to the Signal table button
(in the HTML, near `console.html:630`). It is `display:none` by default and reads
`✕ {familyName}`. Show it when `_activeFamily` is set; clicking it sets
`_activeFamily = null` and re-renders.

```javascript
function _updateFamilyClear() {
  const el = document.getElementById("fusion-family-clear");
  if (!el) return;
  if (_activeFamily) {
    el.textContent = `✕ ${_activeFamily}`;
    el.style.display = "";
  } else {
    el.style.display = "none";
  }
}
```

Call `_updateFamilyClear()` after every change to `_activeFamily`.

### HTML addition (near `console.html:630`)

```html
<button id="fusion-table-btn" class="send-btn" style="padding:3px 10px;font-size:.82em">Signal table ↵</button>
<span id="fusion-family-clear" style="display:none;cursor:pointer;color:var(--text3);font-size:.82em;margin-left:8px"></span>
```

### Behavior

- Signal table renders with family header rows (▸ `prefix:get — 5 stubs · 1 ⚠`) grouping stubs with the same `convention_family`. Ungrouped stubs (no family) follow.
- Clicking a family header: filters table to that family; graphs the first member; shows `✕ familyName` clear button.
- Clicking the header again (or `✕`): clears filter; shows all stubs grouped.
- Clicking a stub row: spotlight + graph (Phase 1 behavior, unchanged).
- Families sorted by member count descending (largest families first).
- Stubs within a family retain composite-score sort from the backend.

### What does NOT change

- Backend / socket events — none changed.
- `stub_fusion_table_result` data shape — unchanged.
- Spotlight behavior — unchanged.
- The graph hops selector, path finder, import graph, topology — unchanged.

### Validation

1. After Signal table loads: family header rows appear, grouping stubs that share a `convention_family`.
2. Stubs with no `convention_family` appear at the bottom, ungrouped.
3. Click a family header → table shows only that family's stubs; graph loads first member; clear button appears.
4. Click clear button or header again → all stubs and family headers return.
5. Click a stub row in filtered view → spotlight + graph (same as Phase 1).
6. Empty family (all stubs ungrouped) → no header rows, flat list.

---

## Phase 3 — Signal convergence summary

**Goal**: a one-line summary above the signal table showing which signals fire most often
across all stubs. Lets the user see the architectural pattern before drilling in.

### No new socket events, no backend changes

Derived from `_fusionRows` on render.

### New HTML (insert above `#fusion-table-wrap`, near `console.html:630`)

```html
<div id="fusion-convergence" style="display:none;font-size:.82em;color:var(--text2);margin-bottom:6px;line-height:1.6"></div>
```

### New function `fusionConvergenceRender()`

Called from `fusionTableRender()` before building the table HTML (only when
`!_activeFamily`):

```javascript
function fusionConvergenceRender() {
  const el = document.getElementById("fusion-convergence");
  if (!el || !_fusionRows.length) { if (el) el.style.display = "none"; return; }

  const n            = _fusionRows.length;
  const nOutlier     = _fusionRows.filter(r => r.convention_is_outlier).length;
  const nDead        = _fusionRows.filter(r => r.artifact_dead).length;
  const nNoImport    = _fusionRows.filter(r => r.concept_in_imports === false).length;
  const nNoRetType   = _fusionRows.filter(r => r.return_type_name && !r.return_type_exists).length;
  const nChain       = _fusionRows.filter(r => r.chain_bonus > 0).length;

  const parts = [];
  if (nOutlier)   parts.push(`<span style="color:var(--orange)">${nOutlier}/${n} outlier</span>`);
  if (nDead)      parts.push(`<span style="color:var(--blue)">${nDead} dead artifact</span>`);
  if (nNoImport)  parts.push(`<span style="color:var(--text3)">${nNoImport} concept not in imports</span>`);
  if (nNoRetType) parts.push(`<span style="color:var(--text3)">${nNoRetType} missing return type</span>`);
  if (nChain)     parts.push(`<span style="color:var(--text3)">${nChain} in chain</span>`);

  if (!parts.length) { el.style.display = "none"; return; }
  el.innerHTML = "Signals: " + parts.join(" · ");
  el.style.display = "";
}
```

### Behavior

- Appears as a single line above the table after Signal table loads, e.g.:
  `Signals: 4/10 outlier · 2 dead artifact · 3 concept not in imports`
- Hidden when table is filtered to a family (clutter when scope is narrow).
- Hidden if no signals fire across any stub.

### What does NOT change

Everything else.

### Validation

1. After Signal table loads: convergence summary line appears above the table.
2. Summary correctly counts each signal across all rows.
3. Click a family header to filter → summary line hides.
4. Clear filter → summary line reappears.
5. If no stubs have any signal → summary line hidden.

---

## Phasing and commit order

1. Phase 1 alone is a valid commit: `data-family` on rows + extended click handler.
2. Phase 2 requires Phase 1 (`data-family` already present).
3. Phase 3 requires Phase 2 (`_fusionRows` and `fusionTableRender` exist).
4. Each phase should pass the full test suite before the next starts. The fusion table
   is frontend-only; `tests/regression/test_ui_surfaces.py` is the relevant test file.

No new backend code, no new socket events, no changes to `agent_tools.py` or
`ui_server.py` in any phase.
