# determined/ui/ui_server.py
#
# Flask + SocketIO server for the developer console UI.
# Start via: python -m determined.agent.local_agent --ui

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.agent.knowledge_status import coverage_summary

import time as _time

_TEMPLATE_DIR = str(Path(__file__).parent / "templates")
_STATIC_DIR   = str(Path(__file__).parent / "static")
_SESSION_FILE = Path(__file__).parent.parent.parent / ".determined_session.json"

app = Flask(__name__, template_folder=_TEMPLATE_DIR, static_folder=_STATIC_DIR)
app.config["SECRET_KEY"] = "dev-console-local"
# dev tool: re-read templates from disk on every request so edits take effect
# on browser reload without a server restart
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


def _emit_log(msg: str) -> None:
    """Broadcast a log line to all connected clients (server_log event)."""
    ts = _time.strftime("%H:%M:%S")
    socketio.emit("server_log", {"ts": ts, "msg": msg})


# shared state (single-user local tool)
_oracle: DBOracle | None = None
_assessor: Assessor | None = None
_db_path: str = ""
_source_path: str = ""
_history: list[dict] = []
_lock = threading.Lock()


def _save_session(db_path: str) -> None:
    try:
        _SESSION_FILE.write_text(json.dumps({"db_path": db_path}), encoding="utf-8")
    except Exception:
        pass


def _load_session() -> str | None:
    try:
        if _SESSION_FILE.exists():
            data = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
            p = data.get("db_path", "")
            if p and Path(p).exists():
                return p
    except Exception:
        pass
    return None


def init(db_path: str) -> None:
    global _oracle, _assessor, _db_path
    _oracle   = DBOracle(db_path)
    # Migrate older DBs forward — ensure_schema is idempotent (CREATE IF NOT EXISTS)
    from determined.persistence.persistence_engine import ensure_schema
    ensure_schema(_oracle.conn)
    _assessor = Assessor(_oracle)
    _db_path  = db_path
    _save_session(db_path)


def _corpus_status() -> dict:
    """Quick stats for the status bar — no LLM, pure DB queries."""
    if not _oracle:
        return {}
    try:
        files     = _oracle.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        hot       = _oracle.conn.execute("SELECT COUNT(*) FROM files WHERE is_hot=1").fetchone()[0]
        stubs     = _oracle.conn.execute("SELECT COUNT(*) FROM functions WHERE is_stub=1").fetchone()[0]
        artifacts = 0
        if _assessor and _assessor._knowledge_conn:
            artifacts = _assessor._knowledge_conn.execute(
                "SELECT COUNT(*) FROM knowledge_artifacts"
            ).fetchone()[0]
        db_name = Path(_db_path).stem.replace("_", " ")
        return {"files": files, "hot": hot, "stubs": stubs,
                "artifacts": artifacts, "db_name": db_name}
    except Exception:
        return {}


@app.route("/")
def index():
    from determined.agent.llm_client import LLM_DISPLAY_NAME
    db_name = Path(_db_path).name if _db_path else "no corpus"
    status  = _corpus_status()
    return render_template("console.html", db_name=db_name, status=status, model_name=LLM_DISPLAY_NAME)


def _corpus_map_data() -> dict:
    """Entry points + hot symbols for the corpus map panel. No LLM, no per-symbol risk queries."""
    if not _oracle:
        return {}
    from determined.agent.graph_utils import find_entry_points
    from determined.agent.risk_annotator import risk_badge

    # Pull any pre-computed risk records from corpus DB in one query.
    precomputed_risk: dict[str, str] = {}
    if _assessor and _assessor._knowledge_conn:
        try:
            rows = _assessor._knowledge_conn.execute(
                "SELECT subject, content FROM knowledge_artifacts WHERE kind = 'risk'"
            ).fetchall()
            for subj, content in rows:
                name = subj.replace("risk::", "")
                body = (content or "").lower()
                level = "HOT" if "hot" in body else "WARM" if "warm" in body else "SAFE"
                precomputed_risk[name] = level
        except Exception:
            pass

    def _risk_for(name: str) -> tuple[str, str]:
        level = precomputed_risk.get(name, "")
        return level, risk_badge(level) if level else ""

    eps = find_entry_points(_oracle)
    top_eps = []
    for ep in eps[:8]:
        level, badge = _risk_for(ep["name"])
        top_eps.append({
            "name": ep["name"],
            "file": Path(ep["file_path"]).name if ep["file_path"] else "",
            "out_degree": ep["out_degree"],
            "risk": level,
            "badge": badge,
        })

    # Hot symbols: use most_connected which correctly excludes builtins/externals
    # by requiring a known project file_path.
    from determined.agent.graph_utils import most_connected
    mc = most_connected(_oracle, n=10)
    hot_syms = []
    for r in mc:
        level, badge = _risk_for(r["symbol"])
        hot_syms.append({
            "name": r["symbol"],
            "file": Path(r["file_path"]).name if r["file_path"] else "",
            "caller_count": r["in_degree"],
            "risk": level,
            "badge": badge,
        })

    return {
        "entry_points": top_eps,
        "hot_symbols": hot_syms,
        "top_entry": eps[0]["name"] if eps else "",
    }


def _gap_summary_data() -> dict:
    """Structured gap data for sidebar rendering. No LLM. Safe to call on every corpus load."""
    if not _oracle:
        return {}
    try:
        conn = _oracle.conn
        total_fns = conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]
        missing_docs = conn.execute(
            "SELECT COUNT(*) FROM functions WHERE docstring IS NULL OR docstring = ''"
        ).fetchone()[0]
        total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        try:
            distilled = conn.execute(
                "SELECT COUNT(*) FROM semantic_summaries "
                "WHERE distilled IS NOT NULL AND distilled != ''"
            ).fetchone()[0]
        except Exception:
            distilled = 0
        k_conn = _assessor._knowledge_conn if _assessor else None
        design_note_count = 0
        if k_conn:
            try:
                design_note_count = k_conn.execute(
                    "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='design_note'"
                ).fetchone()[0]
            except Exception:
                pass
        mod_rows = conn.execute(
            "SELECT REPLACE(REPLACE(file_path, '\\', '/'), '\\\\', '/') as fp, "
            "SUM(CASE WHEN docstring IS NULL OR docstring='' THEN 1 ELSE 0 END) as missing, "
            "COUNT(*) as total FROM functions GROUP BY fp"
        ).fetchall()
        from collections import defaultdict
        mod_gaps: dict = defaultdict(lambda: [0, 0])
        for fp, miss, tot in mod_rows:
            parts = fp.replace("\\", "/").split("/")
            mod = parts[0] if parts else "."
            mod_gaps[mod][0] += miss
            mod_gaps[mod][1] += tot
        modules = [
            {"module": mod, "missing": m, "total": t}
            for mod, (m, t) in sorted(mod_gaps.items(), key=lambda x: -x[1][0])
            if m > 0
        ][:8]
        return {
            "total_fns": total_fns,
            "documented_fns": total_fns - missing_docs,
            "total_files": total_files,
            "distilled_files": distilled,
            "design_note_count": design_note_count,
            "modules": modules,
        }
    except Exception:
        return {}


def _queue_count() -> int:
    """Count of pending next_up workflow items."""
    if not _assessor:
        return 0
    try:
        k_conn = _assessor._knowledge_conn
        if not k_conn:
            return 0
        return k_conn.execute(
            "SELECT COUNT(*) FROM workflow_items WHERE kind='next_up' AND status='pending'"
        ).fetchone()[0]
    except Exception:
        return 0


def _check_design_doc_hint():
    """Scan for markdown docs with constraint density not yet ingested; write count to project_meta."""
    if not _oracle:
        return
    try:
        import json
        from determined.agent.doc_extractor import discover_docs
        root = _oracle.get_project_root()
        if not root:
            return
        docs = [d for d in discover_docs(root) if d.constraint_score >= 0.3]
        if not docs:
            _oracle.conn.execute("DELETE FROM project_meta WHERE key='design_doc_hint'")
            _oracle.conn.commit()
            return
        # Count how many are already ingested (have any design_note artifacts for their path)
        uningested = []
        for d in docs:
            row = _oracle.conn.execute(
                "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='design_note' AND subject LIKE ?",
                (f"%{d.rel_path}%",)
            ).fetchone()
            if row[0] == 0:
                uningested.append(d.rel_path)
        if uningested:
            hint = json.dumps({"count": len(uningested), "paths": uningested[:5]})
        else:
            hint = None
        if hint:
            _oracle.conn.execute(
                "INSERT OR REPLACE INTO project_meta (key, value) VALUES ('design_doc_hint', ?)", (hint,)
            )
        else:
            _oracle.conn.execute("DELETE FROM project_meta WHERE key='design_doc_hint'")
        _oracle.conn.commit()
    except Exception:
        pass


def _design_doc_hint():
    """Read stored design_doc_hint from project_meta; return parsed dict or None."""
    if not _oracle:
        return None
    try:
        import json
        row = _oracle.conn.execute(
            "SELECT value FROM project_meta WHERE key='design_doc_hint'"
        ).fetchone()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def _emit_corpus_ready(switched=False):
    if _oracle:
        s = _corpus_status()
        m = _corpus_map_data()
        emit("corpus_ready", {
            "switched": switched,
            "db_name": Path(_db_path).name,
            "db_path": _db_path,
            "source_path": _source_path,
            "files": s.get("files", 0),
            "hot": s.get("hot", 0),
            "stubs": s.get("stubs", 0),
            "artifacts": s.get("artifacts", 0),
            "top_entry": m.get("top_entry", ""),
            "entry_points": m.get("entry_points", []),
            "hot_symbols": m.get("hot_symbols", []),
            "stubs_list": m.get("stubs", []),
            "gap_summary": _gap_summary_data(),
            "queue_count": _queue_count(),
            "design_doc_hint": _design_doc_hint(),
        })


@socketio.on("connect")
def handle_connect():
    """On browser connect, send current corpus status so the UI updates immediately."""
    _emit_corpus_ready()


@socketio.on("corpus_status")
def handle_corpus_status():
    """Client requests a corpus_ready refresh (e.g. after ingest completes)."""
    _emit_corpus_ready()


