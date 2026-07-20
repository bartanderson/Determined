# determined/ingestion/shape_scanner.py
#
# Corpus-wide shape scanner: walks all non-code files, runs multi-method
# structure detection, stores findings in knowledge_artifacts (kind='shape_finding').
# Runs automatically at end of ingest — no user action required.
#
# Detection philosophy mirrors structure_induction.py: multiple independent passes,
# convergence gating, tiered confidence. Format-agnostic once parsed.
#
# Supported formats: JSON, YAML, TOML (structured); .md/.txt/.rst (prose).
# PDF/docx: noted as future — skipped for now.
#
# Public API:
#   scan_corpus(root, conn) -> list[ShapeFinding]
#   scan_file(path)         -> ShapeFinding | None

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

@dataclass
class ShapeFinding:
    file: str                    # repo-relative path
    kind: str                    # directed_graph | tree | manifest | tabular | prose_structure | flat
    confidence: float            # 0.0 – 1.0
    node_count: int = 0
    edge_count: int = 0
    missing: list[str] = field(default_factory=list)   # referenced but undefined
    notes: str = ""              # human-readable summary of signals found


# ---------------------------------------------------------------------------
# Format parsers
# ---------------------------------------------------------------------------

def _parse_structured(path: Path) -> dict | list | None:
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        if suffix in (".yaml", ".yml"):
            try:
                import yaml
                with open(path, encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except ImportError:
                return None
        if suffix == ".toml":
            try:
                import tomllib  # Python 3.11+
            except ImportError:
                try:
                    import tomli as tomllib
                except ImportError:
                    return None
            with open(path, "rb") as f:
                return tomllib.loads(f.read().decode())
    except (json.JSONDecodeError, Exception):
        return None
    return None


def _read_prose(path: Path) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Structured data passes
# ---------------------------------------------------------------------------

def _collect_all_strings(obj: Any, depth: int = 0) -> list[str]:
    """Recursively collect all string values from a parsed structure."""
    if depth > 20:
        return []
    if isinstance(obj, str):
        return [obj] if 2 <= len(obj) <= 80 and " " not in obj else []
    if isinstance(obj, dict):
        out = []
        for v in obj.values():
            out.extend(_collect_all_strings(v, depth + 1))
        return out
    if isinstance(obj, list):
        out = []
        for v in obj:
            out.extend(_collect_all_strings(v, depth + 1))
        return out
    return []


def _node_collection_pass(obj: Any) -> set[str]:
    """
    Array-consistency pass: arrays of objects sharing a 'name'/'id'/'key' field
    → candidate node ID set.
    """
    node_ids: set[str] = set()

    def _walk(o: Any) -> None:
        if isinstance(o, list) and len(o) >= 2:
            name_hits = []
            for item in o:
                if isinstance(item, dict):
                    for k in ("name", "id", "key", "label", "title"):
                        if k in item and isinstance(item[k], str):
                            name_hits.append(item[k])
                            break
            if len(name_hits) >= 2:
                node_ids.update(name_hits)
        if isinstance(o, dict):
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)

    _walk(obj)
    return node_ids


def _reference_pass(obj: Any, node_ids: set[str]) -> int:
    """
    Count string values in the doc that reference known node IDs but
    are not in a name/id/key field themselves.
    """
    if not node_ids:
        return 0

    ref_count = 0

    def _walk(o: Any, parent_key: str = "") -> None:
        nonlocal ref_count
        if isinstance(o, str):
            if o in node_ids and parent_key not in ("name", "id", "key", "label", "title"):
                ref_count += 1
        elif isinstance(o, dict):
            for k, v in o.items():
                _walk(v, k)
        elif isinstance(o, list):
            for v in o:
                _walk(v, parent_key)

    _walk(obj)
    return ref_count


_FROM_KEYS = frozenset(("from", "source", "caller", "parent", "depends", "requires", "after", "start"))
_TO_KEYS   = frozenset(("to", "target", "callee", "child", "provides", "before", "end"))


def _topology_pass(obj: Any, node_ids: set[str]) -> tuple[int, set[str]]:
    """
    Topology pass: find objects with both a source-field and a target-field
    whose values are in node_ids → candidate edges.

    Returns (edge_count, missing_refs) where missing_refs are values that
    look like node IDs referenced in transitions but not defined anywhere.
    """
    edge_count = 0
    missing: set[str] = set()

    def _walk(o: Any) -> None:
        nonlocal edge_count
        if isinstance(o, dict):
            from_val = None
            to_val = None
            for k, v in o.items():
                if k in _FROM_KEYS and isinstance(v, str):
                    from_val = v
                if k in _TO_KEYS and isinstance(v, str):
                    to_val = v
            if from_val and to_val:
                edge_count += 1
                # Check for dangling references
                if node_ids:
                    if from_val not in node_ids:
                        missing.add(from_val)
                    if to_val not in node_ids:
                        missing.add(to_val)
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)

    _walk(obj)
    return edge_count, missing


def _hierarchy_pass(obj: Any) -> int:
    """
    Hierarchy pass: nested dicts where keys appear as 'name' values elsewhere
    or where the structure is consistently nested 2+ levels deep with string keys.
    Returns a depth score (0 = flat, >2 = meaningful hierarchy).
    """
    def _max_depth(o: Any, d: int = 0) -> int:
        if isinstance(o, dict) and o:
            return max(_max_depth(v, d + 1) for v in o.values())
        if isinstance(o, list) and o:
            return max(_max_depth(v, d) for v in o)
        return d

    return _max_depth(obj)


