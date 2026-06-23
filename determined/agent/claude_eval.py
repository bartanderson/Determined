# tools/analysis/agent/claude_eval.py
#
# Claude's non-interactive access path to the agent pipeline.
# Simulates what Bart does in the REPL, driven by Claude's own judgment.
# Bart directs the work; Claude runs this, evaluates outputs, writes
# human-confirmed corrections to knowledge.db.
#
# Usage:
#   python -m determined.agent.claude_eval.py corpus.db ask "how does encounter work?"
#   python -m determined.agent.claude_eval.py corpus.db batch questions.txt
#   python -m determined.agent.claude_eval.py corpus.db auto --mode unknown --limit 5
#   python -m determined.agent.claude_eval.py corpus.db store adjudication_engine.py file_purpose "Central game action router..."
#   python -m determined.agent.claude_eval.py corpus.db store --workflow backlog "add crafting" "Implement crafting system"

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.agent.agent_resolver import (
    ground_question, detect_heuristic, parse_needs,
    resolve_and_expand, facts_to_text,
)
from determined.agent.local_agent import (
    _decompose_prompt, _assemble_prompt, _call_ollama,
    _postprocess_answer, _is_survey_needs, build_survey_answer,
    _is_git_history_needs, build_git_history_answer,
    _is_impact_needs, build_impact_answer,
    OLLAMA_MODEL,
)

# ------------------------------------------------------------------
# Core: run one question through the full pipeline, return structure
# ------------------------------------------------------------------

def run_question(
    question: str,
    oracle: DBOracle,
    assessor: Assessor,
) -> dict:
    """
    Run the full pipeline for one question.
    Returns a structured dict - no printing, no side effects.
    """
    # Phase 0: GROUND
    grounding = ground_question(question, oracle, assessor)

    # Phase 1: DECOMPOSE (heuristic or Ollama)
    heuristic_name = None
    needs = detect_heuristic(question)
    if needs:
        heuristic_name = _detect_heuristic_name(question)
        needs_source = "heuristic"
    else:
        decompose_msgs = _decompose_prompt(question, [], grounding=grounding)
        needs_text = _call_ollama(decompose_msgs, label="")
        if needs_text.startswith("ERROR:"):
            return {"question": question, "error": needs_text}
        needs = parse_needs(needs_text)
        needs_source = "ollama"

    # Phase 2: RESOLVE
    facts = []
    if needs:
        facts = resolve_and_expand(needs, oracle, assessor)

    unmatched = [f for f in facts if f["tool"] == "unmatched"]
    matched   = [f for f in facts if f["tool"] != "unmatched"]

    # Phase 3: ASSEMBLE
    facts_text = facts_to_text(facts) if facts else "(no facts)"
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
        assemble_msgs = _assemble_prompt(question, facts_text, [], facts=facts, needs=needs)
        answer = _call_ollama(assemble_msgs, label="")
        answer = _postprocess_answer(answer, facts)

    return {
        "question":        question,
        "grounding":       grounding,
        "needs_source":    needs_source,
        "heuristic":       heuristic_name,
        "needs":           needs,
        "facts":           matched,
        "unmatched_needs": [f["args"] for f in unmatched],
        "fact_count":      len(matched),
        "answer":          answer,
        "error":           None,
    }


