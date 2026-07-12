# tests/regression/test_inline_note_extraction.py
# RM50: inline comment extraction from function bodies stored as kind='inline_note'

import ast
import json
import sqlite3
import textwrap
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from determined.ingestion.parse_ast import _extract_functions, _collect_comments
from determined.persistence.persistence_engine import ensure_schema, persist_file_analysis
from determined.shared.types import FileAnalysis, FileMetadata


def _parse(source: str):
    src = textwrap.dedent(source)
    tree = ast.parse(src)
    return _extract_functions(tree, comment_map=_collect_comments(src))


def _db():
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    conn.commit()
    return conn


def _make_analysis(file_path, functions):
    return FileAnalysis(
        file_path=file_path,
        metadata=FileMetadata(line_count=10),
        functions=functions,
    )


# ---------------------------------------------------------------------------
# _collect_comments unit tests
# ---------------------------------------------------------------------------

def test_block_comment_captured():
    source = """\
def foo():
    # validates the move before applying
    x = 1
"""
    fns = _parse(source)
    assert len(fns[0].inline_notes) == 1
    note = fns[0].inline_notes[0]
    assert note['text'] == 'validates the move before applying'
    assert note['position'] == 'block'
    assert note['marker'] is None


def test_inline_comment_captured():
    source = """\
def foo():
    x = compute()  # result of the computation
    return x
"""
    fns = _parse(source)
    assert len(fns[0].inline_notes) == 1
    note = fns[0].inline_notes[0]
    assert note['text'] == 'result of the computation'
    assert note['position'] == 'inline'
    assert note['marker'] is None


def test_marker_todo_detected():
    source = """\
def foo():
    # TODO: handle None state
    return 1
"""
    fns = _parse(source)
    assert fns[0].inline_notes[0]['marker'] == 'TODO'


def test_marker_fixme_detected():
    source = """\
def foo():
    # FIXME: this is wrong
    return 1
"""
    fns = _parse(source)
    assert fns[0].inline_notes[0]['marker'] == 'FIXME'


def test_marker_note_detected():
    source = """\
def foo():
    # NOTE: only called from authenticated handlers
    return 1
"""
    fns = _parse(source)
    assert fns[0].inline_notes[0]['marker'] == 'NOTE'


def test_marker_hyphen_delimiter():
    source = """\
def foo():
    # SAFETY - must hold the lock before calling
    return 1
"""
    fns = _parse(source)
    assert fns[0].inline_notes[0]['marker'] == 'SAFETY'


def test_marker_double_space_delimiter():
    source = """\
def foo():
    # CONTRACT  caller must validate input first
    return 1
"""
    fns = _parse(source)
    assert fns[0].inline_notes[0]['marker'] == 'CONTRACT'


def test_marker_returns_swallowed():
    # Mixed-case labels like 'Returns' match too -- consumer decides if meaningful
    source = '''\
def foo():
    # Returns: the computed value
    return 1
'''
    fns = _parse(source)
    # 'Returns' starts with uppercase letter followed by all-caps... wait, it's mixed case
    # 'R' then 'eturns' -- the regex requires [A-Z][A-Z0-9_]+ so 'Returns' does NOT match
    # (the 'e' after 'R' is lowercase). This is intentional: only ALL_CAPS labels are markers.
    assert fns[0].inline_notes[0]['marker'] is None
    assert fns[0].inline_notes[0]['text'] == 'Returns: the computed value'


def test_no_marker_when_not_keyword():
    source = """\
def foo():
    # validates the move before applying
    return 1
"""
    fns = _parse(source)
    assert fns[0].inline_notes[0]['marker'] is None


def test_multiple_comments_captured():
    source = """\
def foo():
    # state must be clean here
    x = 1
    # only called from authenticated handlers
    return x
"""
    fns = _parse(source)
    assert len(fns[0].inline_notes) == 2
    texts = [n['text'] for n in fns[0].inline_notes]
    assert 'state must be clean here' in texts
    assert 'only called from authenticated handlers' in texts


