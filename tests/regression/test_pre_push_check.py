"""tools/pre_push_check.py: what a push would publish is checked, in throwaway repos."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
import pre_push_check as ppc  # noqa: E402


def _git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "README.md").write_text("base\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "base")
    return r


def _commit(repo, files: dict, msg="change"):
    for name, content in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", msg)
    return _git(repo, "rev-parse", "HEAD")


def _run(repo, base, terms=(), max_kb=1024):
    return ppc.check_range(repo, base, "main", list(terms), max_kb)


def test_clean_change_passes(repo):
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, {"a.py": "def f():\n    return 1\n", "docs/n.md": "notes\n"})
    assert _run(repo, base) == []


def test_max_tokens_is_not_a_secret(repo):
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, {"a.py": "kw = {'max_tokens': 5, 'token_count': 3}\n"})
    assert _run(repo, base) == []


# Built at runtime: this file is itself pushed and checked, so it must not contain
# secret-shaped literals.
_PRIVATE_KEY = "-----BEGIN RSA " + "PRIVATE KEY-----"
_PASSWORD_LINE = "pass" + "word = 'hunter2hunter2'"


@pytest.mark.parametrize("line", [
    "key = 'sk-" + "a" * 30 + "'",
    "AIza" + "B" * 35,
    "ghp_" + "c" * 36,
    _PRIVATE_KEY,
    _PASSWORD_LINE,
    "API" + "_KEY = 'abcdefgh12345678'",
])
def test_secret_shapes_flagged(repo, line):
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, {"conf.py": line + "\n"})
    problems = _run(repo, base)
    assert problems and "conf.py" in problems[0]


@pytest.mark.parametrize("name", ["corpus.db", "model.gguf", "backup.bak", "id.pem", "x.exe"])
def test_blocked_file_types_flagged(repo, name):
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, {name: b"\x00\x01binary"})
    assert any(name in p and "must not be published" in p for p in _run(repo, base))


def test_large_file_flagged(repo):
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, {"big.txt": "x" * (3 * 1024)})
    assert any("big.txt" in p and "exceeds" in p for p in _run(repo, base, max_kb=2))


def test_private_term_in_message_line_and_path(repo):
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, {"notes/zeppelin_plan.md": "see the Zeppelin project\n"}, msg="mentions ZEPPELIN")
    problems = _run(repo, base, terms=["zeppelin"])
    text = "\n".join(problems)
    assert "message mentions private term" in text
    assert "path mentions private term" in text
    assert "line mentions private term" in text


def test_only_outgoing_commits_are_checked(repo):
    _commit(repo, {"old.py": _PASSWORD_LINE + "\n"}, msg="already published")
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, {"new.py": "x = 1\n"})
    assert _run(repo, base) == []          # the secret is before base: not in this push


def test_load_terms_ignores_comments_and_blanks(tmp_path, monkeypatch):
    f = tmp_path / "terms.txt"
    f.write_text("# private\n\nAlpha\n  Beta  \n", encoding="utf-8")
    monkeypatch.setenv("DETERMINED_PRIVATE_TERMS", str(f))
    assert ppc.load_terms() == ["Alpha", "Beta"]


def test_load_terms_handles_powershell_bom(tmp_path, monkeypatch):
    f = tmp_path / "terms.txt"
    f.write_bytes(b"\xef\xbb\xbf# comment first line\nAlpha\n")
    monkeypatch.setenv("DETERMINED_PRIVATE_TERMS", str(f))
    assert ppc.load_terms() == ["Alpha"]


def test_new_branch_is_judged_against_remote_main_not_root(repo):
    # origin/main has the big old file; a new branch adds only a small one.
    big = _commit(repo, {"vendor/big.min.js": "y" * (4 * 1024)}, msg="already public")
    _git(repo, "update-ref", "refs/remotes/origin/main", big)
    _git(repo, "checkout", "-qb", "feature")
    _commit(repo, {"small.py": "x = 1\n"}, msg="feature work")
    code, problems = ppc.evaluate(repo, "origin", "feature", [], max_kb=2)
    assert code == 0 and problems == []
    _commit(repo, {"big2.txt": "z" * (4 * 1024)}, msg="adds a big file")
    code, problems = ppc.evaluate(repo, "origin", "feature", [], max_kb=2)
    assert code == 1 and any("big2.txt" in p for p in problems)


def test_load_terms_missing_file_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("DETERMINED_PRIVATE_TERMS", str(tmp_path / "none.txt"))
    assert ppc.load_terms() == []


def test_behind_remote_is_reported(repo):
    # Fake a remote-tracking ref that has a commit main lacks.
    _git(repo, "checkout", "-qb", "other")
    other = _commit(repo, {"o.txt": "o\n"}, msg="remote-only")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "update-ref", "refs/remotes/origin/main", other)
    code, problems = ppc.evaluate(repo, "origin", "main", [], 1024)
    assert code == 1 and any("behind origin/main" in p for p in problems)


def test_missing_branch_is_code_2(repo):
    code, problems = ppc.evaluate(repo, "origin", "nope", [], 1024)
    assert code == 2