def _detect_heuristic_name(question: str) -> str:
    """Best-effort label for which heuristic fired."""
    q = question.lower()
    if "entry point" in q:
        return "entry_points"
    if "connect" in q or "interface between" in q or "what connects" in q:
        return "connection"
    if "relate" in q and "to" in q:
        return "connection"
    if "how do i" in q or "how would i" in q or "how should i" in q:
        return "dev_plan"
    if "how does" in q or any(w in q for w in ("trace", "walk")):
        return "trace"
    if "how do" in q or "how is" in q:
        return "trace"
    if "what does" in q and ".py" in q:
        return "describe_file"
    if ("symbols" in q or "functions" in q or "classes" in q) and ".py" in q:
        return "symbols_in_file"
    if "what does" in q or "explain" in q or "purpose of" in q:
        return "explain_symbol"
    if "what calls" in q or "callers" in q or "who calls" in q:
        return "callers"
    if "where is" in q and ("triggered" in q or "called" in q or "used" in q):
        return "callers"
    if "what happens" in q:
        return "trace"
    if "what is responsible" in q or "find all files" in q or "find files" in q:
        return "survey"
    if "dev plan" in q or "development plan" in q:
        return "workflow"
    if "show me how" in q or "show me an example" in q or "example of how" in q:
        return "callers"
    if "files that use" in q or "files using" in q or "list all files" in q:
        return "callers"
    if ("what exists" in q or "find everything" in q or "survey" in q
            or "current state of" in q or "status of" in q
            or "architecture of" in q or "structure of" in q or "design of" in q
            or "tell me about" in q or q.startswith("show me")
            or q.startswith("what is")):
        return "survey"
    if any(w in q for w in ("add", "implement", "build", "where would")):
        return "dev_plan"
    if "what's next" in q or "priorities" in q or "workflow" in q:
        return "workflow"
    if "reprioritize" in q or "suggest order" in q:
        return "reprioritize"
    if "what changed" in q or ("when was" in q and "modified" in q) or "recent changes" in q:
        return "git_history"
    if "no docstring" in q or "missing docstring" in q or "undocumented" in q:
        return "quality_docstrings"
    if "todo" in q or "fixme" in q or "unfinished" in q:
        return "quality_todos"
    if ("find similar" in q or "similar to" in q or "same pattern as" in q
            or "how was" in q and "implemented" in q or "other things like" in q):
        return "pattern_similar"
    if ("if I change" in q or "what breaks" in q or "what depends on" in q
            or "impact of" in q or "blast radius" in q or "ripple" in q):
        return "impact"
    return "unknown"


# ------------------------------------------------------------------
# Output formatter
# ------------------------------------------------------------------

def format_result(r: dict, show_facts: bool = True) -> str:
    lines = []
    lines.append(f"QUESTION: {r['question']}")
    if r.get("error"):
        lines.append(f"ERROR: {r['error']}")
        return "\n".join(lines)

    h = r["heuristic"] or "-"
    lines.append(f"HEURISTIC: {h} ({r['needs_source']})")
    lines.append(f"NEEDS ({len(r['needs'])}): {' | '.join(r['needs'][:6])}")

    if r["unmatched_needs"]:
        lines.append(f"UNMATCHED: {r['unmatched_needs']}")

    if show_facts and r["facts"]:
        lines.append(f"FACTS ({r['fact_count']}):")
        for f in r["facts"][:8]:
            preview = (f["result"] or "")[:120].replace("\n", " ")
            lines.append(f"  [{f['tool']}] {preview}")
        if r["fact_count"] > 8:
            lines.append(f"  ... +{r['fact_count']-8} more facts")

    lines.append(f"ANSWER:")
    for ln in r["answer"].splitlines():
        lines.append(f"  {ln}")

    known_findings = sum(1 for f in r["facts"] if f["tool"] == "get_findings"
                         and "No stored" not in f["result"])
    lines.append(f"SIGNALS: facts={r['fact_count']} unmatched={len(r['unmatched_needs'])} "
                 f"known_findings={known_findings}")
    return "\n".join(lines)


# ------------------------------------------------------------------
# Auto question generator
# ------------------------------------------------------------------

