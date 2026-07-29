"""
tools/rm70_baseline.py — RM70 V1+V2 baseline runner for dj2 stubs.

Run with llama-server only (no UI server) to avoid LLM contention:
  .venv\Scripts\python.exe tools\rm70_baseline.py

Writes results to stdout. Actionable stubs only (design-intent-stated,
blocked-on-prerequisite, config_declared body shape).
"""
import sys
import os

# Repo root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.agent.sketch_stub import build_brief, _llm_candidate, _verify_candidate
from determined.agent.export_context import _complexity_score

DB_PATH = r"C:\Users\bartl\dev\Determined\C_Users_bartl_dev_dj2.db"

EXCLUDE_DIRS = ("Lib/", "archive/", "tools/", "tools.old/", "og_system/",
                "recovered_code/", "codebase_analyzer/", "Scripts/")


def get_stubs(conn):
    rows = conn.execute(
        "SELECT name, file_path FROM functions WHERE is_stub = 1"
    ).fetchall()
    result = []
    for name, fp in rows:
        if fp and any(d in fp.replace("\\", "/") for d in EXCLUDE_DIRS):
            continue
        result.append((name, fp))
    return result


def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: DB not found: {DB_PATH}")
        sys.exit(1)

    oracle = DBOracle(DB_PATH)
    conn = oracle.conn
    assessor = Assessor(oracle)

    stubs = get_stubs(conn)
    print(f"Total stubs (after dir filter): {len(stubs)}")

    v1_results = []
    v2_results = []
    complexity_rows = []   # (name, score, signals) for RM71 calibration
    not_actionable = 0
    llm_unavailable = 0
    errors = 0

    for name, fp in stubs:
        brief = build_brief(oracle, name)
        if "error" in brief:
            errors += 1
            continue
        if not brief.get("actionable"):
            not_actionable += 1
            continue

        # RM71: complexity score (deterministic, no LLM needed)
        cscore, csignals = _complexity_score(brief, oracle)
        complexity_rows.append((name, cscore, csignals))

        best_sibling_body = (
            brief["siblings"][0].get("body_preview") if brief.get("siblings") else None
        )
        candidate = _llm_candidate(brief)
        if candidate is None:
            llm_unavailable += 1
            print(f"  [no LLM] {name}")
            continue

        vr = _verify_candidate(
            candidate, oracle,
            declared_return_type=brief.get("return_type"),
            best_sibling_body=best_sibling_body,
        )
        v1_pass = vr["v1_pass"]
        v2 = vr["v2_score"]
        comp = vr["composite"]
        v1_results.append(v1_pass)
        v2_results.append(v2)
        status = "V1=PASS" if v1_pass else "V1=FAIL"
        print(f"  {name:40s}  {status}  V2={v2:.3f}  composite={comp:.3f}"
              + (f"  unresolved={vr['v2_unresolved']}" if vr["v2_unresolved"] else ""))

    print()
    total_ran = len(v1_results)
    print(f"Actionable stubs tried: {total_ran}")
    print(f"Not actionable (skipped): {not_actionable}")
    print(f"LLM unavailable: {llm_unavailable}")
    print(f"Errors: {errors}")
    if total_ran:
        v1_rate = sum(v1_results) / total_ran
        v2_mean = sum(v2_results) / total_ran
        print(f"V1 pass rate:  {v1_rate:.3f}  ({sum(v1_results)}/{total_ran})")
        print(f"V2 mean score: {v2_mean:.3f}")
        print(f"V2 range:      {min(v2_results):.3f} – {max(v2_results):.3f}")
    else:
        print("No results to summarize.")

    # RM71 calibration
    if complexity_rows:
        print()
        print("=" * 60)
        print("RM71 COMPLEXITY CALIBRATION")
        print("=" * 60)
        complexity_rows.sort(key=lambda r: r[1], reverse=True)
        for name, score, sigs in complexity_rows:
            tier = "ESCALATE" if score >= 0.5 else "local"
            print(f"  {name:40s}  score={score:.3f}  [{tier}]")
            print(f"    caller_cx={sigs['caller_complexity']:.3f}  "
                  f"low_conf={sigs['low_confidence']:.3f}  "
                  f"unres={sigs['unresolved_ratio']:.3f}  "
                  f"type_miss={sigs['type_missing']:.3f}  "
                  f"sib_miss={sigs['sibling_missing']:.0f}")
        scores = [r[1] for r in complexity_rows]
        print()
        print(f"Complexity range: {min(scores):.3f} – {max(scores):.3f}  "
              f"mean={sum(scores)/len(scores):.3f}")
        escalate_count = sum(1 for s in scores if s >= 0.5)
        print(f"Above threshold (0.5): {escalate_count}/{len(scores)}")


if __name__ == "__main__":
    main()
