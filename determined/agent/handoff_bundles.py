# determined/agent/handoff_bundles.py
#
# Read-only awareness of verified handoff bundles (handoffs/<corpus>/NNN-slug/).
#
# A bundle is a verified patch Determined produced for another repo (see
# tools/handoff.py). The corpus DB describes that repo as it is, so a stub a pending
# bundle already implements still looks like open work. This module answers, from the
# bundle files and the repo's git state alone (no LLM): which open items does a
# bundle already cover, and has the bundle been applied yet?
#
# Public API:
#   load_bundles(corpus_name, root=None)      -> list[Bundle]   (verified bundles only)
#   bundle_state(bundle, project_root)        -> "applied" | "pending" | "unknown"
#   annotate_items(items, bundles, root)      -> (actionable, handed_off)
#   corpus_handoff_context(conn)              -> (bundles, project_root) for a corpus DB
#
# Matching is deliberately conservative and explained, not guessed:
#   FSM handler  - its name appears on an added line of a non-test .py file in the patch
#                  (a def, or a registry key such as 'update_price': builtins.update_price)
#   Python stub  - the patch defines or changes a function of that name in the stub's file
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
HANDOFFS_ROOT = _REPO / "handoffs"

_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")
_HUNK_RE = re.compile(r"^@@ .*? @@ ?(.*)$")
_WORD_RE = re.compile(r"[A-Za-z_]\w*")
_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")


@dataclass
class PatchFile:
    path: str                                   # repo-relative, forward slashes
    touched_defs: set[str] = field(default_factory=set)   # functions defined or changed
    added_words: set[str] = field(default_factory=set)    # identifiers on added lines

    @property
    def is_test(self) -> bool:
        p = self.path.lower()
        name = p.rsplit("/", 1)[-1]
        return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in "/" + p


@dataclass
class Bundle:
    id: str
    slug: str
    dir: Path
    base_sha: str
    verified_at: str
    files: list[PatchFile]

    @property
    def label(self) -> str:
        return f"{self.id}-{self.slug}" if self.slug else self.id


def parse_patch(text: str) -> list[PatchFile]:
    """Per file: which functions the patch defines or changes, and added identifiers."""
    files: list[PatchFile] = []
    cur: PatchFile | None = None
    current_def: str | None = None
    in_hunk = False
    for line in text.splitlines():
        if line.startswith("diff --git "):
            cur, current_def, in_hunk = None, None, False
            continue
        m = _FILE_RE.match(line)
        if m and not in_hunk:
            cur = PatchFile(path=m.group(1).strip().replace("\\", "/"))
            files.append(cur)
            continue
        if cur is None:
            continue
        h = _HUNK_RE.match(line)
        if h:
            in_hunk = True
            dm = _DEF_RE.match(h.group(1))
            current_def = dm.group(1) if dm else None
            continue
        if not in_hunk or not line or line[0] not in " +-":
            continue
        sign, content = line[0], line[1:]
        dm = _DEF_RE.match(content)
        if dm:
            if sign == "-":
                current_def = None          # removed or renamed away: not an implementation
            else:
                current_def = dm.group(1)
                if sign == "+":
                    cur.touched_defs.add(current_def)
        elif sign in "+-" and content.strip() and current_def:
            cur.touched_defs.add(current_def)
        if sign == "+":
            cur.added_words.update(_WORD_RE.findall(content))
    return files


def load_bundles(corpus_name: str, root: Path | None = None) -> list[Bundle]:
    """Verified bundles under handoffs/<corpus_name>/, in id order. Unverified, malformed
    or patch-less directories are skipped (a bundle that is not verified is not ready)."""
    base = (root or HANDOFFS_ROOT) / corpus_name
    if not base.is_dir():
        return []
    out: list[Bundle] = []
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        mpath, ppath = d / "MANIFEST.json", d / "change.patch"
        if not (mpath.is_file() and ppath.is_file()):
            continue
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
            patch = ppath.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue
        if not manifest.get("verified_at"):
            continue
        name = d.name
        bid, _, slug = name.partition("-")
        out.append(Bundle(
            id=str(manifest.get("id") or bid), slug=slug, dir=d,
            base_sha=str(manifest.get("base_sha") or ""),
            verified_at=str(manifest["verified_at"]),
            files=parse_patch(patch),
        ))
    return out