@socketio.on("query")
def handle_query(data):
    global _history
    question = (data.get("question") or "").strip()
    if not question or _oracle is None:
        emit("error", {"message": "No question or corpus not loaded."})
        return

    q_lower = question.lower().rstrip("?")

    # special keywords — handle directly, bypass LLM pipeline
    if q_lower in ("what do you know", "coverage"):
        from determined.agent.knowledge_status import coverage_summary
        answer = coverage_summary(_oracle, _assessor)
        emit("answer", {"question": question, "answer": answer})
        return

    if q_lower in ("what haven't you explored", "what havent you explored", "unexplored"):
        from determined.agent.knowledge_status import coverage_report
        r = coverage_report(_oracle, _assessor)
        unknown = r["unknown_files"]
        if unknown:
            lines = [f"Unexplored files ({len(unknown)} of {r['total_files']}):"]
            lines += [f"  {f}" for f in unknown]
            answer = "\n".join(lines)
        else:
            answer = "All files have been surveyed."
        emit("answer", {"question": question, "answer": answer})
        return

    if q_lower in ("reprioritize", "suggest priorities", "suggest order"):
        status = _assessor.workflow_status()
        if status == "No active workflow items.":
            emit("answer", {"question": question, "answer": status})
            return
        msgs = [
            {"role": "system", "content":
                "You are a project planning assistant. Given a list of workflow items, "
                "suggest a priority ordering with brief reasoning for each position. "
                "End with: 'To apply this order, type: reorder as <id>,<id>,...'"},
            {"role": "user", "content":
                f"Here are the current workflow items:\n\n{status}\n\n"
                "Suggest a priority order for the active backlog/next_up items, "
                "considering dependencies and logical sequencing."},
        ]
        try:
            from determined.agent.llm_client import chat as _llm_chat
            answer = _llm_chat(msgs) or "(reprioritize unavailable: no response)"
        except Exception as exc:
            answer = f"(reprioritize unavailable: {exc})"
        emit("answer", {"question": question, "answer": answer})
        return

    if q_lower in ("discover", "discover more"):
        sid = request.sid
        def _run_discover():
            try:
                from determined.agent.discovery_agent import run as discover_run
                from determined.agent.knowledge_status import coverage_summary, coverage_report
                batch = 0
                while True:
                    batch += 1
                    rpt = coverage_report(_oracle, _assessor)
                    remaining = rpt.get("unknown_total", 0)
                    if remaining == 0:
                        break
                    socketio.emit("status", {"message": f"Discovering… batch {batch} ({remaining} files remaining)"}, to=sid)
                    found = discover_run(_db_path, limit=20, verbose=False)
                    if found == 0:
                        break
                answer = coverage_summary(_oracle, _assessor)
                socketio.emit("answer", {"question": question, "answer": answer}, to=sid)
            except Exception as exc:
                socketio.emit("error", {"message": f"Discovery error: {exc}"}, to=sid)
        threading.Thread(target=_run_discover, daemon=True).start()
        return

    emit("status", {"message": "Thinking..."})

    # import here to avoid circular at module level
    from determined.agent.local_agent import _answer

    try:
        trace = {}
        with _lock:
            answer, _history = _answer(
                question, _history, _oracle, _assessor, verbose=True, _trace=trace
            )
        emit("answer", {
            "question": question,
            "answer":   answer,
            "trace":    trace,
        })
    except Exception as exc:
        emit("error", {"message": f"Pipeline error: {exc}"})


# Tab -> direct tool dispatch. These are deterministic structural lookups;
# no LLM needed, so they're instant and never hit LLM timeouts.
_TAB_TOOLS = {
    "work_queue": ("workflow_status",      {}),
    "docstrings": ("missing_docstrings",   {"limit": 50}),
    "todos":      ("find_todos",           {"limit": 100}),
}


def _dead_code_answer() -> str:
    """Pull dead-code candidates stored by extract_design_facts (subject 'dead::%')."""
    if not _assessor or not _assessor._knowledge_conn:
        return "No knowledge DB - run 'extract design facts' first."
    rows = _assessor._knowledge_conn.execute(
        "SELECT subject, content FROM knowledge_artifacts "
        "WHERE subject LIKE 'dead::%' ORDER BY subject"
    ).fetchall()
    if not rows:
        return "No dead-code candidates found (or facts not yet extracted)."
    lines = [f"Dead-code candidates ({len(rows)}):"]
    lines += [f"  {r[0].replace('dead::', '')}" for r in rows]
    return "\n".join(lines)

@socketio.on("tab_query")
def handle_tab_query(data):
    """Run a named tab query via direct tool dispatch - no LLM, results to tab_answer."""
    tab      = (data.get("tab") or "").strip()
    question = (data.get("question") or "").strip()
    if not tab or _oracle is None:
        emit("tab_answer", {"tab": tab, "answer": "No corpus loaded.", "question": question})
        return

    sid = request.sid

    def _run():
        try:
            if tab == "unexplored":
                from determined.agent.knowledge_status import coverage_report
                r = coverage_report(_oracle, _assessor)
                unknown = r["unknown_files"]
                answer = ("\n".join([f"Unexplored files ({len(unknown)} of {r['total_files']}):"]
                          + [f"  {f}" for f in unknown]) if unknown else "All files have been surveyed.")

            elif tab == "discover":
                from determined.agent.knowledge_status import coverage_summary
                answer = coverage_summary(_oracle, _assessor)

            elif tab == "dead_code":
                answer = _dead_code_answer()

            elif tab in _TAB_TOOLS:
                from determined.agent.agent_tools import dispatch
                tool, args = _TAB_TOOLS[tab]
                answer = dispatch(tool, args, _oracle, _assessor)

            else:
                answer = f"(no handler for tab '{tab}')"

            socketio.emit("tab_answer", {"tab": tab, "answer": answer, "question": question}, to=sid)
        except Exception as exc:
            socketio.emit("tab_answer", {"tab": tab, "answer": f"Error: {exc}", "question": question}, to=sid)

    threading.Thread(target=_run, daemon=True).start()


@socketio.on("clear_history")
def handle_clear():
    global _history
    with _lock:
        _history = []
    emit("status", {"message": "History cleared."})


@socketio.on("browse")
def handle_browse(data):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        path = filedialog.askdirectory(title="Select project folder")
        root.destroy()
        emit("browse_result", {"path": path or ""})
    except Exception as exc:
        emit("browse_result", {"path": "", "error": str(exc)})


def _staleness_check(db_path: str, source_path: str) -> dict:
    """Compare source file mtimes against last_modified stored in DB files table.
    Returns {stale_count, new_count, last_ingested_ts}."""
    import os
    try:
        conn = sqlite3.connect(db_path)
        rows = {r[0]: r[1] for r in conn.execute(
            "SELECT file_path, last_modified FROM files"
        )}
        conn.close()
    except Exception:
        return {"stale_count": 0, "new_count": 0, "last_ingested_ts": None}

    last_ts = max(rows.values()) if rows else None
    stale, new = 0, 0
    root = Path(source_path)
    for f in root.rglob("*.py"):
        try:
            rel = str(f.relative_to(root))
            mtime = f.stat().st_mtime
            if rel in rows:
                if mtime > rows[rel]:
                    stale += 1
            else:
                new += 1
        except Exception:
            pass
    return {"stale_count": stale, "new_count": new, "last_ingested_ts": last_ts}


@socketio.on("scan")
def handle_scan(data):
    path = (data.get("path") or "").strip()
    if not path:
        emit("scan_result", {"error": "No path provided."})
        return
    target = Path(path).resolve()
    if not target.is_dir():
        emit("scan_result", {"error": f"Not a directory: {path}"})
        return
    try:
        from determined.ingestion.scan_project_files import load_ignore_list, should_ignore_path
        from determined.engine.db_resolver import resolve_analysis_db_path
        extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".c", ".cpp", ".h"}
        ignored = load_ignore_list(target)
        files = [
            f for f in target.rglob("*")
            if f.is_file() and f.suffix in extensions
            and not should_ignore_path(f.relative_to(target), ignored)
        ]
        total_bytes = sum(f.stat().st_size for f in files)
        db_path = resolve_analysis_db_path(str(target))
        db_exists = Path(db_path).exists()
        staleness = _staleness_check(db_path, str(target)) if db_exists else {}
        emit("scan_result", {
            "path": str(target),
            "file_count": len(files),
            "size_mb": round(total_bytes / (1024 * 1024), 1),
            "db_exists": db_exists,
            "db_path": db_path,
            **staleness,
        })
    except Exception as exc:
        emit("scan_result", {"error": str(exc)})


@socketio.on("load_corpus")
def handle_load_corpus(data):
    """Load an existing corpus DB without re-ingesting."""
    db_path = (data.get("db_path") or "").strip()
    if not db_path or not Path(db_path).exists():
        emit("ingest_error", {"message": f"DB not found: {db_path}"})
        return
    init(db_path)
    _emit_corpus_ready(switched=True)


@socketio.on("ingest")
def handle_ingest(data):
    path = (data.get("path") or "").strip()
    if not path:
        emit("ingest_error", {"message": "No path provided."})
        return

    target = Path(path).resolve()
    if not target.is_dir():
        emit("ingest_error", {"message": f"Not a directory: {path}"})
        return

    sid = request.sid

    def _run():
        try:
            from determined.engine.run_engine import EngineRunner
            from determined.engine.db_resolver import resolve_analysis_db_path

            db_path = resolve_analysis_db_path(str(target))
            # close active connection unconditionally before re-analyzing to avoid WinError 32
            with _lock:
                global _oracle, _assessor
                if _oracle:
                    try: _oracle.conn.close()
                    except Exception: pass
                    _oracle = None
                    _assessor = None
            if Path(db_path).exists():
                # clear tables in place rather than deleting the file (avoids WinError 32 from
                # external processes holding the file e.g. Windows Search / Defender)
                _clear_conn = sqlite3.connect(db_path)
                _tables = [r[0] for r in _clear_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()]
                for _t in _tables:
                    _clear_conn.execute(f"DELETE FROM {_t}")
                _clear_conn.commit()
                _clear_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                _clear_conn.close()
            global _source_path
            _source_path = str(target)
            socketio.emit("ingest_status", {"message": f"Analyzing {target.name}…"}, to=sid)

            corpus = type("Corpus", (), {"root_path": str(target)})()
            conn = sqlite3.connect(db_path)
            runner = EngineRunner()
            run_stats = runner.run(corpus=corpus, project_prefixes=[], repo_root=str(target), connection=conn) or {}
            conn.close()

            init(db_path)
            try:
                from determined.agent.agent_tools import ingest_design_docs
                socketio.emit("ingest_status", {"message": "Scanning for design docs…"}, to=sid)
                design_result = ingest_design_docs(_assessor, {})
                summary = design_result.splitlines()[0] if design_result else "Design docs: nothing found"
                socketio.emit("ingest_status", {"message": summary}, to=sid)
            except Exception as design_exc:
                socketio.emit("ingest_status", {"message": f"Design doc scan skipped: {design_exc}"}, to=sid)
            socketio.emit("ingest_done", {
                "db_name": Path(db_path).name,
                "db_path": db_path,
                "skipped": run_stats.get("skipped", 0),
            }, to=sid)
        except Exception as exc:
            socketio.emit("ingest_error", {"message": f"Analysis failed: {exc}"}, to=sid)

    threading.Thread(target=_run, daemon=True).start()


