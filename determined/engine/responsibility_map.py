# tools/analysis/engine/responsibility_map.py

from collections import defaultdict

# ------------------------------------------------------------------
# HIGH BLAST RADIUS
# Modules whose changes have disproportionate system-wide impact.
# Rule: any change to a file in this set triggers full regression
# (tools/run_regression.py), not targeted tests.
#
# Threshold for auto-detection: files with >= BLAST_EDGE_THRESHOLD
# outbound call edges in the corpus are flagged alongside these
# explicitly named files.
# ------------------------------------------------------------------

HIGH_BLAST_RADIUS_FILES = {
    "agent_tools.py",   # 12k+ lines, dispatches every tool call
}

BLAST_EDGE_THRESHOLD = 500   # outbound edges from a single caller_file


def get_high_blast_radius_files(conn) -> list[str]:
    """
    Return list of (file_path, edge_count) for files that exceed the
    blast-radius threshold by fan-out edge count, plus all explicitly
    named files that appear in the corpus.
    Cheap SQL query -- safe to call on every analyze_corpus run.
    """
    try:
        rows = conn.execute(
            """
            SELECT caller_file, COUNT(*) AS edge_count
            FROM graph_edges
            WHERE caller_file IS NOT NULL AND caller_file != ''
            GROUP BY caller_file
            HAVING edge_count >= ?
            ORDER BY edge_count DESC
            """,
            (BLAST_EDGE_THRESHOLD,),
        ).fetchall()
    except Exception:
        rows = []

    results = [(r[0], r[1]) for r in rows]

    # Also include explicitly named files even if below threshold
    for name in HIGH_BLAST_RADIUS_FILES:
        try:
            row = conn.execute(
                "SELECT caller_file, COUNT(*) FROM graph_edges WHERE caller_file LIKE ? GROUP BY caller_file",
                (f"%{name}",),
            ).fetchone()
            if row and not any(r[0] == row[0] for r in results):
                results.append((row[0], row[1]))
        except Exception:
            pass

    return results


ROLE_PATTERNS = {
    "ingestion": [
        "scan",
        "parse",
        "ast",
        "ingestion",
        "scanner",
    ],
    "classification": [
        "classify",
        "semantic",
        "symbol",
        "reference",
    ],
    "graph": [
        "graph",
        "edge",
        "node",
        "builder",
    ],
    "persistence": [
        "sqlite",
        "database",
        "persist",
        "insert",
        "update",
    ],
    "reporting": [
        "report",
        "summary",
        "snapshot",
        "json",
        "print",
    ],
}


def detect_file_roles(file_analysis):

    text = " ".join([
        getattr(file_analysis, "file_path", ""),
        " ".join(
            ref.callee
            for ref in getattr(file_analysis, "symbol_references", [])
        ),
    ]).lower()

    roles = {}

    for role_name, patterns in ROLE_PATTERNS.items():
        roles[role_name] = any(
            pattern in text
            for pattern in patterns
        )

    return roles


def build_responsibility_map(file_analyses):

    files = []
    totals = defaultdict(int)

    for analysis in file_analyses:

        roles = detect_file_roles(analysis)

        for role_name, enabled in roles.items():
            if enabled:
                totals[role_name] += 1

        files.append({
            "file_path": analysis.file_path,
            "roles": roles,
            "edge_count": len(
                getattr(
                    analysis,
                    "symbol_references",
                    [],
                )
            ),
        })

    return {
        "files": files,
        "totals": dict(totals),
    }


def print_responsibility_map(snapshot):

    engine = snapshot["engine"]
    responsibility = snapshot["responsibility"]

    print("\n=== RESPONSIBILITY MAP ===\n")

    for role_name in sorted(responsibility["totals"]):
        print(
            f"{role_name}: "
            f"{responsibility['totals'][role_name]}"
        )

    print("\n=== ENGINE TOTALS ===\n")

    for k in ["file_count", "symbol_reference_count", "edge_count"]:
        print(f"{k}: {engine.get(k, 0)}")

    print("\n=== FILE BREAKDOWN ===\n")

    ranked = sorted(
        responsibility["files"],
        key=lambda x: -x["edge_count"],
    )

    for row in ranked[:25]:

        active_roles = [
            role
            for role, enabled in row["roles"].items()
            if enabled
        ]

        print(
            f"{row['edge_count']:5d}  "
            f"{','.join(active_roles)}  "
            f"{row['file_path']}"
        )