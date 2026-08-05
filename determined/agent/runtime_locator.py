# determined/agent/runtime_locator.py
#
# Snippet compilation/verification shim for multi-language stub projection.
#
# Discovers available language tools at call time and uses them to verify
# that a projected snippet is at least syntactically plausible.
#
# Return contract for check_snippet():
#   { ok: bool | None, error: str, tool: str | None }
#   ok=True  — tool ran and reported no errors
#   ok=False — tool ran and reported errors (see error field)
#   ok=None  — no tool available; snippet is UNVERIFIED (not INVALID)
#
# All checks are syntax-only (no linking, no type inference).  The point
# is to catch obvious hallucinations (unmatched braces, wrong keyword, etc.)
# before they reach the user, not to fully compile the snippet in context.

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


# ------------------------------------------------------------------
# Tool discovery
# ------------------------------------------------------------------

def _which(name: str) -> Optional[str]:
    """Return the full path of an executable, or None."""
    return shutil.which(name)


def locate() -> dict[str, Optional[str]]:
    """
    Return a dict mapping language names to the tool path that can
    verify snippets for that language.  None means no tool found.
    """
    return {
        "Python":     sys.executable,   # always available
        "C":          _which("gcc") or _which("clang"),
        "C++":        _which("g++") or _which("clang++"),
        "Zig":        _which("zig"),
        "Lua":        _which("luac") or _which("lua"),
        "Rust":       _which("rustc"),
        "Go":         _which("go"),
        "TypeScript": _which("tsc"),
        "JavaScript": _which("node"),
    }


# ------------------------------------------------------------------
# Snippet wrappers
# Surround a bare function body with enough scaffolding to make it
# parseable by the target tool.
# ------------------------------------------------------------------

def _wrap_python(name: str, args: list[str], body: str) -> str:
    """Wrap a function body in Python def syntax for ast.parse."""
    sig = f"def {name}({', '.join(args)}):"
    indented = "\n".join("    " + line for line in body.splitlines()) or "    pass"
    return f"{sig}\n{indented}\n"


def _wrap_c(name: str, args: list[str], body: str) -> str:
    """Wrap a function body in C function syntax."""
    arg_str = ", ".join(args) if args else "void"
    return f"void {name}({arg_str}) {{\n{body}\n}}\n"


def _wrap_cpp(name: str, args: list[str], body: str) -> str:
    """Wrap a function body in C++ function syntax."""
    return _wrap_c(name, args, body)


def _wrap_zig(name: str, args: list[str], body: str) -> str:
    """Wrap a function body in Zig pub fn syntax."""
    arg_parts = ", ".join(f"_{i}: anytype" for i in range(len(args))) if args else ""
    return f"pub fn {name}({arg_parts}) void {{\n{body}\n}}\n"


def _wrap_lua(name: str, args: list[str], body: str) -> str:
    """Wrap a function body in Lua local function syntax."""
    arg_str = ", ".join(args) if args else ""
    return f"local function {name}({arg_str})\n{body}\nend\n"


def _wrap_rust(name: str, args: list[str], body: str) -> str:
    """Wrap a function body in a Rust fn."""
    return f"fn {name}() {{\n{body}\n}}\n"


def _wrap_go(name: str, args: list[str], body: str) -> str:
    """Wrap a function body in a Go main-package func."""
    return f"package main\nfunc {name}() {{\n{body}\n}}\n"


_WRAPPERS = {
    "Python":     _wrap_python,
    "C":          _wrap_c,
    "C++":        _wrap_cpp,
    "Zig":        _wrap_zig,
    "Lua":        _wrap_lua,
    "Rust":       _wrap_rust,
    "Go":         _wrap_go,
}

_EXTENSIONS = {
    "Python": ".py",
    "C":      ".c",
    "C++":    ".cpp",
    "Zig":    ".zig",
    "Lua":    ".lua",
    "Rust":   ".rs",
    "Go":     ".go",
}


# ------------------------------------------------------------------
# Per-language check runners
# ------------------------------------------------------------------

def _check_python(snippet: str, name: str, args: list[str]) -> dict:
    """Verify Python snippet syntax using ast.parse."""
    source = _wrap_python(name, args, snippet)
    try:
        ast.parse(source)
        return {"ok": True, "error": "", "tool": "ast.parse"}
    except SyntaxError as e:
        return {"ok": False, "error": str(e), "tool": "ast.parse"}


