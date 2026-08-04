"""
Tests for runtime_locator.py — syntax-check shim for multi-language stub projection.
"""
import pytest
from determined.agent.runtime_locator import check_snippet, check_projection, locate


# ── locate() ──────────────────────────────────────────────────────────────────

def test_locate_returns_python():
    tools = locate()
    assert "Python" in tools
    assert tools["Python"] is not None  # sys.executable is always present


def test_locate_returns_all_keys():
    tools = locate()
    for lang in ("Python", "C", "C++", "Zig", "Lua", "Rust", "Go"):
        assert lang in tools  # may be None if not installed


# ── Python checks (always available via ast.parse) ────────────────────────────

def test_python_valid_body():
    result = check_snippet("Python", "    return 42", name="f", args=["x"])
    assert result["ok"] is True
    assert result["tool"] == "ast.parse"
    assert result["error"] == ""


def test_python_valid_multiline():
    body = "    result = x + 1\n    return result"
    result = check_snippet("Python", body, name="add_one", args=["x"])
    assert result["ok"] is True


def test_python_invalid_syntax():
    result = check_snippet("Python", "    return (", name="broken", args=[])
    assert result["ok"] is False
    assert result["tool"] == "ast.parse"
    assert result["error"] != ""


def test_python_empty_body_treated_as_pass():
    result = check_snippet("Python", "", name="noop", args=[])
    # empty body → wraps to "    pass" → valid
    assert result["ok"] is True


def test_python_just_pass():
    result = check_snippet("Python", "    pass", name="noop", args=[])
    assert result["ok"] is True


def test_python_raise_not_implemented():
    body = "    raise NotImplementedError('not implemented')"
    result = check_snippet("Python", body, name="stub", args=["self"])
    assert result["ok"] is True


# ── Non-Python without tool (ok=None) ────────────────────────────────────────

def _no_tool_for(lang: str) -> bool:
    return locate().get(lang) is None


@pytest.mark.skipif(not _no_tool_for("C"), reason="gcc/clang available; test only covers missing-tool path")
def test_c_no_tool_returns_unverified():
    result = check_snippet("C", "    return 0;", name="f", args=["int x"])
    assert result["ok"] is None
    assert "no C tool" in result["error"].lower() or "no" in result["error"].lower()
    assert result["tool"] is None


@pytest.mark.skipif(not _no_tool_for("Zig"), reason="zig available")
def test_zig_no_tool_returns_unverified():
    result = check_snippet("Zig", "    return;", name="f", args=[])
    assert result["ok"] is None


@pytest.mark.skipif(not _no_tool_for("Lua"), reason="luac available")
def test_lua_no_tool_returns_unverified():
    result = check_snippet("Lua", "    return 1", name="f", args=[])
    assert result["ok"] is None


# ── With tool (runs only when compiler is present) ───────────────────────────

@pytest.mark.skipif(_no_tool_for("C"), reason="gcc/clang not found")
def test_c_valid_body_with_tool():
    result = check_snippet("C", "    return 0;", name="f", args=["int x"])
    assert result["ok"] is True


@pytest.mark.skipif(_no_tool_for("C"), reason="gcc/clang not found")
def test_c_invalid_body_with_tool():
    result = check_snippet("C", "    return (;", name="f", args=[])
    assert result["ok"] is False


# ── Unknown language ─────────────────────────────────────────────────────────

def test_unknown_lang_unverified():
    result = check_snippet("COBOL", "    DISPLAY 'hello'.", name="f", args=[])
    # no tool found → unverified
    assert result["ok"] is None


# ── check_projection() ───────────────────────────────────────────────────────

def test_check_projection_python_pass():
    proj = {
        "stub_name": "my_module.my_func",
        "lang": "Python",
        "suggested_body": "    return True",
        "file_path": "some/module.py",
        "line_number": 10,
        "context_summary": {},
    }
    result = check_projection(proj)
    assert "syntax_check" in result
    assert result["syntax_check"]["ok"] is True
    # original keys preserved
    assert result["stub_name"] == proj["stub_name"]
    assert result["lang"] == "Python"


def test_check_projection_python_fail():
    proj = {
        "stub_name": "bad.func",
        "lang": "Python",
        "suggested_body": "    return (",
        "file_path": "bad.py",
        "line_number": 5,
        "context_summary": {},
    }
    result = check_projection(proj)
    assert result["syntax_check"]["ok"] is False


def test_check_projection_non_python_no_tool():
    proj = {
        "stub_name": "my_crate::do_thing",
        "lang": "Zig",
        "suggested_body": "    return;",
        "file_path": "src/main.zig",
        "line_number": 42,
        "context_summary": {},
    }
    result = check_projection(proj)
    # ok=True if zig installed, None if not; never False for valid Zig
    assert result["syntax_check"]["ok"] in (True, None)


def test_check_projection_name_sanitized():
    # FSM-style stub names with :: should not crash the name sanitizer
    proj = {
        "stub_name": "EncounterFSM::action::resolve_flee",
        "lang": "Python",
        "suggested_body": "    pass",
        "file_path": "encounter.json",
        "line_number": 0,
        "context_summary": {},
    }
    result = check_projection(proj)
    # result should not raise
    assert "syntax_check" in result
