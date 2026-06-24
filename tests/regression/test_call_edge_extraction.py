# tests/regression/test_call_edge_extraction.py
#
# Regression tests for call-edge extraction in parse_ast._extract_symbol_references.
# Guards two bugs found while auditing dead-code false positives:
#   1. Chained attribute calls (self.x.method()) had their dotted name scrambled
#      with the method name yanked to the front (generate.self.x instead of
#      self.x.generate).
#   2. Plain obj.method() calls where obj is a local/param/self were dropped
#      entirely, so methods only ever called as instance.method() looked dead.

import ast
from determined.ingestion.parse_ast import _extract_symbol_references


def _callees(src: str) -> list[str]:
    tree = ast.parse(src)
    refs = _extract_symbol_references(
        tree, known_symbols=set(), alias_map={}, module_name="testmod"
    )
    return [r.callee for r in refs]


def test_chained_attribute_call_not_scrambled():
    # self.ai_system.generate_structured_data() must keep source order
    src = (
        "def handler(self):\n"
        "    self.ai_system.generate_structured_data()\n"
    )
    callees = _callees(src)
    # the method name must be the LAST segment, not the first
    assert any(c.endswith(".generate_structured_data") for c in callees), callees
    # the scrambled form must NOT appear
    assert not any(c.startswith("generate_structured_data.") for c in callees), callees


def test_instance_method_call_recorded():
    # character.is_alive() must produce an edge (was dropped before)
    src = (
        "def handler(character):\n"
        "    character.is_alive()\n"
    )
    callees = _callees(src)
    assert any(c.endswith(".is_alive") for c in callees), callees


def test_self_method_call_recorded():
    src = (
        "def handler(self):\n"
        "    self.advance_time()\n"
    )
    callees = _callees(src)
    assert any(c.endswith(".advance_time") for c in callees), callees


def test_subscript_receiver_method_call_recorded():
    # grid[x].is_door() - receiver is a subscript, was dropped before
    src = (
        "def handler(grid, x):\n"
        "    grid[x].is_door()\n"
    )
    callees = _callees(src)
    assert any(c.rsplit(".", 1)[-1] == "is_door" for c in callees), callees


def test_call_result_receiver_method_call_recorded():
    # get_cell().is_door() - receiver is a call result
    src = (
        "def handler(self):\n"
        "    self.get_cell().is_door()\n"
    )
    callees = _callees(src)
    last = [c.rsplit(".", 1)[-1] for c in callees]
    assert "is_door" in last, callees


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t(); print(f"  PASS  {t.__name__}"); passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}"); failed += 1
    print(f"\n{passed} passed, {failed} failed")
