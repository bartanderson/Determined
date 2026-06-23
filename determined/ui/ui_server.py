# tools/analysis/ui/ui_server.py
#
# Flask + SocketIO server for the developer console UI.
# Wraps the same _answer() pipeline as local_agent.py.
# Start via: python -m tools.analysis.agent.local_agent <corpus.db> --ui

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

    def _run():
        try:
            from determined.engine.run_engine import EngineRunner
            from determined.engine.db_resolver import resolve_analysis_db_path

            db_path = resolve_analysis_db_path(str(target))
            emit("ingest_status", {"message": f"Ingesting {target.name}…"})

            corpus = type("Corpus", (), {"root_path": str(target)})()
            conn = sqlite3.connect(db_path)
            runner = EngineRunner()
            runner.run(corpus=corpus, project_prefixes=[], repo_root=str(target), connection=conn)
            conn.close()

            # switch active corpus
            init(db_path)
            emit("ingest_done", {"db_name": Path(db_path).name, "db_path": db_path})
        except Exception as exc:
            emit("ingest_error", {"message": f"Ingestion failed: {exc}"})

    threading.Thread(target=_run, daemon=True).start()


def run_server(db_path: str | None = None, host: str = "127.0.0.1", port: int = 5050) -> None:
    if db_path:
        init(db_path)
    print(f"\nDev console: http://{host}:{port}")
    print(f"Corpus:       {db_path or 'none — use Ingest to load one'}")
    print(f"Press Ctrl+C to stop.\n")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
