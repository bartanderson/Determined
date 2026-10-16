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
    apply   -- apply a verified bundle to a working repo, on a feature branch, in order,
               run its tests, and commit; roll back on any failure

Usage:
    .venv/Scripts/python tools/handoff.py make --clone PATH --bundle-dir PATH --id 001 --base-sha SHA
    .venv/Scripts/python tools/handoff.py check handoffs/dj2/001-encounter
    .venv/Scripts/python tools/handoff.py verify --bundle-dir PATH --clone PATH
    .venv/Scripts/python tools/handoff.py apply --bundle-dir handoffs/dj2/004-trade-fsm --repo C:/path/dj2
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
    (bundle_dir / "change.patch").write_text(patch_text, encoding="utf-8", newline="\n")

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
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
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
        # Allow HEAD ahead of base_sha (earlier bundles applied and committed)
        # so a later bundle can be verified on top of them. Non-ancestor HEAD
        # is still rejected.
        ancestor = _git(["merge-base", "--is-ancestor", base_sha, head_sha], clone)
        if ancestor.returncode != 0:
            return (f"Error: clone HEAD {head_sha[:8]} != base_sha {base_sha[:8]} "
                    f"and base_sha is not an ancestor of HEAD")

    status = _git(["status", "--short"], clone)
    if status.stdout.strip():
        return "Error: clone is not clean:\n" + status.stdout

    check = _git(["apply", "--check", str(patch_path)], clone)
    if check.returncode == 0:
        apply_result = _git(["apply", str(patch_path)], clone)
        apply_method = "direct"
    else:
        # Context mismatch - expected when earlier bundles have already
        # changed the same files. Fall back to three-way merge using the
        # blob SHAs recorded in the patch.
        apply_result = _git(["apply", "--3way", str(patch_path)], clone)
        apply_method = "3way"

    if apply_result.returncode != 0:
        return f"FAIL: git apply failed ({apply_method}): {apply_result.stderr.strip()}"

    if apply_method == "direct":
        command_lines = [
            "- `git apply --check change.patch` -> OK",
            "- `git apply change.patch` -> OK",
        ]
    else:
        command_lines = [
            "- `git apply --check change.patch` -> context mismatch (earlier bundles already applied)",
            "- `git apply --3way change.patch` -> OK (three-way merge succeeded)",
        ]

    lines = [
        f"# Verification for {manifest['id']}",
        "",
        f"Base SHA: {base_sha}",
        f"Clone HEAD: {head_sha}",
        f"Clone: {clone}",
        f"Apply method: {apply_method}",
        "",
        "## Commands",
        "",
        *command_lines,
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

    (bundle_dir / "verify.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")

    manifest["verified_at"] = verified_at
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")

    return f"verify: wrote {bundle_dir / 'verify.md'}"


PROTECTED_BRANCHES = {"", "main", "master"}


def lf_patch(patch_path):
    """Path to a patch git apply can match against LF files.

    A patch checked out on Windows with core.autocrlf=true has CRLF on every line,
    headers included, and then fails against LF content. That case is detected by
    the first line (the `diff --git` header) ending in CRLF; a genuine patch of a
    CRLF file has LF headers and is returned untouched. A temp copy is returned when
    a conversion was needed, otherwise the original path. Callers may delete a copy
    (it differs from the input path)."""
    import os
    import tempfile
    p = Path(patch_path)
    data = p.read_bytes()
    first = data.split(b"\n", 1)[0]
    if not first.endswith(b"\r"):
        return p
    fd, tmp = tempfile.mkstemp(suffix=".patch")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data.replace(b"\r\n", b"\n"))
    return Path(tmp)


def _patch_applied(repo, patch_path, bundle_id=None):
    """True if the bundle is already in the repo.

    Evidence, in order: a commit on HEAD's history whose subject starts "bundle <id>: "
    (what `apply` writes; survives later bundles editing the same lines), then whether
    the patch reverses cleanly (bundles applied by hand)."""
    if bundle_id:
        log = _git(["log", "HEAD", "-n", "1", "--format=%h",
                    f"--grep=^bundle {bundle_id}: "], repo)
        if log.returncode == 0 and log.stdout.strip():
            return True
    pp = lf_patch(patch_path)
    try:
        r = _git(["apply", "--reverse", "--check", "--whitespace=nowarn", str(pp)], repo)
    finally:
        if pp != Path(patch_path):
            pp.unlink(missing_ok=True)
    return r.returncode == 0