def bundle_state(bundle: Bundle, project_root: str | Path | None) -> str:
    """'applied' if the patch reverses cleanly in the repo, 'pending' if it does not,
    'unknown' if the repo is missing or git cannot decide."""
    if not project_root:
        return "unknown"
    root = Path(project_root)
    if not (root / ".git").exists():
        return "unknown"
    patch = bundle.dir / "change.patch"
    tmp: Path | None = None
    try:
        # `tools/handoff.py apply` commits as "bundle <id>: <slug>"; that record survives
        # later bundles editing the same lines, which breaks the reverse-apply check.
        log = subprocess.run(
            ["git", "-C", str(root), "log", "HEAD", "-n", "1", "--format=%h",
             f"--grep=^bundle {bundle.id}: "],
            capture_output=True, text=True, timeout=20,
        )
        if log.returncode == 0 and log.stdout.strip():
            return "applied"
        # A patch checked out on Windows (core.autocrlf) has CRLF on every line and
        # cannot match LF files; same normalization as tools/handoff.py lf_patch.
        data = patch.read_bytes()
        if data.split(b"\n", 1)[0].endswith(b"\r"):
            import os
            import tempfile
            fd, name = tempfile.mkstemp(suffix=".patch")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data.replace(b"\r\n", b"\n"))
            tmp = Path(name)
            patch = tmp
        r = subprocess.run(
            ["git", "-C", str(root), "apply", "--reverse", "--check", "--whitespace=nowarn",
             str(patch)],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return "applied" if r.returncode == 0 else "pending"


def _covers_handler(bundle: Bundle, name: str) -> bool:
    return any(
        not pf.is_test and pf.path.endswith(".py") and name in pf.added_words
        for pf in bundle.files
    )


def _covers_stub(bundle: Bundle, name: str, file_path: str) -> bool:
    fp = (file_path or "").replace("\\", "/")
    for pf in bundle.files:
        if pf.is_test or name not in pf.touched_defs:
            continue
        if fp == pf.path or fp.endswith("/" + pf.path):
            return True
    return False


def annotate_items(items: list[dict], bundles: list[Bundle],
                   project_root: str | Path | None = None) -> tuple[list[dict], list[dict]]:
    """Attach a 'handoff' entry to items a bundle covers and split them.

    Returns (actionable, handed_off). actionable keeps input order and holds items with
    no coverage or partial coverage (partial ones carry handoff.remaining).
    handed_off holds items every handler/function of which a bundle covers.
    Items are copied; the input list is not mutated."""
    if not bundles:
        return list(items), []
    states = {b.id: bundle_state(b, project_root) for b in bundles}
    actionable: list[dict] = []
    handed_off: list[dict] = []
    for item in items:
        item = dict(item)
        names = (item.get("actions") or []) + (item.get("guards") or []) if item.get("is_fsm") \
            else [item["name"]]
        hits: list[dict] = []
        covered_names: set[str] = set()
        for b in bundles:
            if item.get("is_fsm"):
                got = [n for n in names if _covers_handler(b, n)]
            else:
                got = names if _covers_stub(b, item["name"], item.get("file_path", "")) else []
            if got:
                hits.append({"id": b.id, "label": b.label, "verified_at": b.verified_at[:10],
                             "state": states[b.id], "covered": got})
                covered_names.update(got)
        if not hits:
            actionable.append(item)
            continue
        remaining = [n for n in names if n not in covered_names]
        item["handoff"] = {"bundles": hits, "total": len(names), "remaining": remaining,
                           "full": not remaining}
        (handed_off if not remaining else actionable).append(item)
    return actionable, handed_off


def corpus_handoff_context(conn) -> tuple[list[Bundle], str | None]:
    """(bundles, project_root) for the corpus behind `conn`, via project_meta.project_root.
    Bundles live in handoffs/<basename of project_root>/. Returns ([], None) when the
    corpus has no recorded root or no handoffs directory."""
    try:
        row = conn.execute(
            "SELECT value FROM project_meta WHERE key='project_root'"
        ).fetchone()
    except Exception:
        return [], None
    if not row or not row[0]:
        return [], None
    root = str(row[0])
    name = root.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return load_bundles(name), root


def describe(handoff: dict) -> list[str]:
    """Human lines for one annotated item, one per bundle, plus a remaining line."""
    advice = {
        "pending": "pending apply: apply the bundle, do not reimplement",
        "applied": "already applied in the working tree: re-ingest (reingest_changed)",
        "unknown": "verified bundle exists: check its state in handoffs/STATE.md",
    }
    lines = []
    for h in handoff["bundles"]:
        lines.append(
            f"bundle {h['label']} (verified {h['verified_at']}) changes "
            f"{len(h['covered'])}/{handoff['total']}: {advice[h['state']]}"
        )
    if handoff["remaining"] and not handoff["full"]:
        # What the patch says, not what the repo lacks: an untouched handler may
        # already exist at baseline.
        lines.append("not changed by the bundle: " + ", ".join(handoff["remaining"]))
    return lines
