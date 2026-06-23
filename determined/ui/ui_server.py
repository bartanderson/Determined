# determined/ui/ui_server.py
#
# Flask + SocketIO server for the developer console UI.
# Start via: python -m determined.agent.local_agent --ui

from __future__ import annotations

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

app = Flask(__name__, template_folder=_TEMPLATE_DIR, static_folder=_STATIC_DIR)
app.config["SECRET_KEY"] = "dev-console-local"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# shared state (single-user local tool)
_oracle: DBOracle | None = None
_assessor: Assessor | None = None
_db_path: str = ""
_history: list[dict] = []
_lock = threading.Lock()


def init(db_path: str) -> None:
    global _oracle, _assessor, _db_path
    _oracle   = DBOracle(db_path)
    _assessor = Assessor(_oracle)
    _db_path  = db_path


@app.route("/")
def index():
    db_name = Path(_db_path).name if _db_path else "no corpus"
    summary = coverage_summary(_oracle, _assessor) if _oracle else ""
    return render_template("console.html", db_name=db_name, summary=summary)


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

    if q_lower in ("discover", "discover more"):
        sid = request.sid
        def _run_discover():
            try:
                from determined.agent.discovery_agent import run as discover_run
                from determined.agent.knowledge_status import coverage_summary
                socketio.emit("status", {"message": "Running discovery…"}, to=sid)
                discover_run(_db_path, limit=20, verbose=False)
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
            socketio.emit("ingest_status", {"message": "Building discovery index…"}, to=sid)
            try:
                from determined.agent.discovery_agent import run as discover_run
                discover_run(db_path, limit=10, verbose=False)
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
    if db_path:
        init(db_path)
    ollama_status = _check_ollama()
    print(f"\nDev console: http://{host}:{port}")
    print(f"Corpus:       {db_path or 'none — use Ingest to load one'}")
    if ollama_status == "ok":
        threading.Thread(target=_warmup_ollama, daemon=True).start()
    else:
        print(f"Ollama:       WARNING — {ollama_status}")
    print(f"Press Ctrl+C to stop.\n")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