@socketio.on("symbol_quick")
def handle_symbol_quick(data):
    """
    Fast symbol lookup: DB only, no LLM. Returns essential facts for hover tooltip.
    """
    symbol = (data.get("symbol") or "").strip()
    if not symbol or _oracle is None:
        emit("symbol_quick_result", {"error": "no symbol"})
        return
    try:
        from determined.agent.risk_annotator import score_risk, risk_badge
        # Find symbol in DB
        row = _oracle.conn.execute(
            "SELECT name, file_path, line_number, docstring, is_stub FROM functions WHERE name = ? LIMIT 1",
            (symbol,)
        ).fetchone()
        sym_type = "function"
        is_stub = False
        if not row:
            row = _oracle.conn.execute(
                "SELECT name, file_path, line_number, docstring, 0 FROM classes WHERE name = ? LIMIT 1",
                (symbol,)
            ).fetchone()
            sym_type = "class"
        if not row:
            emit("symbol_quick_result", {"error": f"'{symbol}' not in corpus"})
            return
        is_stub = bool(row[4])
        caller_count = _oracle.conn.execute(
            "SELECT COUNT(*) FROM graph_edges WHERE callee = ? OR callee LIKE ?",
            (symbol, f"%.{symbol}")
        ).fetchone()[0]
        callee_count = _oracle.conn.execute(
            "SELECT COUNT(*) FROM graph_edges WHERE caller = ?",
            (symbol,)
        ).fetchone()[0]
        findings_count = 0
        if _assessor and _assessor._knowledge_conn:
            findings_count = _assessor._knowledge_conn.execute(
                "SELECT COUNT(*) FROM knowledge_artifacts WHERE subject LIKE ?",
                (f"%{symbol}%",)
            ).fetchone()[0]
        risk = score_risk(_oracle, symbol)
        badge = risk_badge(risk["level"])
        doc = (row[3] or "").strip()
        doc_snippet = doc.split("\n")[0][:120] if doc else ""
        file_short = (row[1] or "").replace("\\", "/").split("/")[-1]
        emit("symbol_quick_result", {
            "symbol": symbol,
            "type": sym_type,
            "file": file_short,
            "line": row[2],
            "risk": risk["level"],
            "badge": badge,
            "docstring": doc_snippet,
            "caller_count": caller_count,
            "callee_count": callee_count,
            "findings_count": findings_count,
            "is_stub": is_stub,
        })
    except Exception as exc:
        emit("symbol_quick_result", {"error": str(exc)})


@socketio.on("symbol_spotlight")
def handle_symbol_spotlight(data):
    """
    Full spotlight: runs understand_symbol pattern, returns structured sections.
    Fires multiple events as sections complete so the panel populates progressively.
    """
    symbol = (data.get("symbol") or "").strip()
    if not symbol or _oracle is None:
        emit("spotlight_error", {"message": "no symbol"})
        return
    sid = request.sid

    def _run():
        try:
            from determined.agent.agent_tools import dispatch
            for tool, args, key in [
                # Fast DB-only sections first — visible immediately
                ("symbol_intent",           {"symbol": symbol}, "intent"),
                ("risk_profile",            {"symbol": symbol}, "risk"),
                ("list_callers",            {"symbol": symbol}, "callers"),
                ("list_callees",            {"symbol": symbol}, "callees"),
                ("get_findings",            {"symbol": symbol}, "findings"),
                # LLM sections after — appear once model responds (~3-5s each)
                ("infer_behavior",          {"symbol": symbol}, "role"),
                ("check_design_violations", {"symbol": symbol}, "violations"),
            ]:
                result = dispatch(tool, args, _oracle, _assessor)
                socketio.emit("spotlight_section", {"symbol": symbol, "key": key, "content": result}, to=sid)
            socketio.emit("spotlight_done", {"symbol": symbol}, to=sid)
        except Exception as exc:
            socketio.emit("spotlight_error", {"message": str(exc)}, to=sid)

    threading.Thread(target=_run, daemon=True).start()


@socketio.on("symbol_analysis")
def handle_symbol_analysis(data):
    """
    On-demand analysis section: trace_data_flow or match_structural_pattern.
    Emits spotlight_section with key="data_flow" or "pattern" when done.
    """
    symbol = (data.get("symbol") or "").strip()
    tool   = (data.get("tool")   or "").strip()
    KEY_MAP = {"trace_data_flow": "data_flow", "match_structural_pattern": "pattern"}
    if not symbol or tool not in KEY_MAP or _oracle is None:
        emit("spotlight_error", {"message": "invalid symbol_analysis request"})
        return
    sid = request.sid
    key = KEY_MAP[tool]

    def _run():
        try:
            from determined.agent.agent_tools import dispatch
            result = dispatch(tool, {"symbol": symbol}, _oracle, _assessor)
            socketio.emit("spotlight_section", {"symbol": symbol, "key": key, "content": result}, to=sid)
        except Exception as exc:
            socketio.emit("spotlight_section",
                          {"symbol": symbol, "key": key,
                           "content": f"Error: {exc}"}, to=sid)

    threading.Thread(target=_run, daemon=True).start()


@socketio.on("store_finding_inline")
def handle_store_finding_inline(data):
    """Store a single finding (from an inline ⚑ chip) without going through chat."""
    symbol  = (data.get("symbol")  or "").strip()
    content = (data.get("content") or "").strip()
    if not symbol or not content or _oracle is None:
        emit("store_finding_result", {"ok": False, "symbol": symbol})
        return
    try:
        from determined.agent.agent_tools import dispatch
        dispatch("store_finding", {"symbol": symbol, "kind": "known_issue", "content": content},
                 _oracle, _assessor)
        emit("store_finding_result", {"ok": True, "symbol": symbol})
    except Exception as exc:
        emit("store_finding_result", {"ok": False, "symbol": symbol, "error": str(exc)})


@socketio.on("project_stub")
def handle_project_stub(data):
    """
    Run stub projector for a symbol. Background thread (LLM call may take ~30s).
    Emits stub_projection: {stub_name, file_path, line_number, suggested_body, context_summary}
    or {error: str}.
    """
    symbol = (data.get("symbol") or "").strip()
    if not symbol or _oracle is None:
        emit("stub_projection", {"error": "no symbol or corpus not loaded"})
        return
    if not _db_path:
        emit("stub_projection", {"error": "no corpus DB path available"})
        return
    sid = request.sid

    def _run():
        try:
            from determined.agent.stub_projector import project_stub
            result = project_stub(_db_path, symbol)
            socketio.emit("stub_projection", result, to=sid)
        except Exception as exc:
            socketio.emit("stub_projection", {"error": str(exc)}, to=sid)

    threading.Thread(target=_run, daemon=True).start()


_REQUIRED_TABLES = {"files", "functions", "graph_edges"}