def _classify_structured(obj: Any) -> ShapeFinding | None:
    """Run all four passes and gate on convergence."""
    node_ids  = _node_collection_pass(obj)
    ref_count = _reference_pass(obj, node_ids)
    edge_count, missing = _topology_pass(obj, node_ids)
    depth     = _hierarchy_pass(obj)

    signals: list[str] = []
    score = 0.0

    if node_ids:
        signals.append(f"node_collection({len(node_ids)})")
        score += 0.3

    if ref_count > 0:
        signals.append(f"references({ref_count})")
        score += 0.2

    if edge_count > 0:
        signals.append(f"topology({edge_count} edges)")
        score += 0.4

    if depth >= 3:
        signals.append(f"hierarchy(depth={depth})")
        score += 0.1

    if score < 0.2:
        return None  # nothing interesting

    # Classify kind based on which passes fired
    if edge_count > 0 and node_ids:
        kind = "directed_graph"
    elif edge_count > 0:
        kind = "directed_graph"  # topology without named nodes still a graph
    elif depth >= 3 and node_ids:
        kind = "tree"
    elif node_ids and ref_count > 0:
        kind = "manifest"
    else:
        kind = "flat"

    notes = "; ".join(signals)
    return ShapeFinding(
        file="",  # filled in by caller
        kind=kind,
        confidence=min(score, 1.0),
        node_count=len(node_ids),
        edge_count=edge_count,
        missing=sorted(missing),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Prose passes (markdown / text)
# ---------------------------------------------------------------------------

_ARROW_RE      = re.compile(r"\b(\w[\w\s]*?)\s*[-=]>\s*([\w][\w\s]*)", re.M)
_TABLE_ROW_RE  = re.compile(r"^\|.+\|", re.M)
_BULLET_LIST_RE = re.compile(r"^[ \t]*[-*]\s+\S", re.M)


def _classify_prose(text: str) -> ShapeFinding | None:
    arrows  = _ARROW_RE.findall(text)
    tables  = _TABLE_ROW_RE.findall(text)
    bullets = _BULLET_LIST_RE.findall(text)

    signals: list[str] = []
    score = 0.0

    if len(arrows) >= 2:
        signals.append(f"transitions({len(arrows)})")
        score += 0.5
    if len(tables) >= 3:
        signals.append(f"table_rows({len(tables)})")
        score += 0.3
    if len(bullets) >= 4:
        signals.append(f"list_items({len(bullets)})")
        score += 0.15

    if score < 0.2:
        return None

    if len(arrows) >= 2:
        kind = "directed_graph"
        edge_count = len(arrows)
    elif len(tables) >= 3:
        kind = "tabular"
        edge_count = 0
    else:
        kind = "prose_structure"
        edge_count = 0

    return ShapeFinding(
        file="",
        kind=kind,
        confidence=min(score, 1.0),
        node_count=0,
        edge_count=edge_count,
        notes="; ".join(signals),
    )


# ---------------------------------------------------------------------------
# Per-file entry point
# ---------------------------------------------------------------------------

_STRUCTURED_SUFFIXES = {".json", ".yaml", ".yml", ".toml"}
_PROSE_SUFFIXES      = {".md", ".txt", ".rst"}
_SKIP_DIRS           = {
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    "dist", "build", "archive", "Lib", "Scripts",
}


def scan_file(path: Path) -> ShapeFinding | None:
    suffix = path.suffix.lower()
    if suffix in _STRUCTURED_SUFFIXES:
        obj = _parse_structured(path)
        if obj is None:
            return None
        finding = _classify_structured(obj)
    elif suffix in _PROSE_SUFFIXES:
        text = _read_prose(path)
        if not text:
            return None
        finding = _classify_prose(text)
    else:
        return None

    if finding is None:
        return None

    finding.file = str(path)
    return finding


# ---------------------------------------------------------------------------
# Corpus walk
# ---------------------------------------------------------------------------

_CODE_SUFFIXES = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".java",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".lua", ".zig",
}


def scan_corpus(root: str | Path, conn: sqlite3.Connection) -> list[ShapeFinding]:
    """
    Walk root, scan every non-code file, store findings in knowledge_artifacts.
    Returns list of ShapeFinding for caller to report.
    """
    root = Path(root)
    now = datetime.now(timezone.utc).isoformat()
    findings: list[ShapeFinding] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in _CODE_SUFFIXES:
            continue

        finding = scan_file(path)
        if finding is None:
            continue

        rel = str(path.relative_to(root)).replace("\\", "/")
        finding.file = rel
        findings.append(finding)

        content = json.dumps({
            "kind": finding.kind,
            "confidence": round(finding.confidence, 3),
            "node_count": finding.node_count,
            "edge_count": finding.edge_count,
            "missing": finding.missing,
            "notes": finding.notes,
        })

        conn.execute(
            """
            INSERT OR REPLACE INTO knowledge_artifacts
              (subject, kind, content, provenance, created_at, needs_review)
            VALUES (?, 'shape_finding', ?, 'shape_scanner', ?, 0)
            """,
            (rel, content, now),
        )

    conn.commit()

    findings.sort(key=lambda f: f.confidence, reverse=True)
    return findings


# ---------------------------------------------------------------------------
# Human-readable summary (for ingest status emit)
# ---------------------------------------------------------------------------

def summarize(findings: list[ShapeFinding]) -> str:
    if not findings:
        return "shape_scanner: no structure found outside code files."

    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1

    parts = [f"{count} {kind}" for kind, count in sorted(by_kind.items())]
    top = findings[0]
    return (
        f"shape_scanner: {len(findings)} finding(s) — {', '.join(parts)}. "
        f"Top: {top.file} ({top.kind}, {top.confidence:.0%})"
    )
