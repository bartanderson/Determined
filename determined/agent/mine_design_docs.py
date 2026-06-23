#!/usr/bin/env python3
"""
Mine game design documents into knowledge.db as design_note artifacts.
Run once per corpus DB to seed design intent before code analysis.

Usage:
    python -m determined.agent.mine_design_docs.py corpus.db
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor

# Each entry: (subject, content)
# subject matches either the system name or the actual filename in world/
# kind is always "design_note", provenance "human-confirmed"
DESIGN_NOTES = [
    # ---------------------------------------------------------------
    # Overall Architecture
    # ---------------------------------------------------------------
    (
        "architecture",
        "Deterministic simulation engine augmented by constrained AI presentation layer. "
        "Separation of concerns: WorldState (canonical truth) → EventLog (causal history) → "
        "EscalationEngine (causal propagation) → ContextBuilder (perception assembly) → "
        "AI/Narrative (presentation only). "
        "AI must NOT mutate authoritative state, invent canonical truth, or bypass deterministic systems. "
        "Structured adjudication outputs pass through unchanged. "
        "Priorities: deterministic behavior, replayability, inspectable causal flow, explicit authority boundaries.",
    ),
    (
        "build_sequence",
        "Build order: (1) EventLog + EscalationEngine (core truth layer); "
        "(2) ContextBuilder + EntityResolution (world interpretation layer); "
        "(3) DialogSystem + QuestSystem + Perception/Discovery (gameplay logic layer); "
        "(4) FSMGenerator (tooling, non-runtime); "
        "(5) UIContract (interface, data shape only); "
        "(6) CombatSystem (simulation stress, depends on full system stability).",
    ),
    # ---------------------------------------------------------------
    # EventLog  (world/event_log.py)
    # ---------------------------------------------------------------
    (
        "EventLog",
        "Authoritative causal history: records every significant occurrence with timestamp, type, "
        "source system, and actor. Events are immutable after emission. "
        "Does NOT determine narrative meaning, salience, visibility, or interpretation. "
        "Consumers: EscalationEngine (derives follow-up events), ContextBuilder (filters into salience context), "
        "Narrative Engine (converts to prose), UI Layer (visualizes). "
        "Events use AttrDict for dot-access to data fields.",
    ),
    (
        "event_log.py",
        "Implements the EventLog: authoritative causal history. "
        "Events are immutable after emission, ordered chronologically, reference entities. "
        "AttrDict wrapper enables dot-access (event.data.entity_id) on all event data fields. "
        "Subscribers: EscalationEngine, ContextBuilder, Narrative/UI.",
    ),
    # ---------------------------------------------------------------
    # EscalationEngine  (world/escalation_engine.py)
    # ---------------------------------------------------------------
    (
        "EscalationEngine",
        "Deterministic causal propagation layer. Evaluates EventLog events against declarative YAML rules. "
        "Emits follow-up events and maintains active effects (world state modifiers) queryable by ContextBuilder. "
        "Rule format: YAML with triggering event, conditions, actions (registered Python functions). "
        "Anti-loop safety: depth guard stored on Event (event.depth >= MAX_DEPTH stops processing). "
        "Must NOT rewrite prior events, mutate WorldState directly, or perform narrative reasoning. "
        "Think: EventLog='what happened', EscalationEngine='what additional consequences follow'.",
    ),
    (
        "escalation_engine.py",
        "Implements EscalationEngine: YAML-rule-driven causal propagation. "
        "Evaluates events, executes registered Python action functions, emits derived events via EventLog. "
        "Maintains persistent active_effects list (queryable by ContextBuilder). "
        "Depth guard on event.depth prevents infinite rule loops.",
    ),
    # ---------------------------------------------------------------
    # ContextBuilder  (world/context_builder.py)
    # ---------------------------------------------------------------
    (
        "ContextBuilder",
        "Deterministic perception and context assembly layer. Consumer of simulation state - NOT a mutator. "
        "Inputs: WorldState, EventLog, EscalationEngine active_effects, session_id. "
        "Outputs: UnifiedContext (JSON-serializable) with visible_entities, hidden_entities, "
        "partially_known_entities, environment, awareness (known_threats, known_allies), "
        "escalation overlays, knowledge_gaps, combat_context. "
        "Visibility computed exactly once per build cycle. "
        "Escalation effects applied BEFORE knowledge gap construction and FSM injection. "
        "Purpose: give AI/DM a filtered, salience-ranked world view without raw simulation data.",
    ),
    (
        "context_builder.py",
        "Implements ContextBuilder: deterministic perception assembly. "
        "Produces UnifiedContext for AI/DM and UI. "
        "Applies EscalationEngine active_effects to visibility, threat interpretation, and awareness. "
        "Visibility computed once per build cycle. "
        "Key output sections: visible_entities, hidden_entities, environment, awareness, knowledge_gaps.",
    ),
    # ---------------------------------------------------------------
    # EntityResolution  (world/entity_resolver.py)
    # ---------------------------------------------------------------
    (
        "EntityResolution",
        "Maps player natural language phrases to actual game objects (items, NPCs, locations, skills, spells). "
        "Multi-stage resolution: (1) Exact match (case-insensitive), (2) Synonym mapping, "
        "(3) Embedding-based similarity (cosine >= 0.8 threshold, replaces fuzzy match). "
        "Input: resolved intent fields (frame.item, frame.target from IntentParser), current context. "
        "v1: global synonyms as class variable. Contextual inference ('it', 'that') deferred to v2. "
        "EscalationEngine effects may influence candidate ranking but cannot alter embedding values or canonical indices.",
    ),
    (
        "entity_resolver.py",
        "Implements EntityResolution: multi-stage lookup for player-typed entity names. "
        "Stages: exact match → synonym mapping → embedding similarity (cosine >= 0.8). "
        "Pre-computes embeddings per index load (~10ms per phrase at runtime). "
        "v1 scope: global synonyms, no contextual inference.",
    ),
    # ---------------------------------------------------------------
    # DialogSystem  (world/models/dialog.py)
    # ---------------------------------------------------------------
    (
        "DialogSystem",
        "Branching NPC conversations represented as FSMs (JSON/YAML declarative). "
        "Each node: NPC text, player choices, conditions (skill checks, reputation, flags, inventory), "
        "actions (give items, start quests, modify faction), and next state. "
        "Player selects by number or keyword (resolved via EntityResolution). "
        "Integrates with EntityResolution (choice mapping) and EventLog (dialogue events). "
        "FSM loaded by generic FSM engine (world/fsm/generic_fsm.py).",
    ),
    (
        "dialog.py",
        "Implements DialogSystem data model: FSM-based branching conversations. "
        "Declarative JSON/YAML definition with states, choices, conditions, and actions. "
        "Loaded by generic FSM engine; integrates with EntityResolution for choice matching.",
    ),
    # ---------------------------------------------------------------
    # QuestSystem  (world/quest_manager.py)
    # ---------------------------------------------------------------
    (
        "QuestSystem",
        "State-driven quest management using FSMs. "
        "States: inactive, active, completed, failed, abandoned. "
        "Transitions triggered by events with guard conditions and side-effect actions. "
        "v1 scope: static pre-authored JSON quests, no level scaling, no time limits, no quest chains, no persistence. "
        "QuestManager holds active quest instances per character/session, listens to game events. "
        "Integrates with dialog (NPCs give/update quests) and event system (kills trigger progress). "
        "Dynamic/procedural quest generation deferred to v2.",
    ),
    (
        "quest_manager.py",
        "Implements QuestSystem: FSM-based quest state management. "
        "Loads static JSON quest definitions; manages active quest instances per session. "
        "Listens to EventLog events to trigger transitions (e.g., kill events → quest progress). "
        "v1: no persistence, no chains, no time limits.",
    ),
    # ---------------------------------------------------------------
    # Perception & Discovery  (handled by context_builder + world state)
    # ---------------------------------------------------------------
    (
        "PerceptionSystem",
        "Hidden entity model: entities exist as visible / hidden / partially known. "
        "Hidden entities originate from location definitions, encounter data, or EscalationEngine effects. "
        "Player actions triggering perception: look, listen, search, investigate. "
        "Each maps to a skill resolution attempt (Perception, Investigation). "
        "Resolution yields: success / failure / partial. "
        "DM/AI overlay may expand narrative based on resolution. "
        "System is a consumer of ContextBuilder's knowledge_gaps and visibility data.",
    ),
    # ---------------------------------------------------------------
    # CombatSystem  (adjudication_engine.py + FSM)
    # ---------------------------------------------------------------
    (
        "CombatSystem",
        "Turn-based combat: single PC vs single enemy in v1 (multiple enemies deferred). "
        "Turn order by initiative roll at start. "
        "Actions: attack (melee), defend (+defense for one turn), use item (healing potion), flee (skill check). "
        "Enemy AI: attacks player each turn. Death: HP <= 0. "
        "Declarative FSM (JSON) driven by data; guards and actions in Python. "
        "Emits events: combat.attack.resolved, combat.entity.killed, combat.ended. "
        "Integrates: AdjudicationEngine.start_combat (called by encounter FSM); "
        "ContextBuilder consumes get_combat_context() for combat_context in UnifiedContext; "
        "QuestManager listens to combat.entity.killed for kill objectives. "
        "v2: status effects, multiple enemies, environmental hazards.",
    ),
    (
        "adjudication_engine.py",
        "Central game action router and simulation state mutator. "
        "Only adjudication-like systems are permitted to mutate canonical WorldState. "
        "Provides AdjudicationEngine.start_combat (entry point for CombatSystem via encounter FSM). "
        "Enforces the authority boundary: only this layer writes authoritative game state changes.",
    ),
    # ---------------------------------------------------------------
    # FSMGenerator  (world/fsm/generic_fsm.py)
    # ---------------------------------------------------------------
    (
        "FSMGenerator",
        "Generic FSM loader and executor for dialog, quest, combat, and encounter FSMs. "
        "Non-runtime tooling: helps build declarative state machines from JSON/YAML data. "
        "Used by DialogSystem, QuestSystem, and CombatSystem. "
        "Not part of runtime game flow itself - it is the engine that runs the FSM definitions.",
    ),
    (
        "generic_fsm.py",
        "Implements the generic FSM engine. "
        "Loads FSM definitions from JSON/YAML; manages state, transitions, guards, and actions. "
        "Used by DialogSystem, QuestSystem, CombatSystem, and EncounterSystem.",
    ),
    # ---------------------------------------------------------------
    # Narrative/AI layer
    # ---------------------------------------------------------------
    (
        "NarrativeEngine",
        "AI presentation and expression layer only. "
        "May: narrate, summarize, contextualize, roleplay, generate prose from events. "
        "Must NOT: mutate authoritative state, alter structured outputs, invent canonical truth, bypass deterministic systems. "
        "Consumes UnifiedContext from ContextBuilder and structured outputs from simulation layer. "
        "LLMs are implementation assistants, not architectural authorities (00A §7).",
    ),
    (
        "narrative_engine.py",
        "Implements the AI/Narrative presentation layer. "
        "Converts simulation state (UnifiedContext from ContextBuilder) into prose for the player. "
        "Strictly a consumer - no mutations to WorldState or EventLog.",
    ),
    (
        "narrative_system.py",
        "Narrative system supporting narrative_engine.py. "
        "Provides prose generation and DM storytelling capabilities. "
        "Presentation layer only - no simulation state mutations.",
    ),
    # ---------------------------------------------------------------
    # WorldState / WorldSession
    # ---------------------------------------------------------------
    (
        "WorldState",
        "Canonical simulation truth. Contains authoritative entity state, positions, combat state, "
        "inventories, flags, persistent world data. "
        "No other system may silently redefine canonical world truth. "
        "Only adjudication-like systems (AdjudicationEngine) may mutate it.",
    ),
    (
        "world_session.py",
        "Session-level world state container. "
        "Holds the authoritative WorldState for a play session. "
        "Coordinates the top-level simulation: EventLog, EscalationEngine, ContextBuilder, and AdjudicationEngine together.",
    ),
]


def main(db_path: str) -> None:
    oracle = DBOracle(db_path)
    assessor = Assessor(oracle)

    stored = 0
    skipped = 0
    for subject, content in DESIGN_NOTES:
        # Check if already exists to avoid duplicates
        existing = assessor.get_artifacts(subject)
        has_design_note = any(a["kind"] == "design_note" for a in existing)
        if has_design_note:
            print(f"  SKIP  {subject} (already has design_note)")
            skipped += 1
            continue
        assessor.add_artifact(subject, "design_note", content, provenance="human-confirmed")
        print(f"  STORED  {subject}")
        stored += 1

    print(f"\n{stored} design notes stored, {skipped} skipped (already present).")
    print(f"Knowledge DB: {oracle.db_path.replace('corpus.db', 'knowledge.db') if hasattr(oracle, 'db_path') else 'alongside corpus'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m determined.agent.mine_design_docs.py <corpus.db>")
        sys.exit(1)
    main(sys.argv[1])
