# tests/regression/test_agent_resolver.py
#
# Regression tests for agent_resolver.py - parse_needs and resolve_need.
# These are pure-Python tests; no DB or LLM needed.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from determined.agent.agent_resolver import parse_needs, resolve_need


# ------------------------------------------------------------------
# parse_needs
# ------------------------------------------------------------------

def test_parse_needs_basic():
    out = "NEED: files in encounter\nNEED: symbols named generate_encounter"
    needs = parse_needs(out)
    assert needs == ["files in encounter", "symbols named generate_encounter"]

def test_parse_needs_dash_prefix():
    out = "- NEED: what calls generate_encounter\n- NEED: intent of generate_encounter"
    needs = parse_needs(out)
    assert needs == ["what calls generate_encounter", "intent of generate_encounter"]

def test_parse_needs_star_prefix():
    out = "* NEED: symbols in world/encounter_generator.py"
    needs = parse_needs(out)
    assert needs == ["symbols in world/encounter_generator.py"]

def test_parse_needs_mixed_case():
    out = "need: files in world\nnEeD: findings for encounter"
    needs = parse_needs(out)
    assert needs == ["files in world", "findings for encounter"]

def test_parse_needs_ignores_non_need_lines():
    out = "Here is what I need:\nNEED: symbols named foo\nSome explanation line.\nNEED: brief for bar"
    needs = parse_needs(out)
    assert needs == ["symbols named foo", "brief for bar"]

def test_parse_needs_empty_input():
    assert parse_needs("") == []

def test_parse_needs_no_need_lines():
    assert parse_needs("Just a plain answer with no NEEDs.") == []


# ------------------------------------------------------------------
# resolve_need - files_in_directory
# ------------------------------------------------------------------

def test_resolve_files_in():
    result = resolve_need("files in encounter")
    assert result == ("files_in_directory", {"path": "encounter"})

def test_resolve_files_in_quoted():
    result = resolve_need("files in 'world/dungeon'")
    assert result == ("files_in_directory", {"path": "world/dungeon"})

def test_resolve_files_in_uppercase():
    result = resolve_need("Files In World")
    assert result == ("files_in_directory", {"path": "World"})


# ------------------------------------------------------------------
# resolve_need - search_files
# ------------------------------------------------------------------

def test_resolve_files_matching():
    result = resolve_need("files matching encounter_generator")
    assert result == ("search_files", {"query": "encounter_generator"})

def test_resolve_files_named():
    result = resolve_need("files named dungeon")
    assert result == ("search_files", {"query": "dungeon"})


# ------------------------------------------------------------------
# resolve_need - search_symbols
# ------------------------------------------------------------------

def test_resolve_symbols_named():
    result = resolve_need("symbols named generate_encounter")
    assert result == ("search_symbols", {"query": "generate_encounter"})

def test_resolve_symbol_named_singular():
    result = resolve_need("symbol named encounter")
    assert result == ("search_symbols", {"query": "encounter"})


# ------------------------------------------------------------------
# resolve_need - symbols_in_file
# ------------------------------------------------------------------

def test_resolve_symbols_in_file():
    result = resolve_need("symbols in world/encounter_generator.py")
    assert result == ("symbols_in_file", {"file_path": "world/encounter_generator.py"})

def test_resolve_symbols_in_bare_name():
    result = resolve_need("symbols in encounter_generator.py")
    assert result == ("symbols_in_file", {"file_path": "encounter_generator.py"})


# ------------------------------------------------------------------
# resolve_need - list_callers
# ------------------------------------------------------------------

def test_resolve_what_calls():
    result = resolve_need("what calls generate_encounter")
    assert result == ("list_callers", {"symbol": "generate_encounter"})

def test_resolve_callers_of():
    result = resolve_need("callers of generate_encounter")
    assert result == ("list_callers", {"symbol": "generate_encounter"})

