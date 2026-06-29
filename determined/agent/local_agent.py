# tools/analysis/agent/local_agent.py
#
# Local conversational agent backed by Ollama (llama3.2:3b).
# Three-phase pipeline (DESIGN.md section 8):
#   Phase 1 DECOMPOSE - AI lists what it needs (NEED: lines)
#   Phase 2 RESOLVE   - deterministic pattern router runs tool calls
#   Phase 3 ASSEMBLE  - AI reads facts and writes plain English answer
#
# Usage:
#   python -m determined.agent.local_agent.py corpus.db
#   python -m determined.agent.local_agent.py corpus.db --verbose
#
# Type 'quit', 'exit', or 'q' to end the session.
# Type 'clear' to reset conversation history.

from __future__ import annotations

import argparse
import sys

import requests

from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.agent.agent_resolver import (
    parse_needs, resolve_and_expand, facts_to_text, ground_question,
    detect_heuristic,
)
from determined.agent.knowledge_status import coverage_summary, suggest_followups
from determined.agent.pattern_executor import PatternExecutor, detect_pattern

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_TIMEOUT = 60


# ------------------------------------------------------------------
# Phase 1 prompt - DECOMPOSE
# ------------------------------------------------------------------

_DECOMPOSE_SYSTEM = """\
You are a code analysis assistant. Your job is to list what information
you need to answer a question about a game codebase. Do NOT answer the
question yet. Just list your needs.

Output exactly one NEED: line per piece of information needed.
Use only these patterns (copy exactly):
  NEED: files in <directory>
  NEED: files matching <substring>
  NEED: symbols named <name>
  NEED: symbols in <file.py>
  NEED: what calls <symbol>
  NEED: callees of <symbol>
  NEED: what does <file.py> do
  NEED: intent of <symbol>
  NEED: findings for <symbol>
  NEED: brief for <symbol>

Extract all symbol and file names explicitly from the question.
Output only NEED: lines, nothing else."""


def _decompose_prompt(
    question: str,
    history: list[dict],
    grounding: str = "",
) -> list[dict]:
    messages = [{"role": "system", "content": _DECOMPOSE_SYSTEM}]
    for turn in history[-6:]:  # last 3 Q/A pairs
        messages.append({"role": turn["role"], "content": turn["content"]})
    user_content = question
    if grounding:
        user_content = f"{question}\n\n{grounding}"
    messages.append({"role": "user", "content": user_content})
    return messages


# ------------------------------------------------------------------
# Phase 3 prompt - ASSEMBLE
# ------------------------------------------------------------------

_ASSEMBLE_SYSTEM = """\
You are a code analysis assistant. Answer the question using ONLY the facts below.
Rules:
- Base every claim on what the facts explicitly say. Do not add knowledge from training.
- If the facts list callers (lines starting "Direct callers of"), name them in your answer.
- If the facts say "No direct callers found", say so - do not invent callers.
- If the facts contain a [file_purpose] or [design_note] finding, treat it as authoritative.
- Be concise. One short paragraph is enough unless the question asks for more detail."""


def _required_elements(facts: list[dict]) -> str:
    """
    Extract files and callers found in facts and return a 'you must mention' hint
    for the ASSEMBLE prompt. Empty string if nothing notable found.
    """
    files = []
    callers = []
    for f in facts:
        tool = f.get("tool", "")
        result = f.get("result", "") or ""
        if tool == "search_files" and result and not result.startswith("No "):
            for line in result.splitlines()[1:]:
                line = line.strip()
                if line:
                    files.append(line.split("(")[0].strip().split("/")[-1])
        elif tool == "list_callers" and result and "No direct callers" not in result:
            lines = result.splitlines()
            callee = lines[0].replace("Direct callers of", "").strip().strip("':").strip("'")
            for line in lines[1:]:
                line = line.strip()
                if line:
                    callers.append(f"{callee} <- {line}")
    parts = []
    if files:
        parts.append("Files found: " + ", ".join(files))
    if callers:
        parts.append("Callers found: " + "; ".join(callers[:5]))
    return "\n".join(parts)


