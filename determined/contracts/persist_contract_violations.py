# tools/analysis/contracts/persist_contract_violations.py

import sqlite3


def _get(v, name, default=""):
    """Read a field from a violation regardless of whether it's a dict or object."""
    if isinstance(v, dict):
        return v.get(name, default)
    return getattr(v, name, default)


def persist_contract_violations(connection: sqlite3.Connection, report):
    cursor = connection.cursor()

    for v in report.violations:
        cursor.execute("""
        INSERT INTO contract_violations (
            file_path,
            contract_name,
            layer,
            severity,
            message,
            observed_value,
            expected_value
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            report.file_path,
            _get(v, "contract_name"),
            _get(v, "layer"),
            _get(v, "severity", "unknown"),
            _get(v, "message"),
            str(_get(v, "observed_value") or _get(v, "observed")),
            str(_get(v, "expected_value") or _get(v, "expected")),
        ))

    connection.commit()