def auto_questions(
    oracle: DBOracle,
    assessor: Assessor,
    mode: str,
    limit: int,
) -> list[str]:
    """
    Generate questions from corpus state.
    mode='unknown'  - 'what does X.py do?' for files not in knowledge.db
    mode='backlog'  - convert top backlog items into relevant questions
    mode='entries'  - 'trace X' for entry points not in knowledge.db
    """
    questions = []

    if mode == "unknown":
        from determined.agent.knowledge_status import coverage_report
        # Files with no symbols are package markers (__init__.py, etc.) - skip them
        files_with_symbols = {
            r["file_path"].replace("\\", "/").split("/")[-1]
            for r in oracle.find_files()
            if oracle.conn.execute(
                "SELECT 1 FROM symbols WHERE file_path = ? LIMIT 1",
                (r["file_path"],)
            ).fetchone()
        }
        r = coverage_report(oracle, assessor, unknown_limit=limit * 3)
        for fname in r["unknown_files"]:
            if fname not in files_with_symbols:
                continue
            questions.append(f"what does {fname} do")
            if len(questions) >= limit:
                break

    elif mode == "backlog":
        items = assessor.list_workflow_items(kind="backlog", status="active")
        for item in items[:limit]:
            subj = item["subject"]
            content = item["content"]
            # Convert backlog item to a probe question
            questions.append(f"what exists for {subj}")
            if len(questions) >= limit:
                break

    elif mode == "entries":
        from determined.agent.graph_utils import find_entry_points
        conn = getattr(assessor, "_knowledge_conn", None)
        eps = find_entry_points(oracle)
        for ep in eps:
            name = ep["name"]
            # Skip if already in knowledge.db
            if conn:
                row = conn.execute(
                    "SELECT 1 FROM knowledge_artifacts WHERE subject = ? LIMIT 1",
                    (name,),
                ).fetchone()
                if row:
                    continue
            questions.append(f"trace {name}")
            if len(questions) >= limit:
                break

    return questions[:limit]


# ------------------------------------------------------------------
# Subcommands
# ------------------------------------------------------------------

def cmd_ask(args, oracle, assessor):
    result = run_question(args.question, oracle, assessor)
    print(format_result(result))


def cmd_batch(args, oracle, assessor):
    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: file not found: {args.file}")
        return
    questions = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")]
    if not questions:
        print("No questions found in file.")
        return
    print(f"Running {len(questions)} questions against {args.db_path}\n")
    for i, q in enumerate(questions, 1):
        print(f"{'='*60}")
        print(f"[{i}/{len(questions)}]")
        result = run_question(q, oracle, assessor)
        print(format_result(result))
        print()


def cmd_auto(args, oracle, assessor):
    questions = auto_questions(oracle, assessor, args.mode, args.limit)
    if not questions:
        print(f"No questions generated for mode='{args.mode}'")
        return
    if args.list_only:
        print(f"Generated {len(questions)} questions (--list-only):")
        for q in questions:
            print(f"  {q}")
        return
    print(f"Auto mode='{args.mode}': running {len(questions)} questions\n")
    for i, q in enumerate(questions, 1):
        print(f"{'='*60}")
        print(f"[{i}/{len(questions)}]")
        result = run_question(q, oracle, assessor)
        print(format_result(result))
        print()


def cmd_pick(args, oracle, assessor):
    """
    PICK: run a question twice, surface only what the two answers disagree on.
    Survey questions (deterministic) are shown once with a note.
    Ollama questions are run twice and diffed at the sentence level.
    """
    question = args.question

    # First run
    r1 = run_question(question, oracle, assessor)
    if r1.get("error"):
        print(f"ERROR on run 1: {r1['error']}")
        return

    # Deterministic heuristics - no point running twice
    _det = (
        ("survey", _is_survey_needs(r1["needs"])),
        ("git_history", _is_git_history_needs(r1["needs"])),
        ("impact", _is_impact_needs(r1["needs"])),
        ("workflow", r1["needs"] == ["workflow status"]),
        ("prioritize", r1["needs"] == ["prioritize work"]),
    )
    det_name = next((name for name, hit in _det if hit), None)
    if det_name:
        print(f"QUESTION: {question}")
        print(f"PICK: {det_name} heuristic (deterministic - showing once)")
        print(format_result(r1, show_facts=False))
        return

    # Second run
    r2 = run_question(question, oracle, assessor)
    if r2.get("error"):
        print(f"ERROR on run 2: {r2['error']}")
        return

    a1 = r1["answer"].strip()
    a2 = r2["answer"].strip()

    # Find disagreements at sentence level
    import re
    def sentences(text):
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

    sents1 = set(sentences(a1))
    sents2 = set(sentences(a2))
    only_in_1 = sents1 - sents2
    only_in_2 = sents2 - sents1
    agreed = sents1 & sents2

    print(f"QUESTION: {question}")
    print(f"PICK: {len(agreed)} agreed | {len(only_in_1)} only-in-run1 | {len(only_in_2)} only-in-run2")
    print(f"NEEDS: {' | '.join(r1['needs'][:6])}")
    print()
    if agreed:
        print("AGREED (confident):")
        for s in sorted(agreed):
            print(f"  + {s}")
        print()
    if only_in_1 or only_in_2:
        print("DISAGREEMENT (needs human review):")
        for s in sorted(only_in_1):
            print(f"  run1: {s}")
        for s in sorted(only_in_2):
            print(f"  run2: {s}")
    else:
        print("PICK: answers identical - high confidence")


