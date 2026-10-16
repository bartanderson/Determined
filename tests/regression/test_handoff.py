"""
Regression tests for tools/handoff.py.

Uses git fixture repos built under tmp_path: one source repo to make a
bundle from, one fresh clone at base_sha to verify it against.
"""

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "handoff", _ROOT / "tools" / "handoff.py"
)
handoff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(handoff)


def _git(args, cwd):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(["config", "user.email", "test@example.com"], path)
    _git(["config", "user.name", "test"], path)


def _commit(path, msg="c"):
    _git(["add", "-A"], path)
    _git(["commit", "-q", "-m", msg], path)
    return _git(["rev-parse", "HEAD"], path).stdout.strip()


def _fresh_clone_at(source, target, sha):
    subprocess.run(["git", "clone", "-q", str(source), str(target)], check=True)
    _git(["checkout", "-q", sha], target)
    _git(["clean", "-fd"], target)
    return target


def _write_complete_bundle(bundle_dir, manifest):
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "MANIFEST.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (bundle_dir / "change.patch").write_text("", encoding="utf-8")
    (bundle_dir / "rationale.md").write_text("x", encoding="utf-8")
    (bundle_dir / "verify.md").write_text("x", encoding="utf-8")


def test_check_rejects_missing_files(tmp_path):
    ns = argparse.Namespace(bundle_dir=str(tmp_path))
    result = handoff.cmd_check(ns)
    assert result.startswith("FAIL")
    assert "MANIFEST.json" in result


def test_check_rejects_no_finding_id(tmp_path):
    _write_complete_bundle(tmp_path, {
        "id": "001", "base_sha": "0" * 40, "files_touched": ["a.py"],
        "tests_run": [], "finding_ids": [], "openspec_task": "",
        "verified_at": None,
    })
    ns = argparse.Namespace(bundle_dir=str(tmp_path))
    result = handoff.cmd_check(ns)
    assert result.startswith("FAIL")
    assert "finding" in result.lower()


def test_check_passes_with_finding_id(tmp_path):
    _write_complete_bundle(tmp_path, {
        "id": "001", "base_sha": "0" * 40, "files_touched": ["a.py"],
        "tests_run": [], "finding_ids": ["F-1"], "openspec_task": "",
        "verified_at": None,
    })
    ns = argparse.Namespace(bundle_dir=str(tmp_path))
    result = handoff.cmd_check(ns)
    assert result.startswith("PASS")


def test_check_passes_with_openspec_task_only(tmp_path):
    _write_complete_bundle(tmp_path, {
        "id": "001", "base_sha": "0" * 40, "files_touched": ["a.py"],
        "tests_run": [], "finding_ids": [], "openspec_task": "2.3",
        "verified_at": None,
    })
    ns = argparse.Namespace(bundle_dir=str(tmp_path))
    result = handoff.cmd_check(ns)
    assert result.startswith("PASS")


