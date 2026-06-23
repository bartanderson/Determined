# tools/analysis/graph/symbol_index.py

import sqlite3
from collections import defaultdict


def build_symbol_index(connection: sqlite3.Connection):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            name,
            file_path,
            symbol_type,
            line_number
        FROM symbols
    """)

    index = defaultdict(list)

    for name, file_path, symbol_type, line_number in cursor.fetchall():
        index[name].append({
            "file_path": file_path,
            "symbol_type": symbol_type,
            "line_number": line_number,
        })

    return dict(index)