# tools\analysis\reducer\reduce.py

def reduce(file_analyses, logger=None):
    edge_activity_total= 0
    reduced_gap = 0
    reduced_builtin = 0

    for i, snap in enumerate(file_analyses):

        if logger:
            logger(f"\n[REDUCE STEP] {i}")
            logger(f"snapshot id: {snap.get('file_path', f'file_{i}')}")

        edge_activity = snap.get("edge_count", 0)
        bs = snap.get("bucket_summary", {})

        gap = bs.get("classification_gap", 0)
        builtin = bs.get("builtin", 0)
        project = bs.get("project", 0)

        if logger:
            logger("incoming values:")
            logger(f"  edge_activity: {edge_activity}")
            logger(f"  gap: {gap}")
            logger(f"  builtin: {builtin}")
            logger(f"  project: {project}")

        before = (edge_activity_total, reduced_gap, reduced_builtin)

        edge_activity_total += edge_activity
        reduced_gap += gap
        reduced_builtin += builtin

        after = (edge_activity_total, reduced_gap, reduced_builtin)

        if logger:
            logger("fold:")
            logger(f"  before: {before}")
            logger(f"  after: {after}")

    if logger:
        logger("\nFINAL REDUCED STATE")
        logger(f"edge_activity_total: {edge_activity_total}")
        logger(f"gap: {reduced_gap}")
        logger(f"builtin: {reduced_builtin}")
        logger("=" * 80)
        logger("\n[STEP 6 - FINAL INVARIANT CHECK]")

    assert edge_activity_total >= 0, "edge_activity_total negative?"
    assert reduced_gap >= 0, "gap negative?"
    assert reduced_builtin >= 0, "builtin negative?"

    return {
        "edge_activity_total": edge_activity_total,
        "gap": reduced_gap,
        "builtin": reduced_builtin
    }