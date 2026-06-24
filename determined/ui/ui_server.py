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


@socketio.on("connect")
def handle_connect():
    """On browser connect, send current corpus status so the UI updates immediately."""
    if _oracle:
        s = _corpus_status()
        emit("corpus_ready", {
            "db_name": Path(_db_path).name,
            "db_path": _db_path,
            "files": s.get("files", 0),
            "hot": s.get("hot", 0),
            "stubs": s.get("stubs", 0),
            "artifacts": s.get("artifacts", 0),
        })


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
        import requests as _req
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
            resp = _req.post(
                "http://localhost:11434/api/chat",
                json={"model": "llama3.2:3b", "messages": msgs, "stream": False,
                      "options": {"temperature": 0.1}},
                timeout=60,
            )
            resp.raise_for_status()
            answer = resp.json()["message"]["content"].strip()
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
                question, _history, _oracle, _assessor, verbose=False
            )
        emit("answer", {
            "question": question,
            "answer":   answer,
        })
    except Exception as exc:
        emit("error", {"message": f"Pipeline error: {exc}"})


@socketio.on("tab_query")
def handle_tab_query(data):
    """Run a named tab query - same pipeline as query but result goes to tab_answer."""
    tab      = (data.get("tab") or "").strip()
    question = (data.get("question") or "").strip()
    if not question or not tab or _oracle is None:
        emit("tab_answer", {"tab": tab, "answer": "No corpus loaded.", "question": question})
        return

    sid = request.sid

    def _run():
        try:
            q_lower = question.lower().rstrip("?")

            if q_lower in ("what haven't you explored", "what havent you explored", "unexplored"):
                from determined.agent.knowledge_status import coverage_report
                r = coverage_report(_oracle, _assessor)
                unknown = r["unknown_files"]
                answer = ("\n".join([f"Unexplored files ({len(unknown)} of {r['total_files']}):"]
                          + [f"  {f}" for f in unknown]) if unknown else "All files have been surveyed.")

            elif q_lower in ("discover", "discover more"):
                from determined.agent.knowledge_status import coverage_summary
                answer = coverage_summary(_oracle, _assessor)

            else:
                from determined.agent.local_agent import _answer
                answer, _ = _answer(question, [], _oracle, _assessor, verbose=False)

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
            "SELECT name, file_path, line_number, docstring FROM functions WHERE name = ? LIMIT 1",
            (symbol,)
        ).fetchone()
        sym_type = "function"
        if not row:
            row = _oracle.conn.execute(
                "SELECT name, file_path, line_number, docstring FROM classes WHERE name = ? LIMIT 1",
                (symbol,)
            ).fetchone()
            sym_type = "class"
        if not row:
            emit("symbol_quick_result", {"error": f"'{symbol}' not in corpus"})
            return
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


def _check_ollama() -> str:
    """Return 'ok' or an error message."""
    try:
        import requests as _req
        from determined.intent.semantic_summary import OLLAMA_URL, OLLAMA_MODEL
        base = OLLAMA_URL.rsplit("/api/", 1)[0]
        r = _req.get(f"{base}/api/tags", timeout=3)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        if not any(m.startswith(OLLAMA_MODEL.split(":")[0]) for m in models):
            return f"Ollama running but model '{OLLAMA_MODEL}' not found. Run: ollama pull {OLLAMA_MODEL}"
        return "ok"
    except Exception as exc:
        return f"Ollama unreachable: {exc}"


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
        s = _corpus_status()
        emit("corpus_ready", {
            "db_name": Path(path).name,
            "db_path": path,
            "files": s.get("files", 0),
            "hot": s.get("hot", 0),
            "stubs": s.get("stubs", 0),
            "artifacts": s.get("artifacts", 0),
        })
    except Exception as exc:
        emit("error", {"message": f"Failed to load {path}: {exc}"})


def _warmup_ollama() -> None:
    """Send a trivial prompt to load the model into memory, then keepalive every 4 min."""
    import requests as _req
    from determined.intent.semantic_summary import OLLAMA_URL, OLLAMA_MODEL
    try:
        print("Ollama:       warming up model...")
        _req.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": "hi", "stream": False}, timeout=120)
        print("Ollama:       model ready")
    except Exception as exc:
        print(f"Ollama:       warmup failed: {exc}")

    # keepalive: ping every 4 minutes so the model stays loaded
    def _keepalive():
        while True:
            import time
            time.sleep(240)
            try:
                _req.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": ".", "stream": False}, timeout=30)
            except Exception:
                pass

    threading.Thread(target=_keepalive, daemon=True).start()


def run_server(db_path: str | None = None, host: str = "127.0.0.1", port: int = 5050) -> None:
    # Use explicit db_path, or fall back to last session, or start with no corpus
    if db_path:
        init(db_path)
    else:
        saved = _load_session()
        if saved:
            print(f"Resuming last session: {saved}")
            init(saved)

    ollama_status = _check_ollama()
    print(f"\nDev console: http://{host}:{port}")
    if _db_path:
        s = _corpus_status()
        print(f"Corpus:       {_db_path}  ({s.get('files',0)} files, {s.get('hot',0)} hot, {s.get('artifacts',0)} artifacts)")
    else:
        print(f"Corpus:       none — use Ingest panel to load one")
    if ollama_status == "ok":
        threading.Thread(target=_warmup_ollama, daemon=True).start()
    else:
        print(f"Ollama:       WARNING — {ollama_status}")
    print(f"Press Ctrl+C to stop.\n")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