# ------------------------------------------------------------------
# Adversarial validation suite
# ------------------------------------------------------------------

# Each entry: (canonical_question, [variant, ...], expected_heuristic_substring)
# Variants should produce the same heuristic and overlapping answer content.
# expected_heuristic_substring: substring of _detect_heuristic_name output,
#   or None to skip routing check (content-only).
_ADVERSARIAL_SUITE = [
    # --- identity / explain_symbol ---
    (
        "what does WorldController do",
        [
            "what is WorldController",
            "explain WorldController",
            "purpose of WorldController",
            "what is the WorldController class",
            "what does world_controller do",
            "describe WorldController",
        ],
        "explain_symbol",
    ),
    # --- callers ---
    (
        "what calls adjudicate_action",
        [
            "who calls adjudicate_action",
            "what invokes adjudicate_action",
            "callers of adjudicate_action",
            "where is adjudicate_action called",
            "what uses adjudicate_action",
            "show me callers of adjudicate_action",
        ],
        "callers",
    ),
    # --- trace / behavioral ---
    (
        "how does the authority system work",
        [
            "how does authority work",
            "explain the authority system",
            "walk me through authority",
            "trace the authority system",
            "how is authority implemented",
        ],
        None,  # Ollama-assembled; check content overlap only
    ),
    # --- survey ---
    (
        "what exists for combat",
        [
            "which files are responsible for combat",
            "what is responsible for combat",
            "find all files related to combat",
            "survey combat",
            "tell me about combat",
        ],
        "survey",
    ),
    # --- git_history (deterministic bypass) ---
    (
        "what changed recently in adjudication_engine.py",
        [
            "recent changes in adjudication_engine.py",
            "what was modified in adjudication_engine.py",
            "git history for adjudication_engine.py",
            "when was adjudication_engine.py last changed",
        ],
        "git_history",
    ),
    # --- impact (deterministic bypass) ---
    (
        "if I change adjudicate_action what breaks",
        [
            "blast radius of adjudicate_action",
            "what depends on adjudicate_action",
            "impact of changing adjudicate_action",
            "what would break if I modify adjudicate_action",
            "ripple effect of adjudicate_action",
        ],
        "impact",
    ),
    # --- quality ---
    (
        "what functions are missing docstrings",
        [
            "what has no docstring",
            "find undocumented functions",
            "what is undocumented",
            "missing docstrings",
            "show me functions without docstrings",
        ],
        "quality_docstrings",
    ),
    # --- dev_plan ---
    (
        "how would I add a new item type",
        [
            "how do I add a new item type",
            "how should I add a new item type",
            "where would I add a new item type",
            "implement a new item type",
            "build a new item type",
        ],
        "dev_plan",
    ),
    # --- pattern_similar ---
    (
        "find similar to CharacterManager",
        [
            "what is similar to CharacterManager",
            "same pattern as CharacterManager",
            "other things like CharacterManager",
            "how was CharacterManager implemented",
        ],
        "pattern_similar",
    ),
    # --- prioritize (deterministic bypass) ---
    (
        "what should I work on",
        [
            "what should I do next",
            "what is the top priority",
            "what are my priorities",
            "what's next on the backlog",
        ],
        "prioritize",
    ),
]


