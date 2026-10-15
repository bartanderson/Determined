"""Pre-push check for a public repository.

Looks at exactly what a push would publish (the commits on a branch that the remote
does not have) and fails on things that should not leave the machine:

  - secret-shaped strings on added lines (keys, tokens, private keys, quoted
    credential assignments)
  - added files that are databases, backups, model weights, archives, binaries,
    key/env files, or larger than --max-kb
  - private terms: any line of the private-terms file, matched case-insensitively in
    commit messages, added lines and added file paths. The file lives OUTSIDE the repo
    (default ~/.determined/private_terms.txt, override with DETERMINED_PRIVATE_TERMS)
    so the list of private names is itself never published.

Usage:
    python tools/pre_push_check.py                  # current branch vs origin/<branch>
    python tools/pre_push_check.py --branch main --remote origin
    python tools/pre_push_check.py --json

Exit 0 = clear to push, 1 = problems found, 2 = could not evaluate. Never pushes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_TERMS_FILE = Path.home() / ".determined" / "private_terms.txt"
BLOCKED_EXT = {
    ".db", ".sqlite", ".sqlite3", ".bak", ".gguf", ".safetensors", ".bin", ".zip", ".7z",
    ".tar", ".gz", ".exe", ".dll", ".pyc", ".pem", ".key", ".p12", ".pfx", ".env",
}
SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("API key (sk-)", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("credential assignment", re.compile(
        r"""(?i)\b(api[_-]?key|secret|passw(?:or)?d|token)\b\s*[:=]\s*['"][^'"\s]{8,}['"]""")),
]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def load_terms(path: Path | None = None) -> list[str]:
    p = Path(os.environ.get("DETERMINED_PRIVATE_TERMS") or path or DEFAULT_TERMS_FILE)
    if not p.is_file():
        return []
    terms = []
    # utf-8-sig: files written by Windows PowerShell 5.1 start with a BOM
    for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return terms


def check_range(repo: Path, base: str | None, tip: str, terms: list[str],
                max_kb: int = 1024) -> list[str]:
    """Problems in the commits reachable from `tip` but not from `base`.
    base=None means "not on any remote" (a new branch)."""
    problems: list[str] = []
    rng = [tip, "--not", base] if base else [tip, "--not", "--remotes"]
    term_res = [(t, re.compile(re.escape(t), re.I)) for t in terms]

    # 1. commit messages
    log = _git(repo, "log", "--format=%h%x00%B%x00%x01", *rng)
    for rec in log.stdout.split("\x01"):
        if "\x00" not in rec:
            continue
        sha, _, rest = rec.strip().partition("\x00")
        body = rest.rstrip("\x00")
        for t, rx in term_res:
            if rx.search(body):
                problems.append(f"commit {sha}: message mentions private term {t!r}")

    # 2. files added/modified (path rules, size, extension)
    diff_base = base or _git(repo, "rev-list", "--max-parents=0", tip).stdout.split()[0]
    names = _git(repo, "diff", "--name-only", "--diff-filter=AM", f"{diff_base}..{tip}")
    for path in names.stdout.splitlines():
        ext = Path(path).suffix.lower()
        if ext in BLOCKED_EXT or Path(path).name.lower() in {".env"}:
            problems.append(f"{path}: file type {ext or Path(path).name!r} must not be published")
        size = _git(repo, "cat-file", "-s", f"{tip}:{path}").stdout.strip()
        if size.isdigit() and int(size) > max_kb * 1024:
            problems.append(f"{path}: {int(size) // 1024} KB exceeds {max_kb} KB")
        for t, rx in term_res:
            if rx.search(path):
                problems.append(f"{path}: path mentions private term {t!r}")

    # 3. added lines
    diff = _git(repo, "diff", "-U0", "--no-color", f"{diff_base}..{tip}")
    cur = ""
    for line in diff.stdout.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        text = line[1:]
        for name, rx in SECRET_PATTERNS:
            if rx.search(text):
                problems.append(f"{cur}: looks like a {name}: {text.strip()[:70]!r}")
        for t, rx in term_res:
            if rx.search(text):
                problems.append(f"{cur}: line mentions private term {t!r}")
    return problems


def evaluate(repo: Path, remote: str, branch: str, terms: list[str], max_kb: int) -> tuple[int, list[str]]:
    if _git(repo, "rev-parse", "--verify", "-q", branch).returncode != 0:
        return 2, [f"branch {branch!r} not found"]
    same_ref = f"refs/remotes/{remote}/{branch}"
    candidates = [same_ref, f"refs/remotes/{remote}/HEAD", f"refs/remotes/{remote}/main"]
    base_ref = next(
        (c for c in candidates if _git(repo, "rev-parse", "--verify", "-q", c).returncode == 0),
        None,
    )
    problems: list[str] = []
    if base_ref == same_ref:
        behind = _git(repo, "rev-list", "--count", f"{branch}..{same_ref}").stdout.strip()
        if behind not in ("", "0"):
            problems.append(
                f"{branch} is behind {remote}/{branch} by {behind} commit(s): "
                f"fetch and integrate before pushing (a push would be rejected)"
            )
    base = None
    if base_ref:
        # merge-base: a new branch is judged against what the remote already has,
        # not against the root commit.
        mb = _git(repo, "merge-base", base_ref, branch).stdout.strip()
        base = mb or base_ref
    problems += check_range(repo, base, branch, terms, max_kb)
    return (1 if problems else 0), problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check what a push would publish.")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--branch", default=None, help="default: current branch")
    ap.add_argument("--max-kb", type=int, default=1024)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    branch = args.branch or _git(repo, "branch", "--show-current").stdout.strip()
    if not branch:
        print("pre_push_check: detached HEAD; pass --branch")
        return 2
    terms = load_terms()
    code, problems = evaluate(repo, args.remote, branch, terms, args.max_kb)
    outgoing = _git(repo, "rev-list", "--count", branch, "--not", "--remotes").stdout.strip() or "?"
    if args.json:
        print(json.dumps({"ok": code == 0, "branch": branch, "outgoing_commits": outgoing,
                          "private_terms_loaded": len(terms), "problems": problems}, indent=2))
    elif code == 0:
        print(f"PRE-PUSH: clear ({branch}: {outgoing} commit(s) outgoing; "
              f"{len(terms)} private term(s) checked)")
        if not terms:
            print("  note: no private terms file found "
                  f"({DEFAULT_TERMS_FILE}); private-name checks skipped")
    else:
        print(f"PRE-PUSH: {len(problems)} problem(s) on {branch}")
        for p in problems:
            print("  - " + p)
    return code


if __name__ == "__main__":
    sys.exit(main())
