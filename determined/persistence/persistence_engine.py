# tools/analysis/persistence/persistence_engine.py


from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from determined.shared.types import FileAnalysis
from determined.core.pathing import normalize_file_path
from determined.identity.edge_identity import edge_identity

def ensure_schema(connection):
    # Corpus DB schema only - structural tables.
    # Intent tables (knowledge_artifacts, semantic_summaries) live in
    # knowledge.db, not in corpus DBs. See DESIGN.md section 7 and
    # oracle/knowledge_oracle.py.
    initialize_database(connection)

def set_project_root(connection: sqlite3.Connection, project_root) -> None:
    """
    Persist the real ingestion-time project root so DBOracle can later
    trim absolute file_path values down to a project-relative module
    identity (oracle/db_oracle.py's _file_path_to_module() /
    get_project_root()) - closes TRACKER.md open item 16 (SUBSYSTEM
    identity strings polluted by the full absolute filesystem path).
    Idempotent (INSERT OR REPLACE), single row keyed 'project_root'.
    No-op if project_root is falsy - callers that don't have one yet
    (e.g. tests building a DB by hand) just leave DBOracle to fall back
    to its own common-prefix inference.
    """
    if not project_root:
        return
    normalized = normalize_file_path(project_root)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO project_meta (key, value) VALUES ('project_root', ?)",
        (normalized,),
    )
    connection.commit()

def _insert_symbol(cursor, file_path, symbol_type, name, line_number, signature=""):
    canonical_id = f"{file_path}:{symbol_type}:{name}:{line_number}"

    cursor.execute("""
    INSERT INTO symbols (
        file_path,
        symbol_type,
        name,
        line_number,
        signature,
        canonical_id
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        file_path,
        symbol_type,
        name,
        line_number,
        signature,
        canonical_id
    ))

def run_sql(connection: sqlite3.Connection, query: str):
    """
    Debug utility ONLY.
    Centralized SQL execution so we don't scatter ad-hoc scripts.
    """
    cursor = connection.cursor()
    cursor.execute(query)
    return cursor.fetchall()

def initialize_database(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        file_path TEXT PRIMARY KEY,
        line_count INTEGER,
        role TEXT,
        is_hot INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS functions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        name TEXT,
        line_number INTEGER,
        return_type TEXT,
        arguments_json TEXT,
        docstring TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        name TEXT,
        line_number INTEGER,
        methods_json TEXT,
        base_classes_json TEXT,
        docstring TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        module TEXT,
        import_type TEXT,
        line_number INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS behavioral_contracts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        function_name TEXT,
        line_number INTEGER,
        description TEXT,
        side_effects_json TEXT,
        raises_json TEXT,
        testable_behaviors_json TEXT,
        complexity_score INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mutations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        line_number INTEGER,
        target TEXT,
        operation TEXT,
        raw_expression TEXT,
        intent TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS file_edges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_file TEXT NOT NULL,
        to_module TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS graph_edges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        /* semantic identity layer (NEW PRIMARY MODEL) */
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,

        /* legacy observational trace (optional but useful) */
        caller TEXT,
        callee TEXT,

        line_number INTEGER,
        caller_file TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS symbols (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        symbol_type TEXT,
        name TEXT,
        line_number INTEGER,
        signature TEXT,
        canonical_id TEXT UNIQUE
        )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS symbol_references (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        caller TEXT,
        callee TEXT,
        line_number INTEGER,
        bucket TEXT,
        edge_role TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contract_violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        contract_name TEXT,
        layer TEXT,
        severity TEXT,
        message TEXT,
        observed_value TEXT,
        expected_value TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contract_drift_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_name TEXT,
    classification TEXT,
    layer TEXT,
    count INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
   """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS query_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        raw_query TEXT,
        intent TEXT,
        queried_at TEXT,
        seeds TEXT,
        expanded TEXT,
        primitives TEXT,
        snapshot_edge_count INTEGER,
        reasoning TEXT,
        self_model TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    connection.commit()


def create_indexes(connection: sqlite3.Connection, include_composite: bool = True) -> None:
    """Add performance indexes to an existing database."""
    cursor = connection.cursor()
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_functions_file_path ON functions(file_path);",
        "CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(name);",
        "CREATE INDEX IF NOT EXISTS idx_classes_file_path ON classes(file_path);",
        "CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(name);",
        "CREATE INDEX IF NOT EXISTS idx_imports_file_path ON imports(file_path);",
        "CREATE INDEX IF NOT EXISTS idx_imports_module ON imports(module);",
        "CREATE INDEX IF NOT EXISTS idx_contracts_file_path ON behavioral_contracts(file_path);",
        "CREATE INDEX IF NOT EXISTS idx_contracts_function_name ON behavioral_contracts(function_name);",
        "CREATE INDEX IF NOT EXISTS idx_mutations_file_path ON mutations(file_path);",
        "CREATE INDEX IF NOT EXISTS idx_file_edges_from_file ON file_edges(from_file);",
        "CREATE INDEX IF NOT EXISTS idx_file_edges_to_module ON file_edges(to_module);",
        "CREATE INDEX IF NOT EXISTS idx_graph_edges_source_id ON graph_edges(source_id);",
        "CREATE INDEX IF NOT EXISTS idx_graph_edges_target_id ON graph_edges(target_id);",
        "CREATE INDEX IF NOT EXISTS idx_graph_edges_caller ON graph_edges(caller);",
        "CREATE INDEX IF NOT EXISTS idx_graph_edges_callee ON graph_edges(callee);",
        "CREATE INDEX IF NOT EXISTS idx_graph_edges_line ON graph_edges(line_number);",
        "CREATE INDEX IF NOT EXISTS idx_symbols_file_path ON symbols(file_path);",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_symbols_canonical ON symbols(canonical_id);",
        "CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);",
        "CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(symbol_type);",
        "CREATE INDEX IF NOT EXISTS idx_symref_caller ON symbol_references(caller);",
        "CREATE INDEX IF NOT EXISTS idx_symref_callee ON symbol_references(callee);",
        "CREATE INDEX IF NOT EXISTS idx_symref_file_path ON symbol_references(file_path);",
        "CREATE INDEX IF NOT EXISTS idx_symref_bucket ON symbol_references(bucket);",
        "CREATE INDEX IF NOT EXISTS idx_contract_violations ON contract_violations(id);",
        "CREATE INDEX IF NOT EXISTS idx_contract_drift_name ON contract_drift_history(contract_name);",
        "CREATE INDEX IF NOT EXISTS idx_contract_drift_time ON contract_drift_history(timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_query_sessions_session_id ON query_sessions(session_id);",
        "CREATE INDEX IF NOT EXISTS idx_query_sessions_queried_at ON query_sessions(queried_at);"
    ]
    if include_composite:
        indexes.extend([
            "CREATE INDEX IF NOT EXISTS idx_functions_file_name ON functions(file_path, name);",
            "CREATE INDEX IF NOT EXISTS idx_classes_file_name ON classes(file_path, name);",
            "CREATE INDEX IF NOT EXISTS idx_symbols_file_name ON symbols(file_path, name);",
        ])
    for sql in indexes:
        cursor.execute(sql)

    # migrate existing DBs that predate the caller_file column
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(graph_edges)")}
    if "caller_file" not in existing:
        cursor.execute("ALTER TABLE graph_edges ADD COLUMN caller_file TEXT")

    connection.commit()