def _answer_overlap(a1: str, a2: str) -> float:
    """Fraction of content words in a1 that also appear in a2 (order-independent)."""
    import re
    stop = {"the", "a", "an", "is", "in", "of", "to", "for", "and", "or", "it",
            "this", "that", "with", "on", "at", "by", "from", "as", "are", "be",
            "has", "have", "its", "not", "do", "does", "was", "were", "what",
            "how", "which", "where", "who"}
    def words(text):
        return {w.lower() for w in re.findall(r'\w+', text) if w.lower() not in stop and len(w) > 2}
    w1, w2 = words(a1), words(a2)
    if not w1:
        return 1.0
    return len(w1 & w2) / len(w1)


def cmd_adversarial(args, oracle, assessor):
    """
    ADVERSARIAL: run each canonical question + variants, report routing and content breaks.

    Routing break: variant triggers a different heuristic than canonical.
    Content break: variant answer shares < 30% content words with canonical answer.
    """
    suite = _ADVERSARIAL_SUITE
    if args.question:
        # Single custom question mode
        variants = args.variants or []
        suite = [(args.question, variants, None)]

    CONTENT_THRESHOLD = 0.30
    total_variants = sum(len(variants) for _, variants, _ in suite)
    routing_breaks = []
    content_breaks = []
    passes = 0

    print(f"ADVERSARIAL: {len(suite)} suites, {total_variants} total variants\n")

    for canonical, variants, expected_heuristic in suite:
        print(f"{'='*60}")
        print(f"CANONICAL: {canonical}")
        r_canon = run_question(canonical, oracle, assessor)
        if r_canon.get("error"):
            print(f"  ERROR (canonical): {r_canon['error']}")
            continue

        canon_heuristic = r_canon["heuristic"] or "unknown"
        canon_answer = r_canon["answer"]
        print(f"  heuristic={canon_heuristic}  needs={r_canon['needs'][:3]}")
        print(f"  answer_preview: {canon_answer[:120].replace(chr(10), ' ')}")
        print()

        for variant in variants:
            r_var = run_question(variant, oracle, assessor)
            if r_var.get("error"):
                print(f"  [ERROR] {variant!r}: {r_var['error']}")
                continue

            var_heuristic = r_var["heuristic"] or "unknown"
            overlap = _answer_overlap(canon_answer, r_var["answer"])
            # Compare actual needs (tools to be called) not heuristic name labels.
            # Heuristic names are human-readable tags; needs are the ground truth.
            needs_mismatch = set(r_var["needs"]) != set(r_canon["needs"])
            broke_content = overlap < CONTENT_THRESHOLD

            if needs_mismatch or broke_content:
                tag = []
                if needs_mismatch:
                    tag.append(f"NEEDS({canon_heuristic}->{var_heuristic})")
                if broke_content:
                    tag.append(f"CONTENT({overlap:.0%})")
                label = " ".join(tag)
                print(f"  [BREAK {label}] {variant!r}")
                if needs_mismatch:
                    routing_breaks.append((canonical, variant, r_canon["needs"], r_var["needs"]))
                if broke_content:
                    content_breaks.append((canonical, variant, overlap))
            else:
                print(f"  [OK  overlap={overlap:.0%}] {variant!r}")
                passes += 1

    print(f"\n{'='*60}")
    print(f"ADVERSARIAL SUMMARY")
    print(f"  Total variants: {total_variants}")
    print(f"  Passed:  {passes}")
    print(f"  Routing breaks: {len(routing_breaks)}")
    print(f"  Content breaks: {len(content_breaks)}")

    if routing_breaks:
        print(f"\nNEEDS BREAKS (different tools would be called):")
        for canon, variant, needs1, needs2 in routing_breaks:
            print(f"  canonical={canon!r}")
            print(f"  variant  ={variant!r}")
            only1 = set(needs1) - set(needs2)
            only2 = set(needs2) - set(needs1)
            if only1:
                print(f"    canonical only: {sorted(only1)}")
            if only2:
                print(f"    variant only:   {sorted(only2)}")
            print()

    if content_breaks:
        print(f"\nCONTENT BREAKS (answer diverged):")
        for canon, variant, overlap in content_breaks:
            print(f"  canonical={canon!r}  variant={variant!r}  overlap={overlap:.0%}")


