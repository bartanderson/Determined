# tools/analysis/query/query_file_analysis.py

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional
from pathlib import Path

def fetch_file_record(
    connection: sqlite3.Connection,
    file_path: str,
) -> Optional[Dict[str, Any]]:
    cursor = connection.cursor()

    normalized_path = normalize_path(file_path)

    cursor.execute("""
    SELECT
        file_path,
        line_count,
        role,
        is_hot
    FROM files
    WHERE file_path = ?
    """, (normalized_path,))

    row = cursor.fetchone()

    if row is None:
        return None

    return {
        "file_path": row[0],
        "line_count": row[1],
        "role": row[2],
        "is_hot": bool(row[3]),
    }

from pathlib import Path

def normalize_path(file_path: str) -> str:
    return str(Path(file_path).resolve()).replace("\\", "/")
    
def fetch_functions_for_file(
    connection: sqlite3.Connection,
    file_path: str,
) -> List[Dict[str, Any]]:
    cursor = connection.cursor()

    cursor.execute("""
    SELECT
        name,
        line_number,
        return_type,
        arguments_json
    FROM functions
    WHERE file_path = ?
    ORDER BY line_number
    """, (file_path,))

    results = []

    for row in cursor.fetchall():
        results.append({
            "name": row[0],
            "line_number": row[1],
            "return_type": row[2],
            "arguments": json.loads(row[3]),
        })

    return results


def fetch_classes_for_file(
    connection: sqlite3.Connection,
    file_path: str,
) -> List[Dict[str, Any]]:
    cursor = connection.cursor()

    cursor.execute("""
    SELECT
        name,
        line_number,
        methods_json,
        base_classes_json
    FROM classes
    WHERE file_path = ?
    ORDER BY line_number
    """, (file_path,))

    results = []

    for row in cursor.fetchall():
        results.append({
            "name": row[0],
            "line_number": row[1],
            "methods": json.loads(row[2]),
            "base_classes": json.loads(row[3]),
        })

    return results


def fetch_imports_for_file(
    connection: sqlite3.Connection,
    file_path: str,
) -> List[Dict[str, Any]]:
    cursor = connection.cursor()

    cursor.execute("""
    SELECT
        module,
        import_type,
        line_number
    FROM imports
    WHERE file_path = ?
    ORDER BY line_number
    """, (file_path,))

    results = []

    for row in cursor.fetchall():
        results.append({
            "module": row[0],
            "import_type": row[1],
            "line_number": row[2],
        })

    return results

def fetch_symbol_references_for_file(
    connection: sqlite3.Connection,
    file_path: str,
):
    cursor = connection.cursor()

    cursor.execute("""
    SELECT
        caller,
        callee,
        line_number
    FROM symbol_references
    WHERE file_path = ?
    """, (file_path,))

    rows = cursor.fetchall()

    return [
        {
            "caller": row[0],
            "callee": row[1],
            "line_number": row[2],
        }
        for row in rows
    ]

def fetch_mutations_for_file(
    connection: sqlite3.Connection,
    file_path: str,
) -> List[Dict[str, Any]]:
    cursor = connection.cursor()

    cursor.execute("""
    SELECT
        line_number,
        target,
        operation,
        raw_expression
    FROM mutations
    WHERE file_path = ?
    ORDER BY line_number
    """, (file_path,))

    results = []

    for row in cursor.fetchall():
        results.append({
            "line_number": row[0],
            "target": row[1],
            "operation": row[2],
            "raw_expression": row[3],
        })

    return results


def fetch_behavioral_contracts_for_file(
    connection: sqlite3.Connection,
    file_path: str,
) -> List[Dict[str, Any]]:
    cursor = connection.cursor()

    cursor.execute("""
    SELECT
        function_name,
        line_number,
        description,
        side_effects_json,
        raises_json,
        testable_behaviors_json,
        complexity_score
    FROM behavioral_contracts
    WHERE file_path = ?
    ORDER BY line_number
    """, (file_path,))

    results = []

    for row in cursor.fetchall():
        results.append({
            "function_name": row[0],
            "line_number": row[1],
            "description": row[2],
            "side_effects": json.loads(row[3]),
            "raises": json.loads(row[4]),
            "testable_behaviors": json.loads(row[5]),
            "complexity_score": row[6],
        })

    return results


def fetch_complete_file_analysis(
    connection: sqlite3.Connection,
    file_path: str,
) -> Optional[Dict[str, Any]]:
    normalized_path = file_path.replace("\\", "/")
    file_record = fetch_file_record(connection, normalized_path)

    if file_record is None:
        return None

    return {
        "file": file_record,
        "functions": fetch_functions_for_file(connection, file_path),
        "classes": fetch_classes_for_file(connection, file_path),
        "imports": fetch_imports_for_file(connection, file_path),
        "symbol_references": fetch_symbol_references_for_file(
            connection,
            file_path,
        ),
        "mutations": fetch_mutations_for_file(connection, file_path),
        "behavioral_contracts": fetch_behavioral_contracts_for_file(
            connection,
            file_path,
        ),
    }