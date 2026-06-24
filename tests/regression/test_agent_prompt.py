# tools/analysis/tests/regression/test_agent_prompt.py
#
# Tests for agent_prompt.py - system prompt construction and tool call parsing.
# The parser is the most fragile piece: llama3.2:3b output varies.

from determined.agent.agent_prompt import (
    parse_tool_call, build_messages, format_observation, SYSTEM_PROMPT,
)


# ------------------------------------------------------------------
# parse_tool_call - the critical path
# ------------------------------------------------------------------

def test_parse_clean_tool_call():
    text = 'TOOL: search_symbols\nARGS: {"query": "encounter"}'
    name, args = parse_tool_call(text)
    assert name == "search_symbols"
    assert args == {"query": "encounter"}


def test_parse_tool_call_with_surrounding_text():
    """Model often reasons before the tool call."""
    text = (
        "I need to find symbols related to encounters first.\n"
        "TOOL: search_symbols\n"
        'ARGS: {"query": "encounter"}\n'
        "Let me check the results."
    )
    name, args = parse_tool_call(text)
    assert name == "search_symbols"
    assert args["query"] == "encounter"


def test_parse_tool_call_multi_arg():
    text = 'TOOL: store_finding\nARGS: {"symbol": "generate_encounter", "kind": "known_issue", "content": "Returns None if context empty."}'
    name, args = parse_tool_call(text)
    assert name == "store_finding"
    assert args["symbol"] == "generate_encounter"
    assert args["kind"] == "known_issue"
    assert "Returns None" in args["content"]


def test_parse_no_tool_call_returns_none():
    """Plain answer with no tool call."""
    text = "The encounter system uses generate_encounter in encounter_generator.py."
    name, args = parse_tool_call(text)
    assert name is None
    assert args is None


def test_parse_tool_call_extra_whitespace():
    text = "TOOL:  search_files\nARGS: {\"query\": \"world\"}"
    name, args = parse_tool_call(text)
    assert name == "search_files"
    assert args["query"] == "world"


def test_parse_tool_call_list_callers():
    text = 'TOOL: list_callers\nARGS: {"symbol": "get_ai_response"}'
    name, args = parse_tool_call(text)
    assert name == "list_callers"
    assert args["symbol"] == "get_ai_response"


# ------------------------------------------------------------------
# Tolerance tests - common small-model drift patterns
# ------------------------------------------------------------------

def test_parse_lowercase_labels():
    """Model outputs 'tool:' and 'args:' in lowercase."""
    text = 'tool: search_symbols\nargs: {"query": "encounter"}'
    name, args = parse_tool_call(text)
    assert name == "search_symbols"
    assert args["query"] == "encounter"


def test_parse_mixed_case_labels():
    text = 'Tool: search_files\nArgs: {"query": "world"}'
    name, args = parse_tool_call(text)
    assert name == "search_files"
    assert args["query"] == "world"


def test_parse_args_on_same_line_as_label():
    """Model puts args immediately after ARGS: with no newline."""
    text = 'TOOL: list_callers\nARGS: {"symbol": "generate_encounter"}'
    name, args = parse_tool_call(text)
    assert name == "list_callers"
    assert args["symbol"] == "generate_encounter"


def test_parse_json_in_markdown_backticks():
    """Model wraps JSON in ```json ... ``` code fence."""
    text = 'TOOL: search_symbols\nARGS: ```json\n{"query": "travel"}\n```'
    name, args = parse_tool_call(text)
    assert name == "search_symbols"
    assert args["query"] == "travel"


def test_parse_single_quotes_in_args():
    """Model uses single quotes instead of double quotes in JSON."""
    text = "TOOL: symbol_intent\nARGS: {'symbol': 'generate_encounter'}"
    name, args = parse_tool_call(text)
    assert name == "symbol_intent"
    assert args["symbol"] == "generate_encounter"


def test_parse_blank_line_between_tool_and_args():
    """Model puts a blank line between TOOL and ARGS."""
    text = 'TOOL: search_symbols\n\nARGS: {"query": "encounter"}'
    name, args = parse_tool_call(text)
    assert name == "search_symbols"
    assert args["query"] == "encounter"


def test_parse_no_args_block_returns_empty_dict():
    """Model names a tool but forgets to include ARGS."""
    text = "I will call TOOL: files_in_directory to look at the world folder."
    name, args = parse_tool_call(text)
    assert name == "files_in_directory"
    assert isinstance(args, dict)


def test_parse_tool_name_normalised_to_lowercase():
    """Tool name should always come back lowercase regardless of model casing."""
    text = 'TOOL: Search_Symbols\nARGS: {"query": "encounter"}'
    name, args = parse_tool_call(text)
    assert name == "search_symbols"


def test_parse_extra_whitespace_in_tool_name():
    text = 'TOOL:   describe_file\nARGS: {"file_path": "world/engine.py"}'
    name, args = parse_tool_call(text)
    assert name == "describe_file"
    assert args["file_path"] == "world/engine.py"


# ------------------------------------------------------------------
# build_messages
# ------------------------------------------------------------------

def test_build_messages_empty_history():
    msgs = build_messages([], "what is the encounter system?")
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == "what is the encounter system?"


def test_build_messages_preserves_history():
    history = [
        {"role": "user", "content": "what calls generate_encounter?"},
        {"role": "assistant", "content": "handle_movement calls it."},
    ]
    msgs = build_messages(history, "what does handle_movement do?")
    assert len(msgs) == 4  # system + 2 history + new user
    assert msgs[2]["content"] == "handle_movement calls it."
    assert msgs[3]["content"] == "what does handle_movement do?"


def test_system_prompt_contains_all_tools():
    tools = [
        "search_symbols", "search_files", "list_callers", "list_callees",
        "symbols_in_file", "files_in_directory", "describe_file",
        "symbol_intent", "symbol_brief", "get_findings", "store_finding",
        "ask_truth_layer",
    ]
    for t in tools:
        assert t in SYSTEM_PROMPT, f"Tool '{t}' missing from system prompt"


def test_system_prompt_contains_protocol():
    assert "TOOL:" in SYSTEM_PROMPT
    assert "ARGS:" in SYSTEM_PROMPT


# ------------------------------------------------------------------
# format_observation
# ------------------------------------------------------------------

def test_format_observation():
    obs = format_observation("search_symbols", "generate_encounter in engine.py line 10")
    assert "search_symbols" in obs
    assert "generate_encounter" in obs


# ------------------------------------------------------------------
# RUN DIRECTLY
# ------------------------------------------------------------------

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {t.__name__}: {exc}")
            failed += 1
    print(f"\n{passed + failed} tests: {passed} passed, {failed} failed")