def test_make_produces_bundle(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "hello.txt").write_text("old\n", encoding="utf-8")
    base = _commit(repo, "base")

    (repo / "hello.txt").write_text("new\n", encoding="utf-8")
    (repo / "added.txt").write_text("added\n", encoding="utf-8")

    bundle = tmp_path / "bundle"
    ns = argparse.Namespace(
        clone=str(repo), bundle_dir=str(bundle),
        id="001", base_sha=base,
        finding_id=["F-1"], openspec_task="",
        test=[],
    )
    result = handoff.cmd_make(ns)
    assert result.startswith("make:")
    assert (bundle / "change.patch").is_file()
    assert (bundle / "MANIFEST.json").is_file()
    assert (bundle / "rationale.md").is_file()
    assert (bundle / "verify.md").is_file()

    manifest = json.loads((bundle / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["base_sha"] == base
    assert "hello.txt" in manifest["files_touched"]
    assert "added.txt" in manifest["files_touched"]
    assert manifest["finding_ids"] == ["F-1"]


def test_verify_applies_and_runs(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "hello.txt").write_text("old\n", encoding="utf-8")
    base = _commit(repo, "base")

    (repo / "hello.txt").write_text("new\n", encoding="utf-8")

    bundle = tmp_path / "bundle"
    handoff.cmd_make(argparse.Namespace(
        clone=str(repo), bundle_dir=str(bundle),
        id="001", base_sha=base,
        finding_id=["F-1"], openspec_task="",
        test=[],
    ))

    verify_clone = tmp_path / "verify"
    _fresh_clone_at(repo, verify_clone, base)

    result = handoff.cmd_verify(argparse.Namespace(
        bundle_dir=str(bundle), clone=str(verify_clone),
    ))
    assert result.startswith("verify:")
    assert (bundle / "verify.md").is_file()
    verify_md = (bundle / "verify.md").read_text(encoding="utf-8")
    assert base in verify_md
    assert (verify_clone / "hello.txt").read_text(encoding="utf-8") == "new\n"

    manifest = json.loads((bundle / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["verified_at"] is not None


def test_verify_rejects_dirty_clone(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "hello.txt").write_text("old\n", encoding="utf-8")
    base = _commit(repo, "base")

    (repo / "hello.txt").write_text("new\n", encoding="utf-8")
    bundle = tmp_path / "bundle"
    handoff.cmd_make(argparse.Namespace(
        clone=str(repo), bundle_dir=str(bundle),
        id="001", base_sha=base,
        finding_id=["F-1"], openspec_task="",
        test=[],
    ))

    verify_clone = tmp_path / "verify"
    _fresh_clone_at(repo, verify_clone, base)
    (verify_clone / "hello.txt").write_text("dirty\n", encoding="utf-8")

    result = handoff.cmd_verify(argparse.Namespace(
        bundle_dir=str(bundle), clone=str(verify_clone),
    ))
    assert result.startswith("Error")
    assert "clean" in result.lower()


def test_verify_accepts_descendant_head_via_3way(tmp_path):
    """
    When HEAD is ahead of base_sha (earlier bundles applied and committed),
    verify falls back to three-way apply and succeeds.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "hello.txt").write_text("old\n", encoding="utf-8")
    base = _commit(repo, "base")

    (repo / "hello.txt").write_text("new\n", encoding="utf-8")
    bundle = tmp_path / "bundle"
    handoff.cmd_make(argparse.Namespace(
        clone=str(repo), bundle_dir=str(bundle),
        id="001", base_sha=base,
        finding_id=["F-1"], openspec_task="",
        test=[],
    ))

    # Add another commit on top of base so HEAD != base_sha.
    (repo / "other.txt").write_text("x\n", encoding="utf-8")
    descendant = _commit(repo, "later work")

    verify_clone = tmp_path / "verify"
    _fresh_clone_at(repo, verify_clone, descendant)

    result = handoff.cmd_verify(argparse.Namespace(
        bundle_dir=str(bundle), clone=str(verify_clone),
    ))
    assert result.startswith("verify:")
    verify_md = (bundle / "verify.md").read_text(encoding="utf-8")
    assert "3way" in verify_md


def test_verify_rejects_non_ancestor_head(tmp_path):
    """A HEAD that does not descend from base_sha is still rejected."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "hello.txt").write_text("old\n", encoding="utf-8")
    _commit(repo, "base")

    bundle = tmp_path / "bundle"
    _write_complete_bundle(bundle, {
        "id": "001", "base_sha": "0" * 40, "files_touched": ["hello.txt"],
        "tests_run": [], "finding_ids": ["F-1"], "openspec_task": "",
        "verified_at": None,
    })

    verify_clone = tmp_path / "verify"
    _fresh_clone_at(repo, verify_clone, _git(["rev-parse", "HEAD"], repo).stdout.strip())

    result = handoff.cmd_verify(argparse.Namespace(
        bundle_dir=str(bundle), clone=str(verify_clone),
    ))
    assert result.startswith("Error")
    assert "ancestor" in result

# ---------------------------------------------------------------------------
# apply: a verified bundle goes onto a feature branch, in order, tested, committed
# ---------------------------------------------------------------------------

import sys as _sys


def _diff_for(repo, changes):
    """Unified diff of `changes` ({relpath: text}) against HEAD; repo is restored."""
    for rel, text in changes.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    _git(["add", "-N", "."], repo)
    diff = _git(["diff"], repo).stdout
    _git(["reset", "-q", "--hard", "HEAD"], repo)
    _git(["clean", "-fdq"], repo)
    return diff


def _bundle(root, name, patch, tests=(), verified=True):
    d = root / "handoffs" / "proj" / name
    d.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": name.split("-")[0], "base_sha": "0" * 40, "files_touched": [],
        "tests_run": list(tests), "finding_ids": [], "openspec_task": "t",
        "verified_at": "2026-10-16T00:00:00+00:00" if verified else None,
    }
    (d / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    (d / "change.patch").write_text(patch, encoding="utf-8", newline="\n")
    (d / "rationale.md").write_text("r", encoding="utf-8")
    (d / "verify.md").write_text("v", encoding="utf-8")
    return d


def _apply(bundle, repo, **kw):
    return handoff.cmd_apply(argparse.Namespace(
        bundle_dir=str(bundle), repo=str(repo), skip_tests=kw.get("skip_tests", False)))


def _work_repo(tmp_path):
    repo = tmp_path / "work"
    _init_repo(repo)
    (repo / "a.txt").write_text("one\n", encoding="utf-8", newline="\n")
    (repo / "b.txt").write_text("base\n", encoding="utf-8", newline="\n")
    _commit(repo, "base")
    return repo


def test_apply_refuses_protected_branch(tmp_path):
    repo = _work_repo(tmp_path)
    b = _bundle(tmp_path, "001-first", _diff_for(repo, {"a.txt": "two\n"}))
    out = _apply(b, repo)
    assert out.startswith("Error:") and "feature branch" in out
    assert (repo / "a.txt").read_text() == "one\n"


def test_apply_commits_on_feature_branch(tmp_path):
    repo = _work_repo(tmp_path)
    b = _bundle(tmp_path, "001-first", _diff_for(repo, {"a.txt": "two\n", "new.txt": "n\n"}))
    _git(["switch", "-c", "feat/x"], repo)
    out = _apply(b, repo)
    assert out.startswith("OK:"), out
    assert (repo / "a.txt").read_text() == "two\n" and (repo / "new.txt").exists()
    subject = _git(["log", "-1", "--format=%s"], repo).stdout.strip()
    assert subject == "bundle 001: first"
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip() == "feat/x"
    assert _git(["status", "--porcelain"], repo).stdout.strip() == ""


def test_apply_is_idempotent(tmp_path):
    repo = _work_repo(tmp_path)
    b = _bundle(tmp_path, "001-first", _diff_for(repo, {"a.txt": "two\n"}))
    _git(["switch", "-c", "feat/x"], repo)
    assert _apply(b, repo).startswith("OK: bundle 001 applied")
    again = _apply(b, repo)
    assert again.startswith("OK:") and "already applied" in again
    assert _git(["rev-list", "--count", "HEAD"], repo).stdout.strip() == "2"


def test_apply_refuses_dirty_tree(tmp_path):
    repo = _work_repo(tmp_path)
    b = _bundle(tmp_path, "001-first", _diff_for(repo, {"a.txt": "two\n"}))
    _git(["switch", "-c", "feat/x"], repo)
    (repo / "b.txt").write_text("edited\n", encoding="utf-8", newline="\n")
    out = _apply(b, repo)
    assert out.startswith("Error:") and "uncommitted" in out
    assert (repo / "a.txt").read_text() == "one\n"


def test_apply_refuses_unverified_bundle(tmp_path):
    repo = _work_repo(tmp_path)
    b = _bundle(tmp_path, "001-first", _diff_for(repo, {"a.txt": "two\n"}), verified=False)
    _git(["switch", "-c", "feat/x"], repo)
    out = _apply(b, repo)
    assert out.startswith("Error:") and "verified" in out


def test_apply_enforces_order(tmp_path):
    repo = _work_repo(tmp_path)
    p1 = _diff_for(repo, {"a.txt": "two\n"})
    b1 = _bundle(tmp_path, "001-first", p1)
    _git(["apply", "--whitespace=nowarn", str(b1 / "change.patch")], repo)
    p2 = _diff_for(repo, {"b.txt": "second\n"})            # diff vs the repo with 001 applied
    _git(["reset", "-q", "--hard", "HEAD"], repo)
    b2 = _bundle(tmp_path, "002-second", p2)
    _git(["switch", "-c", "feat/x"], repo)
    out = _apply(b2, repo)
    assert out.startswith("Error:") and "001-first" in out and "apply it first" in out
    assert (repo / "b.txt").read_text() == "base\n"
    assert _apply(b1, repo).startswith("OK:")
    assert _apply(b2, repo).startswith("OK:")
    assert (repo / "b.txt").read_text() == "second\n"


def test_apply_failing_test_rolls_back(tmp_path):
    repo = _work_repo(tmp_path)
    patch = _diff_for(repo, {"a.txt": "two\n", "tests/test_it.py": "def test_it():\n    assert False\n"})
    b = _bundle(tmp_path, "001-first", patch, tests=["tests/test_it.py"])
    _git(["switch", "-c", "feat/x"], repo)
    before = _git(["rev-parse", "HEAD"], repo).stdout.strip()
    out = _apply(b, repo)
    assert out.startswith("FAIL:") and "restored" in out
    assert _git(["rev-parse", "HEAD"], repo).stdout.strip() == before
    assert (repo / "a.txt").read_text() == "one\n"
    assert not (repo / "tests" / "test_it.py").exists()


def test_apply_passing_test_is_recorded_in_commit(tmp_path):
    repo = _work_repo(tmp_path)
    patch = _diff_for(repo, {"a.txt": "two\n", "tests/test_it.py": "def test_it():\n    assert True\n"})
    b = _bundle(tmp_path, "001-first", patch, tests=["tests/test_it.py"])
    _git(["switch", "-c", "feat/x"], repo)
    out = _apply(b, repo)
    assert out.startswith("OK:") and "tests/test_it.py: PASS" in out
    body = _git(["log", "-1", "--format=%B"], repo).stdout
    assert "tests/test_it.py: PASS" in body


def test_apply_conflict_rolls_back(tmp_path):
    repo = _work_repo(tmp_path)
    b = _bundle(tmp_path, "001-first", _diff_for(repo, {"a.txt": "two\n"}))
    _git(["switch", "-c", "feat/x"], repo)
    (repo / "a.txt").write_text("something else\n", encoding="utf-8", newline="\n")
    _commit(repo, "diverge")
    out = _apply(b, repo)
    assert out.startswith("FAIL:") and "restored" in out
    assert (repo / "a.txt").read_text() == "something else\n"
    assert _git(["status", "--porcelain"], repo).stdout.strip() == ""


def test_lf_patch_converts_a_crlf_checkout(tmp_path):
    p = tmp_path / "change.patch"
    p.write_bytes(b"diff --git a/x b/x\r\n--- a/x\r\n+++ b/x\r\n@@ -1 +1 @@\r\n-a\r\n+b\r\n")
    out = handoff.lf_patch(p)
    assert out != p
    assert b"\r" not in out.read_bytes()
    out.unlink()


def test_lf_patch_leaves_a_real_crlf_content_patch_alone(tmp_path):
    p = tmp_path / "change.patch"
    # LF headers, CRLF content lines: a genuine patch of a CRLF file
    p.write_bytes(b"diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\r\n+b\r\n")
    assert handoff.lf_patch(p) == p


def test_apply_works_when_the_patch_was_checked_out_with_crlf(tmp_path):
    repo = _work_repo(tmp_path)
    patch = _diff_for(repo, {"a.txt": "two\n"})
    crlf = patch.replace("\n", "\r\n")
    b = _bundle(tmp_path, "001-first", "")
    (b / "change.patch").write_bytes(crlf.encode("utf-8"))
    _git(["switch", "-c", "feat/x"], repo)
    out = _apply(b, repo)
    assert out.startswith("OK:"), out
    assert (repo / "a.txt").read_text() == "two\n"


def test_order_uses_the_commit_record_when_later_bundles_edit_the_same_lines(tmp_path):
    repo = _work_repo(tmp_path)
    b1 = _bundle(tmp_path, "001-first", _diff_for(repo, {"a.txt": "two\n"}))
    _git(["apply", "--whitespace=nowarn", str(b1 / "change.patch")], repo)
    _git(["commit", "-qam", "tmp"], repo)
    p2 = _diff_for(repo, {"a.txt": "three\n"})            # 002 edits the line 001 edited
    _git(["reset", "-q", "--hard", "HEAD~1"], repo)
    b2 = _bundle(tmp_path, "002-second", p2)
    b3 = _bundle(tmp_path, "003-third", _diff_for(repo, {"b.txt": "third\n"}))
    _git(["switch", "-c", "feat/x"], repo)
    assert _apply(b1, repo).startswith("OK:")
    assert _apply(b2, repo).startswith("OK:")
    # 001's patch no longer reverses (002 changed the same line) but its commit is there
    assert not handoff._patch_applied(repo, b1 / "change.patch")
    assert handoff._patch_applied(repo, b1 / "change.patch", "001")
    assert _apply(b3, repo).startswith("OK:")
    assert (repo / "a.txt").read_text() == "three\n"
    assert (repo / "b.txt").read_text() == "third\n"


def test_apply_refuses_a_patch_that_leaves_python_unparseable(tmp_path):
    repo = _work_repo(tmp_path)
    (repo / "m.py").write_text("X = {'a': 1}\n", encoding="utf-8", newline="\n")
    _commit(repo, "add module")
    patch = _diff_for(repo, {"m.py": "X = {X = {'a': 1},: 2}\n"})   # the bundle-004 shape
    b = _bundle(tmp_path, "001-first", patch)
    _git(["switch", "-c", "feat/x"], repo)
    before = _git(["rev-parse", "HEAD"], repo).stdout.strip()
    out = _apply(b, repo)
    assert out.startswith("FAIL:") and "do not parse" in out and "m.py" in out
    assert (repo / "m.py").read_text() == "X = {'a': 1}\n"
    assert _git(["rev-parse", "HEAD"], repo).stdout.strip() == before


def test_syntax_problems_reports_file_and_line(tmp_path):
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("x = 1\ny = (\n", encoding="utf-8")
    (tmp_path / "note.txt").write_text("(((", encoding="utf-8")
    probs = handoff._syntax_problems(tmp_path, ["ok.py", "bad.py", "note.txt", "gone.py"])
    assert len(probs) == 1 and probs[0].startswith("bad.py:")
