# Claude Analysis 1 — dj2 Encounter Domain Survey

**Date:** 2026-07-30  
**Corpus:** dj2 (C_Users_bartl_dev_dj2.db)  
**Method:** Direct DB queries via Determined (stubs, graph_edges, knowledge_artifacts)

---

## Summary

The encounter system exists as a **complete island** — every layer is present but nothing connects end-to-end. All the pieces are there; none of them talk to each other.

---

## Layer-by-layer status

| Layer | File(s) | Status |
|---|---|---|
| Frontend | `static/js/travel.js` — `TravelUI.resolveEncounter`, `TravelUI.showEncounter` | Exists; calls `/api/resolve-encounter` — route status unknown |
| Travel system | `world/travel_system.py` — `generate_encounter`, `get_encounter_options`, `progress_journey` | All zero callers |
| Data model | `world/encounter_models.py` — `Encounter`, `Monster`, `EncounterPoint` | Complete (no stubs), but zero callers — fully orphaned |
| Generator | `world/encounter_generator.py` — `generate_encounter()` | Zero callers |
| Resolver | `resolver/encounter_resolver.py` — `resolve_flee()` | Zero callers; stub |
| FSM config | `config/fsms/encounter.json` — states + 3 actions + 2 guards | All actions/guards stubbed |
| World controller | `world/world_controller.py` — `_generate_encounter_points_for_region` | Exists; `test_generate_random_encounter` is dead code |
| Phases pipeline | `engine/phases.py` — `trigger_encounter` | Defined; zero callers |

---

## The missing wiring

The chain that should exist but doesn't:

```
travel_system.progress_journey      (stub)
  -> trigger_encounter              (dead, phases.py)
  -> encounter_generator.generate_encounter  (orphaned)
  -> EncounterFSM                   (encounter.json — fight / flee / parley branches)
  -> encounter_resolver.resolve_flee / resolve_parley / start_combat  (stubs)
  -> /api/resolve-encounter         (route unknown)
  -> TravelUI.resolveEncounter      (frontend — exists and works)
```

---

## Design available

- **`encounter.json` FSM** — clearest design artifact. States: `initiating`, `in_encounter`. Three resolution branches: fight, flee, parley.
- **`encounter_models.py`** — data model is complete and has no stubs. Good foundation.
- **`travel_system.py`** — all functions have docstrings describing intent.
- **Missing:** no design doc for the encounter → combat handoff. No combat system visible in corpus yet. `start_combat` is an FSM action with no implementation target.

---

## Recommendation

**Next investigative step:** check whether `/api/resolve-encounter` exists in the routes (`routes/api.py`). That tells us whether the frontend → backend connection is already built or not.

**Lowest-risk implementation path:** wire `progress_journey` → `generate_encounter` → FSM, implement flee + parley resolution only, leave `start_combat` as a stub. This delivers one complete end-to-end path without needing the combat system.