def _assembly_hint(needs: list[str]) -> str:
    """
    Per-heuristic focus instruction injected into the ASSEMBLE prompt. Steers Ollama
    on genuine synthesis cases (deterministic cases bypass assembly entirely).
    In-code for now; could migrate to knowledge.db for data-level tuning once stable.
    """
    has = lambda p: any(n.startswith(p) for n in needs)
    # pattern_similar: callees + what-calls + findings + symbols-named, no intent, no brief
    if (has("callees of") and has("what calls") and has("findings for")
            and has("symbols named") and not has("intent of") and not has("brief for")):
        return ("Name the similar symbols found and what makes them structurally similar "
                "(same name suffix / role). Show their callers. Do not claim similarity "
                "the facts do not support.")
    # (workflow prioritization is now handled deterministically by the prioritize_work
    #  tool + bypass, so no assembly hint is needed for it.)
    return ""


def _assemble_prompt(question: str, facts_text: str, history: list[dict],
                     facts: list[dict] | None = None,
                     needs: list[str] | None = None) -> list[dict]:
    messages = [{"role": "system", "content": _ASSEMBLE_SYSTEM}]
    for turn in history[-6:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    required = _required_elements(facts) if facts else ""
    required_block = f"\nMust include in answer:\n{required}\n" if required else ""
    hint = _assembly_hint(needs) if needs else ""
    hint_block = f"\nFocus for this question type:\n{hint}\n" if hint else ""
    content = (
        f"Question: {question}\n"
        f"{required_block}{hint_block}\n"
        f"=== FACTS (use only these) ===\n{facts_text}\n=== END FACTS ==="
    )
    messages.append({"role": "user", "content": content})
    return messages


# ------------------------------------------------------------------
# Survey bypass: build structured answer directly from facts
# (bypasses Ollama for survey heuristic - tiny model ignores facts)
# ------------------------------------------------------------------

def _is_survey_needs(needs: list[str]) -> bool:
    # dev_plan heuristic has the same symbols/files/findings pattern but also has
    # "entry points" - exclude those so they go through Ollama for synthesis
    if any(n == "entry points" for n in needs):
        return False
    return (any(n.startswith("symbols named ") for n in needs) and
            any(n.startswith("files matching ") for n in needs) and
            any(n.startswith("findings for ") for n in needs))


def build_survey_answer(facts: list[dict]) -> str:
    """
    Deterministic survey answer built directly from facts.
    Used when survey heuristic fires to avoid Ollama ignoring the fact set.
    """
    files: list[str] = []
    symbols: list[str] = []
    callers: list[str] = []
    findings: list[str] = []

    for f in facts:
        tool = f.get("tool", "")
        result = f.get("result", "") or ""
        if not result:
            continue

        if tool == "search_files":
            if not result.startswith("No "):
                for line in result.splitlines()[1:]:
                    line = line.strip()
                    if line:
                        files.append(line)

        elif tool == "search_symbols":
            if not result.startswith("No "):
                seen = set()
                for line in result.splitlines()[1:]:
                    line = line.strip()
                    if line and line not in seen:
                        seen.add(line)
                        symbols.append(line)

        elif tool == "list_callers":
            if "No direct callers" not in result:
                lines = result.splitlines()
                callee = lines[0].replace("Direct callers of", "").strip().strip("':").strip("'")
                for line in lines[1:]:
                    line = line.strip()
                    if line:
                        callers.append(f"  {callee} <- {line}")

        elif tool == "get_findings":
            if "No stored" not in result:
                findings.append(result)

    sections: list[str] = []

    sections.append("Files:\n" + ("\n".join(f"  {f}" for f in files) if files else "  (none found)"))

    if symbols:
        sections.append("Symbols:\n" + "\n".join(f"  {s}" for s in symbols))
    else:
        sections.append("Symbols: (none found)")

    if callers:
        sections.append("Call relationships:\n" + "\n".join(callers))

    if findings:
        sections.append("Stored findings:\n" + "\n".join(f"  {f}" for f in findings))
    else:
        sections.append("Stored findings: (none - run discovery pass to populate)")

    return "\n\n".join(sections)


# ------------------------------------------------------------------
# git_history bypass: the git log output IS the answer.
# Ollama ignores the log fact and talks about callers instead, so
# we return the log directly (same rationale as survey/workflow).
# ------------------------------------------------------------------

def _is_git_history_needs(needs: list[str]) -> bool:
    return any(n.startswith("git history of ") for n in needs)


def build_git_history_answer(facts: list[dict]) -> str:
    """Deterministic git-history answer: return the git_log_for result directly."""
    git_fact = next(
        (f["result"] for f in facts if f["tool"] == "git_log_for" and f["result"]),
        None,
    )
    return git_fact if git_fact else "(no git history found)"


# ------------------------------------------------------------------
# impact bypass: symbol_brief (task_generator output) already IS the
# impact analysis - direct callers + impact zone. Ollama degrades it
# (can't synthesize "no direct callers" into "this is an entry point").
# Return the brief directly, append knowledge.db findings for context.
# ------------------------------------------------------------------

def _is_impact_needs(needs: list[str]) -> bool:
    # impact NEEDs: "brief for X" + "what calls X" + "findings for X", no "symbols named"
    # (distinguishes from explain, which has "brief for" but also "symbols named")
    return (any(n.startswith("brief for ") for n in needs) and
            any(n.startswith("what calls ") for n in needs) and
            not any(n.startswith("symbols named ") for n in needs))


def build_impact_answer(facts: list[dict]) -> str:
    """Deterministic impact answer: the symbol_brief (task_generator output) is the
    impact analysis - it already includes direct callers, impact zone, and findings.
    Fall back to raw callers + findings only if the brief is missing."""
    brief = next(
        (f["result"] for f in facts if f["tool"] == "symbol_brief" and f["result"]),
        None,
    )
    if brief:
        return brief
    callers = next((f["result"] for f in facts if f["tool"] == "list_callers"), "")
    findings = [
        f["result"] for f in facts
        if f["tool"] == "get_findings" and f["result"] and "No stored" not in f["result"]
    ]
    parts = [p for p in ([callers] + findings) if p]
    return "\n\n".join(parts) if parts else "(no impact data found)"


def _postprocess_answer(answer: str, facts: list[dict]) -> str:
    """
    Guard against fact-omission: if answer claims no callers but facts list callers,
    append the correct caller list from facts. Pure string post-processing, no AI call.
    """
    import re
    answer_lower = answer.lower()
    no_caller_phrases = ("no direct caller", "no callers", "not called", "no caller found")
    if not any(p in answer_lower for p in no_caller_phrases):
        return answer

    # Extract caller lines from facts
    caller_lines = []
    for f in facts:
        if f.get("tool") != "list_callers" or not f.get("result"):
            continue
        result = f["result"]
        if "No direct callers" in result:
            continue
        for line in result.splitlines():
            line = line.strip()
            if line and not line.startswith("Direct callers"):
                caller_lines.append(line)

    if not caller_lines:
        return answer

    injected = "\n\nNote: Facts show these direct callers: " + "; ".join(caller_lines[:5])
    return answer + injected


# ------------------------------------------------------------------
# Ollama call
# ------------------------------------------------------------------

def _call_ollama(messages: list[dict], verbose: bool = False, label: str = "") -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        resp.raise_for_status()
        text = resp.json()["message"]["content"].strip()
        if verbose and label:
            print(f"\n[{label}]\n{text}\n[/{label}]", flush=True)
        return text
    except requests.exceptions.ConnectionError:
        return "ERROR: Ollama is not running. Start it with: ollama serve"
    except requests.exceptions.Timeout:
        return "ERROR: Ollama timed out. The model may be loading - try again."
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


# ------------------------------------------------------------------
# Single question/answer cycle (three-phase)
# ------------------------------------------------------------------

def _answer(
    user_input: str,
    history: list[dict],
    oracle: DBOracle,
    assessor: Assessor,
    verbose: bool = False,
) -> tuple[str, list[dict]]:
    """
    Run three-phase pipeline for one user question.
    Returns (final_answer, updated_history).
    History is a list of {role, content} dicts (user/assistant pairs),
    extended in place with the (question, answer) pair.
    """
    # Phase 0a: PATTERN EXECUTOR - check for named task patterns before anything else
    pattern_name, subject = detect_pattern(user_input)
    if pattern_name:
        if verbose:
            print(f"\n[pattern detected] {pattern_name} / subject={subject}", flush=True)
        executor = PatternExecutor(OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT)
        answer = executor.run(pattern_name, subject, user_input, oracle, assessor, verbose=verbose)
        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant", "content": answer})
        return answer, history

    # Phase 0b: GROUND
    grounding = ground_question(user_input, oracle, assessor)
    if verbose and grounding:
        print(f"\n[phase0-ground]\n{grounding}\n[/phase0-ground]", flush=True)

    # Phase 1: DECOMPOSE - try named heuristic first, fall back to Ollama
    needs = detect_heuristic(user_input)
    if needs:
        if verbose:
            print(f"\n[heuristic matched] {needs}", flush=True)
    else:
        decompose_msgs = _decompose_prompt(user_input, history, grounding=grounding)
        needs_text = _call_ollama(decompose_msgs, verbose=verbose, label="phase1-decompose")
        if needs_text.startswith("ERROR:"):
            return needs_text, history
        needs = parse_needs(needs_text)

    if verbose:
        print(f"\n[needs parsed] {needs}", flush=True)

    # Phase 2: RESOLVE
    facts = []
    if needs:
        facts = resolve_and_expand(needs, oracle, assessor)
        if verbose:
            for f in facts:
                print(f"  [tool={f['tool']} args={f['args']}] {f['result'][:120]}", flush=True)
        facts_text = facts_to_text(facts)
    else:
        facts_text = "(no structured needs identified - answering from general knowledge)"

    # Phase 3: ASSEMBLE
    # Several heuristics get a deterministic answer (tiny model ignores or degrades facts).
    if _is_survey_needs(needs):
        answer = build_survey_answer(facts)
    elif _is_git_history_needs(needs):
        answer = build_git_history_answer(facts)
    elif _is_impact_needs(needs):
        answer = build_impact_answer(facts)
    elif needs == ["workflow status"]:
        wf_fact = next((f["result"] for f in facts if f["tool"] == "workflow_status"), None)
        answer = wf_fact if wf_fact else "(no workflow items found)"
    elif needs == ["prioritize work"]:
        pw_fact = next((f["result"] for f in facts if f["tool"] == "prioritize_work"), None)
        answer = pw_fact if pw_fact else "(no work items found)"
    else:
        assemble_msgs = _assemble_prompt(user_input, facts_text, history, facts=facts, needs=needs)
        answer = _call_ollama(assemble_msgs, verbose=verbose, label="phase3-assemble")
        answer = _postprocess_answer(answer, facts)

    # Phase 4: SUGGEST
    suggestions = suggest_followups(facts, oracle, assessor)
    if suggestions:
        answer = answer + "\n\n" + suggestions

    history.append({"role": "user",      "content": user_input})
    history.append({"role": "assistant", "content": answer})
    return answer, history


# ------------------------------------------------------------------
# Main REPL
# ------------------------------------------------------------------

def run(db_path: str, verbose: bool = False) -> None:
    print(f"\nLoading corpus: {db_path}")
    try:
        oracle = DBOracle(db_path)
        assessor = Assessor(oracle)
    except Exception as e:
        print(f"ERROR loading corpus: {e}")
        sys.exit(1)

    root = oracle.get_project_root() or db_path
    print(f"Project root:   {root}")
    print(f"Model:          {OLLAMA_MODEL}")
    print(f"\n{coverage_summary(oracle, assessor)}")
    print(f"\nType your question. 'clear' to reset. 'quit' to exit.")
    print(f"Special: 'what do you know?' | 'what haven't you explored?' | 'discover'")
    print(f"Workflow: 'what's next' | 'reprioritize' | 'add to backlog: <item>' | 'reorder as 3,1,2'\n")

    history: list[dict] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        if user_input.lower() == "clear":
            history = []
            print("[conversation history cleared]\n")
            continue

        if user_input.lower() in ("what do you know?", "what do you know"):
            print(f"\n{coverage_summary(oracle, assessor)}\n")
            continue

        if user_input.lower() in ("what haven't you explored?", "what havent you explored?",
                                   "what haven't you explored", "unexplored"):
            from determined.agent.knowledge_status import coverage_report
            r = coverage_report(oracle, assessor)
            unknown = r["unknown_files"]
            if unknown:
                print(f"\nUnexplored files ({len(unknown)} of {r['total_files']}):")
                for f in unknown:
                    print(f"  {f}")
            else:
                print("\nAll files have been surveyed.")
            print()
            continue

        if user_input.lower() == "discover":
            from determined.agent.discovery_agent import run as discover_run
            discover_run(db_path, limit=5, verbose=True)
            print(f"\n{coverage_summary(oracle, assessor)}\n")
            continue

        if user_input.lower() in ("reprioritize", "suggest priorities", "suggest order"):
            status = assessor.workflow_status()
            if status == "No active workflow items.":
                print(f"\n{status}\n")
                continue
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
            suggestion = _call_ollama(msgs, verbose=verbose, label="reprioritize")
            print(f"\nAgent: {suggestion}\n")
            continue

        print("\nThinking...", flush=True)
        answer, history = _answer(user_input, history, oracle, assessor, verbose=verbose)
        print(f"\nAgent: {answer}\n")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def _ingest_source(source_dir: str, summarize: bool = False) -> str:
    """Ingest a source directory into a corpus DB, return the DB path."""
    import re
    from pathlib import Path
    from determined.engine.run_engine import EngineRunner
    from determined.persistence.persistence_engine import create_database

    src = Path(source_dir).resolve()
    if not src.is_dir():
        print(f"ERROR: --source path is not a directory: {source_dir}")
        sys.exit(1)

    # derive DB name from full path to match convention: C_Users_bartl_dev_harrow.db
    # Drop colons (drive separator), replace other non-alphanumeric with underscore
    path_str = str(src).replace(":", "")
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", path_str).strip("_")
    db_path = f"{safe}.db"

    print(f"Ingesting {src} -> {db_path} ...")
    db = create_database(db_path)
    corpus = type("Corpus", (), {"root_path": str(src)})()
    EngineRunner().run(corpus=corpus, project_prefixes=[], repo_root=str(src), connection=db)
    db.close()
    print(f"Ingestion complete: {db_path}")

    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor
    oracle = DBOracle(db_path)
    assessor = Assessor(oracle)

    # Auto-extract structural design facts (no LLM, < 1s)
    if assessor._knowledge_conn is not None:
        counts = assessor.extract_design_facts()
        total = sum(counts.values())
        print(f"Knowledge extracted: {total} structural facts "
              f"({counts.get('entry_points',0)} entry points, "
              f"{counts.get('dead_code',0)} dead code candidates, "
              f"{counts.get('hot_symbols',0)} hot symbols, "
              f"{counts.get('stub_files',0)} stub files)")

    # Contract checks: persist violations + record drift history for health tracking
    from determined.contracts.persist_contract_violations import persist_contract_violations
    from determined.contracts.contract_drift_classifier import ContractDriftClassifier
    reports = assessor.file_contract_reports()
    violation_count = sum(len(r.violations) for r in reports)
    if violation_count:
        for report in reports:
            if report.violations:
                persist_contract_violations(oracle.conn, report)
        print(f"Contract violations: {violation_count} persisted")
    signals = ContractDriftClassifier().classify(reports)
    for s in signals:
        oracle.conn.execute(
            "INSERT INTO contract_drift_history (contract_name, classification, layer, count)"
            " VALUES (?, ?, ?, ?)",
            (s.contract_name, s.classification, s.layer, s.count),
        )
    oracle.conn.commit()

    # Optional: generate AI summaries for every file (requires Ollama)
    if summarize:
        _summarize_all_files(src, oracle, assessor)

    oracle.conn.close()
    return db_path


_DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}
_SKIP_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__",
    "dist", "build", ".mypy_cache", ".pytest_cache",
    "Lib", "Scripts", "Include", "lib", "bin", "include",
    "ai_context", "archive", "archives",
}