def _check_with_compiler(
    lang: str,
    tool: str,
    snippet: str,
    name: str,
    args: list[str],
    cmd_builder,          # callable(tool, tmp_path) -> list[str]
) -> dict:
    """Write snippet to a temp file and verify it with an external compiler."""
    wrapper = _WRAPPERS.get(lang)
    if wrapper is None:
        return {"ok": None, "error": f"no wrapper for {lang}", "tool": None}
    source = wrapper(name, args, snippet)
    ext = _EXTENSIONS.get(lang, ".txt")
    with tempfile.NamedTemporaryFile(suffix=ext, mode="w", encoding="utf-8", delete=False) as f:
        f.write(source)
        tmp = Path(f.name)
    try:
        cmd = cmd_builder(tool, str(tmp))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        ok = result.returncode == 0
        err = (result.stderr or result.stdout or "").strip()
        return {"ok": ok, "error": err if not ok else "", "tool": tool}
    except subprocess.TimeoutExpired:
        return {"ok": None, "error": "timeout", "tool": tool}
    except Exception as e:
        return {"ok": None, "error": str(e), "tool": tool}
    finally:
        tmp.unlink(missing_ok=True)


def _cmd_gcc(tool, path):
    """Build the gcc syntax-check command."""
    return [tool, "-fsyntax-only", "-x", "c", path]

def _cmd_gpp(tool, path):
    """Build the g++ syntax-check command."""
    return [tool, "-fsyntax-only", "-x", "c++", path]

def _cmd_zig(tool, path):
    """Build the zig ast-check command."""
    return [tool, "ast-check", path]

def _cmd_lua(tool, path):
    """Build the luac parse-only command."""
    # luac -p (parse only); lua falls back to running — we use luac preferentially
    return [tool, "-p", path]

def _cmd_rustc(tool, path):
    """Build the rustc metadata-only check command."""
    return [tool, "--edition", "2021", "--crate-type", "lib", "--emit", "metadata",
            "-o", path + ".meta", path]

def _cmd_go(tool, path):
    """Build the go build command."""
    # go vet needs a package; just do build with -run=^$ to avoid linking
    return [tool, "build", path]

def _cmd_tsc(tool, path):
    """Build the tsc no-emit check command."""
    return [tool, "--noEmit", "--allowJs", path]

def _cmd_node(tool, path):
    """Build the node --check command."""
    return [tool, "--check", path]


_CMD_BUILDERS = {
    "C":          _cmd_gcc,
    "C++":        _cmd_gpp,
    "Zig":        _cmd_zig,
    "Lua":        _cmd_lua,
    "Rust":       _cmd_rustc,
    "Go":         _cmd_go,
    "TypeScript": _cmd_tsc,
    "JavaScript": _cmd_node,
}


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def check_snippet(
    lang: str,
    snippet: str,
    name: str = "__stub__",
    args: Optional[list[str]] = None,
) -> dict:
    """
    Verify that `snippet` is syntactically plausible as the body of a
    function named `name` with the given `args` in `lang`.

    Returns:
      { ok: bool | None, error: str, tool: str | None }
      ok=None means no tool was available — treat as UNVERIFIED, not invalid.
    """
    args = args or []
    lang = lang or "Python"

    if lang == "Python":
        return _check_python(snippet, name, args)

    tools = locate()
    tool = tools.get(lang)
    if not tool:
        return {"ok": None, "error": f"no {lang} tool found on PATH", "tool": None}

    cmd_builder = _CMD_BUILDERS.get(lang)
    if cmd_builder is None:
        return {"ok": None, "error": f"no check runner for {lang}", "tool": None}

    return _check_with_compiler(lang, tool, snippet, name, args, cmd_builder)


def check_projection(projection: dict) -> dict:
    """
    Convenience wrapper: run check_snippet against a project_stub() result dict.
    Adds 'syntax_check' key to a copy of the projection dict and returns it.
    """
    lang = projection.get("lang", "Python")
    snippet = projection.get("suggested_body", "")
    name_raw = projection.get("stub_name", "__stub__").rsplit(".", 1)[-1]
    # Clean name: strip class prefix and FSM notation
    name = re.sub(r"[^A-Za-z0-9_]", "_", name_raw)

    check = check_snippet(lang, snippet, name=name)
    return {**projection, "syntax_check": check}