def test_hash_in_string_not_captured():
    source = '''\
def foo():
    url = "http://example.com/path#anchor"
    return url
'''
    fns = _parse(source)
    assert fns[0].inline_notes == []


def test_def_line_comment_not_captured():
    # A comment after the def line itself should not appear
    source = """\
def foo():  # this is the def line
    return 1
"""
    fns = _parse(source)
    assert fns[0].inline_notes == []


def test_docstring_and_inline_notes_independent():
    source = '''\
def foo():
    """This is the docstring."""
    # state must be clean here
    x = 1
'''
    fns = _parse(source)
    assert fns[0].docstring == "This is the docstring."
    assert len(fns[0].inline_notes) == 1
    assert fns[0].inline_notes[0]['text'] == 'state must be clean here'


def test_no_comment_map_gives_empty_notes():
    source = textwrap.dedent("""\
def foo():
    # should not appear
    x = 1
""")
    tree = ast.parse(source)
    fns = _extract_functions(tree, comment_map=None)
    assert fns[0].inline_notes == []


def test_short_comment_captured():
    # Short comments like TODO, ok, etc. should NOT be filtered — no length threshold
    source = """\
def foo():
    # ok
    return 1
"""
    fns = _parse(source)
    assert len(fns[0].inline_notes) == 1
    assert fns[0].inline_notes[0]['text'] == 'ok'


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

def test_inline_notes_written_to_db():
    source = """\
def process():
    # validates the move before applying
    x = compute()  # result here
    return x
"""
    fns = _parse(source)
    assert len(fns[0].inline_notes) == 2

    conn = _db()
    analysis = _make_analysis("app/process.py", fns)
    persist_file_analysis(conn, analysis, project_prefixes=set())
    conn.commit()

    rows = conn.execute(
        "SELECT subject, content FROM knowledge_artifacts WHERE kind='inline_note'"
    ).fetchall()
    assert len(rows) == 2
    assert all(r[0] == 'process' for r in rows)

    parsed = [json.loads(c.split('] ', 1)[1]) for _, c in rows]
    positions = {p['position'] for p in parsed}
    assert 'block' in positions
    assert 'inline' in positions

    # Content prefixed with file path
    assert all('process.py]' in r[1] for r in rows)


def test_inline_notes_store_marker():
    source = """\
def foo():
    # TODO: handle edge case
    return 1
"""
    fns = _parse(source)
    conn = _db()
    persist_file_analysis(conn, _make_analysis("app/foo.py", fns), project_prefixes=set())
    conn.commit()

    rows = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE kind='inline_note'"
    ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][0].split('] ', 1)[1])
    assert payload['marker'] == 'TODO'


def test_inline_notes_cleared_on_reingest():
    source1 = """\
def foo():
    # first comment about foo
    return 1
"""
    source2 = """\
def foo():
    # updated comment about foo
    return 2
"""
    fns1 = _parse(source1)
    fns2 = _parse(source2)

    conn = _db()
    persist_file_analysis(conn, _make_analysis("app/foo.py", fns1), project_prefixes=set())
    conn.commit()

    count1 = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='inline_note'"
    ).fetchone()[0]
    assert count1 == 1

    persist_file_analysis(conn, _make_analysis("app/foo.py", fns2), project_prefixes=set())
    conn.commit()

    rows = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE kind='inline_note'"
    ).fetchall()
    assert len(rows) == 1
    assert 'updated comment' in rows[0][0]
    assert 'first comment' not in rows[0][0]


def test_no_inline_notes_no_artifacts():
    source = """\
def foo():
    return 1
"""
    fns = _parse(source)
    assert fns[0].inline_notes == []

    conn = _db()
    persist_file_analysis(conn, _make_analysis("app/foo.py", fns), project_prefixes=set())
    conn.commit()

    count = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='inline_note'"
    ).fetchone()[0]
    assert count == 0