def cmd_apply(args):
    """Apply a verified bundle to a working repo and commit it, or change nothing.

    Refuses unless: the bundle passes `check` and has verified_at; the repo is on a
    feature branch (not main/master/detached); the tracked tree is clean; every earlier
    bundle in the same handoffs directory is already applied. The patch is applied
    directly or with --3way, the manifest's tests_run run in the repo, and only then
    committed. Any failure resets the repo to HEAD (safe: the tree was clean)."""
    bundle_dir = Path(args.bundle_dir).resolve()
    repo = Path(args.repo).resolve()

    checked = cmd_check(argparse.Namespace(bundle_dir=str(bundle_dir)))
    if not checked.startswith("PASS"):
        return "Error: bundle is not valid:\n" + checked
    manifest = json.loads((bundle_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    if not manifest.get("verified_at"):
        return f"Error: bundle {manifest.get('id')} has no verified_at; verify it first"
    original_patch = bundle_dir / "change.patch"
    patch = lf_patch(original_patch)
    try:
        return _apply_patch(args, manifest, bundle_dir, repo, original_patch, patch)
    finally:
        if patch != original_patch:
            patch.unlink(missing_ok=True)


def _apply_patch(args, manifest, bundle_dir, repo, original_patch, patch):
    """The body of cmd_apply once the bundle is known valid; `patch` is LF-safe."""

    if not (repo / ".git").exists():
        return f"Error: not a git repo: {repo}"
    branch = _git(["branch", "--show-current"], repo).stdout.strip()
    if branch in PROTECTED_BRANCHES:
        return (f"Error: {repo} is on {branch or 'a detached HEAD'}; apply bundles on a "
                f"feature branch (git switch -c feat/<name>)")
    dirty = _git(["status", "--porcelain", "--untracked-files=no"], repo).stdout.strip()
    if dirty:
        return "Error: the working tree has uncommitted tracked changes:\n" + dirty

    if _patch_applied(repo, patch, str(manifest["id"])):
        return f"OK: bundle {manifest['id']} is already applied in {repo} (nothing to do)"

    # Order: every earlier sibling bundle must already be in the tree.
    for sib in sorted(p for p in bundle_dir.parent.iterdir() if p.is_dir()):
        if sib.name >= bundle_dir.name:
            break
        sp = sib / "change.patch"
        if sp.is_file() and not _patch_applied(repo, sp, sib.name.partition("-")[0]):
            return f"Error: earlier bundle {sib.name} is not applied; apply it first"

    names = _git(["apply", "--numstat", str(patch)], repo).stdout.splitlines()
    files = [ln.split("\t")[-1] for ln in names if ln.strip()]
    preexisting = {f for f in files if (repo / f).exists()}

    def rollback():
        # reset --hard undoes tracked changes; a file the patch created is untracked after
        # a direct apply, so remove exactly those (never one that existed beforehand).
        _git(["reset", "--hard", "-q", "HEAD"], repo)
        for f in files:
            p = repo / f
            if f not in preexisting and p.is_file():
                p.unlink()
                try:
                    p.parent.rmdir()
                except OSError:
                    pass

    direct = _git(["apply", "--check", "--whitespace=nowarn", str(patch)], repo)
    method = "direct"
    if direct.returncode == 0:
        done = _git(["apply", "--whitespace=nowarn", str(patch)], repo)
    else:
        method = "3way"
        done = _git(["apply", "--3way", "--whitespace=nowarn", str(patch)], repo)
    if done.returncode != 0:
        rollback()
        return f"FAIL: git apply failed ({method}); repo restored:\n{done.stderr.strip()}"

    lines = []
    if not getattr(args, "skip_tests", False):
        for t in manifest.get("tests_run") or []:
            try:
                res = subprocess.run(
                    [sys.executable, "-m", "pytest", t, "-q", "-p", "no:cacheprovider"],
                    cwd=repo, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=600,
                )
            except subprocess.TimeoutExpired:
                rollback()
                return f"FAIL: test {t} timed out after 600 s; repo restored"
            tail = (res.stdout or "").strip().splitlines()
            last = tail[-1] if tail else "(no output)"
            lines.append(f"- {t}: {'PASS' if res.returncode == 0 else 'FAIL'} ({last})")
            if res.returncode != 0:
                rollback()
                return (f"FAIL: test {t} failed; repo restored\n"
                        + "\n".join((res.stdout or "").strip().splitlines()[-15:]))

    add = _git(["add", "--", *files], repo)
    if add.returncode != 0:
        rollback()
        return f"FAIL: git add failed; repo restored:\n{add.stderr.strip()}"
    slug = bundle_dir.name.partition("-")[2] or bundle_dir.name
    message = (
        f"bundle {manifest['id']}: {slug}\n\n"
        f"Applied from {bundle_dir.name} (base {str(manifest.get('base_sha'))[:8]}, "
        f"{method}). Verified {manifest.get('verified_at')}.\n"
        + ("Tests:\n" + "\n".join(lines) + "\n" if lines else "Tests: none named in the manifest.\n")
    )
    commit = subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-F", "-"],
        input=message, capture_output=True, text=True, encoding="utf-8",
    )
    if commit.returncode != 0:
        rollback()
        return f"FAIL: git commit failed; repo restored:\n{commit.stderr.strip()}"
    sha = _git(["rev-parse", "--short", "HEAD"], repo).stdout.strip()
    return "\n".join([
        f"OK: bundle {manifest['id']} applied ({method}) and committed as {sha} on {branch}",
        f"files: {len(files)}",
        *lines,
    ])


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

    a = sub.add_parser("apply", help="apply a verified bundle to a repo on a feature branch")
    a.add_argument("--bundle-dir", required=True)
    a.add_argument("--repo", required=True)
    a.add_argument("--skip-tests", action="store_true",
                   help="do not run the manifest's tests_run (not for unattended use)")
    a.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    result = args.func(args)
    print(result)
    return 0 if not result.startswith(("Error:", "FAIL:")) else 1


if __name__ == "__main__":
    sys.exit(main())