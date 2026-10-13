"""
tools/handoff.py -- manage dj2 handoff bundles.

A handoff bundle is a directory handoffs/dj2/<NNN>-<slug>/ containing exactly:
    MANIFEST.json    bundle metadata (id, base_sha, files_touched, tests_run,
                     finding_ids, openspec_task, verified_at)
    change.patch     unified diff relative to the dj2 repo root, applicable
                     with `git apply`
    rationale.md     why this change, citing Determined findings and dj2 docs
    verify.md        exact commands run in a clone at base_sha, with output

Subcommands:
    make    -- create a bundle from a dj2 clone that has the change applied
    verify  -- apply a bundle to a fresh clone at base_sha and run named tests
    check   -- assert the bundle directory has all four files and a valid manifest

Usage:
    python tools/handoff.py make --clone PATH --bundle-dir PATH --id 001 --base-sha SHA
    python tools/handoff.py check handoffs/dj2/001-encounter
    python tools/handoff.py verify --bundle-dir PATH --clone PATH
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_MANIFEST_KEYS = [
    "id", "base_sha", "files_touched", "tests_run",
    "finding_ids", "openspec_task", "verified_at",
]
REQUIRED_FILES = ["MANIFEST.json", "change.patch", "rationale.md", "verify.md"]


def _git(args, cwd):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def cmd_make(args):
    clone = Path(args.clone).resolve()
    if not clone.is_dir():
        return f"Error: clone not found: {clone}"
    if not (clone / ".git").is_dir():
        return f"Error: not a git repo: {clone}"

    head = _git(["rev-parse", "HEAD"], clone)
    if head.returncode != 0:
        return f"Error: cannot read HEAD in {clone}"
    head_sha = head.stdout.strip()

    # Stage everything in the scratch clone so newly added files appear in the
    # diff. The clone is disposable; this never touches the user's working copy.
    _git(["add", "-A"], clone)

    diff = _git(["diff", "--cached", args.base_sha], clone)
    if diff.returncode != 0:
        return f"Error: git diff --cached {args.base_sha} failed: {diff.stderr.strip()}"
    patch_text = diff.stdout

    names = _git(["diff", "--cached", "--name-only", args.base_sha], clone)
    files_touched = [l for l in names.stdout.splitlines() if l.strip()]

    bundle_dir = Path(args.bundle_dir).resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "change.patch").write_text(patch_text, encoding="utf-8")

    manifest = {
        "id": args.id,
        "base_sha": args.base_sha,
        "files_touched": files_touched,
        "tests_run": list(args.test or []),
        "finding_ids": list(args.finding_id or []),
        "openspec_task": args.openspec_task or "",
        "verified_at": None,
    }
    (bundle_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    if not (bundle_dir / "rationale.md").exists():
        (bundle_dir / "rationale.md").write_text(
            "# Rationale\n\n"
            "(fill in: why this change, citing Determined findings and dj2 design docs)\n",
            encoding="utf-8",
        )
    if not (bundle_dir / "verify.md").exists():
        (bundle_dir / "verify.md").write_text(
            "# Verification\n\n(not yet verified)\n", encoding="utf-8"
        )

    return (
        f"make: wrote bundle {bundle_dir} "
        f"(HEAD {head_sha[:8]}, {len(files_touched)} file(s) touched)"
    )


def cmd_check(args):
    bundle_dir = Path(args.bundle_dir).resolve()
    if not bundle_dir.is_dir():
        return f"FAIL: not a directory: {bundle_dir}"

    problems = []
    for name in REQUIRED_FILES:
        if not (bundle_dir / name).is_file():
            problems.append(f"missing file: {name}")

    manifest = {}
    manifest_path = bundle_dir / "MANIFEST.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"MANIFEST.json parse error: {exc}")

    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            problems.append(f"MANIFEST.json missing key: {key}")

    finding_ids = manifest.get("finding_ids") or []
    openspec_task = (manifest.get("openspec_task") or "").strip()
    if not finding_ids and not openspec_task:
        problems.append(
            "bundle cites no Determined finding id and no OpenSpec task"
        )

    if problems:
        lines = [f"FAIL: {bundle_dir}"]
        lines.extend("  " + p for p in problems)
        return "\n".join(lines)

    return f"PASS: {bundle_dir}"


def cmd_verify(args):
    bundle_dir = Path(args.bundle_dir).resolve()
    if not bundle_dir.is_dir():
        return f"Error: bundle not found: {bundle_dir}"

    manifest_path = bundle_dir / "MANIFEST.json"
    patch_path = bundle_dir / "change.patch"
    if not manifest_path.is_file() or not patch_path.is_file():
        return "Error: bundle is missing MANIFEST.json or change.patch"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_sha = manifest["base_sha"]

    clone = Path(args.clone).resolve()
    if not (clone / ".git").is_dir():
        return f"Error: not a git repo: {clone}"

    head = _git(["rev-parse", "HEAD"], clone)
    head_sha = head.stdout.strip()
    if head_sha != base_sha:
        return f"Error: clone HEAD {head_sha[:8]} != base_sha {base_sha[:8]}"

    status = _git(["status", "--short"], clone)
    if status.stdout.strip():
        return "Error: clone is not clean:\n" + status.stdout

    check = _git(["apply", "--check", str(patch_path)], clone)
    if check.returncode != 0:
        return f"FAIL: git apply --check failed: {check.stderr.strip()}"

    apply_result = _git(["apply", str(patch_path)], clone)
    if apply_result.returncode != 0:
        return f"FAIL: git apply failed: {apply_result.stderr.strip()}"

    lines = [
        f"# Verification for {manifest['id']}",
        "",
        f"Base SHA: {base_sha}",
        f"Clone: {clone}",
        "",
        "## Commands",
        "",
        "- `git apply --check change.patch` -> OK",
        "- `git apply change.patch` -> OK",
        "",
    ]

    tests_run = manifest.get("tests_run") or []
    if tests_run:
        lines.append("## Tests")
        lines.append("")
        for t in tests_run:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", t, "-q"],
                cwd=clone, capture_output=True, text=True, encoding="utf-8",
            )
            label = "PASS" if result.returncode == 0 else "FAIL"
            out_lines = (result.stdout or "").strip().splitlines()
            last = out_lines[-1] if out_lines else "(no output)"
            lines.append(f"- `{t}` -> {label}  ({last})")
        lines.append("")
    else:
        lines.append("## Tests")
        lines.append("")
        lines.append("(no tests named in MANIFEST.tests_run)")
        lines.append("")

    lines.append("## Not run")
    lines.append("")
    lines.append("(list any named test that could not be run, with the reason)")
    lines.append("")

    verified_at = datetime.now(timezone.utc).isoformat()
    lines.append(f"verified_at: {verified_at}")
    lines.append("")

    (bundle_dir / "verify.md").write_text("\n".join(lines), encoding="utf-8")

    manifest["verified_at"] = verified_at
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return f"verify: wrote {bundle_dir / 'verify.md'}"


def main():
    parser = argparse.ArgumentParser(
        description="Manage dj2 handoff bundles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("make", help="create a bundle from a clone with the change applied")
    m.add_argument("--clone", required=True)
    m.add_argument("--bundle-dir", required=True)
    m.add_argument("--id", required=True)
    m.add_argument("--base-sha", required=True)
    m.add_argument("--finding-id", action="append", default=[])
    m.add_argument("--openspec-task", default="")
    m.add_argument("--test", action="append", default=[])
    m.set_defaults(func=cmd_make)

    c = sub.add_parser("check", help="verify a bundle directory is complete")
    c.add_argument("bundle_dir")
    c.set_defaults(func=cmd_check)

    v = sub.add_parser("verify", help="apply a bundle to a fresh clone at base_sha and run tests")
    v.add_argument("--bundle-dir", required=True)
    v.add_argument("--clone", required=True)
    v.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    result = args.func(args)
    print(result)
    return 0 if not result.startswith(("Error:", "FAIL:")) else 1


if __name__ == "__main__":
    sys.exit(main())