# tools/analysis/contracts/persist_contract_violations.py

import sqlite3

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
            v.contract_name,
            v.layer,
            getattr(v, "severity", "unknown"),
            v.message,
            str(getattr(v, "observed", "")),
            str(getattr(v, "expected", "")),
        ))

    connection.commit()