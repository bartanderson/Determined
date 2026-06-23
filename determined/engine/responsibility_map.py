# tools/analysis/engine/responsibility_map.py

from collections import defaultdict


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