def test_resolve_caller_of_singular():
    result = resolve_need("caller of foo")
    assert result == ("list_callers", {"symbol": "foo"})


# ------------------------------------------------------------------
# resolve_need - list_callees
# ------------------------------------------------------------------

def test_resolve_callees_of():
    result = resolve_need("callees of generate_encounter")
    assert result == ("list_callees", {"symbol": "generate_encounter"})

def test_resolve_callee_of_singular():
    result = resolve_need("callee of foo")
    assert result == ("list_callees", {"symbol": "foo"})


# ------------------------------------------------------------------
# resolve_need - describe_file
# ------------------------------------------------------------------

def test_resolve_what_does_file_do():
    result = resolve_need("what does encounter_generator.py do")
    assert result == ("describe_file", {"file_path": "encounter_generator.py"})

def test_resolve_describe_file():
    result = resolve_need("describe file world/encounter_generator.py")
    assert result == ("describe_file", {"file_path": "world/encounter_generator.py"})

def test_resolve_describe_file_no_prefix():
    result = resolve_need("describe encounter_generator.py")
    assert result == ("describe_file", {"file_path": "encounter_generator.py"})


# ------------------------------------------------------------------
# resolve_need - symbol_intent
# ------------------------------------------------------------------

def test_resolve_intent_of():
    result = resolve_need("intent of generate_encounter")
    assert result == ("symbol_intent", {"symbol": "generate_encounter"})

def test_resolve_purpose_of():
    result = resolve_need("purpose of dungeon_master")
    assert result == ("symbol_intent", {"symbol": "dungeon_master"})


# ------------------------------------------------------------------
# resolve_need - get_findings
# ------------------------------------------------------------------

def test_resolve_findings_for():
    result = resolve_need("findings for generate_encounter")
    assert result == ("get_findings", {"symbol": "generate_encounter"})

def test_resolve_known_findings_for():
    result = resolve_need("known findings for generate_encounter")
    assert result == ("get_findings", {"symbol": "generate_encounter"})


# ------------------------------------------------------------------
# resolve_need - symbol_brief
# ------------------------------------------------------------------

def test_resolve_brief_for():
    result = resolve_need("brief for generate_encounter")
    assert result == ("symbol_brief", {"symbol": "generate_encounter"})


# ------------------------------------------------------------------
# resolve_need - fallback search
# ------------------------------------------------------------------

def test_resolve_search_fallback():
    result = resolve_need("search encounter")
    assert result == ("search_symbols", {"query": "encounter"})

def test_resolve_find_fallback():
    result = resolve_need("find dungeon")
    assert result == ("search_symbols", {"query": "dungeon"})


# ------------------------------------------------------------------
# resolve_need - unmatched
# ------------------------------------------------------------------

def test_resolve_glob_stripped_from_search_files():
    result = resolve_need("files matching encounter_*")
    assert result == ("search_files", {"query": "encounter_"})

def test_resolve_glob_star_only_becomes_empty_skipped():
    # "files matching *" -> query="" after strip -> should return None (no empty query)
    result = resolve_need("files matching *")
    assert result is None

def test_resolve_glob_stripped_from_search_symbols():
    result = resolve_need("symbols named encounter*")
    assert result == ("search_symbols", {"query": "encounter"})

def test_symbols_from_result_filters_dunder():
    from determined.agent.agent_resolver import _symbols_from_result
    result = (
        "Symbols in 'action_system.py':\n"
        "  line 7: class Action\n"
        "  line 14: class ActionQueue\n"
        "  line 15: function __init__\n"
        "  line 20: function to_dict\n"
    )
    syms = _symbols_from_result(result)
    assert "__init__" not in syms
    assert "to_dict" not in syms
    assert "Action" in syms
    assert "ActionQueue" in syms