def _summarize_all_files(src, oracle, assessor) -> None:
    """
    Walk src to discover files and generate semantic summaries.
    Source pass: .py files processed via semantic_summary().
    Doc pass: text/doc files checked for relevance via doc_extractor,
    then ingested into knowledge_artifacts if they describe the code.
    Skips already-cached. Aborts gracefully if Ollama is unreachable.
    """
    from pathlib import Path
    from determined.agent.doc_extractor import discover_docs, extract_rules

    src = Path(src)

    # --- Pass 1: Python source files ---
    py_files = []
    for p in src.rglob("*.py"):
        if any(part in _SKIP_DIRS or part.startswith(".") for part in p.parts):
            continue
        py_files.append(p)
    py_files.sort()

    total_py = len(py_files)
    print(f"Generating AI summaries for {total_py} source files (requires Ollama) ...")
    done = skipped = failed = 0

    for p in py_files:
        rel = str(p.relative_to(src)).replace("\\", "/")
        existing = assessor.semantic_summary_if_fresh(rel)
        if existing:
            skipped += 1
            continue
        try:
            result = assessor.semantic_summary(rel)
            if result.get("content"):
                done += 1
                print(f"  [{done+skipped}/{total_py}] {rel}", flush=True)
            else:
                failed += 1
        except Exception as e:
            msg = str(e).lower()
            if "connection" in msg or "refused" in msg or "timeout" in msg:
                print(f"\nOllama unreachable ({e}). Stopping -- {done} summaries written.")
                return
            failed += 1

    print(f"Source summaries: {done} generated, {skipped} already cached, {failed} failed.")

    # --- Pass 2: Text/doc files -- discover and ingest design rules ---
    if assessor._knowledge_conn is None:
        return

    docs = discover_docs(str(src))
    # discover_docs already filters by extension, skip dirs, and constraint density
    if not docs:
        return

    print(f"Found {len(docs)} doc files; ingesting design rules ...")
    rules_written = 0
    corpus = oracle.get_project_root() or str(src)

    for doc in docs:
        rules = extract_rules(doc.path, rel_path=doc.rel_path, source_confidence=doc.confidence)
        for rule in rules:
            try:
                assessor._knowledge_conn.execute(
                    """INSERT OR IGNORE INTO knowledge_artifacts
                       (subject, kind, content, provenance, corpus, created_at)
                       VALUES (?, 'design_note', ?, ?, ?, datetime('now'))""",
                    (rule.subject, rule.rule,
                     f"{rule.provenance}", corpus),
                )
                rules_written += 1
            except Exception:
                pass
        assessor._knowledge_conn.commit()

    print(f"Design rules ingested: {rules_written} rules from {len(docs)} docs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Local codebase analysis agent backed by Ollama."
    )
    parser.add_argument("db_path", nargs="?",
                        help="Path to corpus DB (e.g. corpus.db). "
                             "Omit when using --source.")
    parser.add_argument("--source", metavar="DIR",
                        help="Source directory to ingest; DB is derived automatically.")
    parser.add_argument("--summarize", action="store_true",
                        help="After ingestion, generate AI file summaries via Ollama (slow; skips cached).")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show phase outputs and tool calls")
    parser.add_argument("--ui", action="store_true",
                        help="Start the browser-based dev console instead of the REPL")
    parser.add_argument("--port", type=int, default=5050,
                        help="Port for the UI server (default: 5050)")
    args = parser.parse_args()

    if getattr(args, "summarize", False) and not args.source:
        parser.error("--summarize requires --source")

    if args.source:
        db_path = _ingest_source(args.source, summarize=getattr(args, "summarize", False))
    elif args.db_path:
        db_path = args.db_path
    else:
        db_path = None

    if args.ui:
        from determined.ui.ui_server import run_server
        run_server(db_path, port=args.port)
    else:
        if not db_path:
            parser.error("Provide db_path or --source <dir> when not using --ui.")
        run(db_path, verbose=args.verbose)
