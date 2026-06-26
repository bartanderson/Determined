"""
Bag tools for the Determined analysis agent.

The bag is the session workspace - an accumulator for typed artifacts
(edges, symbols, files, findings) discovered during an investigation.

Two kinds of bags:
  system    - auto-filled as tools run (edges_of, risk_profile, etc.)
  user:NAME - manually curated, named by the user

Tools:
  bag_status()                    - counts per bag and type
  bag_list(bag?, type?)           - contents of a bag
  bag_add(bag, type, ref, note?)  - manually add an item
  bag_label(bag, label)           - name/label a user bag
  bag_clear(bag)                  - empty a bag
  bag_report(bag?)                - structured report from bag contents
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.assessor.assessor import Assessor

SYSTEM_BAG = "system"


def _get_bags(assessor: "Assessor"):
    """Get BagStore or return an error string."""
    bags = assessor.bags
    if bags is None:
        return None, "No bag store available (knowledge.db not loaded)"
    return bags, None


# ---------------------------------------------------------------------------
# Tool: bag_status
# ---------------------------------------------------------------------------

def bag_status(assessor: "Assessor", args: dict) -> str:
    """
    Show all bags and their item counts.

    Returns a summary table: bag name, total items, breakdown by type.
    """
    bags, err = _get_bags(assessor)
    if err:
        return f"ERROR: {err}"

    status = bags.status()
    if not status:
        return ("No bags yet. Tools like edges_of and risk_profile auto-fill\n"
                "the system bag as they run. Or use bag_add to add manually.")

    labels = bags.bag_labels()
    lines = ["Bags:"]
    for bag_id, type_counts in sorted(status.items()):
        total = sum(type_counts.values())
        label = labels.get(bag_id, "")
        header = f"  [{bag_id}]" + (f"  ({label})" if label else "") + f"  — {total} item(s)"
        lines.append(header)
        for itype, count in sorted(type_counts.items()):
            lines.append(f"      {itype}: {count}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: bag_list
# ---------------------------------------------------------------------------

def bag_list(assessor: "Assessor", args: dict) -> str:
    """
    List contents of a bag.

    Args:
      bag   - bag id (default "system")
      type  - (optional) filter to one item type: "edge" | "symbol" | "file" | "finding"
    """
    bags, err = _get_bags(assessor)
    if err:
        return f"ERROR: {err}"

    bag_id = args.get("bag", SYSTEM_BAG).strip()
    item_type = args.get("type", "").strip() or None

    items = bags.list_items(bag_id=bag_id, item_type=item_type)
    if not items:
        type_clause = f" (type={item_type})" if item_type else ""
        return f"Bag '{bag_id}' is empty{type_clause}."

    # Group by item_type
    grouped: dict[str, list] = {}
    for it in items:
        grouped.setdefault(it["item_type"], []).append(it)

    lines = [f"Bag '{bag_id}'  ({len(items)} item(s)):"]
    for itype in sorted(grouped):
        group = grouped[itype]
        lines.append(f"\n  {itype.upper()} ({len(group)}):")
        for it in group:
            c = it["content"]
            note = f"  # {it['note']}" if it.get("note") else ""
            if itype == "edge":
                arrow = {"call": "calls", "import": "imports", "manual": "→",
                         "inherit": "inherits"}.get(c.get("edge_type", ""), "→")
                flag = "" if c.get("is_internal", True) else "  [external]"
                lines.append(f"    {c.get('src','')} {arrow} {c.get('dst','')}"
                              f"  [{c.get('edge_type','')}]{flag}{note}")
            elif itype == "symbol":
                fp = c.get("file_path", "").replace("\\", "/").split("/")[-1]
                lines.append(f"    {c.get('name','')}  in {fp}{note}")
            elif itype == "file":
                fp = c.get("file_path", "").replace("\\", "/")
                lines.append(f"    {fp}{note}")
            else:
                summary = str(c)[:80]
                lines.append(f"    {summary}{note}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: bag_add
# ---------------------------------------------------------------------------

def bag_add(assessor: "Assessor", args: dict) -> str:
    """
    Manually add an item to a bag.

    Args:
      bag   - target bag (default "user:default")
      type  - "symbol" | "file" | "edge" | "finding"
      ref   - the thing to add: symbol name, file path, or edge as "src->dst"
      note  - (optional) why you're keeping this
    """
    bags, err = _get_bags(assessor)
    if err:
        return f"ERROR: {err}"

    bag_id = args.get("bag", "user:default").strip()
    item_type = args.get("type", "").strip()
    ref = args.get("ref", "").strip()
    note = args.get("note", "").strip() or None

    if not ref:
        return "ERROR: ref is required (symbol name, file path, or 'src->dst' for edges)"
    if not item_type:
        return "ERROR: type is required: symbol | file | edge | finding"

    added = False
    if item_type == "symbol":
        # Look up file from corpus
        fp = ""
        if assessor.oracle:
            row = assessor.oracle.conn.execute(
                "SELECT file_path FROM functions WHERE name = ? "
                "UNION SELECT file_path FROM classes WHERE name = ? LIMIT 1",
                (ref, ref)
            ).fetchone()
            if row:
                fp = row[0]
        added = bags.add_symbol(bag_id, ref, fp, note=note)
    elif item_type == "file":
        added = bags.add_file(bag_id, ref, note=note)
    elif item_type == "edge":
        # Parse "src->dst" or "src → dst"
        for sep in ("->", "→", " > "):
            if sep in ref:
                src, dst = ref.split(sep, 1)
                from determined.agent.edge_types import EdgeRef
                edge = EdgeRef(src=src.strip(), src_type="symbol",
                               dst=dst.strip(), dst_type="symbol",
                               edge_type="manual", note=note)
                added = bags.add_edge(bag_id, edge)
                break
        else:
            return "ERROR: for edge type, use format 'src->dst'"
    elif item_type == "finding":
        added = bags.add_item(bag_id, "finding", {"text": ref}, note=note,
                              key=f"finding::{ref[:60]}")
    else:
        return f"ERROR: unknown type '{item_type}'. Use: symbol | file | edge | finding"

    verb = "Added to" if added else "Already in"
    result = f"{verb} bag '{bag_id}': [{item_type}] {ref}"
    if note:
        result += f"\n  note: {note}"
    return result


# ---------------------------------------------------------------------------
# Tool: bag_label
# ---------------------------------------------------------------------------

def bag_label(assessor: "Assessor", args: dict) -> str:
    """
    Set a human-readable label on a bag.

    Args:
      bag   - bag id (e.g. "user:1" or "user:auth-refactor")
      label - display name (e.g. "Auth flow investigation")
    """
    bags, err = _get_bags(assessor)
    if err:
        return f"ERROR: {err}"
    bag_id = args.get("bag", "").strip()
    label = args.get("label", "").strip()
    if not bag_id or not label:
        return "ERROR: bag and label are required"
    bags.set_label(bag_id, label)
    return f"Labeled bag '{bag_id}': {label}"


# ---------------------------------------------------------------------------
# Tool: bag_clear
# ---------------------------------------------------------------------------

def bag_clear(assessor: "Assessor", args: dict) -> str:
    """
    Empty a bag.

    Args:
      bag - bag id to clear (default "system")
    """
    bags, err = _get_bags(assessor)
    if err:
        return f"ERROR: {err}"
    bag_id = args.get("bag", SYSTEM_BAG).strip()
    count = bags.clear(bag_id)
    return f"Cleared bag '{bag_id}': {count} item(s) removed."


# ---------------------------------------------------------------------------
# Tool: bag_report
# ---------------------------------------------------------------------------

def bag_report(assessor: "Assessor", args: dict) -> str:
    """
    Generate a structured summary of bag contents.

    Args:
      bag - bag id (default "system")

    Produces: item counts, edge type breakdown, risk annotations on symbols,
    import chain summary, and a plain list of everything accumulated.
    Intended as the raw material for a written report or further analysis.
    """
    bags, err = _get_bags(assessor)
    if err:
        return f"ERROR: {err}"

    bag_id = args.get("bag", SYSTEM_BAG).strip()
    items = bags.list_items(bag_id=bag_id)
    if not items:
        return f"Bag '{bag_id}' is empty. Run some tools first to accumulate findings."

    oracle = assessor.oracle
    from determined.agent.risk_annotator import score_risk, risk_badge

    grouped: dict[str, list] = {}
    for it in items:
        grouped.setdefault(it["item_type"], []).append(it)

    lines = [f"=== Report: bag '{bag_id}' ({len(items)} item(s)) ===\n"]

    # ---- Summary counts ----
    for itype in sorted(grouped):
        lines.append(f"  {itype}: {len(grouped[itype])}")
    lines.append("")

    # ---- Edges ----
    if "edge" in grouped:
        edges = grouped["edge"]
        by_etype: dict[str, list] = {}
        for it in edges:
            by_etype.setdefault(it["content"].get("edge_type", "?"), []).append(it)
        lines.append(f"EDGES ({len(edges)}):")
        for etype, elist in sorted(by_etype.items()):
            lines.append(f"\n  {etype} edges ({len(elist)}):")
            internal = [e for e in elist if e["content"].get("is_internal", True)]
            external = [e for e in elist if not e["content"].get("is_internal", True)]
            for it in internal[:20]:
                c = it["content"]
                note = f"  # {it['note']}" if it.get("note") else ""
                arrow = {"call": "→", "import": "⇒", "inherit": "↑", "manual": "↔"}.get(etype, "→")
                lines.append(f"    {c.get('src','')} {arrow} {c.get('dst','')}{note}")
            if len(internal) > 20:
                lines.append(f"    ... +{len(internal)-20} more")
            if external:
                lines.append(f"    [external: {', '.join(e['content'].get('dst','') for e in external[:5])}]")
        lines.append("")

    # ---- Symbols with risk ----
    if "symbol" in grouped:
        syms = grouped["symbol"]
        lines.append(f"SYMBOLS ({len(syms)}):")
        for it in syms:
            c = it["content"]
            name = c.get("name", "")
            try:
                risk = score_risk(oracle, name)
                badge = risk_badge(risk["level"])
                fp = c.get("file_path", "").replace("\\", "/").split("/")[-1]
                note = f"  # {it['note']}" if it.get("note") else ""
                lines.append(f"  {badge}  {name}  ({fp}){note}")
            except Exception:
                lines.append(f"  {name}")
        lines.append("")

    # ---- Files ----
    if "file" in grouped:
        files = grouped["file"]
        lines.append(f"FILES ({len(files)}):")
        for it in files:
            fp = it["content"].get("file_path", "").replace("\\", "/")
            note = f"  # {it['note']}" if it.get("note") else ""
            lines.append(f"  {fp}{note}")
        lines.append("")

    # ---- Findings ----
    if "finding" in grouped:
        findings = grouped["finding"]
        lines.append(f"FINDINGS ({len(findings)}):")
        for it in findings:
            text = it["content"].get("text", str(it["content"]))[:100]
            note = f"  # {it['note']}" if it.get("note") else ""
            lines.append(f"  {text}{note}")
        lines.append("")

    return "\n".join(lines)
