# tests/regression/test_claim_verifier.py
#
# Tests for RM21 Technique 1: claim extraction and verification.

import sqlite3
import pytest

from determined.agent.claim_verifier import (
    extract_claims,
    verify_claim,
    verify_answer,
    build_correction_block,
    Claim,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """In-memory DB with a minimal graph_edges table."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE graph_edges "
        "(caller TEXT, callee TEXT, caller_file TEXT, line_number INTEGER, resolved INTEGER)"
    )
    conn.executemany(
        "INSERT INTO graph_edges (caller, callee) VALUES (?, ?)",
        [
            ("load_corpus", "parse_ast"),
            ("load_corpus", "persist"),
            ("run_engine", "load_corpus"),
        ],
    )
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# extract_claims
# ---------------------------------------------------------------------------

def test_extract_calls_basic():
    claims = extract_claims("load_corpus calls parse_ast to parse files.")
    calls = [c for c in claims if c.kind == "CALLS"]
    assert any(c.subject == "load_corpus" and c.object_ == "parse_ast" for c in calls)


def test_extract_calls_invokes():
    claims = extract_claims("run_engine invokes load_corpus at startup.")
    calls = [c for c in claims if c.kind == "CALLS"]
    assert any(c.subject == "run_engine" and c.object_ == "load_corpus" for c in calls)


def test_extract_no_callers_has_no():
    claims = extract_claims("parse_ast has no callers in the corpus.")
    nc = [c for c in claims if c.kind == "NO_CALLERS"]
    assert any(c.subject == "parse_ast" for c in nc)


def test_extract_no_callers_is_not_called():
    claims = extract_claims("persist is not called by anything.")
    nc = [c for c in claims if c.kind == "NO_CALLERS"]
    assert any(c.subject == "persist" for c in nc)


def test_extract_skips_noise_words():
    claims = extract_claims("It calls the function and is not called.")
    # "It", "the", "and", "is" should be filtered out as noise
    assert all(c.subject.lower() not in ("it", "the", "and", "is") for c in claims)


def test_extract_deduplicates():
    answer = "load_corpus calls parse_ast. Also, load_corpus calls parse_ast again."
    calls = [c for c in extract_claims(answer) if c.kind == "CALLS"]
    matching = [c for c in calls if c.subject == "load_corpus" and c.object_ == "parse_ast"]
    assert len(matching) == 1


# ---------------------------------------------------------------------------
# verify_claim
# ---------------------------------------------------------------------------

def test_verify_calls_correct(db):
    claim = Claim(text="", kind="CALLS", subject="load_corpus", object_="parse_ast")
    result = verify_claim(claim, db)
    assert result is None  # claim is correct


def test_verify_calls_wrong(db):
    claim = Claim(text="", kind="CALLS", subject="load_corpus", object_="nonexistent_fn")
    result = verify_claim(claim, db)
    assert result is not None
    assert "load_corpus" in result.correction_text
    assert "nonexistent_fn" in result.correction_text


def test_verify_no_callers_correct(db):
    # run_engine has no callers (only appears as caller, never as callee)
    claim = Claim(text="", kind="NO_CALLERS", subject="run_engine")
    result = verify_claim(claim, db)
    assert result is None


def test_verify_no_callers_wrong(db):
    # load_corpus IS called by run_engine
    claim = Claim(text="", kind="NO_CALLERS", subject="load_corpus")
    result = verify_claim(claim, db)
    assert result is not None
    assert "run_engine" in result.correction_text


# ---------------------------------------------------------------------------
# verify_answer / build_correction_block
# ---------------------------------------------------------------------------

def test_verify_answer_returns_corrections(db):
    answer = "load_corpus calls nonexistent_fn and load_corpus has no callers."
    corrections = verify_answer(answer, db)
    kinds = {c.original_claim for c in corrections}
    # at least the no-callers claim should be caught
    assert any("no callers" in c for c in kinds)


def test_build_correction_block_format(db):
    claim = Claim(text="", kind="NO_CALLERS", subject="load_corpus")
    correction = verify_claim(claim, db)
    assert correction is not None
    block = build_correction_block([correction])
    assert "CORRECTION" in block
    assert "run_engine" in block