def cmd_store(args, oracle, assessor):
    if args.workflow:
        # --workflow kind subject content
        kind, subject, content = args.workflow
        item_id = assessor.add_workflow_item(kind, subject, content,
                                             rank=args.rank, provenance="human")
        print(f"Stored workflow item #{item_id}: [{kind}] {subject}")
    else:
        # positional: subject kind content
        try:
            artifact_id = assessor.add_artifact(
                args.subject, args.kind, args.content,
                provenance="human-confirmed",
            )
            print(f"Stored finding #{artifact_id}: [{args.kind}] {args.subject}")
            print(f"  {args.content[:120]}")
        except ValueError as e:
            print(f"ERROR: {e}")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Claude's non-interactive access path to the agent pipeline."
    )
    parser.add_argument("db_path", help="Corpus DB (e.g. corpus.db)")

    sub = parser.add_subparsers(dest="cmd", required=True)

    # ask
    p_ask = sub.add_parser("ask", help="Run one question through the pipeline")
    p_ask.add_argument("question", help="The question to ask")

    # batch
    p_batch = sub.add_parser("batch", help="Run questions from a file")
    p_batch.add_argument("file", help="Text file with one question per line")

    # auto
    p_auto = sub.add_parser("auto", help="Auto-generate and run questions from corpus gaps")
    p_auto.add_argument("--mode", choices=["unknown", "backlog", "entries"],
                        default="unknown")
    p_auto.add_argument("--limit", type=int, default=5)
    p_auto.add_argument("--list-only", action="store_true",
                        help="Print questions without running them")

    # pick
    p_pick = sub.add_parser("pick", help="Run question twice, show only disagreements (PICK pattern)")
    p_pick.add_argument("question", help="The question to ask")

    # adversarial
    p_adv = sub.add_parser("adversarial", help="Run built-in adversarial variant suite, report routing/content breaks")
    p_adv.add_argument("--question", default=None, help="Custom canonical question (runs built-in suite if omitted)")
    p_adv.add_argument("--variants", nargs="*", help="Variants for custom question")

    # store
    p_store = sub.add_parser("store", help="Write a human-confirmed finding or workflow item")
    p_store.add_argument("subject", nargs="?", help="Symbol or file name")
    p_store.add_argument("kind", nargs="?", help="Artifact kind (file_purpose, design_note, ...)")
    p_store.add_argument("content", nargs="?", help="Finding text")
    p_store.add_argument("--workflow", nargs=3, metavar=("KIND", "SUBJECT", "CONTENT"),
                         help="Add a workflow item instead: --workflow backlog 'add X' 'description'")
    p_store.add_argument("--rank", type=int, default=None,
                         help="Priority rank for workflow items")

    args = parser.parse_args()

    try:
        oracle = DBOracle(args.db_path)
        assessor = Assessor(oracle)
    except Exception as e:
        print(f"ERROR loading corpus: {e}")
        sys.exit(1)

    if args.cmd == "ask":
        cmd_ask(args, oracle, assessor)
    elif args.cmd == "batch":
        cmd_batch(args, oracle, assessor)
    elif args.cmd == "auto":
        cmd_auto(args, oracle, assessor)
    elif args.cmd == "pick":
        cmd_pick(args, oracle, assessor)
    elif args.cmd == "adversarial":
        cmd_adversarial(args, oracle, assessor)
    elif args.cmd == "store":
        cmd_store(args, oracle, assessor)


if __name__ == "__main__":
    main()
