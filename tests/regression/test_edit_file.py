# tests/regression/test_edit_file.py
#
# Regression tests for the edit_file agent tool (RM11).
# Uses a real temp directory so path-validation logic is exercised.

import os
import pathlib
import tempfile

from determined.agent.agent_tools import edit_file

os.environ.setdefault("PYTHONPATH", ".")


class _FakeOracle:
    def __init__(self, root):
        self._root = root

    def get_project_root(self):
        return str(self._root)


class _FakeAssessor:
    def __init__(self, root):
        self.oracle = _FakeOracle(root)


def _setup():
    """Return (assessor, root_path) with a temp project root."""
    tmp = tempfile.mkdtemp()
    return _FakeAssessor(tmp), pathlib.Path(tmp)


# --- read_file ---

def test_read_file_absolute():
    assessor, root = _setup()
    fp = root / "hello.py"
    fp.write_text("print('hi')", encoding="utf-8")
    result = edit_file(assessor, {"op": "read_file", "file_path": str(fp)})
    assert result == "print('hi')"


def test_read_file_relative():
    assessor, root = _setup()
    fp = root / "rel.py"
    fp.write_text("x = 1", encoding="utf-8")
    result = edit_file(assessor, {"op": "read_file", "file_path": "rel.py"})
    assert result == "x = 1"


def test_read_file_missing():
    assessor, root = _setup()
    result = edit_file(assessor, {"op": "read_file", "file_path": "nope.py"})
    assert result.startswith("ERROR")


# --- write_file ---

def test_write_file_creates():
    assessor, root = _setup()
    result = edit_file(assessor, {
        "op": "write_file",
        "file_path": "new.py",
        "content": "# written by agent\n",
    })
    assert "wrote" in result
    assert (root / "new.py").read_text(encoding="utf-8") == "# written by agent\n"


def test_write_file_overwrites():
    assessor, root = _setup()
    fp = root / "over.py"
    fp.write_text("old content", encoding="utf-8")
    edit_file(assessor, {"op": "write_file", "file_path": "over.py", "content": "new content"})
    assert fp.read_text(encoding="utf-8") == "new content"


def test_write_file_no_content():
    assessor, root = _setup()
    result = edit_file(assessor, {"op": "write_file", "file_path": "x.py"})
    assert result.startswith("ERROR")


# --- replace_in_file ---

def test_replace_in_file():
    assessor, root = _setup()
    fp = root / "patch.py"
    fp.write_text("def old_name(): pass\n", encoding="utf-8")
    result = edit_file(assessor, {
        "op": "replace_in_file",
        "file_path": "patch.py",
        "old": "old_name",
        "new": "new_name",
    })
    assert "replaced" in result
    assert "new_name" in fp.read_text(encoding="utf-8")


def test_replace_in_file_not_found():
    assessor, root = _setup()
    fp = root / "nomatch.py"
    fp.write_text("something else", encoding="utf-8")
    result = edit_file(assessor, {
        "op": "replace_in_file",
        "file_path": "nomatch.py",
        "old": "DOES_NOT_EXIST",
        "new": "x",
    })
    assert result.startswith("ERROR")


def test_replace_only_first_occurrence():
    assessor, root = _setup()
    fp = root / "multi.py"
    fp.write_text("a a a", encoding="utf-8")
    edit_file(assessor, {
        "op": "replace_in_file",
        "file_path": "multi.py",
        "old": "a",
        "new": "b",
    })
    assert fp.read_text(encoding="utf-8") == "b a a"


# --- path guard ---

def test_path_outside_root_blocked():
    assessor, root = _setup()
    outside = str(pathlib.Path(root).parent / "escape.py")
    result = edit_file(assessor, {"op": "read_file", "file_path": outside})
    assert result.startswith("ERROR")


# --- bad op ---

def test_unknown_op():
    assessor, root = _setup()
    result = edit_file(assessor, {"op": "delete_file", "file_path": "x.py"})
    assert result.startswith("ERROR")


def test_missing_op():
    assessor, root = _setup()
    result = edit_file(assessor, {"file_path": "x.py"})
    assert result.startswith("ERROR")
