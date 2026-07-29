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

import sqlite3
from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.agent.sketch_stub import build_brief, _llm_candidate, _verify_candidate

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

    conn = sqlite3.connect(DB_PATH)
    oracle = DBOracle(conn)
    assessor = Assessor(oracle)

    stubs = get_stubs(conn)
    print(f"Total stubs (after dir filter): {len(stubs)}")

    v1_results = []
    v2_results = []
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


if __name__ == "__main__":
    main()
