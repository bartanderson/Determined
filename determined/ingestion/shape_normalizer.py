# determined/ingestion/shape_normalizer.py
#
# Normalizer: takes high-confidence directed_graph findings from shape_scanner
# and writes their edges to graph_edges, their nodes/actions/guards to
# knowledge_artifacts. Driven by scanner output — not format-specific.
#
# Public API:
#   normalize_findings(root, conn, min_confidence) -> NormalizationResult
#   normalize_file(path, conn, fsm_name)           -> NormalizationResult

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from determined.ingestion.shape_scanner import (
    _parse_structured,
    _node_collection_pass,
    _topology_pass,
    _FROM_KEYS,
    _TO_KEYS,
)


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

@dataclass
class NormalizationResult:
    file: str
    edges_written: int = 0
    nodes_written: int = 0
    actions_written: int = 0
    skipped: bool = False       # True if already normalized (idempotent)
    error: str = ""


# ---------------------------------------------------------------------------
# Edge/node extraction from parsed structured data
# ---------------------------------------------------------------------------

def _extract_edges(obj: Any) -> list[dict]:
    """
    Walk the parsed structure and extract all transition-like objects.
    Returns list of dicts: {from, to, event, actions, cond}
    """
    edges: list[dict] = []

    def _walk(o: Any, event_name: str = "") -> None:
        if isinstance(o, dict):
            from_val = None
            to_val = None
            for k, v in o.items():
                if k in _FROM_KEYS and isinstance(v, str):
                    from_val = v
                if k in _TO_KEYS and isinstance(v, str):
                    to_val = v
            if from_val and to_val:
                edges.append({
                    "from": from_val,
                    "to": to_val,
                    "event": event_name,
                    "actions": o.get("actions", []),
                    "cond": o.get("cond", ""),
                })
            # Descend — pass event name down through "events" dict keys
            for k, v in o.items():
                child_event = k if k not in _FROM_KEYS | _TO_KEYS else event_name
                _walk(v, child_event)
        elif isinstance(o, list):
            for v in o:
                _walk(v, event_name)

    _walk(obj)
    return edges


def _extract_nodes(obj: Any) -> list[dict]:
    """
    Extract named nodes from node_collection_pass, with any metadata present.
    Returns list of dicts: {name, initial, final, prompt}
    """
    nodes: list[dict] = []

    def _walk(o: Any) -> None:
        if isinstance(o, list):
            name_hits = []
            for item in o:
                if isinstance(item, dict):
                    for k in ("name", "id", "key", "label", "title"):
                        if k in item and isinstance(item[k], str):
                            name_hits.append(item)
                            break
            if len(name_hits) >= 2:
                for item in name_hits:
                    name = next(
                        item[k] for k in ("name", "id", "key", "label", "title")
                        if k in item and isinstance(item[k], str)
                    )
                    nodes.append({
                        "name": name,
                        "initial": item.get("initial", False),
                        "final": item.get("final", False),
                        "prompt": item.get("prompt", ""),
                    })
        if isinstance(o, dict):
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)

    _walk(obj)
    # Deduplicate by name
    seen: set[str] = set()
    unique = []
    for n in nodes:
        if n["name"] not in seen:
            seen.add(n["name"])
            unique.append(n)
    return unique


def _extract_actions(obj: Any, fsm_name: str) -> list[dict]:
    """
    Extract named actions/guards from top-level 'actions' and 'guards' keys.
    Returns list of dicts: {name, kind, description}
    """
    items: list[dict] = []
    if not isinstance(obj, dict):
        return items
    for section_key, artifact_kind in (("actions", "fsm_action"), ("guards", "fsm_guard")):
        section = obj.get(section_key, {})
        if not isinstance(section, dict):
            continue
        for name, data in section.items():
            desc = data.get("description", "") if isinstance(data, dict) else str(data)
            items.append({"name": name, "kind": artifact_kind, "description": desc})
    return items


# ---------------------------------------------------------------------------
# Write to DB
# ---------------------------------------------------------------------------

def _already_normalized(conn: sqlite3.Connection, rel_path: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM graph_edges WHERE caller_file = ? AND edge_type = 'config_edge'",
        (rel_path,),
    ).fetchone()
    return (row[0] or 0) > 0