def _is_valid_corpus(path: str) -> bool:
    """Return True if the .db file has the expected Determined schema tables."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        return _REQUIRED_TABLES.issubset(tables)
    except Exception:
        return False


@socketio.on("get_source")
def handle_get_source(data):
    """
    Return the source lines for a symbol (function or class).
    Uses ast.end_lineno for accurate function boundary detection.
    """
    symbol = (data.get("symbol") or "").strip()
    if not symbol or _oracle is None:
        emit("source_result", {"error": "no corpus"}); return
    try:
        # look up in functions first, then classes
        row = _oracle.conn.execute(
            "SELECT file_path, line_number FROM functions WHERE name = ? LIMIT 1", (symbol,)
        ).fetchone()
        if not row:
            row = _oracle.conn.execute(
                "SELECT file_path, line_number FROM classes WHERE name = ? LIMIT 1", (symbol,)
            ).fetchone()
        if not row:
            emit("source_result", {"error": f"'{symbol}' not found in corpus"}); return

        file_path, start_line = row
        if not file_path or not Path(file_path).exists():
            emit("source_result", {"error": f"source file not found: {file_path}"}); return

        src = Path(file_path).read_text(encoding="utf-8", errors="replace")
        lines = src.splitlines()

        # use AST to find the actual end line
        end_line = start_line + 60  # fallback cap
        try:
            import ast as _ast
            tree = _ast.parse(src)
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                    if node.name == symbol and node.lineno == start_line:
                        end_line = node.end_lineno
                        break
        except Exception:
            pass

        # clamp and extract
        start_idx = max(0, start_line - 1)
        end_idx   = min(len(lines), end_line)
        snippet   = lines[start_idx:end_idx]

        emit("source_result", {
            "symbol":    symbol,
            "file":      file_path.replace("\\", "/"),
            "file_short": Path(file_path).name,
            "start_line": start_line,
            "end_line":   end_line,
            "lines":      snippet,
        })
    except Exception as exc:
        emit("source_result", {"error": str(exc)})


@socketio.on("graph_subgraph")
def handle_graph_subgraph(data):
    """
    BFS N hops out from a root symbol in both directions.
    Returns {root, nodes:[{id,label,risk,file,line}], edges:[{source,target}]}.
    Caps at 80 nodes to avoid hairball. No LLM.
    """
    symbol = (data.get("symbol") or "").strip()
    hops   = max(1, min(3, int(data.get("hops", 2))))
    if not symbol or _oracle is None:
        emit("graph_result", {"error": "no corpus"}); return

    import builtins as _bi

    # Build a last-segment → canonical-name map for all functions/classes.
    # If a bare name maps to exactly one function, dotted callees like
    # self.foo or obj.bar.foo resolve to that function for graph traversal.
    # Ambiguous bare names (two+ functions named 'process') are kept dotted.
    def _build_name_index():
        idx: dict[str, list[str]] = {}
        for (name,) in _oracle.conn.execute("SELECT name FROM functions").fetchall():
            idx.setdefault(name, []).append(name)
        for (name,) in _oracle.conn.execute("SELECT name FROM classes").fetchall():
            idx.setdefault(name, []).append(name)
        return idx

    name_idx = _build_name_index()

    def _resolve(callee: str) -> str:
        """Return the best resolvable name for a callee string."""
        bare = callee.rsplit(".", 1)[-1] if "." in callee else callee
        if bare in dir(_bi):
            return ""  # builtin, skip
        # exact match wins
        if callee in name_idx:
            return callee
        # bare segment unambiguous → resolve
        if bare in name_idx and len(name_idx[bare]) == 1:
            return bare
        # ambiguous or unknown — keep bare for edge recording but don't expand
        return bare if bare not in dir(_bi) else ""

    try:
        bare_root = _resolve(symbol) or symbol

        visited: set[str] = set()
        edges_set: set[tuple] = set()
        frontier: set[str] = {bare_root}

        for _ in range(hops):
            next_frontier: set[str] = set()
            for sym in frontier:
                if sym in visited:
                    continue
                visited.add(sym)
                bare = sym.rsplit(".", 1)[-1]
                # callees
                rows = _oracle.conn.execute(
                    "SELECT DISTINCT callee FROM graph_edges WHERE caller = ? OR caller = ?",
                    (sym, bare),
                ).fetchall()
                for (callee,) in rows:
                    resolved = _resolve(callee)
                    if not resolved: continue
                    edges_set.add((sym, resolved))
                    if resolved not in visited:
                        next_frontier.add(resolved)
                # callers
                rows2 = _oracle.conn.execute(
                    "SELECT DISTINCT caller FROM graph_edges WHERE callee = ? OR callee LIKE ? OR callee = ? OR callee LIKE ?",
                    (sym, f"%.{sym}", bare, f"%.{bare}"),
                ).fetchall()
                for (caller,) in rows2:
                    resolved = _resolve(caller)
                    if not resolved: continue
                    edges_set.add((resolved, sym))
                    if resolved not in visited:
                        next_frontier.add(resolved)
                if len(visited) + len(next_frontier) > 80:
                    break
            frontier = next_frontier - visited
            if not frontier or len(visited) > 80:
                break

        # trim to 80 nodes closest to root (visited is BFS order)
        keep = set(list(visited)[:80])
        filtered_edges = [(s, t) for s, t in edges_set if s in keep and t in keep]

        # look up file/line for each node
        def node_info(sym):
            row = _oracle.conn.execute(
                "SELECT file_path, line_number FROM functions WHERE name = ? LIMIT 1", (sym,)
            ).fetchone()
            if not row:
                row = _oracle.conn.execute(
                    "SELECT file_path, line_number FROM classes WHERE name = ? LIMIT 1", (sym,)
                ).fetchone()
            fp = (row[0] if row else "").replace("\\", "/").split("/")[-1]
            ln = row[1] if row else 0
            return fp, ln

        # risk level from knowledge.db if available
        def node_risk(sym):
            if not (_assessor and _assessor._knowledge_conn):
                return "cool"
            row = _assessor._knowledge_conn.execute(
                "SELECT content FROM knowledge_artifacts WHERE subject = ? AND kind = 'risk' LIMIT 1",
                (f"risk::{sym}",)
            ).fetchone()
            if row:
                body = (row[0] or "").lower()
                if "hot" in body: return "hot"
                if "warm" in body: return "warm"
            return "cool"

        nodes = []
        for sym in keep:
            fp, ln = node_info(sym)
            nodes.append({"id": sym, "label": sym.rsplit(".", 1)[-1],
                          "risk": node_risk(sym), "file": fp, "line": ln})

        emit("graph_result", {
            "root": bare_root,
            "nodes": nodes,
            "edges": [{"source": s, "target": t} for s, t in filtered_edges],
        })
    except Exception as exc:
        emit("graph_result", {"error": str(exc)})


def _frontier_rows(conn, mode: str):
    """
    Core frontier query parameterized by mode:
      direct — functional callers of stubs  (amber -> red)
      chain  — stubs that call other stubs  (gray  -> red)
      all    — both combined
    Returns rows of (caller_name, caller_file, caller_line, callee_name, callee_file, callee_line).
    """
    def _run(caller_stub: int, callee_stub: int):
        return conn.execute("""
            SELECT DISTINCT f_caller.name, f_caller.file_path, f_caller.line_number,
                            f_callee.name, f_callee.file_path, f_callee.line_number
            FROM graph_edges ge
            JOIN functions f_caller ON ge.source_id = f_caller.name
            JOIN functions f_callee ON (
                ge.target_id = f_callee.name
                OR ge.target_id LIKE '%.' || f_callee.name
            )
            WHERE f_caller.is_stub = ? AND f_callee.is_stub = 1
        """, (caller_stub,)).fetchall()

    if mode == "chain":
        return _run(caller_stub=1, callee_stub=1)
    if mode == "all":
        return _run(0, 1) + _run(1, 1)
    return _run(caller_stub=0, callee_stub=1)  # default: direct


@socketio.on("get_topology")
def handle_get_topology():
    """Return detect_topology() + frontier_coverage() as combined text."""
    if _oracle is None:
        emit("topology_result", {"error": "No corpus loaded."})
        return
    try:
        from determined.agent.agent_tools import dispatch
        topo = dispatch("detect_topology", {}, _oracle, _assessor)
        coverage = dispatch("frontier_coverage", {}, _oracle, _assessor)
        emit("topology_result", {"text": topo + "\n\n" + coverage})
    except Exception as exc:
        emit("topology_result", {"error": str(exc)})


@socketio.on("get_frontier_graph")
def handle_get_frontier_graph(data):
    """
    Return the implementation frontier.
    mode: 'direct' (functional->stub), 'chain' (stub->stub), 'all' (both), 'abc' (ABC interface gaps).
    Nodes: red=stub, amber=frontier-caller, gray=stub-caller (chain), purple=abc-interface (abc mode).
    """
    if _oracle is None:
        emit("frontier_graph_result", {"error": "no corpus loaded"})
        return
    mode = (data or {}).get("mode", "direct")

    if mode == "orphan":
        # Orphan/disconnected mode: implemented fns with no real callers
        try:
            conn = _oracle.conn

            # Decorated functions are assumed framework-registered (e.g. @app.route,
            # @celery.task, @socketio.on); exclude to avoid false orphans. Pure
            # structural decorators (@property, @staticmethod, @classmethod) don't
            # register anything externally so they still qualify as orphans.
            _STRUCTURAL = {"property", "staticmethod", "classmethod"}
            rows = conn.execute(
                """
                SELECT f.name, f.file_path, f.line_number,
                       COUNT(ge.caller) AS total_callers,
                       SUM(CASE WHEN cf.is_stub = 1 THEN 1 ELSE 0 END) AS stub_callers,
                       f.decorators_json
                FROM functions f
                LEFT JOIN graph_edges ge ON (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
                LEFT JOIN functions cf ON cf.name = ge.caller
                WHERE f.is_stub = 0
                GROUP BY f.name, f.file_path, f.line_number
                HAVING total_callers = 0
                    OR (stub_callers IS NOT NULL AND stub_callers = total_callers)
                ORDER BY f.file_path, f.line_number
                LIMIT 80
                """
            ).fetchall()
            import json as _json
            def _has_framework_decorator(decorators_json):
                if not decorators_json:
                    return False
                decs = _json.loads(decorators_json)
                return any(d.split("(")[0].split(".")[-1] not in _STRUCTURAL for d in decs)
            rows = [r for r in rows if not _has_framework_decorator(r[5])]

            def _short(path):
                return (path or "").replace("\\", "/").split("/")[-1]

            nodes: dict[str, dict] = {}
            for name, file_path, line_no, total_callers, stub_callers, _decs in rows:
                role = "stranded" if (total_callers or 0) > 0 else "anticipatory"
                nodes[name] = {
                    "id": name, "label": name, "role": role,
                    "file": _short(file_path), "line": line_no or 0,
                }

            emit("frontier_graph_result", {
                "nodes": list(nodes.values()),
                "edges": [],
                "mode": mode,
                "stub_count": 0,
                "frontier_count": 0,
                "chain_count": 0,
                "anticipatory_count": sum(1 for n in nodes.values() if n["role"] == "anticipatory"),
                "stranded_count": sum(1 for n in nodes.values() if n["role"] == "stranded"),
            })
        except Exception as exc:
            emit("frontier_graph_result", {"error": str(exc)})
        return

    if mode == "abc":
        # ABC mode: show abstract-interface stubs grouped by class, edges from class->method
        try:
            from determined.agent.agent_tools import find_abc_gaps as _find_abc
            import json as _json
            conn = _oracle.conn

            abc_rows = conn.execute(
                "SELECT name, methods_json, file_path FROM classes "
                "WHERE base_classes_json LIKE '%ABC%' OR base_classes_json LIKE '%Abstract%'"
            ).fetchall()

            nodes: dict[str, dict] = {}
            edges: list[dict] = []

            def _short(path):
                return (path or "").replace("\\", "/").split("/")[-1]

            for cls_name, methods_json, cls_file in abc_rows:
                methods = _json.loads(methods_json or "[]")
                has_gap = False
                for method in methods:
                    row = conn.execute(
                        "SELECT file_path, line_number, is_stub FROM functions "
                        "WHERE name=? AND file_path=? LIMIT 1", (method, cls_file)
                    ).fetchone()
                    if not row or not row[2]:
                        continue
                    # Check for non-stub override
                    override = conn.execute(
                        "SELECT COUNT(*) FROM functions WHERE name=? AND is_stub=0 AND file_path!=?",
                        (method, cls_file)
                    ).fetchone()[0]
                    if override > 0:
                        continue
                    # Unimplemented abstract method — add stub node + edge from class
                    has_gap = True
                    if method not in nodes:
                        nodes[method] = {
                            "id": method, "label": method, "role": "stub",
                            "file": _short(row[0]), "line": row[1] or 0,
                        }
                    edges.append({"source": cls_name, "target": method})

                if has_gap and cls_name not in nodes:
                    nodes[cls_name] = {
                        "id": cls_name, "label": cls_name, "role": "abc",
                        "file": _short(cls_file), "line": 0,
                    }

            emit("frontier_graph_result", {
                "nodes": list(nodes.values()),
                "edges": edges,
                "mode": mode,
                "stub_count": sum(1 for n in nodes.values() if n["role"] == "stub"),
                "frontier_count": 0,
                "chain_count": 0,
                "abc_count": sum(1 for n in nodes.values() if n["role"] == "abc"),
            })
        except Exception as exc:
            emit("frontier_graph_result", {"error": str(exc)})
        return

    try:
        rows = _frontier_rows(_oracle.conn, mode)

        def _short(path):
            return (path or "").replace("\\", "/").split("/")[-1]

        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        for caller, caller_file, caller_line, callee, callee_file, callee_line in rows:
            if caller not in nodes:
                caller_stub = _oracle.conn.execute(
                    "SELECT is_stub FROM functions WHERE name=? LIMIT 1", (caller,)
                ).fetchone()
                role = "chain" if (caller_stub and caller_stub[0]) else "frontier"
                nodes[caller] = {"id": caller, "label": caller, "role": role,
                                 "file": _short(caller_file), "line": caller_line or 0}
            if callee not in nodes:
                nodes[callee] = {"id": callee, "label": callee, "role": "stub",
                                 "file": _short(callee_file), "line": callee_line or 0}
            edges.append({"source": caller, "target": callee})

        emit("frontier_graph_result", {
            "nodes": list(nodes.values()),
            "edges": edges,
            "mode": mode,
            "stub_count": sum(1 for n in nodes.values() if n["role"] == "stub"),
            "frontier_count": sum(1 for n in nodes.values() if n["role"] == "frontier"),
            "chain_count": sum(1 for n in nodes.values() if n["role"] == "chain"),
        })
    except Exception as exc:
        emit("frontier_graph_result", {"error": str(exc)})


@socketio.on("project_stub_request")
def handle_project_stub(data):
    """Call stub_projector for a single stub and return the suggested implementation."""
    stub_name = (data or {}).get("symbol", "").strip()
    if not stub_name or _oracle is None:
        emit("project_stub_result", {"error": "stub name and corpus required"})
        return
    try:
        from determined.agent.stub_projector import project_stub as _proj
        result = _proj(_oracle.db_path, stub_name)
        emit("project_stub_result", result)
    except Exception as exc:
        emit("project_stub_result", {"error": str(exc)})


@socketio.on("stub_score_quick")
def handle_stub_score_quick(data):
    """
    Fast structural score for a symbol — no LLM, pure DB.
    Returns caller_count, is_stub, risk_level, file, line.
    Fires on node click so UI can show a badge immediately.
    """
    symbol = (data or {}).get("symbol", "").strip()
    if not symbol or _oracle is None:
        emit("stub_score_result", {"error": "no corpus"})
        return
    conn = _oracle.conn
    row = conn.execute(
        "SELECT f.file_path, f.line_number, f.is_stub "
        "FROM functions f WHERE f.name = ? LIMIT 1", (symbol,)
    ).fetchone()
    caller_count = conn.execute(
        "SELECT COUNT(DISTINCT caller) FROM graph_edges WHERE callee = ? OR callee LIKE '%.' || ?",
        (symbol, symbol),
    ).fetchone()[0]
    try:
        from determined.agent.risk_annotator import score_risk
        risk = score_risk(_oracle, symbol)
        risk_level = risk["level"]
    except Exception:
        risk_level = "UNKNOWN"
    emit("stub_score_result", {
        "symbol": symbol,
        "caller_count": caller_count,
        "is_stub": bool(row and row[2]) if row else False,
        "risk_level": risk_level,
        "file": (row[0] or "").replace("\\", "/").split("/")[-1] if row else "",
        "line": row[1] if row else 0,
    })


@socketio.on("reason_about_request")
def handle_reason_about(data):
    """
    Run the full Decompose -> Route -> Synthesize pipeline on a symbol.
    Runs in a background thread so the socket server stays responsive.
    Emits reason_about_progress: { msg } as each step completes.
    Emits reason_about_result: { symbol, text } or { error } when done.
    """
    symbol = (data or {}).get("symbol", "").strip()
    question = (data or {}).get("question", "").strip()
    if not symbol or _oracle is None or _assessor is None:
        emit("reason_about_result", {"error": "symbol and corpus required"})
        return
    if not question:
        question = (f"should {symbol} be a standalone function or a method, "
                    f"and is it the right priority to implement next?")

    db_path   = _oracle.db_path
    k_conn_db = getattr(_assessor, "_knowledge_conn", None)
    k_db_path = getattr(k_conn_db, "row_factory", None)  # just a sentinel check
    # Pass paths not connections — background thread opens its own connections
    k_path = None
    if k_conn_db is not None:
        try:
            k_path = k_conn_db.execute("PRAGMA database_list").fetchone()[2]
        except Exception:
            pass

    def _run():
        import sqlite3 as _sq
        conn = _sq.connect(db_path, check_same_thread=False)
        k_conn = _sq.connect(k_path, check_same_thread=False) if k_path else None

        def progress(msg: str):
            socketio.emit("reason_about_progress", {"msg": msg})

        try:
            from determined.agent.reasoning_engine import reason_about as _reason
            text = _reason(question, symbol, conn, knowledge_conn=k_conn,
                           progress_fn=progress)
            socketio.emit("reason_about_result", {"symbol": symbol, "text": text})
        except Exception as exc:
            socketio.emit("reason_about_result", {"error": str(exc)})
        finally:
            conn.close()
            if k_conn:
                k_conn.close()

    threading.Thread(target=_run, daemon=True).start()


@socketio.on("frontier_to_queue")
def handle_frontier_to_queue(_data):
    """
    Load stub ranking from list_stubs() and write each into workflow_items
    as kind='next_up' ranked by caller count. Idempotent — skips stubs
    already present as next_up items.
    """
    if _oracle is None or _assessor is None:
        emit("frontier_to_queue_result", {"error": "no corpus loaded"})
        return
    try:
        from determined.agent.agent_tools import list_stubs
        from determined.intent.workflow_store import list_items, add_item

        raw = list_stubs(_oracle, {"limit": 50})
        # parse the text output into (name, callers) pairs
        entries = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("Stub functions"):
                continue
            # format: "name in file.py  (N callers)"
            parts = line.rsplit("(", 1)
            name = parts[0].split(" in ")[0].strip()
            try:
                callers = int(parts[1].split()[0]) if len(parts) > 1 else 0
            except (ValueError, IndexError):
                callers = 0
            if name:
                entries.append((name, callers))

        conn = _assessor._knowledge_conn
        if conn is None:
            emit("frontier_to_queue_result", {"error": "no knowledge DB"})
            return

        existing = {i["subject"] for i in list_items(conn, kind="next_up", status="active", limit=200)}
        added = 0
        for rank, (name, callers) in enumerate(entries, 1):
            subject = f"implement stub: {name}"
            if subject not in existing:
                add_item(conn, kind="next_up", subject=subject,
                         content=f"{callers} caller(s) — ranked #{rank} by caller count",
                         rank=rank, provenance="frontier")
                added += 1

        emit("frontier_to_queue_result", {
            "added": added, "total": len(entries),
            "message": f"Added {added} stubs to build queue ({len(entries) - added} already present)"
        })
    except Exception as exc:
        emit("frontier_to_queue_result", {"error": str(exc)})


@socketio.on("call_tree_expand")
def handle_call_tree_expand(data):
    """
    Expand one node of the call tree.
    Returns direct callees (direction='down') or callers (direction='up') for a symbol.
    No LLM — pure DB query.
    """
    symbol = (data.get("symbol") or "").strip()
    direction = data.get("direction", "down")  # 'down' = callees, 'up' = callers
    if not symbol or _oracle is None:
        emit("call_tree_result", {"error": "no corpus", "symbol": symbol}); return
    import builtins as _bi
    # dotted names (self.foo, obj.bar) won't match as callers in the DB;
    # fall back to the bare last segment so re-rooting on a dotted callee works
    bare_symbol = symbol.rsplit(".", 1)[-1] if "." in symbol else symbol
    try:
        if direction == "down":
            rows = _oracle.conn.execute(
                """
                SELECT ge.callee, sr.file_path, ge.line_number
                FROM graph_edges ge
                LEFT JOIN symbol_references sr
                    ON ge.caller = sr.caller AND ge.callee = sr.callee
                WHERE ge.caller = ? OR ge.caller = ?
                ORDER BY ge.line_number
                """,
                (symbol, bare_symbol),
            ).fetchall()
            seen: dict[str, dict] = {}
            for callee, fp, ln in rows:
                bare = (callee or "").rsplit(".", 1)[-1]
                if not bare or bare in dir(_bi):
                    continue
                if callee not in seen:
                    file_short = (fp or "").replace("\\", "/").split("/")[-1]
                    seen[callee] = {"symbol": callee, "file": file_short, "line": ln or 0}
            children = list(seen.values())
        else:
            rows = _oracle.conn.execute(
                """
                SELECT ge.caller, sr.file_path, ge.line_number
                FROM graph_edges ge
                LEFT JOIN symbol_references sr
                    ON ge.caller = sr.caller AND ge.callee = sr.callee
                WHERE ge.callee = ? OR ge.callee LIKE ? OR ge.callee = ? OR ge.callee LIKE ?
                ORDER BY sr.file_path, ge.line_number
                """,
                (symbol, f"%.{symbol}", bare_symbol, f"%.{bare_symbol}"),
            ).fetchall()
            seen2: dict[str, dict] = {}
            for caller, fp, ln in rows:
                bare = (caller or "").rsplit(".", 1)[-1]
                if not bare or bare in dir(_bi):
                    continue
                if caller not in seen2:
                    file_short = (fp or "").replace("\\", "/").split("/")[-1]
                    seen2[caller] = {"symbol": caller, "file": file_short, "line": ln or 0}
            children = list(seen2.values())
        emit("call_tree_result", {
            "symbol": symbol,
            "direction": direction,
            "children": children,
        })
    except Exception as exc:
        emit("call_tree_result", {"error": str(exc), "symbol": symbol})


@socketio.on("list_dbs")
def handle_list_dbs():
    """Scan CWD for .db files and return list with schema validity flag."""
    import os
    cwd = Path(os.getcwd())
    dbs = []
    for p in sorted(cwd.glob("*.db")):
        valid = _is_valid_corpus(str(p))
        size_mb = round(p.stat().st_size / (1024 * 1024), 1)
        dbs.append({"name": p.name, "path": str(p), "valid": valid, "size_mb": size_mb})
    emit("db_list", {"dbs": dbs})


@socketio.on("load_db")
def handle_load_db(data):
    """Load an existing corpus DB without re-ingesting."""
    path = (data.get("path") or "").strip()
    if not path or not Path(path).exists():
        emit("error", {"message": f"DB not found: {path}"}); return
    if not _is_valid_corpus(path):
        emit("error", {"message": f"Not a valid Determined corpus: {path}"}); return
    try:
        init(path)
        _check_design_doc_hint()
        _emit_corpus_ready(switched=True)
        # Auto-orient on corpus load
        import threading
        sid = request.sid
        def _auto_orient():
            from determined.agent.local_agent import _answer
            global _history
            answer, _history = _answer("orient", _history, _oracle, _assessor, verbose=True)
            socketio.emit("answer", {"question": "orient", "answer": answer}, to=sid)
        threading.Thread(target=_auto_orient, daemon=True).start()
    except Exception as exc:
        emit("error", {"message": f"Failed to load {path}: {exc}"})


@socketio.on("bag_query")
def handle_bag_query(data):
    """Return bag contents as JSON for the Bag tab."""
    if _oracle is None:
        emit("bag_data", {"error": "no corpus loaded"})
        return
    bag_id = (data.get("bag") or "system").strip()
    try:
        if not _assessor or _assessor.bags is None:
            emit("bag_data", {"bag_id": bag_id, "items": [], "status": {}, "all_bags": []})
            return
        bags = _assessor.bags
        items = bags.list_items(bag_id=bag_id)
        status = bags.status()
        emit("bag_data", {
            "bag_id": bag_id,
            "items": [
                {**it["content"], "item_type": it["item_type"], "note": it.get("note") or ""}
                for it in items
            ],
            "status": status.get(bag_id, {}),
            "all_bags": sorted(status.keys()),
        })
    except Exception as exc:
        emit("bag_data", {"error": str(exc)})


@socketio.on("import_graph")
def handle_import_graph(data):
    """
    Return project-internal import graph as Cytoscape-compatible JSON.
    Nodes = files, edges = import relationships, grouped by top-level package.
    """
    if _oracle is None:
        emit("import_graph_result", {"error": "no corpus loaded"})
        return
    try:
        from determined.agent.edge_tools import _resolve_module_to_file, _rel
        rows = _oracle.conn.execute(
            "SELECT DISTINCT from_file, to_module FROM file_edges"
        ).fetchall()
        nodes_set: set[str] = set()
        edges: list[dict] = []
        for from_file, to_module in rows:
            resolved = _resolve_module_to_file(_oracle, to_module)
            if resolved:
                src = _rel(_oracle, from_file)
                dst = _rel(_oracle, resolved)
                nodes_set.add(src)
                nodes_set.add(dst)
                if src != dst:
                    edges.append({"source": src, "target": dst})

        def _group(path: str) -> str:
            parts = path.replace("\\", "/").split("/")
            return parts[0] if len(parts) > 1 else "root"

        # Assign a stable color index per group
        groups = sorted({_group(p) for p in nodes_set})
        group_idx = {g: i for i, g in enumerate(groups)}
        nodes = [
            {"id": p,
             "label": p.split("/")[-1].replace(".py", ""),
             "group": _group(p),
             "group_idx": group_idx[_group(p)]}
            for p in sorted(nodes_set)
        ]
        emit("import_graph_result", {
            "nodes": nodes,
            "edges": edges,
            "groups": groups,
        })
    except Exception as exc:
        emit("import_graph_result", {"error": str(exc)})


@socketio.on("bag_clear")
def handle_bag_clear(data):
    """Clear a bag and return updated bag_data."""
    bag_id = (data.get("bag") or "system").strip()
    if _assessor and _assessor.bags is not None:
        _assessor.bags.clear(bag_id)
    handle_bag_query({"bag": bag_id})


@socketio.on("open_file")
def handle_open_file(data):
    """Return full file content + DB symbol list for the editor panel."""
    path = (data.get("path") or "").strip()
    if not path or _oracle is None:
        emit("file_content", {"error": "no corpus loaded"}); return
    try:
        fp = Path(path)
        if not fp.is_absolute():
            root = Path(_oracle.get_project_root())
            fp = root / path
        if not fp.exists():
            # fuzzy: find first file in project root whose path ends with the given name
            root = Path(_oracle.get_project_root())
            matches = [p for p in root.rglob(fp.name) if p.is_file()]
            if matches:
                fp = matches[0]
            else:
                emit("file_content", {"error": f"not found: {path}"}); return
        content = fp.read_text(encoding="utf-8", errors="replace")
        # symbols from DB, keyed by filename suffix match
        name_pat = f"%{fp.name}"
        fns = _oracle.conn.execute(
            "SELECT name, line_number, docstring FROM functions "
            "WHERE replace(file_path,'\\\\','/') LIKE ? OR file_path LIKE ? ORDER BY line_number",
            (name_pat, name_pat)
        ).fetchall()
        cls = _oracle.conn.execute(
            "SELECT name, line_number, docstring FROM classes "
            "WHERE replace(file_path,'\\\\','/') LIKE ? OR file_path LIKE ? ORDER BY line_number",
            (name_pat, name_pat)
        ).fetchall()
        symbols = sorted(
            [{"name": n, "line": ln, "kind": "fn", "has_doc": bool(doc)} for n, ln, doc in fns] +
            [{"name": n, "line": ln, "kind": "cls", "has_doc": bool(doc)} for n, ln, doc in cls],
            key=lambda s: s["line"]
        )
        rel = str(fp).replace("\\", "/")
        root_str = _oracle.get_project_root().replace("\\", "/").rstrip("/") + "/"
        rel = rel.replace(root_str, "")
        emit("file_content", {
            "path": str(fp).replace("\\", "/"),
            "rel_path": rel,
            "lines": content.splitlines(),
            "symbols": symbols,
        })
    except Exception as exc:
        emit("file_content", {"error": str(exc)})


@socketio.on("save_file")
def handle_save_file(data):
    """Write edited file content back to disk."""
    path = (data.get("path") or "").strip()
    content = data.get("content", "")
    if not path:
        emit("save_result", {"error": "no path given"}); return
    try:
        fp = Path(path)
        if not fp.is_absolute():
            if _oracle is None:
                emit("save_result", {"error": "no corpus loaded"}); return
            fp = Path(_oracle.get_project_root()) / path
        if _oracle is not None:
            root = Path(_oracle.get_project_root()).resolve()
            try:
                fp.resolve().relative_to(root)
            except ValueError:
                emit("save_result", {"error": "path outside project root"}); return
        fp.write_text(content, encoding="utf-8")
        saved_path = str(fp).replace("\\", "/")
        emit("save_result", {"path": saved_path})
        # Auto-reingest the saved file so the corpus stays in sync
        if _assessor is not None and _db_path:
            try:
                from determined.ingestion.reingest_file import reingest_file
                reingest_file(_db_path, str(fp))
                _emit_corpus_ready()
            except Exception as e:
                emit("toast", {"message": f"Re-ingest failed: {e}", "kind": "warn"})
    except Exception as exc:
        emit("save_result", {"error": str(exc)})


@socketio.on("get_docstring_proposals")
def handle_get_docstring_proposals(_data=None):
    """Return active llm-proposed docstring items from the workflow store."""
    if _assessor is None:
        emit("docstring_proposals", {"error": "no corpus loaded"}); return
    import json as _json
    from determined.intent.workflow_store import list_items
    try:
        k_conn = _assessor._knowledge_conn
        rows = list_items(k_conn, kind="next_up", status="active", limit=200)
        proposals = []
        for r in rows:
            if not r["subject"].startswith("docstring::"):
                continue
            if r["provenance"] != "llm-proposed":
                continue
            try:
                data = _json.loads(r["content"])
            except Exception:
                continue
            proposals.append({
                "id": r["id"],
                "subject": r["subject"],
                "proposed_docstring": data.get("proposed_docstring", ""),
                "file_path": data.get("file_path", ""),
                "line_number": data.get("line_number"),
                "staleness_score": data.get("staleness_score"),
            })
        emit("docstring_proposals", {"proposals": proposals})
    except Exception as exc:
        emit("docstring_proposals", {"error": str(exc)})


def _insert_docstring(file_path: str, line_number: int, docstring: str) -> str:
    """
    Insert a docstring into a Python source file immediately after the def/class
    at line_number (1-based). Returns the modified source text.
    Raises ValueError if line_number doesn't point at a def/class line.
    """
    fp = Path(file_path)
    lines = fp.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    idx = line_number - 1
    if idx < 0 or idx >= len(lines):
        raise ValueError(f"line_number {line_number} out of range for {file_path}")
    def_line = lines[idx]
    stripped = def_line.lstrip()
    if not stripped.startswith(("def ", "class ", "async def ")):
        raise ValueError(f"line {line_number} is not a def/class: {def_line!r}")

    # Detect indentation of the def line, add 4 spaces for body
    indent = len(def_line) - len(def_line.lstrip())
    body_indent = " " * (indent + 4)

    # Format as a single-line or multi-line docstring
    text = docstring.strip().replace('"""', "'''")
    if "\n" in text:
        doc_lines = [f'{body_indent}"""\n']
        for part in text.splitlines():
            doc_lines.append(f"{body_indent}{part}\n")
        doc_lines.append(f'{body_indent}"""\n')
        doc_block = "".join(doc_lines)
    else:
        doc_block = f'{body_indent}"""{text}"""\n'

    # Insert after the def line (handle multi-line def signatures by finding the colon)
    insert_at = idx + 1
    # If the def line ends with a colon, we're on the last line of the signature.
    # Otherwise walk forward to find it.
    search = idx
    while search < len(lines) and ":" not in lines[search]:
        search += 1
    insert_at = search + 1

    lines.insert(insert_at, doc_block)
    return "".join(lines)


@socketio.on("accept_docstring_proposal")
def handle_accept_docstring_proposal(data):
    """Write the proposed docstring into the source file and mark the item done."""
    item_id = data.get("id")
    if _assessor is None or item_id is None:
        emit("proposal_result", {"error": "no corpus or missing id"}); return
    import json as _json
    from determined.intent.workflow_store import get_item, update_item
    try:
        k_conn = _assessor._knowledge_conn
        item = get_item(k_conn, item_id)
        if not item:
            emit("proposal_result", {"error": f"item {item_id} not found"}); return
        payload = _json.loads(item["content"])
        file_path = payload["file_path"]
        line_number = payload["line_number"]
        proposed = payload["proposed_docstring"]

        override = data.get("override_text", "").strip()
        if override:
            proposed = override
        new_content = _insert_docstring(file_path, line_number, proposed)
        Path(file_path).write_text(new_content, encoding="utf-8")
        update_item(k_conn, item_id, status="done")
        emit("proposal_result", {"ok": True, "id": item_id, "file_path": file_path})
    except Exception as exc:
        emit("proposal_result", {"error": str(exc), "id": item_id})


@socketio.on("dismiss_docstring_proposal")
def handle_dismiss_docstring_proposal(data):
    """Mark a docstring proposal as deferred without writing anything."""
    item_id = data.get("id")
    if _assessor is None or item_id is None:
        emit("proposal_result", {"error": "no corpus or missing id"}); return
    from determined.intent.workflow_store import update_item
    try:
        update_item(_assessor._knowledge_conn, item_id, status="deferred")
        emit("proposal_result", {"ok": True, "id": item_id, "dismissed": True})
    except Exception as exc:
        emit("proposal_result", {"error": str(exc), "id": item_id})


@socketio.on("propose_docstring_for")
def handle_propose_docstring_for(data):
    """Generate an on-demand docstring proposal for a single symbol via LLM."""
    symbol = (data.get("symbol") or "").strip()
    if not symbol or _oracle is None or _assessor is None:
        emit("docstring_proposal_for", {"error": "no corpus or missing symbol"}); return
    try:
        import json as _json
        from determined.agent.llm_client import chat as _llm_chat
        from determined.intent.workflow_store import add_item
        conn = _oracle.conn
        row = conn.execute(
            "SELECT name, file_path, line_number FROM functions WHERE name = ? LIMIT 1",
            (symbol,)
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT name, file_path, line_number FROM classes WHERE name = ? LIMIT 1",
                (symbol,)
            ).fetchone()
        if not row:
            emit("docstring_proposal_for", {"error": f"symbol not found: {symbol}"}); return
        name, file_path, line_number = row
        dist_row = conn.execute(
            "SELECT distilled FROM semantic_summaries WHERE subject = ? AND distilled IS NOT NULL",
            (file_path,)
        ).fetchone()
        context = dist_row[0] if dist_row else ""
        prompt = f"Write a concise one-line Python docstring for `{name}`."
        if context:
            prompt += f" The file is described as: {context}"
        prompt += " Reply with only the docstring text, no quotes, no triple-quotes."
        msgs = [
            {"role": "system", "content": "You are a Python docstring writer. Be concise and accurate."},
            {"role": "user", "content": prompt},
        ]
        proposed = _llm_chat(msgs) or context or f"No description available for {name}."
        content_json = _json.dumps({
            "proposed_docstring": proposed,
            "file_path": file_path,
            "line_number": line_number,
        })
        item_id = add_item(
            _assessor._knowledge_conn, kind="next_up",
            subject=f"docstring::{file_path}::{name}",
            content=content_json, provenance="llm-proposed",
        )
        emit("docstring_proposal_for", {
            "symbol": symbol,
            "proposed": proposed,
            "file_path": file_path,
            "line_number": line_number,
            "item_id": item_id,
        })
    except Exception as exc:
        emit("docstring_proposal_for", {"error": str(exc)})


@socketio.on("bag_add")
def handle_bag_add(data):
    """Add a single item to the system bag from the editor."""
    if _assessor is None or _assessor.bags is None:
        emit("bag_add_result", {"error": "no corpus"}); return
    item_type = (data.get("type") or "file").strip()
    value     = (data.get("value") or "").strip()
    note      = data.get("note") or None
    try:
        if item_type == "file":
            added = _assessor.bags.add_file("system", value, note=note)
        elif item_type == "symbol":
            added = _assessor.bags.add_symbol("system", value, note=note)
        else:
            added = False
        emit("bag_add_result", {"ok": True, "added": added, "value": value})
    except Exception as exc:
        emit("bag_add_result", {"error": str(exc)})


@socketio.on("direct_intent")
def handle_direct_intent(data):
    """Run intent-directed analysis pass, fill system bag, return chat summary."""
    intent = (data.get("intent") or "").strip()
    if not intent or _oracle is None:
        emit("intent_result", {"error": "no corpus or empty intent"}); return
    try:
        from determined.agent.intent_director import direct_from_intent, summary_text
        bags = _assessor.bags if _assessor else None
        result = direct_from_intent(_oracle, bags, intent)
        emit("intent_result", {"summary": summary_text(result), "result": result})
    except Exception as exc:
        emit("intent_result", {"error": str(exc)})


@socketio.on("get_knowledge_artifacts")
def handle_get_knowledge_artifacts(data=None):
    """Return knowledge artifacts for the Knowledge tab, filtered by kind."""
    if _assessor is None:
        emit("knowledge_artifacts", {"error": "no corpus"}); return
    kind = ((data or {}).get("kind") or "all").strip()
    try:
        k_conn = _assessor._knowledge_conn
        if kind == "design_note":
            rows = k_conn.execute(
                "SELECT id, kind, subject, content, provenance, created_at, needs_review "
                "FROM knowledge_artifacts WHERE kind='design_note' "
                "AND subject NOT LIKE 'sots::%' ORDER BY created_at DESC"
            ).fetchall()
        elif kind == "sots":
            rows = k_conn.execute(
                "SELECT id, kind, subject, content, provenance, created_at, needs_review "
                "FROM knowledge_artifacts WHERE kind='design_note' "
                "AND subject LIKE 'sots::%' ORDER BY subject"
            ).fetchall()
        elif kind == "known_issue":
            rows = k_conn.execute(
                "SELECT id, kind, subject, content, provenance, created_at, needs_review "
                "FROM knowledge_artifacts WHERE kind IN ('known_issue','violation') "
                "ORDER BY created_at DESC"
            ).fetchall()
        elif kind == "query_finding":
            rows = k_conn.execute(
                "SELECT id, kind, subject, content, provenance, created_at, needs_review "
                "FROM knowledge_artifacts WHERE kind='query_finding' "
                "ORDER BY created_at DESC"
            ).fetchall()
        else:  # all
            rows = k_conn.execute(
                "SELECT id, kind, subject, content, provenance, created_at, needs_review "
                "FROM knowledge_artifacts "
                "WHERE kind IN ('design_note','known_issue','violation','query_finding') "
                "ORDER BY kind, created_at DESC LIMIT 200"
            ).fetchall()
        artifacts = [
            {
                "id": r[0], "kind": r[1], "subject": r[2],
                "content": r[3], "provenance": r[4],
                "created_at": r[5], "needs_review": bool(r[6]),
            }
            for r in rows
        ]
        # counts per kind for filter badges
        counts = {}
        for k in ("design_note", "sots", "known_issue", "query_finding"):
            if k == "design_note":
                n = k_conn.execute(
                    "SELECT COUNT(*) FROM knowledge_artifacts "
                    "WHERE kind='design_note' AND subject NOT LIKE 'sots::%'"
                ).fetchone()[0]
            elif k == "sots":
                n = k_conn.execute(
                    "SELECT COUNT(*) FROM knowledge_artifacts "
                    "WHERE kind='design_note' AND subject LIKE 'sots::%'"
                ).fetchone()[0]
            else:
                n = k_conn.execute(
                    "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind=?", (k,)
                ).fetchone()[0]
            counts[k] = n
        emit("knowledge_artifacts", {
            "artifacts": artifacts,
            "kind": kind,
            "counts": counts,
            "total": sum(counts.values()),
        })
    except Exception as exc:
        emit("knowledge_artifacts", {"error": str(exc)})


@socketio.on("get_build_queue")
def handle_get_build_queue(_data=None):
    """Return workflow_items WHERE kind='next_up' for the Build queue tab."""
    if _assessor is None:
        emit("build_queue_result", {"error": "no corpus"}); return
    try:
        k_conn = _assessor._knowledge_conn
        if k_conn is None:
            emit("build_queue_result", {"error": "no knowledge DB"}); return
        from determined.intent.workflow_store import list_items
        items = list_items(k_conn, kind="next_up", status="all", limit=100)
        emit("build_queue_result", {"items": items})
    except Exception as exc:
        emit("build_queue_result", {"error": str(exc)})


@socketio.on("mark_queue_done")
def handle_mark_queue_done(data):
    """Mark a workflow item as done."""
    item_id = int((data or {}).get("id", 0))
    if not item_id or _assessor is None:
        emit("build_queue_result", {"error": "bad request"}); return
    try:
        from determined.intent.workflow_store import mark_done, list_items
        k_conn = _assessor._knowledge_conn
        mark_done(k_conn, item_id)
        items = list_items(k_conn, kind="next_up", status="all", limit=100)
        emit("build_queue_result", {"items": items})
    except Exception as exc:
        emit("build_queue_result", {"error": str(exc)})


@socketio.on("get_artifacts")
def handle_get_artifacts(_data=None):
    """Return tool artifacts (kind='artifact') for the Artifacts panel."""
    if _assessor is None:
        emit("artifacts_result", {"error": "no corpus"}); return
    try:
        k_conn = _assessor._knowledge_conn
        if k_conn is None:
            emit("artifacts_result", {"error": "no knowledge DB"}); return
        from determined.intent.workflow_store import list_artifacts, ensure_artifact_columns
        ensure_artifact_columns(k_conn.cursor())
        artifacts = list_artifacts(k_conn, limit=200)
        fresh = sum(1 for a in artifacts if a["artifact_status"] == "fresh")
        stale = sum(1 for a in artifacts if a["artifact_status"] == "stale")
        emit("artifacts_result", {"artifacts": artifacts, "fresh": fresh, "stale": stale})
    except Exception as exc:
        emit("artifacts_result", {"error": str(exc)})


@socketio.on("get_waypoints")
def handle_get_waypoints(_data=None):
    """Return knowledge_artifacts WHERE kind='waypoint' for the Waypoints tab."""
    if _assessor is None:
        emit("waypoints_result", {"error": "no corpus"}); return
    try:
        k_conn = _assessor._knowledge_conn
        if k_conn is None:
            emit("waypoints_result", {"error": "no knowledge DB"}); return
        rows = k_conn.execute(
            "SELECT id, subject, content, provenance, created_at FROM knowledge_artifacts "
            "WHERE kind='waypoint' ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
        waypoints = [
            {"id": r[0], "subject": r[1], "content": r[2], "provenance": r[3], "created_at": r[4]}
            for r in rows
        ]
        emit("waypoints_result", {"waypoints": waypoints})
    except Exception as exc:
        emit("waypoints_result", {"error": str(exc)})


_TOUR_STEPS = [
    {
        "index": 0,
        "title": "1. Orient — What is this codebase?",
        "instruction": "Run knowledge_status to see the corpus overview: file count, entry points, hot files, stubs, and coverage gaps.",
        "tool": "knowledge_status",
        "tool_args": {},
        "explanation": (
            "The knowledge layer starts from structural facts Determined extracts automatically at ingest time: "
            "entry points (functions with many callers or at module root), hot files (high inbound edge count), "
            "and stub files. The GAPS AT A GLANCE section shows docstring coverage, distillation coverage, "
            "and design note count — the three dimensions of how well the codebase is understood."
        ),
    },
    {
        "index": 1,
        "title": "2. Frontier: Direct — Are there broken stubs?",
        "instruction": "Run frontier_coverage to find functions that are called but not yet implemented.",
        "tool": "frontier_coverage",
        "tool_args": {},
        "explanation": (
            "Empty result is good news: the seed has 0 stubs. Nothing is definitively broken. "
            "The codebase is fully implemented at this scale. On a real project, this view shows "
            "exactly which stubs still need implementing and who is waiting on them."
        ),
    },
    {
        "index": 2,
        "title": "3. Frontier: Orphan — Find unwired code",
        "instruction": "Run find_orphaned_impls to find implemented functions that nothing calls yet.",
        "tool": "find_orphaned_impls",
        "tool_args": {},
        "explanation": (
            "validate_entry is 'anticipatory': it's implemented and correct, but not yet wired "
            "into any route. The action is clear: add a call from capture() or a route handler. "
            "create_app is a known false positive — Flask factories are always invisible to static "
            "call graphs because the WSGI server calls them, not your code."
        ),
    },
    {
        "index": 3,
        "title": "4. Frontier: ABC — Are all interfaces implemented?",
        "instruction": "Run find_abc_gaps to check whether all abstract methods have concrete implementations.",
        "tool": "find_abc_gaps",
        "tool_args": {},
        "explanation": (
            "EntryProcessor has 3 subclasses (CleanupProcessor, DeduplicateProcessor, "
            "EnrichmentProcessor) all with overrides in place — no gaps. On a project with "
            "unimplemented ABCs, this shows exactly which methods need implementing before the "
            "class hierarchy is wired up."
        ),
    },
    {
        "index": 4,
        "title": "5. Topology — Full structural picture",
        "instruction": "Run detect_topology to see the full shape of the codebase and its action queues.",
        "tool": "detect_topology",
        "tool_args": {},
        "explanation": (
            "The topology summarizes the whole corpus in one view. 0 stubs means nothing is broken. "
            "2 orphaned-impl means code is ready but not yet called. The 'Action queues' section "
            "translates the structural picture into concrete next steps: 'Write callers: "
            "orphaned-impl (2)' is the only thing the corpus is asking for."
        ),
    },
    {
        "index": 5,
        "title": "6. Tools — Conditional stubs",
        "instruction": "Run find_conditional_stubs to check for hidden runtime gaps behind conditionals.",
        "tool": "find_conditional_stubs",
        "tool_args": {},
        "explanation": (
            "No conditional stubs found means no hidden runtime gaps. A conditional stub raises "
            "NotImplementedError only on certain code paths — harder to spot than a pure stub "
            "and easier to miss in testing. Clean here means the seed is production-safe."
        ),
    },
    {
        "index": 6,
        "title": "7. Tools — Docstring health",
        "instruction": "Run docstring_health to see which functions lack documentation.",
        "tool": "docstring_health",
        "tool_args": {},
        "explanation": (
            "9 of 31 functions are missing docstrings. Determined flags these so you can document "
            "before the codebase grows too large to remember from context. The staleness check "
            "compares existing docstrings against the distilled code summary — divergence flags "
            "that the docstring no longer describes what the function actually does."
        ),
    },
    {
        "index": 7,
        "title": "8. Knowledge — What gaps remain?",
        "instruction": "Run gap_analysis to brainstorm what is missing, incomplete, or could bridge existing pieces.",
        "tool": "gap_analysis",
        "tool_args": {},
        "explanation": (
            "gap_analysis is generative: it uses the LLM to brainstorm typed fills (extend, bridge, mirror, "
            "consolidate) for the highest-signal area it finds. Results are explicitly framed as possibilities, "
            "not prescriptions. The proposals are stored in the build queue for you to accept or dismiss. "
            "Next steps: run extract_design_facts, then ingest_design_docs pointing at "
            "examples/commonplace/docs/DESIGN.md to populate the design-rule layer."
        ),
    },
]


@socketio.on("get_tour_steps")
def handle_get_tour_steps(_data=None):
    """Return tour step metadata (titles, instructions, explanations — no execution)."""
    steps = [
        {"index": s["index"], "title": s["title"],
         "instruction": s["instruction"], "explanation": s["explanation"]}
        for s in _TOUR_STEPS
    ]
    emit("tour_steps", {"steps": steps, "count": len(steps)})


@socketio.on("tour_run_step")
def handle_tour_run_step(data):
    """Run the tool for tour step N and emit tour_step_result."""
    if _oracle is None:
        emit("tour_step_result", {"error": "No corpus loaded. Load the Commonplace seed corpus first."})
        return
    step_index = (data or {}).get("step", 0)
    if step_index < 0 or step_index >= len(_TOUR_STEPS):
        emit("tour_step_result", {"error": f"Invalid step index {step_index}."})
        return
    step = _TOUR_STEPS[step_index]
    sid = request.sid

    def _run():
        try:
            from determined.agent.agent_tools import dispatch
            result = dispatch(step["tool"], step["tool_args"], _oracle, _assessor)
            socketio.emit("tour_step_result", {
                "step": step_index,
                "result": result,
                "explanation": step["explanation"],
            }, to=sid)
        except Exception as exc:
            socketio.emit("tour_step_result", {
                "step": step_index,
                "error": str(exc),
            }, to=sid)

    threading.Thread(target=_run, daemon=True).start()


# ── Workbench palette ─────────────────────────────────────────────────────────

_WORKBENCH_TOOLS = [
    {
        "id": "knowledge_status",
        "label": "Orient",
        "tool": "knowledge_status",
        "description": "File count, entry points, hot files, coverage gaps at a glance",
        "args": {},
    },
    {
        "id": "frontier_coverage",
        "label": "Frontier: Direct",
        "tool": "frontier_coverage",
        "description": "Called-but-not-implemented stubs and direct call coverage",
        "args": {},
    },
    {
        "id": "find_orphaned_impls",
        "label": "Frontier: Orphans",
        "tool": "find_orphaned_impls",
        "description": "Implemented functions that nothing calls yet (anticipatory + stranded)",
        "args": {},
    },
    {
        "id": "find_abc_gaps",
        "label": "Frontier: ABC",
        "tool": "find_abc_gaps",
        "description": "Abstract methods without concrete implementations",
        "args": {},
    },
    {
        "id": "detect_topology",
        "label": "Topology",
        "tool": "detect_topology",
        "description": "Full structural picture plus action queues",
        "args": {},
    },
    {
        "id": "find_conditional_stubs",
        "label": "Conditional stubs",
        "tool": "find_conditional_stubs",
        "description": "Hidden runtime gaps behind conditionals",
        "args": {},
    },
    {
        "id": "docstring_health",
        "label": "Doc health",
        "tool": "docstring_health",
        "description": "Missing and stale docstrings across the corpus",
        "args": {},
    },
    {
        "id": "gap_analysis",
        "label": "Gap analysis",
        "tool": "gap_analysis",
        "description": "LLM brainstorm of extend/bridge/mirror/consolidate fills for the highest-signal area",
        "args": {},
    },
    {
        "id": "check_design_violations",
        "label": "Design violations",
        "tool": "check_design_violations",
        "description": "SOTS and GRASP violations detected against ingested design notes",
        "args": {},
    },
    {
        "id": "concept_search",
        "label": "Concept search",
        "tool": "concept_search",
        "description": "Semantic + keyword search across all text surfaces",
        "args": {},
        "param": {"name": "query", "placeholder": "search term or concept"},
    },
    {
        "id": "extract_design_facts",
        "label": "Extract design facts",
        "tool": "extract_design_facts",
        "description": "Extract design facts from ingested design documents",
        "args": {},
    },
]


@socketio.on("get_workbench_tools")
def handle_get_workbench_tools(_data=None):
    """Return the Workbench tool palette (metadata only, no execution)."""
    emit("workbench_tools", {"tools": _WORKBENCH_TOOLS})


@socketio.on("workbench_run_tool")
def handle_workbench_run_tool(data):
    """Run a Workbench tool, store result as artifact, and emit workbench_tool_result."""
    if _oracle is None:
        emit("workbench_tool_result", {"error": "No corpus loaded.", "id": (data or {}).get("id", "")})
        return
    tool_id = (data or {}).get("id", "")
    extra_args = (data or {}).get("args", {})
    tool_def = next((t for t in _WORKBENCH_TOOLS if t["id"] == tool_id), None)
    if tool_def is None:
        emit("workbench_tool_result", {"error": f"Unknown tool: {tool_id}", "id": tool_id})
        return
    sid = request.sid

    def _run():
        try:
            from determined.agent.agent_tools import dispatch
            from determined.intent.workflow_store import store_artifact, ensure_artifact_columns
            tool_args = {**tool_def["args"], **extra_args}
            result = dispatch(tool_def["tool"], tool_args, _oracle, _assessor)
            artifact_name = tool_def["id"]
            k_conn = _assessor._knowledge_conn if _assessor else None
            if k_conn:
                ensure_artifact_columns(k_conn.cursor())
                store_artifact(k_conn, artifact_name, tool_def["tool"], str(result))
            socketio.emit("workbench_tool_result", {
                "id": tool_id,
                "result": result,
                "stored": k_conn is not None,
            }, to=sid)
        except Exception as exc:
            socketio.emit("workbench_tool_result", {
                "id": tool_id,
                "error": str(exc),
            }, to=sid)

    threading.Thread(target=_run, daemon=True).start()


# ── Discovery mode ────────────────────────────────────────────────────────────

_DISCOVERY_STEPS = [
    {
        "num": 1,
        "id": "orient",
        "label": "Orient",
        "tool": "knowledge_status",
        "args": {},
        "narrate": (
            "You just ran a knowledge status check on a codebase. "
            "Here is the output:\n\n{result}\n\n"
            "In 2-3 sentences, what does this tell you about the state of this codebase? "
            "Be specific to the actual numbers and gaps shown."
        ),
    },
    {
        "num": 2,
        "id": "frontier",
        "label": "Frontier",
        "tool": "frontier_coverage",
        "args": {},
        "narrate": (
            "You just ran a frontier coverage analysis on a codebase. "
            "Here is the output:\n\n{result}\n\n"
            "In 2-3 sentences, what does this reveal about implementation completeness? "
            "Be specific to any stubs or orphaned functions shown."
        ),
    },
    {
        "num": 3,
        "id": "topology",
        "label": "Topology",
        "tool": "detect_topology",
        "args": {},
        "narrate": (
            "You just ran a topology analysis on a codebase. "
            "Here is the output:\n\n{result}\n\n"
            "In 2-3 sentences, what does this reveal about the structural shape of the codebase "
            "and where work is concentrated?"
        ),
    },
    {
        "num": 4,
        "id": "orphans",
        "label": "Orphaned impls",
        "tool": "find_orphaned_impls",
        "args": {},
        "narrate": (
            "You just found orphaned implementations in a codebase. "
            "Here is the output:\n\n{result}\n\n"
            "In 2-3 sentences, what do these orphans suggest about wiring gaps or premature code?"
        ),
    },
    {
        "num": 5,
        "id": "doc_health",
        "label": "Doc health",
        "tool": "docstring_health",
        "args": {},
        "narrate": (
            "You just ran a docstring health check on a codebase. "
            "Here is the output:\n\n{result}\n\n"
            "In 2-3 sentences, what does the documentation coverage tell you about the maturity "
            "and maintainability of this codebase?"
        ),
    },
    {
        "num": 6,
        "id": "gaps",
        "label": "Gap analysis",
        "tool": "gap_analysis",
        "args": {},
        "narrate": (
            "You just ran a gap analysis on a codebase. "
            "Here is the output:\n\n{result}\n\n"
            "In 2-3 sentences, which gap category looks most actionable and why?"
        ),
    },
]

_DISCOVERY_SYNTHESIS_PROMPT = """\
You have completed a Discovery analysis of a codebase. Here are the findings from each step:

{summaries}

Based on all of this, write a concise synthesis (4-6 sentences) covering:
1. What kind of codebase this appears to be and how mature it is
2. The most pressing structural issue
3. One concrete next action the developer should take
"""


@socketio.on("discovery_start")
def handle_discovery_start(_data=None):
    """Run the 6-step Discovery arc, narrating each step with the LLM."""
    if _oracle is None:
        emit("discovery_step", {"error": "No corpus loaded."})
        return
    sid = request.sid

    def _run():
        from determined.agent.agent_tools import dispatch
        from determined.agent.local_agent import _call_ollama
        from determined.intent.workflow_store import store_artifact, ensure_artifact_columns

        narrations = []
        k_conn = _assessor._knowledge_conn if _assessor else None
        if k_conn:
            ensure_artifact_columns(k_conn.cursor())

        for step in _DISCOVERY_STEPS:
            _emit_log(f"Discovery step {step['num']}/{len(_DISCOVERY_STEPS)}: {step['label']} — running tool…")
            socketio.emit("discovery_progress", {
                "num": step["num"], "label": step["label"],
                "total": len(_DISCOVERY_STEPS),
            }, to=sid)
            # Run tool
            try:
                result = dispatch(step["tool"], step["args"], _oracle, _assessor)
            except Exception as exc:
                _emit_log(f"Discovery step {step['num']} ERROR: {exc}")
                socketio.emit("discovery_step", {
                    "num": step["num"], "id": step["id"], "label": step["label"],
                    "result": "", "narration": "", "error": str(exc),
                }, to=sid)
                narrations.append(f"Step {step['num']} ({step['label']}): ERROR — {exc}")
                continue

            _emit_log(f"Discovery step {step['num']}: tool done — narrating…")
            # Narrate
            prompt = step["narrate"].format(result=str(result)[:6000])
            try:
                narration = _call_ollama([{"role": "user", "content": prompt}])
            except Exception as exc:
                narration = f"(narration unavailable: {exc})"

            # Store tool result and narration as artifacts
            if k_conn:
                store_artifact(k_conn, f"discovery_{step['id']}", step["tool"], str(result))
                if narration:
                    store_artifact(k_conn, f"discovery_{step['id']}_narration", step["tool"], narration)

            _emit_log(f"Discovery step {step['num']}: {step['label']} complete")
            socketio.emit("discovery_step", {
                "num": step["num"], "id": step["id"], "label": step["label"],
                "result": result, "narration": narration,
            }, to=sid)

            narrations.append(f"Step {step['num']} ({step['label']}):\n{narration}")

        # Final synthesis
        _emit_log("Discovery: synthesizing all findings…")
        summaries_text = "\n\n".join(narrations)
        synthesis_prompt = _DISCOVERY_SYNTHESIS_PROMPT.format(summaries=summaries_text)
        try:
            synthesis = _call_ollama([{"role": "user", "content": synthesis_prompt}])
        except Exception as exc:
            synthesis = f"(synthesis unavailable: {exc})"

        if k_conn and synthesis:
            store_artifact(k_conn, "discovery_synthesis", "discovery", synthesis)

        _emit_log("Discovery: done")
        socketio.emit("discovery_done", {"synthesis": synthesis}, to=sid)

    threading.Thread(target=_run, daemon=True).start()


def _start_llm_server() -> None:
    """Launch llama-server subprocess and warm up the model. Runs in background thread."""
    from determined.agent.llm_client import start_server, LLM_DISPLAY_NAME
    _emit_log(f"LLM: starting {LLM_DISPLAY_NAME}…")
    socketio.emit("llm_status", {"state": "starting"})
    ready = start_server(wait_seconds=120)
    if ready:
        _emit_log(f"LLM: {LLM_DISPLAY_NAME} ready")
        socketio.emit("llm_status", {"state": "running"})
    else:
        _emit_log(f"LLM: WARNING — could not start {LLM_DISPLAY_NAME}")
        socketio.emit("llm_status", {"state": "stopped"})


@socketio.on("llm_get_status")
def handle_llm_get_status(_data=None):
    from determined.agent.llm_client import is_available
    state = "running" if is_available() else "stopped"
    emit("llm_status", {"state": state})


@socketio.on("llm_restart")
def handle_llm_restart(_data=None):
    from determined.agent.llm_client import stop_server
    _emit_log("LLM: stopping for restart…")
    socketio.emit("llm_status", {"state": "starting"})
    stop_server()
    threading.Thread(target=_start_llm_server, daemon=True).start()


def run_server(db_path: str | None = None, host: str = "127.0.0.1", port: int = 5050) -> None:
    import atexit
    from determined.agent.llm_client import stop_server

    # Load explicit db_path if provided; otherwise start with no corpus
    if db_path:
        init(db_path)

    atexit.register(stop_server)

    print(f"\nDev console: http://{host}:{port}")
    if _db_path:
        s = _corpus_status()
        print(f"Corpus:       {_db_path}  ({s.get('files',0)} files, {s.get('hot',0)} hot, {s.get('artifacts',0)} artifacts)")
    else:
        print(f"Corpus:       none — use Ingest panel to load one")
    threading.Thread(target=_start_llm_server, daemon=True).start()
    print(f"Press Ctrl+C to stop.\n")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    run_server()
