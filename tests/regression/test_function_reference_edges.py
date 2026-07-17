"""
Regression tests for function_reference edge extraction (parse_ast.py).

Covers the three patterns:
  1. Dict literal values: {'key': module.fn}
  2. 2-arg register calls: obj.register('name', fn)
  3. Callback kwargs: Thread(target=fn), sorted(key=fn)
"""
import ast
import pytest
from determined.ingestion.parse_ast import _extract_function_references


def _refs(source: str):
    tree = ast.parse(source)
    return _extract_function_references(tree)


def _edges(source: str):
    return {(r.caller, r.callee) for r in _refs(source)}


def _edge_types(source: str):
    return {r.edge_type for r in _refs(source)}


# ---------------------------------------------------------------------------
# Pattern 1: dict literal values (ast.Attribute only)
# ---------------------------------------------------------------------------

def test_dict_attribute_value_emits_edge():
    src = """
import builtins
guard_registry = {'price_too_low': builtins.price_lt}
"""
    edges = _edges(src)
    assert ("<module>", "builtins.price_lt") in edges


def test_dict_bare_name_not_emitted():
    # Bare ast.Name dict values are intentionally excluded to avoid false positives
    src = "registry = {'mode': my_handler}"
    edges = _edges(src)
    assert not edges


def test_dict_self_attribute_not_emitted():
    # self.* in dict values are instance attribute reads, not function references
    src = """
class Foo:
    def setup(self):
        opts = {'default': self.DEFAULT_OPTIONS, 'color': self.COLORS}
"""
    assert not _refs(src)


def test_dict_deep_chain_not_emitted():
    # Deep chains like self.phase.value are data accesses, not fn refs
    src = "d = {'x': self.current_phase.value, 'y': obj.attr.method}"
    assert not _refs(src)


def test_callback_kwarg_deep_chain_not_emitted():
    # event.data.target_id as callback value is a data read, not a fn ref
    src = "foo(callback=event.data.target_id)"
    assert not _refs(src)


def test_callback_kwarg_self_not_emitted():
    src = "foo(target=self.handler)"
    assert not _refs(src)


def test_dict_string_value_not_emitted():
    src = "d = {'key': 'some_string'}"
    assert not _refs(src)


def test_dict_inside_function_uses_fn_as_caller():
    src = """
def setup():
    registry = {'check': guards.price_lt}
"""
    edges = _edges(src)
    assert ("setup", "guards.price_lt") in edges


def test_multiple_dict_attribute_values():
    src = """
registry = {
    'a': mod.fn_a,
    'b': mod.fn_b,
    'label': 'not a fn',
}
"""
    edges = _edges(src)
    assert ("<module>", "mod.fn_a") in edges
    assert ("<module>", "mod.fn_b") in edges
    assert len(edges) == 2


# ---------------------------------------------------------------------------
# Pattern 2: 2-arg register calls
# ---------------------------------------------------------------------------

def test_register_action_bare_name():
    src = """
def setup():
    register_action('shoot', do_shoot)
"""
    edges = _edges(src)
    assert ("setup", "do_shoot") in edges


def test_register_action_dotted():
    src = """
def setup():
    actions.register('move', handlers.move_player)
"""
    edges = _edges(src)
    assert ("setup", "handlers.move_player") in edges


def test_register_not_two_args_not_emitted():
    # 1-arg and 3-arg register calls are not the pattern
    src = """
register('only_one')
register('a', fn, extra)
"""
    assert not _refs(src)


def test_register_handler_attr():
    src = "obj.register_handler('event', my_fn)"
    edges = _edges(src)
    assert ("<module>", "my_fn") in edges


# ---------------------------------------------------------------------------
# Pattern 3: callback kwargs
# ---------------------------------------------------------------------------

def test_thread_target_kwarg():
    src = """
import threading
def start_worker():
    t = threading.Thread(target=worker_fn)
"""
    edges = _edges(src)
    assert ("start_worker", "worker_fn") in edges


def test_sorted_key_kwarg():
    src = "result = sorted(items, key=get_priority)"
    edges = _edges(src)
    assert ("<module>", "get_priority") in edges


def test_callback_kwarg_dotted():
    src = "timer.on_tick(callback=handlers.tick)"
    edges = _edges(src)
    assert ("<module>", "handlers.tick") in edges


def test_unknown_kwarg_not_emitted():
    src = "foo(bar=some_val)"
    assert not _refs(src)


# ---------------------------------------------------------------------------
# Edge type
# ---------------------------------------------------------------------------

def test_edge_type_is_function_reference():
    src = "{'x': mod.fn}"
    types = _edge_types(src)
    assert types == {"function_reference"}


# ---------------------------------------------------------------------------
# Builtins excluded
# ---------------------------------------------------------------------------

def test_builtin_name_not_emitted():
    # 'len' is a builtin; should not emit a function_reference edge
    src = "Thread(target=len)"
    edges = _edges(src)
    assert ("<module>", "len") not in edges


# ---------------------------------------------------------------------------
# No false positives on normal call expressions
# ---------------------------------------------------------------------------

def test_normal_call_not_duplicated():
    # A normal function call should not produce a function_reference edge;
    # that's handled by _extract_symbol_references as a static edge.
    src = "do_thing()"
    assert not _refs(src)