def normalize_file(
    path: Path,
    conn: sqlite3.Connection,
    root: Path,
    fsm_name: str = "",
) -> NormalizationResult:
    """
    Parse one structured file and write its directed-graph representation to the DB.
    Idempotent: skips if config_edge rows for this file already exist.
    """
    rel_path = str(path.relative_to(root)).replace("\\", "/")
    result = NormalizationResult(file=rel_path)

    if _already_normalized(conn, rel_path):
        result.skipped = True
        return result

    obj = _parse_structured(path)
    if obj is None:
        result.error = "could not parse"
        return result

    if not fsm_name:
        fsm_name = obj.get("name", path.stem) if isinstance(obj, dict) else path.stem

    now = datetime.now(timezone.utc).isoformat()

    # Write nodes
    nodes = _extract_nodes(obj)
    for node in nodes:
        name = node["name"]
        flags = []
        if node.get("initial"):
            flags.append("initial")
        if node.get("final"):
            flags.append("final")
        content_parts = [f"flags: {', '.join(flags)}"] if flags else []
        if node.get("prompt"):
            content_parts.append(f"prompt: {node['prompt']}")
        content = "; ".join(content_parts) or name
        conn.execute(
            """
            INSERT OR IGNORE INTO knowledge_artifacts
              (subject, kind, content, provenance, created_at, needs_review)
            VALUES (?, 'fsm_state', ?, ?, ?, 0)
            """,
            (f"{fsm_name}.{name}", content, rel_path, now),
        )
        result.nodes_written += 1

    # Write edges
    edges = _extract_edges(obj)
    for edge in edges:
        from_state = edge["from"]
        to_state = edge["to"]
        event = edge["event"]
        actions = edge.get("actions", [])
        cond = edge.get("cond", "")

        source_id = f"{fsm_name}.{from_state}"
        target_id = f"{fsm_name}.{to_state}"

        conn.execute(
            """
            INSERT INTO graph_edges
              (source_id, target_id, caller, callee, caller_file, resolved, edge_type)
            VALUES (?, ?, ?, ?, ?, 1, 'config_edge')
            """,
            (source_id, target_id, from_state, to_state, rel_path),
        )
        result.edges_written += 1

        # Store action linkage
        for action_name in actions:
            label = f"on {event}: {from_state} -> {to_state}"
            if cond:
                label += f" [guard: {cond}]"
            conn.execute(
                """
                INSERT OR IGNORE INTO knowledge_artifacts
                  (subject, kind, content, provenance, created_at, needs_review)
                VALUES (?, 'fsm_action', ?, ?, ?, 0)
                """,
                (f"{fsm_name}.{action_name}", label, rel_path, now),
            )

    # Write named actions/guards with descriptions
    for item in _extract_actions(obj, fsm_name):
        subject = f"{fsm_name}.{item['name']}"
        existing = conn.execute(
            "SELECT id, content FROM knowledge_artifacts WHERE subject = ? AND kind = ?",
            (subject, item["kind"]),
        ).fetchone()
        if existing and item["description"]:
            merged = f"{existing[1]}; desc: {item['description']}"
            conn.execute(
                "UPDATE knowledge_artifacts SET content = ? WHERE id = ?",
                (merged, existing[0]),
            )
        elif not existing:
            conn.execute(
                """
                INSERT INTO knowledge_artifacts
                  (subject, kind, content, provenance, created_at, needs_review)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (subject, item["kind"], item["description"] or item["name"], rel_path, now),
            )
        result.actions_written += 1

    conn.commit()
    return result


# ---------------------------------------------------------------------------
# Corpus-wide normalization driven by shape_finder results
# ---------------------------------------------------------------------------

def normalize_findings(
    root: str | Path,
    conn: sqlite3.Connection,
    min_confidence: float = 0.7,
) -> list[NormalizationResult]:
    """
    Query knowledge_artifacts for high-confidence directed_graph findings,
    normalize each source file into graph_edges.

    Returns list of NormalizationResult, one per file attempted.
    """
    root = Path(root)
    rows = conn.execute(
        """
        SELECT subject, content FROM knowledge_artifacts
        WHERE kind = 'shape_finding'
        ORDER BY subject
        """
    ).fetchall()

    results: list[NormalizationResult] = []
    for rel_path, content_str in rows:
        try:
            data = json.loads(content_str)
        except (json.JSONDecodeError, TypeError):
            continue

        if data.get("kind") != "directed_graph":
            continue
        if data.get("confidence", 0.0) < min_confidence:
            continue

        full_path = root / rel_path
        if not full_path.exists():
            r = NormalizationResult(file=rel_path, error="file not found")
            results.append(r)
            continue

        r = normalize_file(full_path, conn, root)
        results.append(r)

    return results


# ---------------------------------------------------------------------------
# Human-readable summary
# ---------------------------------------------------------------------------

def summarize_normalization(results: list[NormalizationResult]) -> str:
    if not results:
        return "shape_normalizer: no directed_graph findings to normalize."

    written = [r for r in results if not r.skipped and not r.error]
    skipped = [r for r in results if r.skipped]
    errors  = [r for r in results if r.error]

    total_edges = sum(r.edges_written for r in written)
    total_nodes = sum(r.nodes_written for r in written)

    parts = [f"shape_normalizer: {len(written)} file(s) normalized"]
    if total_edges:
        parts.append(f"{total_edges} edge(s)")
    if total_nodes:
        parts.append(f"{total_nodes} node(s)")
    if skipped:
        parts.append(f"{len(skipped)} skipped (already done)")
    if errors:
        parts.append(f"{len(errors)} error(s)")
    return ", ".join(parts) + "."