def test_symbols_from_result_filters_boilerplate_search_output():
    from determined.agent.agent_resolver import _symbols_from_result
    result = (
        "Symbols matching 'x':\n"
        "  generate_encounter (function) in enc.py line 36\n"
        "  __init__ (function) in enc.py line 1\n"
        "  from_dict (function) in enc.py line 10\n"
    )
    syms = _symbols_from_result(result)
    assert "generate_encounter" in syms
    assert "__init__" not in syms
    assert "from_dict" not in syms

def test_resolve_unmatched_returns_none():
    result = resolve_need("this is not a recognized need pattern")
    assert result is None

def test_resolve_empty_returns_none():
    result = resolve_need("")
    assert result is None


# ------------------------------------------------------------------
# Phase 0: ground_question / _extract_keywords
# ------------------------------------------------------------------

def test_extract_keywords_basic():
    from determined.agent.agent_resolver import _extract_keywords
    kws = _extract_keywords("how is character creation currently handled?")
    assert "character" in kws
    assert "creation" in kws
    # stopwords filtered
    assert "how" not in kws
    assert "currently" not in kws
    assert "handled" not in kws

def test_extract_keywords_ordered_longest_first():
    from determined.agent.agent_resolver import _extract_keywords
    kws = _extract_keywords("what is the encounter development progress?")
    # "development" (11) and "encounter" (9) should come before "progress" (8)
    assert kws[0] in ("development", "encounter")
    assert "development" in kws[:2]

def test_extract_keywords_deduplicates():
    from determined.agent.agent_resolver import _extract_keywords
    kws = _extract_keywords("encounter encounter encounter")
    assert kws.count("encounter") == 1

def test_extract_keywords_max_five():
    from determined.agent.agent_resolver import _extract_keywords
    kws = _extract_keywords("alpha beta gamma delta epsilon zeta eta theta")
    assert len(kws) <= 5

def test_ground_question_empty_corpus():
    """ground_question returns empty string when corpus has no matches."""
    import sqlite3
    from determined.agent.agent_resolver import ground_question

    class _Oracle:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
        def get_project_root(self): return "/project"
        def find_symbols(self, *a, **kw): return []
        def find_files(self, *a, **kw): return []

    result = ground_question("what does encounter do?", _Oracle(), None)
    assert result == ""

def test_ground_question_returns_found_names():
    """ground_question returns corpus-matched names when results exist."""
    import sqlite3
    from determined.agent.agent_resolver import ground_question

    class _Oracle:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
        def get_project_root(self): return "/project"
        def find_symbols(self, query, limit=10):
            if "encounter" in query.lower():
                return [{"name": "generate_encounter", "file_path": "/project/world/enc.py"}]
            return []
        def find_files(self, pattern=""):
            if "encounter" in pattern.lower():
                return [{"file_path": "/project/world/encounter_generator.py", "line_count": 120}]
            return []

    result = ground_question("how does encounter development work?", _Oracle(), None)
    assert "generate_encounter" in result
    assert "encounter_generator.py" in result
    assert "Corpus search results" in result


# ------------------------------------------------------------------
# _symbols_from_result / _files_from_result
# ------------------------------------------------------------------

def test_symbols_from_search_symbols_result():
    from determined.agent.agent_resolver import _symbols_from_result
    result = (
        "Symbols matching 'encounter':\n"
        "  generate_encounter (function) in encounter_generator.py line 42\n"
        "  _validate_encounter (function) in authority_system.py line 259\n"
    )
    syms = _symbols_from_result(result)
    assert syms == ["generate_encounter", "_validate_encounter"]

def test_symbols_from_symbols_in_file_result():
    from determined.agent.agent_resolver import _symbols_from_result
    result = (
        "Symbols in 'encounter_generator.py':\n"
        "  line 10: class EncounterGenerator\n"
        "  line 42: function generate_encounter [has docstring]\n"
    )
    syms = _symbols_from_result(result)
    assert syms == ["EncounterGenerator", "generate_encounter"]

