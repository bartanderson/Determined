# tools/analysis/persistence/persistence_engine.py


from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from determined.shared.types import FileAnalysis
from determined.core.pathing import normalize_file_path
from determined.identity.edge_identity import edge_identity

def ensure_schema(connection):
    initialize_database(connection)
    _migrate(connection)


def _migrate(connection):
    """Add columns that were missing from older corpus DBs."""
    cursor = connection.cursor()
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(graph_edges)").fetchall()}
    if "resolved" not in existing:
        cursor.execute("ALTER TABLE graph_edges ADD COLUMN resolved INTEGER DEFAULT 0")
    if "edge_type" not in existing:
        cursor.execute("ALTER TABLE graph_edges ADD COLUMN edge_type TEXT DEFAULT 'static'")
    fn_existing = {row[1] for row in cursor.execute("PRAGMA table_info(functions)").fetchall()}
    if "decorators_json" not in fn_existing:
        cursor.execute("ALTER TABLE functions ADD COLUMN decorators_json TEXT")
    if "http_route" not in fn_existing:
        cursor.execute("ALTER TABLE functions ADD COLUMN http_route TEXT")
    f_existing = {row[1] for row in cursor.execute("PRAGMA table_info(files)").fetchall()}
    if "ingested_at" not in f_existing:
        cursor.execute("ALTER TABLE files ADD COLUMN ingested_at TEXT")
    connection.commit()

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
    INSERT OR IGNORE INTO symbols (
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
        docstring TEXT,
        is_stub INTEGER DEFAULT 0,
        param_types_json TEXT,
        decorators_json TEXT,
        http_route TEXT
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

        /* TRAVERSAL KEYS — canonical bare names (last segment after last dot).
           Computed by edge_identity() → normalize_symbol() at store time.
           ALWAYS use these for graph traversal, degree counting, and
           connectivity queries. They are stable regardless of import form. */
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,

        /* DISPLAY / AUDIT — raw surface names as emitted by parse_ast.
           caller is always a bare name (parse_ast tracks current_function by
           node.name). callee may be bare ("fn"), fully-qualified
           ("pkg.module.fn" for `from pkg.module import fn` calls), or
           dotted-attr ("obj.method"). Use for display and blame only —
           never for traversal or existence checks. */
        caller TEXT,
        callee TEXT,

        line_number INTEGER,
        caller_file TEXT,
        resolved INTEGER DEFAULT 0,
        edge_type TEXT DEFAULT 'static'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS symbol_names (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_id TEXT NOT NULL,
        name TEXT NOT NULL,
        name_type TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS class_attributes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        class_name TEXT NOT NULL,
        attribute TEXT NOT NULL,
        inferred_type TEXT NOT NULL
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

    from determined.intent.semantic_summary import ensure_semantic_summaries_table
    from determined.intent.knowledge_artifact import ensure_knowledge_artifacts_table
    from determined.intent.workflow_store import ensure_workflow_items_table
    from determined.agent.semantic_cache import ensure_semantic_cache_table
    ensure_semantic_summaries_table(cursor)
    ensure_knowledge_artifacts_table(cursor)
    ensure_workflow_items_table(cursor)
    _ensure_bags_tables(cursor)
    ensure_semantic_cache_table(cursor)

    connection.commit()


def _ensure_bags_tables(cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bag_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bag_id INTEGER NOT NULL REFERENCES bags(id),
        symbol TEXT NOT NULL,
        note TEXT,
        added_at TEXT NOT NULL
    )
    """)


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
        "CREATE INDEX IF NOT EXISTS idx_symbol_names_canonical ON symbol_names(canonical_id);",
        "CREATE INDEX IF NOT EXISTS idx_symbol_names_name ON symbol_names(name);",
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
    # Clear stale inline notes for this file before reinserting
    cursor.execute(
        "DELETE FROM knowledge_artifacts WHERE kind='inline_note' AND content LIKE ?",
        (f"[{analysis.file_path}]%",),
    )

    for function in analysis.functions:
        cursor.execute("""
        INSERT INTO functions (
            file_path,
            name,
            line_number,
            return_type,
            arguments_json,
            param_types_json,
            docstring,
            is_stub,
            decorators_json,
            http_route
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis.file_path,
            _canonical_symbol(function.name),
            function.line_number,
            function.return_type,
            json.dumps(function.arguments),
            json.dumps(getattr(function, "param_types", {})) or None,
            function.docstring,
            1 if getattr(function, "is_stub", False) else 0,
            json.dumps(getattr(function, "decorators", [])) or None,
            getattr(function, "http_route", None),
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

        # Persist inline body comments as knowledge artifacts
        for note in getattr(function, 'inline_notes', []):
            created_at = datetime.now(timezone.utc).isoformat()
            content = f"[{analysis.file_path}] {json.dumps(note)}"
            cursor.execute(
                "INSERT INTO knowledge_artifacts "
                "(subject, kind, content, provenance, created_at, file_hash, needs_review, corpus) "
                "VALUES (?, 'inline_note', ?, 'human-confirmed', ?, NULL, 0, NULL)",
                (function.name, content, created_at),
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
    # CLASS ATTRIBUTES
    # -------------------------
    cursor.execute(
        "DELETE FROM class_attributes WHERE file_path = ?",
        (analysis.file_path,),
    )
    for ca in getattr(analysis, "class_attributes", []):
        cursor.execute("""
        INSERT INTO class_attributes (file_path, class_name, attribute, inferred_type)
        VALUES (?, ?, ?, ?)
        """, (analysis.file_path, ca.class_name, ca.attribute, ca.inferred_type))

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
        pass  # existing DB removed; logger not available in this scope

    connection = sqlite3.connect(str(database_path))
    initialize_database(connection)
    create_indexes(connection)

    return connection



# ==================================================
# PUBLIC ENTRY POINT (ONLY FUNCTION CALLED OUTSIDE)
# ==================================================
def persist_all(connection, file_analyses, graph, project_prefixes, logger=None, project_root=None, annotation_file=None):
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

    # -----------------------------------------
    # 5b. CROSS-LANGUAGE + ANNOTATION EDGES
    # -----------------------------------------
    _persist_cross_boundary_edges(connection, file_analyses, annotation_file)

    # -----------------------------------------
    # 5c. PERSIST JS/TS LAYER (LanguageWalker)
    # -----------------------------------------
    if project_root:
        _persist_js_ts_files(connection, project_root, logger=logger)

    # -----------------------------------------
    # 6. RECALCULATE is_hot FROM GRAPH
    # -----------------------------------------
    _recalculate_hot_files(connection)

def _persist_js_ts_files(connection, project_root, ignored_directory_names=None, logger=None):
    """
    Discover JS/TS files under project_root, run LanguageWalker on each,
    and insert symbols + call edges into functions / graph_edges.
    """
    from pathlib import Path
    from determined.ingestion.scan_project_files import discover_js_ts_files
    from determined.ingestion.language_walker import LanguageWalker, detect_language
    from determined.identity.edge_identity import edge_identity
    from determined.identity.symbol_identity import all_name_forms

    cursor = connection.cursor()
    js_files = discover_js_ts_files(project_root, ignored_directory_names)

    if not js_files:
        return

    # Scoped delete: remove existing rows for files we're about to re-insert
    file_paths = [str(p) for p in js_files]
    placeholders = ",".join("?" * len(file_paths))
    cursor.execute(f"DELETE FROM functions WHERE file_path IN ({placeholders})", file_paths)
    cursor.execute(
        f"DELETE FROM graph_edges WHERE caller_file IN ({placeholders})", file_paths
    )

    symbol_names_batch: list[tuple[str, str, str]] = []

    for path in js_files:
        lang = detect_language(str(path))
        if lang is None:
            continue
        try:
            src = Path(path).read_text(encoding="utf-8", errors="ignore")
            walker = LanguageWalker(src, str(path), lang)
        except Exception:
            continue

        # --- symbols → functions table ---
        for sym in walker.symbols():
            cursor.execute("""
            INSERT INTO functions (
                file_path, name, line_number, return_type, arguments_json,
                param_types_json, docstring, is_stub, decorators_json, http_route
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sym["file_path"], sym["name"], sym["line_number"],
                sym["return_type"], sym["arguments_json"], sym["param_types_json"],
                sym["docstring"], 1 if sym["is_stub"] else 0,
                sym["decorators_json"], sym["http_route"],
            ))
            _insert_symbol(cursor, sym["file_path"], "function", sym["name"], sym["line_number"])

        # --- call edges → graph_edges table ---
        for caller_fqdn, callee_name, etype, resolved in walker.call_edges():
            src_id, tgt_id = edge_identity(caller_fqdn, callee_name)
            cursor.execute("""
            INSERT INTO graph_edges (
                source_id, target_id, caller, callee, caller_file, resolved, edge_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (src_id, tgt_id, caller_fqdn, callee_name, str(path), 1 if resolved else 0, etype))
            for name, ntype in all_name_forms(caller_fqdn):
                symbol_names_batch.append((src_id, name, ntype))
            for name, ntype in all_name_forms(callee_name):
                symbol_names_batch.append((tgt_id, name, ntype))

        logger and logger.write(f"[JS/TS] {path.name}: {len(walker.symbols())} symbols, {len(walker.call_edges())} edges")

    # Cross-file resolution post-pass: mark an edge resolved=1 when the callee
    # matches a known JS/TS symbol (full fqdn OR the bare suffix after the last '.').
    # This covers both same-file and cross-file calls.  The walker always emits
    # resolved=False because it only sees one file at a time; this pass has the full set.
    if file_paths:
        cursor.execute(f"""
            UPDATE graph_edges
            SET resolved = 1
            WHERE caller_file IN ({placeholders})
              AND edge_type = 'static'
              AND EXISTS (
                SELECT 1 FROM functions f
                WHERE f.file_path IN ({placeholders})
                  AND (
                    f.name = graph_edges.callee
                    OR (
                      INSTR(f.name, '.') > 0
                      AND SUBSTR(f.name, INSTR(f.name, '.') + 1) = graph_edges.callee
                    )
                  )
              )
        """, file_paths + file_paths)

    seen: set[tuple[str, str]] = set()
    for canonical_id, name, ntype in symbol_names_batch:
        key = (canonical_id, name)
        if key not in seen:
            seen.add(key)
            cursor.execute(
                "INSERT OR IGNORE INTO symbol_names (canonical_id, name, name_type) VALUES (?, ?, ?)",
                (canonical_id, name, ntype),
            )


def _persist_cross_boundary_edges(connection, file_analyses, annotation_file=None):
    """
    Inject virtual edges that cross boundaries static AST can't see:
      - Gap 7: JS socket.emit → Python @socketio.on handler (cross_language)
      - RM38: DOM element → JS fn (js_event_binding), fetch/HTMX → Flask handler (http_fetch)
      - Gap 8+: manually declared edges from virtual_edges.json (annotation/polymorphic)

    These are stored in graph_edges with synthetic source symbols
    (__js_client__, __http_client__, __htmx__, __abc_base__, __annotation__) so they're
    traversable and queryable alongside static edges.
    """
    from determined.ingestion.dynamic_edges import (
        extract_socketio_handler_map,
        extract_cross_language_edges,
        extract_flask_route_map,
        extract_htmx_edges,
        extract_js_event_bindings,
        extract_fetch_edges,
        load_virtual_edge_annotations,
    )
    from determined.identity.symbol_identity import normalize_symbol, all_name_forms

    cursor = connection.cursor()
    seen_names: set[tuple[str, str]] = set()

    def _insert_virtual(src: str, tgt: str, etype: str):
        src_id = normalize_symbol(src)
        tgt_id = normalize_symbol(tgt)
        cursor.execute("""
        INSERT INTO graph_edges (source_id, target_id, caller, callee, edge_type)
        VALUES (?, ?, ?, ?, ?)
        """, (src_id, tgt_id, src, tgt, etype))
        for name, ntype in all_name_forms(src):
            key = (src_id, name)
            if key not in seen_names:
                seen_names.add(key)
                cursor.execute(
                    "INSERT OR IGNORE INTO symbol_names (canonical_id, name, name_type) VALUES (?,?,?)",
                    (src_id, name, ntype),
                )
        for name, ntype in all_name_forms(tgt):
            key = (tgt_id, name)
            if key not in seen_names:
                seen_names.add(key)
                cursor.execute(
                    "INSERT OR IGNORE INTO symbol_names (canonical_id, name, name_type) VALUES (?,?,?)",
                    (tgt_id, name, ntype),
                )

    # --- Gap 7: match JS socket.emit to Python @socketio.on handlers ---
    # Find the Python server file and any HTML templates in the analyzed files
    py_handler_map: dict[str, str] = {}
    html_sources: list[str] = []

    for analysis in (file_analyses or []):
        fp = getattr(analysis, 'file_path', '') or ''
        src = getattr(analysis, 'source_text', None) or None
        if src is None:
            continue
        if fp.endswith('.py'):
            py_handler_map.update(extract_socketio_handler_map(src))
        elif fp.endswith(('.html', '.js')):
            html_sources.append(src)

    if py_handler_map and html_sources:
        # Delete stale cross_language edges before reinserting
        cursor.execute("DELETE FROM graph_edges WHERE edge_type = 'cross_language'")
        for html_src in html_sources:
            for src, tgt, etype in extract_cross_language_edges(html_src, py_handler_map):
                _insert_virtual(src, tgt, etype)

    # --- RM38: HTTP/HTMX → Flask route chain ---
    # Build Flask route map from all Python files, then scan HTML/JS for fetch and HTMX.
    # scan_project_files only processes .py; read HTML/JS directly from disk via project_root.
    flask_route_map: dict[str, str] = {}
    html_srcs: list[str] = []
    js_srcs: list[str] = []

    for analysis in (file_analyses or []):
        fp = getattr(analysis, 'file_path', '') or ''
        src = getattr(analysis, 'source_text', None) or None
        if src is None:
            continue
        if fp.endswith('.py'):
            flask_route_map.update(extract_flask_route_map(src))
        elif fp.endswith('.html'):
            html_srcs.append(src)
        elif fp.endswith('.js'):
            js_srcs.append(src)

    # If no HTML/JS from file_analyses (scan_project_files skips them), read from disk
    if flask_route_map and not html_srcs and not js_srcs:
        try:
            row = cursor.execute("SELECT value FROM project_meta WHERE key='project_root'").fetchone()
            if row:
                _root = Path(row[0])
                _SKIP = {'.venv', 'node_modules', '__pycache__', '.git'}
                for _p in _root.rglob('*'):
                    if any(s in _p.parts for s in _SKIP):
                        continue
                    if _p.suffix == '.html':
                        try:
                            html_srcs.append(_p.read_text(encoding='utf-8', errors='replace'))
                        except OSError:
                            pass
                    elif _p.suffix == '.js':
                        try:
                            js_srcs.append(_p.read_text(encoding='utf-8', errors='replace'))
                        except OSError:
                            pass
        except Exception:
            pass

    if flask_route_map and (html_srcs or js_srcs):
        cursor.execute("DELETE FROM graph_edges WHERE edge_type IN ('http_fetch', 'js_event_binding')")
        for html_src in html_srcs:
            for src, tgt, etype in extract_htmx_edges(html_src, flask_route_map):
                _insert_virtual(src, tgt, etype)
            for src, tgt, etype in extract_js_event_bindings(html_src):
                _insert_virtual(src, tgt, etype)
        for js_src in js_srcs:
            for src, tgt, etype in extract_fetch_edges(js_src, flask_route_map):
                _insert_virtual(src, tgt, etype)

    # --- Gap 8: auto-generate polymorphic edges from ABC/subclass data ---
    # Uses Item 20 infrastructure: classes.base_classes_json, functions.decorators_json,
    # classes.methods_json. For each abstract method on an ABC class, emit virtual edges
    # to every concrete subclass override: AbstractBase.method → ConcreteSubclass.method
    _persist_polymorphic_edges(connection, cursor, _insert_virtual)

    # --- Gap 8+: manually declared virtual edges ---
    if annotation_file:
        from determined.ingestion.dynamic_edges import load_virtual_edge_annotations
        cursor.execute("DELETE FROM graph_edges WHERE edge_type = 'annotation'")
        for src, tgt, etype in load_virtual_edge_annotations(annotation_file):
            _insert_virtual(src, tgt, etype)

    connection.commit()


def _persist_polymorphic_edges(connection, cursor, insert_fn):
    """
    Auto-generate polymorphic virtual edges from ABC class hierarchy.

    For each abstract method M on ABC class A, and each concrete subclass S of A
    that overrides M, emit: A.M → S.M (edge_type='polymorphic').

    This closes Gap 8: callers of abstract methods now have a traversable path
    to concrete implementations without needing manual annotation.
    Uses Item 20 columns: classes.base_classes_json, classes.methods_json,
    functions.decorators_json.
    """
    import json as _json

    cursor.execute("DELETE FROM graph_edges WHERE edge_type = 'polymorphic'")

    # Step 1: find all ABC classes and their abstract methods
    abc_rows = connection.execute(
        "SELECT name, methods_json, file_path FROM classes "
        "WHERE base_classes_json LIKE '%ABC%' OR base_classes_json LIKE '%Abstract%'"
    ).fetchall()

    if not abc_rows:
        return

    # abc_method_map: {abc_class_name: set of abstract method names}
    abc_method_map: dict[str, set[str]] = {}
    for cls_name, methods_json, file_path in abc_rows:
        try:
            methods = _json.loads(methods_json or "[]")
        except Exception:
            continue
        abstract: set[str] = set()
        for method in methods:
            row = connection.execute(
                "SELECT decorators_json FROM functions WHERE name = ? AND file_path = ? LIMIT 1",
                (method, file_path),
            ).fetchone()
            if row:
                try:
                    decs = _json.loads(row[0] or "[]")
                except Exception:
                    decs = []
                if any("abstractmethod" in d for d in decs):
                    abstract.add(method)
        if abstract:
            abc_method_map[cls_name] = abstract

    if not abc_method_map:
        return

    # Step 2: find concrete subclasses
    all_classes = connection.execute(
        "SELECT name, base_classes_json, methods_json FROM classes"
    ).fetchall()

    for sub_name, bases_json, sub_methods_json in all_classes:
        try:
            bases = _json.loads(bases_json or "[]")
        except Exception:
            bases = []
        try:
            sub_methods = set(_json.loads(sub_methods_json or "[]"))
        except Exception:
            sub_methods = set()

        for base in bases:
            abstract_methods = abc_method_map.get(base)
            if not abstract_methods:
                continue
            for method in abstract_methods:
                if method in sub_methods:
                    # Concrete override found — emit polymorphic edge
                    src = f"{base}.{method}"
                    tgt = f"{sub_name}.{method}"
                    insert_fn(src, tgt, 'polymorphic')


def _recalculate_hot_files(connection):
    """
    Recalculate files.is_hot after the graph is written.

    A file is HOT if it contains at least one project-defined symbol that has
    >= 3 distinct callers in graph_edges. This replaces the parse-time
    approximation (bool(mutations)) which flagged 88%+ of files as HOT.
    Threshold 3 targets ~20% of files — meaningful signal, not noise.
    """
    cursor = connection.cursor()
    cursor.execute("UPDATE files SET is_hot = 0")
    cursor.execute("""
        UPDATE files SET is_hot = 1
        WHERE file_path IN (
            SELECT DISTINCT fn.file_path
            FROM functions fn
            WHERE fn.name IN (
                SELECT callee
                FROM graph_edges
                WHERE callee IN (SELECT name FROM functions)
                GROUP BY callee
                HAVING COUNT(DISTINCT caller) >= 3
                UNION
                SELECT SUBSTR(callee, INSTR(callee, '.') + 1)
                FROM graph_edges
                WHERE INSTR(callee, '.') > 0
                  AND SUBSTR(callee, INSTR(callee, '.') + 1) IN (SELECT name FROM functions)
                GROUP BY callee
                HAVING COUNT(DISTINCT caller) >= 3
            )
        )
    """)
    connection.commit()


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

    from determined.identity.symbol_identity import all_name_forms
    symbol_names_batch: list[tuple[str, str, str]] = []

    if files_in_run:
        placeholders = ",".join("?" * len(files_in_run))
        cursor.execute(
            f"DELETE FROM symbol_names WHERE canonical_id IN ("
            f"  SELECT DISTINCT source_id FROM graph_edges WHERE caller_file IN ({placeholders})"
            f")",
            list(files_in_run),
        )

    for edge in edges:
        source_id, target_id = edge_identity(edge.caller, edge.callee)
        etype = getattr(edge, "edge_type", "static")
        cursor.execute("""
        INSERT INTO graph_edges (
            source_id,
            target_id,
            caller,
            callee,
            line_number,
            caller_file,
            resolved,
            edge_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id,
            target_id,
            edge.caller,
            edge.callee,
            getattr(edge, "line_number", None),
            getattr(edge, "caller_file", None),
            1 if getattr(edge, "resolved", False) else 0,
            etype,
        ))
        for name, ntype in all_name_forms(edge.caller):
            symbol_names_batch.append((source_id, name, ntype))
        for name, ntype in all_name_forms(edge.callee):
            symbol_names_batch.append((target_id, name, ntype))

    # Deduplicate and insert symbol_names
    seen_names: set[tuple[str, str]] = set()
    for canonical_id, name, ntype in symbol_names_batch:
        key = (canonical_id, name)
        if key not in seen_names:
            seen_names.add(key)
            cursor.execute(
                "INSERT OR IGNORE INTO symbol_names (canonical_id, name, name_type) VALUES (?, ?, ?)",
                (canonical_id, name, ntype),
            )

    connection.commit()