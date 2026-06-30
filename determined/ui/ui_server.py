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

# shared state (single-user local tool)
_oracle: DBOracle | None = None
_assessor: Assessor | None = None
_db_path: str = ""
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
    db_name = Path(_db_path).name if _db_path else "no corpus"
    status  = _corpus_status()
    return render_template("console.html", db_name=db_name, status=status)


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


def _emit_corpus_ready():
    if _oracle:
        s = _corpus_status()
        m = _corpus_map_data()
        emit("corpus_ready", {
            "db_name": Path(_db_path).name,
            "db_path": _db_path,
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
        with _lock:
            answer, _history = _answer(
                question, _history, _oracle, _assessor, verbose=True
            )
        emit("answer", {
            "question": question,
            "answer":   answer,
        })
    except Exception as exc:
        emit("error", {"message": f"Pipeline error: {exc}"})


# Tab -> direct tool dispatch. These are deterministic structural lookups;
# no LLM needed, so they're instant and never hit Ollama timeouts.
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
        extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".c", ".cpp", ".h"}
        ignored = load_ignore_list(target)
        files = [
            f for f in target.rglob("*")
            if f.is_file() and f.suffix in extensions
            and not should_ignore_path(f.relative_to(target), ignored)
        ]
        total_bytes = sum(f.stat().st_size for f in files)
        emit("scan_result", {
            "path": str(target),
            "file_count": len(files),
            "size_mb": round(total_bytes / (1024 * 1024), 1),
        })
    except Exception as exc:
        emit("scan_result", {"error": str(exc)})


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
            if Path(db_path).exists():
                # close active connection before deleting to avoid WinError 32
                with _lock:
                    global _oracle, _assessor
                    if _oracle and str(Path(_db_path).resolve()) == str(Path(db_path).resolve()):
                        try: _oracle.conn.close()
                        except Exception: pass
                        _oracle = None
                        _assessor = None
                Path(db_path).unlink()
            socketio.emit("ingest_status", {"message": f"Analyzing {target.name}…"}, to=sid)

            corpus = type("Corpus", (), {"root_path": str(target)})()
            conn = sqlite3.connect(db_path)
            runner = EngineRunner()
            run_stats = runner.run(corpus=corpus, project_prefixes=[], repo_root=str(target), connection=conn) or {}
            conn.close()

            init(db_path)
            try:
                from determined.agent.discovery_agent import run as discover_run
                from determined.agent.knowledge_status import coverage_report
                batch = 0
                while True:
                    batch += 1
                    rpt = coverage_report(_oracle, _assessor)
                    remaining = rpt.get("unknown_total", 0)
                    if remaining == 0:
                        socketio.emit("ingest_status", {"message": "Discovery complete — all files surveyed."}, to=sid)
                        break
                    socketio.emit("ingest_status", {
                        "message": f"Discovering… batch {batch} ({remaining} files remaining)"
                    }, to=sid)
                    found = discover_run(db_path, limit=20, verbose=False)
                    if found == 0:
                        socketio.emit("ingest_status", {"message": f"Discovery stalled — {remaining} files unreachable."}, to=sid)
                        break
            except Exception as disc_exc:
                socketio.emit("ingest_status", {"message": f"Discovery skipped: {disc_exc}"}, to=sid)
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
            sections = {}
            for tool, args, key in [
                ("symbol_intent",  {"symbol": symbol}, "intent"),
                ("risk_profile",   {"symbol": symbol}, "risk"),
                ("list_callers",   {"symbol": symbol}, "callers"),
                ("list_callees",   {"symbol": symbol}, "callees"),
                ("get_findings",   {"symbol": symbol}, "findings"),
            ]:
                result = dispatch(tool, args, _oracle, _assessor)
                sections[key] = result
                socketio.emit("spotlight_section", {"symbol": symbol, "key": key, "content": result}, to=sid)
            socketio.emit("spotlight_done", {"symbol": symbol}, to=sid)
        except Exception as exc:
            socketio.emit("spotlight_error", {"message": str(exc)}, to=sid)

    threading.Thread(target=_run, daemon=True).start()


@socketio.on("project_stub")
def handle_project_stub(data):
    """
    Run stub projector for a symbol. Background thread (Ollama call may take ~30s).
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


def _check_llm() -> str:
    """Return 'ok' or an error message."""
    from determined.agent.llm_client import is_available
    return "ok" if is_available() else "llama-server unreachable at localhost:8080"


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
        _emit_corpus_ready()
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
            emit("file_content", {"error": f"not found: {path}"}); return
        content = fp.read_text(encoding="utf-8", errors="replace")
        # symbols from DB, keyed by filename suffix match
        name_pat = f"%{fp.name}"
        fns = _oracle.conn.execute(
            "SELECT name, line_number FROM functions "
            "WHERE replace(file_path,'\\\\','/') LIKE ? OR file_path LIKE ? ORDER BY line_number",
            (name_pat, name_pat)
        ).fetchall()
        cls = _oracle.conn.execute(
            "SELECT name, line_number FROM classes "
            "WHERE replace(file_path,'\\\\','/') LIKE ? OR file_path LIKE ? ORDER BY line_number",
            (name_pat, name_pat)
        ).fetchall()
        symbols = sorted(
            [{"name": n, "line": ln, "kind": "fn"} for n, ln in fns] +
            [{"name": n, "line": ln, "kind": "cls"} for n, ln in cls],
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
        emit("save_result", {"path": str(fp).replace("\\", "/")})
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


def _warmup_llm() -> None:
    """Send a trivial prompt to load the model into memory."""
    from determined.agent.llm_client import generate as _llm_generate
    try:
        print("llama-server: warming up model...")
        _llm_generate("hi", timeout=120)
        print("llama-server: model ready")
    except Exception as exc:
        print(f"llama-server: warmup failed: {exc}")


def run_server(db_path: str | None = None, host: str = "127.0.0.1", port: int = 5050) -> None:
    # Use explicit db_path, or fall back to last session, or start with no corpus
    if db_path:
        init(db_path)
    else:
        saved = _load_session()
        if saved:
            print(f"Resuming last session: {saved}")
            init(saved)

    llm_status = _check_llm()
    print(f"\nDev console: http://{host}:{port}")
    if _db_path:
        s = _corpus_status()
        print(f"Corpus:       {_db_path}  ({s.get('files',0)} files, {s.get('hot',0)} hot, {s.get('artifacts',0)} artifacts)")
    else:
        print(f"Corpus:       none — use Ingest panel to load one")
    if llm_status == "ok":
        threading.Thread(target=_warmup_llm, daemon=True).start()
    else:
        print(f"llama-server: WARNING — {llm_status}")
    print(f"Press Ctrl+C to stop.\n")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