def test_files_from_directory_result():
    from determined.agent.agent_resolver import _files_from_result
    result = (
        "Files in 'world/':\n"
        "  world/encounter_generator.py (120 lines)\n"
        "  world/travel.py (80 lines)\n"
    )
    files = _files_from_result(result)
    assert files == ["world/encounter_generator.py", "world/travel.py"]

def test_symbols_max_expand():
    from determined.agent.agent_resolver import _symbols_from_result, _MAX_EXPAND
    lines = "\n".join(
        f"  sym{i} (function) in file.py line {i}" for i in range(20)
    )
    result = f"Symbols matching 'x':\n{lines}"
    syms = _symbols_from_result(result)
    assert len(syms) == _MAX_EXPAND

def test_expand_facts_produces_callers_and_intent():
    """expand_facts on a search_symbols result produces list_callers + symbol_intent calls."""
    import sqlite3
    from determined.agent.agent_resolver import expand_facts

    class _Oracle:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            self.conn.execute(
                "CREATE TABLE graph_edges (caller TEXT, callee TEXT, line_number INTEGER)"
            )
            self.conn.execute(
                "CREATE TABLE symbol_references (caller TEXT, callee TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE functions (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE classes (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
        def get_project_root(self): return "/project"

    class _Assessor:
        _knowledge_conn = None
        def get_artifacts(self, *a): return []

    oracle = _Oracle()
    assessor = _Assessor()

    facts = [{
        "need": "symbols named encounter",
        "tool": "search_symbols",
        "args": {"query": "encounter"},
        "result": (
            "Symbols matching 'encounter':\n"
            "  generate_encounter (function) in encounter_generator.py line 42\n"
        ),
    }]
    seen = {("search_symbols", (("query", "encounter"),))}
    new_facts = expand_facts(facts, oracle, assessor, seen)

    tools_run = [f["tool"] for f in new_facts]
    assert "list_callers" in tools_run
    assert "symbol_intent" in tools_run

def test_expand_facts_files_expands_to_findings():
    """files_in_directory results now expand to get_findings per file."""
    from determined.agent.agent_resolver import expand_facts

    class _Assessor:
        def get_artifacts(self, subject):
            return []
        _knowledge_conn = None

    facts = [{
        "need": "files in world",
        "tool": "files_in_directory",
        "args": {"path": "world"},
        "result": "Files in 'world/':\n  world/encounter_generator.py (120 lines)\n",
    }]
    seen = {("files_in_directory", (("path", "world"),))}
    new_facts = expand_facts(facts, None, _Assessor(), seen)
    tools_run = [f["tool"] for f in new_facts]
    assert "get_findings" in tools_run

def test_expand_facts_deduplicates():
    """expand_facts does not re-run tool calls already in seen."""
    import sqlite3
    from determined.agent.agent_resolver import expand_facts

    class _Oracle:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            self.conn.execute(
                "CREATE TABLE graph_edges (caller TEXT, callee TEXT, line_number INTEGER)"
            )
            self.conn.execute("CREATE TABLE symbol_references (caller TEXT, callee TEXT)")
            self.conn.execute(
                "CREATE TABLE functions (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE classes (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
        def get_project_root(self): return "/project"

    class _Assessor:
        _knowledge_conn = None
        def get_artifacts(self, *a): return []

    oracle = _Oracle()
    assessor = _Assessor()

    facts = [{
        "need": "symbols named encounter",
        "tool": "search_symbols",
        "args": {"query": "encounter"},
        "result": "Symbols matching 'encounter':\n  generate_encounter (function) in f.py line 1\n",
    }]
    # Pre-populate seen with the follow-up calls that would be generated
    seen = {
        ("search_symbols", (("query", "encounter"),)),
        ("list_callers",  (("symbol", "generate_encounter"),)),
        ("symbol_intent", (("symbol", "generate_encounter"),)),
    }
    new_facts = expand_facts(facts, oracle, assessor, seen)
    assert new_facts == []


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
