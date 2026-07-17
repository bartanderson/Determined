# tests/regression/test_stub_detection.py
#
# Guards stub detection in parse_ast._is_stub and docstring-based override.
# Covers patterns found in Commonplace: trivial returns ([], {}, "", 0, 0.0, False)
# and "STUB:" docstring prefix.

import ast
from determined.ingestion.parse_ast import _is_stub, _extract_functions, _is_protocol_class


def _parse_fn(src: str):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    raise ValueError("no function found")


# --- classic stubs (pre-existing) ---

def test_stub_pass():
    assert _is_stub(_parse_fn("def f(): pass"))


def test_stub_ellipsis():
    assert _is_stub(_parse_fn("def f(): ..."))


def test_stub_raise_not_implemented():
    assert _is_stub(_parse_fn("def f(): raise NotImplementedError"))


def test_stub_return_none():
    assert _is_stub(_parse_fn("def f(): return None"))


def test_stub_empty_body_with_docstring():
    src = 'def f():\n    """doc"""\n    pass\n'
    assert _is_stub(_parse_fn(src))


# --- new trivial-return patterns ---

def test_stub_return_empty_list():
    assert _is_stub(_parse_fn("def f(): return []"))


def test_stub_return_empty_dict():
    assert _is_stub(_parse_fn("def f(): return {}"))


def test_stub_return_empty_string():
    assert _is_stub(_parse_fn("def f(): return ''"))


def test_stub_return_zero():
    assert _is_stub(_parse_fn("def f(): return 0"))


def test_stub_return_zero_float():
    assert _is_stub(_parse_fn("def f(): return 0.0"))


def test_stub_return_false():
    assert _is_stub(_parse_fn("def f(): return False"))


# --- NOT stubs ---

def test_not_stub_real_body():
    src = "def f(x):\n    return x + 1\n"
    assert not _is_stub(_parse_fn(src))


def test_not_stub_return_nonempty_list():
    src = "def f():\n    return [1, 2]\n"
    assert not _is_stub(_parse_fn(src))


def test_not_stub_return_true():
    src = "def f():\n    return True\n"
    assert not _is_stub(_parse_fn(src))


# --- docstring "STUB:" prefix via _extract_functions ---

def test_docstring_stub_marker_detected():
    src = (
        "def suggest_tags(content, endpoint=None):\n"
        "    '''\n"
        "    STUB: Ask LLM to suggest tags for the given content.\n"
        "    Returns list of tag strings.\n"
        "    '''\n"
        "    return []\n"
    )
    fns = _extract_functions(ast.parse(src))
    assert fns, "no functions extracted"
    assert fns[0].is_stub


def test_docstring_stub_case_insensitive_yes():
    # "stub:" in any case at the start of the docstring should trigger stub detection.
    src = (
        "def f():\n"
        "    '''stub: something'''\n"
        "    return 42\n"
    )
    fns = _extract_functions(ast.parse(src))
    assert fns, "no functions extracted"
    assert fns[0].is_stub


# --- Protocol method suppression (new) ---

def test_protocol_method_ellipsis_not_stub():
    src = (
        "from typing import Protocol\n"
        "class MyProto(Protocol):\n"
        "    def resolve(self, symbol: str) -> str:\n"
        "        ...\n"
    )
    fns = _extract_functions(ast.parse(src))
    assert fns, "no functions extracted"
    fn = next(f for f in fns if f.name == "resolve")
    assert not fn.is_stub, "Protocol method should not be flagged as stub"


def test_protocol_method_pass_not_stub():
    src = (
        "from typing import Protocol\n"
        "class MyProto(Protocol):\n"
        "    def do_thing(self) -> None:\n"
        "        pass\n"
    )
    fns = _extract_functions(ast.parse(src))
    fn = next(f for f in fns if f.name == "do_thing")
    assert not fn.is_stub


def test_non_protocol_class_ellipsis_is_stub():
    src = (
        "class Plain:\n"
        "    def resolve(self) -> str:\n"
        "        ...\n"
    )
    fns = _extract_functions(ast.parse(src))
    fn = next(f for f in fns if f.name == "resolve")
    assert fn.is_stub, "Non-Protocol ... body should still be a stub"


def test_is_protocol_class_detects_protocol_base():
    src = (
        "from typing import Protocol\n"
        "class MyProto(Protocol):\n"
        "    pass\n"
    )
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
    assert _is_protocol_class(cls)


def test_is_protocol_class_false_for_plain():
    src = "class Plain:\n    pass\n"
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
    assert not _is_protocol_class(cls)
