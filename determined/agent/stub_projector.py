# determined/agent/stub_projector.py
#
# Given a stub function, gather its call-graph context and behavioral
# contracts, then ask Ollama to suggest a concrete implementation.
#
# The key insight: the stub's callers constrain what it must accept and
# return; the stub's expected callees (inferred from sibling functions in
# the same file) constrain what it can call. The contracts on those
# neighbors pin down the behavioral envelope. The LLM fills the body
# within those guardrails -- not open-ended generation.
#
# Usage (CLI):
#   python -m determined.agent.stub_projector <corpus.db> <function_name>
#   python -m determined.agent.stub_projector <corpus.db> --all [--limit N]

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional


# ------------------------------------------------------------------
# Context gathering
# ------------------------------------------------------------------

def _get_stub(conn: sqlite3.Connection, name: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT file_path, name, line_number, return_type, arguments_json, docstring "
        "FROM functions WHERE name = ? AND is_stub = 1 LIMIT 1",
        (name,),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def _get_callers(conn: sqlite3.Connection, stub_name: str, limit: int = 5) -> list[dict]:
    # callee may be stored as bare name OR fully-qualified (module.name)
    rows = conn.execute(
        """
        SELECT DISTINCT ge.caller, f.file_path, f.docstring
        FROM graph_edges ge
        LEFT JOIN functions f ON f.name = ge.caller
        WHERE (ge.callee = ? OR ge.callee LIKE ?) AND ge.caller != ?
        LIMIT ?
        """,
        (stub_name, f"%.{stub_name}", stub_name, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _get_sibling_callees(conn: sqlite3.Connection, stub_name: str, file_path: str, limit: int = 8) -> list[str]:
    """Functions that siblings in the same file call — hints at what's available."""
    rows = conn.execute(
        """
        SELECT DISTINCT ge.callee
        FROM graph_edges ge
        JOIN functions f ON f.name = ge.caller
        WHERE f.file_path = ? AND ge.caller != ? AND f.is_stub = 0
        LIMIT ?
        """,
        (file_path, stub_name, limit),
    ).fetchall()
    # strip module prefix so names are usable in prompt
    return [r[0].rsplit(".", 1)[-1] if "." in r[0] else r[0] for r in rows]


def _get_contracts(conn: sqlite3.Connection, function_names: list[str]) -> list[dict]:
    if not function_names:
        return []
    # strip module prefixes so bare names match behavioral_contracts.function_name
    bare_names = list({n.rsplit(".", 1)[-1] for n in function_names})
    placeholders = ",".join("?" * len(bare_names))
    rows = conn.execute(
        f"SELECT function_name, description, side_effects_json, raises_json, testable_behaviors_json "
        f"FROM behavioral_contracts WHERE function_name IN ({placeholders})",
        bare_names,
    ).fetchall()
    return [dict(r) for r in rows]


def _get_source_lines(file_path: str, around_line: int, window: int = 30) -> str:
    try:
        lines = Path(file_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        start = max(0, around_line - 3)
        end = min(len(lines), around_line + window)
        return "\n".join(f"{i+1:4d}  {l}" for i, l in enumerate(lines[start:end], start=start))
    except Exception:
        return ""


def gather_context(conn: sqlite3.Connection, stub_name: str) -> Optional[dict]:
    stub = _get_stub(conn, stub_name)
    if not stub:
        return None

    callers = _get_callers(conn, stub_name)
    caller_names = [c["caller"] for c in callers if c["caller"]]
    sibling_callees = _get_sibling_callees(conn, stub_name, stub["file_path"])
    contracts = _get_contracts(conn, caller_names)

    source_snippet = _get_source_lines(stub["file_path"], stub["line_number"])

    return {
        "stub": stub,
        "callers": callers,
        "sibling_callees": sibling_callees,
        "contracts": contracts,
        "source_snippet": source_snippet,
    }


# ------------------------------------------------------------------
# Prompt construction
# ------------------------------------------------------------------

def _build_prompt(ctx: dict) -> str:
    stub = ctx["stub"]
    args = json.loads(stub["arguments_json"] or "[]")
    sig = f"def {stub['name']}({', '.join(args)})"
    if stub["return_type"]:
        sig += f" -> {stub['return_type']}"

    lines = [
        "You are a Python developer. Implement the following stub function.",
        "Return ONLY the function body as valid Python (no def line, no markdown).",
        "Use only what is available in the context below. Do not import new modules.",
        "",
        f"STUB SIGNATURE: {sig}",
    ]

    if stub["docstring"]:
        lines += ["", f'DOCSTRING: """{stub["docstring"]}"""']

    if ctx["callers"]:
        lines += ["", "CALLED BY:"]
        for c in ctx["callers"]:
            lines.append(f"  - {c['caller']}" + (f": {c['docstring'][:80]}" if c["docstring"] else ""))

    if ctx["contracts"]:
        lines += ["", "BEHAVIORAL CONTRACTS ON CALLERS:"]
        for c in ctx["contracts"]:
            lines.append(f"  {c['function_name']}:")
            if c["description"]:
                lines.append(f"    description: {c['description'][:120]}")
            behaviors = json.loads(c["testable_behaviors_json"] or "[]")
            for b in behaviors[:3]:
                lines.append(f"    expects: {b}")
            raises = json.loads(c["raises_json"] or "[]")
            for r in raises[:2]:
                lines.append(f"    raises: {r}")

    if ctx["sibling_callees"]:
        lines += ["", "FUNCTIONS AVAILABLE IN THIS MODULE (siblings call these):"]
        lines.append("  " + ", ".join(ctx["sibling_callees"][:8]))

    if ctx["source_snippet"]:
        lines += ["", "SURROUNDING SOURCE CONTEXT:"]
        lines.append("```python")
        lines.append(ctx["source_snippet"])
        lines.append("```")

    lines += [
        "",
        "Write only the indented function body. No def line. No explanation.",
    ]

    return "\n".join(lines)


# ------------------------------------------------------------------
# Ollama call
# ------------------------------------------------------------------

def _call_ollama(prompt: str) -> str:
    import requests
    from determined.intent.semantic_summary import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as exc:
        return f"# [Ollama error: {exc}]"


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def project_stub(db_path: str, stub_name: str, *, verbose: bool = False) -> dict:
    """
    Return a projection dict for one stub:
      { stub_name, file_path, line_number, suggested_body, context_summary }
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    ctx = gather_context(conn, stub_name)
    conn.close()

    if ctx is None:
        return {"stub_name": stub_name, "error": "not found or not a stub"}

    if verbose:
        print(f"\nProjecting: {stub_name}")
        print(f"  callers: {[c['caller'] for c in ctx['callers']]}")
        print(f"  contracts: {[c['function_name'] for c in ctx['contracts']]}")
        print(f"  sibling callees: {ctx['sibling_callees']}")

    prompt = _build_prompt(ctx)
    body = _call_ollama(prompt)

    return {
        "stub_name": stub_name,
        "file_path": ctx["stub"]["file_path"],
        "line_number": ctx["stub"]["line_number"],
        "suggested_body": body,
        "context_summary": {
            "callers": len(ctx["callers"]),
            "contracts": len(ctx["contracts"]),
            "sibling_callees": len(ctx["sibling_callees"]),
        },
    }


def project_all_stubs(db_path: str, limit: int = 5, *, verbose: bool = False) -> list[dict]:
    conn = sqlite3.connect(db_path)
    stubs = conn.execute(
        "SELECT name FROM functions WHERE is_stub = 1 ORDER BY file_path, line_number LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()

    results = []
    for (name,) in stubs:
        result = project_stub(db_path, name, verbose=verbose)
        results.append(result)
        if verbose:
            print(f"\n--- {name} ---")
            print(result.get("suggested_body", result.get("error", "")))

    return results


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project stub implementations from call-graph context.")
    parser.add_argument("db_path", help="Corpus DB path")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("function_name", nargs="?", help="Name of the stub function to project")
    group.add_argument("--all", action="store_true", help="Project all stubs in the corpus")
    parser.add_argument("--limit", type=int, default=5, help="Max stubs when using --all (default 5)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.all:
        results = project_all_stubs(args.db_path, limit=args.limit, verbose=args.verbose)
        for r in results:
            print(f"\n=== {r['stub_name']} ({r.get('file_path','')}) ===")
            print(r.get("suggested_body", r.get("error", "")))
    else:
        r = project_stub(args.db_path, args.function_name, verbose=args.verbose)
        print(f"\n=== {r['stub_name']} ===")
        print(r.get("suggested_body", r.get("error", "")))