def _canonical_symbol(name: str) -> str:
    if not name:
        return name
    return name.split(".")[-1]

def persist_file_analysis(
    connection: sqlite3.Connection,
    analysis,
    project_prefixes,
    logger=None
) -> None:

    cursor = connection.cursor()

    analysis.file_path = normalize_file_path(analysis.file_path)


    # =========================
    # DEBUG (pre-persist inspection)
    # =========================
    logger and logger.write("\n[PERSIST START]")
    logger and logger.write("file:", analysis.file_path)
    logger and logger.write("symbol_refs:", len(analysis.symbol_references))


    # -------------------------
    # FILE
    # -------------------------
    cursor.execute("""
    INSERT OR REPLACE INTO files (
        file_path,
        line_count,
        role,
        is_hot
    )
    VALUES (?, ?, ?, ?)
    """, (
        analysis.file_path,
        analysis.metadata.line_count,
        analysis.metadata.role,
        int(analysis.metadata.is_hot),
    ))

    # -------------------------
    # FUNCTIONS
    # -------------------------
    cursor.execute(
        "DELETE FROM functions WHERE file_path = ?",
        (analysis.file_path,),
    )

    for function in analysis.functions:
        cursor.execute("""
        INSERT INTO functions (
            file_path,
            name,
            line_number,
            return_type,
            arguments_json,
            docstring
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            analysis.file_path,
            _canonical_symbol(function.name),
            function.line_number,
            function.return_type,
            json.dumps(function.arguments),
            function.docstring,
        ))

        # CLAUDE-EDIT 2026-06-17: was gated on
        # `getattr(function, "bucket", None) == "project"`, but
        # FunctionRepresentation has no `bucket` field and nothing in the
        # pipeline ever sets one - that condition was unconditionally
        # False for every function in the codebase, so this insert had
        # never fired for any project function, ever (confirmed via a
        # real engine run against the "tools" corpus: symbols table had
        # zero symbol_type='function'/'class' rows, 100% caller/callee
        # noise from the separate patch in _persist_file_analysis below).
        # EngineRunner only scans project-corpus files, so every function
        # _extract_functions() finds in a scanned file IS a project
        # declaration by construction - there is no "external function
        # declaration" case here to gate against. Insert unconditionally,
        # matching the always-run INSERT INTO functions call above.
        _insert_symbol(
            cursor,
            analysis.file_path,
            "function",
            _canonical_symbol(function.name),
            function.line_number,
            function.return_type or "",
        )

    # -------------------------
    # CLASSES
    # -------------------------
    cursor.execute(
        "DELETE FROM classes WHERE file_path = ?",
        (analysis.file_path,),
    )

    for cls_obj in analysis.classes:
        cursor.execute("""
        INSERT INTO classes (
            file_path,
            name,
            line_number,
            methods_json,
            base_classes_json,
            docstring
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            analysis.file_path,
            _canonical_symbol(cls_obj.name),
            cls_obj.line_number,
            json.dumps(cls_obj.methods),
            json.dumps(cls_obj.base_classes),
            cls_obj.docstring,
        ))

        # CLAUDE-EDIT 2026-06-17: same dead-gate fix as the function case
        # above - ClassRepresentation has no `bucket` field either.
        _insert_symbol(
            cursor,
            analysis.file_path,
            "class",
            _canonical_symbol(cls_obj.name),
            cls_obj.line_number,
        )

    # -------------------------
    # IMPORTS
    # -------------------------
    cursor.execute(
        "DELETE FROM imports WHERE file_path = ?",
        (analysis.file_path,),
    )

    for imp in analysis.imports:
        cursor.execute("""
        INSERT INTO imports (
            file_path,
            module,
            import_type,
            line_number
        )
        VALUES (?, ?, ?, ?)
        """, (
            analysis.file_path,
            imp.module,
            imp.import_type,
            imp.line_number,
        ))

    cursor.execute(
        "DELETE FROM file_edges WHERE from_file = ?",
        (analysis.file_path,),
    )

    for imp in analysis.imports:
        cursor.execute("""
        INSERT INTO file_edges (
            from_file,
            to_module
        )
        VALUES (?, ?)
        """, (
            analysis.file_path,
            imp.module,
        ))

    # -------------------------
    # BEHAVIORAL CONTRACTS
    # -------------------------
    cursor.execute(
        "DELETE FROM behavioral_contracts WHERE file_path = ?",
        (analysis.file_path,),
    )

    for contract in analysis.behavioral_contracts:
        cursor.execute("""
        INSERT INTO behavioral_contracts (
            file_path,
            function_name,
            line_number,
            description,
            side_effects_json,
            raises_json,
            testable_behaviors_json,
            complexity_score
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis.file_path,
            contract.function_name,
            contract.line_number,
            contract.description,
            json.dumps(contract.side_effects),
            json.dumps(contract.raises),
            json.dumps(contract.testable_behaviors),
            contract.complexity_score,
        ))

    # -------------------------
    # MUTATIONS
    # -------------------------
    cursor.execute(
        "DELETE FROM mutations WHERE file_path = ?",
        (analysis.file_path,),
    )

    for mutation in analysis.mutations:
        cursor.execute("""
        INSERT INTO mutations (
            file_path,
            line_number,
            target,
            operation,
            raw_expression,
            intent
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            analysis.file_path,
            mutation.line_number,
            mutation.target,
            mutation.operation,
            mutation.raw_expression,
            mutation.intent,
        ))

    # -------------------------
    # SYMBOL REFERENCES
    # -------------------------
    cursor.execute(
        "DELETE FROM symbol_references WHERE file_path = ?",
        (analysis.file_path,),
    )

    for ref in analysis.symbol_references:
        cursor.execute("""
        INSERT INTO symbol_references (
            file_path,
            caller,
            callee,
            line_number,
            bucket,
            edge_role
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            analysis.file_path,
            ref.caller,
            ref.callee,
            ref.line_number,
            getattr(ref, "bucket", None),
            getattr(ref, "edge_role", None),
        ))

    logger and logger.write("[PERSIST MID] symbol_references inserted (in-memory):",
          len(analysis.symbol_references))

    connection.commit()

    # DB is now source of truth
    cursor.execute(
        "SELECT COUNT(*) FROM symbol_references WHERE file_path = ?",
        (analysis.file_path,)
    )

    db_count = cursor.fetchone()[0]

    logger and logger.write("\n[PERSIST END]")
    logger and logger.write("file:", analysis.file_path)
    logger and logger.write("db_rows:", db_count)
    logger and logger.write("in_memory:", len(analysis.symbol_references))
    logger and logger.write("match:", db_count == len(analysis.symbol_references))

def create_database(database_path: str | Path) -> sqlite3.Connection:
    database_path = Path(database_path)

    if database_path.exists():
        database_path.unlink()
        logger and logger.write(f"[RESET DB] {database_path}")

    connection = sqlite3.connect(str(database_path))
    initialize_database(connection)
    create_indexes(connection)

    return connection



# ==================================================
# PUBLIC ENTRY POINT (ONLY FUNCTION CALLED OUTSIDE)
# ==================================================
def persist_all(connection, file_analyses, graph, project_prefixes, logger=None, project_root=None):
    """
    Single persistence orchestrator.

    ALL DB writes must flow through here.
    """

    # -----------------------------------------
    # 1. SCHEMA GUARANTEE (MUST BE FIRST)
    # -----------------------------------------
    ensure_schema(connection)

    # -----------------------------------------
    # 1b. PROJECT ROOT (item 16 - optional, no-op if not supplied)
    # -----------------------------------------
    set_project_root(connection, project_root)

    cursor = connection.cursor()

    # -----------------------------------------
    # 2. OPTIONAL DEBUG (safe after schema exists)
    # -----------------------------------------
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    logger and logger.write("[DB TABLES]", cursor.fetchall())

    # -----------------------------------------
    # 3. SNAPSHOT (SAFE NOW)
    # -----------------------------------------
    cursor.execute("SELECT COUNT(*) FROM symbol_references")
    db_total = cursor.fetchone()[0]

    db_snapshot = {
        "symbol_reference_count": db_total
    }

    # -----------------------------------------
    # 4. PERSIST FILE LAYER
    # -----------------------------------------
    _persist_file_analysis(connection, file_analyses, project_prefixes)

    # -----------------------------------------
    # 5. PERSIST GRAPH LAYER
    # -----------------------------------------
    _persist_graph_edges(connection, graph)

# ==================================================
# --- SYMBOL IDENTITY LAYER (NEW) ---
# ==================================================

def make_canonical_id(file_path, symbol_type, name, line_number):
    return f"{file_path}:{symbol_type}:{name}:{line_number}"

# ==================================================
# FILE / SYMBOL PERSISTENCE (LEGACY BUT CONTAINED)
# ==================================================
def _persist_file_analysis(connection, file_analyses, project_prefixes):
    cursor = connection.cursor()

    for analysis in file_analyses:

        # existing legacy persistence
        persist_file_analysis(connection, analysis, project_prefixes)

        # CLAUDE-EDIT 2026-06-17: removed the caller/callee-into-symbols
        # block that used to live here (marked "THIS WAS MISSING"). It was
        # a workaround added on top of the real bug instead of fixing it:
        # persist_file_analysis()'s function/class -> symbols insert was
        # gated on a `bucket == "project"` check that could never be True
        # (see the CLAUDE-EDIT comments on that function), so `symbols`
        # was always empty, and this block patched the symptom by
        # stuffing every call-site's raw caller/callee name into `symbols`
        # instead - uncanonicalized (dotted stdlib names like "ast.parse"
        # landing verbatim) and with no project-only filter (external/
        # stdlib/builtin callees included), which is exactly what made
        # `symbols` fail its "short names only" / "no duplicates" /
        # "every declared name is real" contracts (see
        # tests/core/test_symbol_*.py and REFACTOR OPS BOARD.md's
        # 2026-06-17 entry). Confirmed via repo-wide grep that nothing
        # live reads symbol_type='caller'/'callee' rows specifically -
        # oracle/db_oracle.py's consumers already explicitly filter to
        # symbol_type IN ('function','class') wherever it matters. Now
        # that the real function/class insert path actually fires,
        # `symbols` holds genuine declarations and this patch is no
        # longer needed.


# ==================================================
# GRAPH EDGE PERSISTENCE (TRUTH LAYER)
# ==================================================
def _persist_graph_edges(connection, graph):
    cursor = connection.cursor()

    edges = getattr(graph, "edges", [])

    # collect the set of source files in this run
    files_in_run = {e.caller_file for e in edges if getattr(e, "caller_file", "")}

    if files_in_run:
        # scoped delete: only remove edges from files being re-ingested
        placeholders = ",".join("?" * len(files_in_run))
        cursor.execute(
            f"DELETE FROM graph_edges WHERE caller_file IN ({placeholders})",
            list(files_in_run),
        )
    else:
        # legacy path: no caller_file info, fall back to full reset
        cursor.execute("DELETE FROM graph_edges")

    for edge in edges:
        source_id, target_id = edge_identity(edge.caller, edge.callee)
        cursor.execute("""
        INSERT INTO graph_edges (
            source_id,
            target_id,
            caller,
            callee,
            line_number,
            caller_file
        ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            source_id,
            target_id,
            edge.caller,
            edge.callee,
            getattr(edge, "line_number", None),
            getattr(edge, "caller_file", None),
        ))

    connection.commit()