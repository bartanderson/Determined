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


def test_verify_rejects_wrong_base_sha(tmp_path):
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

    # Fresh clone but reset to a DIFFERENT commit (fabricate one)
    (repo / "other.txt").write_text("x\n", encoding="utf-8")
    other = _commit(repo, "other")
    verify_clone = tmp_path / "verify"
    _fresh_clone_at(repo, verify_clone, other)

    result = handoff.cmd_verify(argparse.Namespace(
        bundle_dir=str(bundle), clone=str(verify_clone),
    ))
    assert result.startswith("Error")
    assert "base_sha" in result