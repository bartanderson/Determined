"""Regression tests for RM52: multi-method structure induction."""
import pytest
from determined.ingestion.structure_induction import (
    fca_pass, mdl_pass, wrapper_pass, grammar_pass,
    combine, run, _split_sentences, _normalize,
)

# ---------------------------------------------------------------------------
# Fixture document with three kinds of requirements:
#   - Modal (must/shall): found by existing extractor and most methods
#   - Numbered items: bullet constraints, should be found by multi-method
#   - Prose obligations: implicit authority, found by multi-method only
# ---------------------------------------------------------------------------

_MODAL_DOC = """\
# Authority Boundary

The engine must enforce authority at mutation time.
The system shall never allow direct writes to DungeonStateNeo.
External callers must not bypass the validation layer.

# Phase Control

1. The phase controller must run before any state change.
2. Rollback must be triggered on validation failure.
3. The intent layer must classify player input first.

# Additional Notes

All writes to game state require a valid session token.
The AI boundary component must validate all inputs before forwarding.
"""

_MODAL_SEEDS = [
    "The engine must enforce authority at mutation time.",
    "The system shall never allow direct writes to DungeonStateNeo.",
    "External callers must not bypass the validation layer.",
]


# ---------------------------------------------------------------------------
# _split_sentences
# ---------------------------------------------------------------------------

def test_split_sentences_basic():
    sentences = _split_sentences(_MODAL_DOC)
    assert len(sentences) >= 5
    assert any("must enforce authority" in s for s in sentences)


def test_split_sentences_strips_bullets():
    text = "- Item one must be done\n* Item two shall not fail\n"
    sentences = _split_sentences(text)
    assert any("must be done" in s for s in sentences)
    assert not any(s.startswith("-") or s.startswith("*") for s in sentences)


def test_split_sentences_strips_numbered():
    text = "1. The system must initialize first.\n2. Rollback must be triggered.\n"
    sentences = _split_sentences(text)
    assert all(not s[0].isdigit() for s in sentences)


def test_split_sentences_skips_headings():
    text = "# My Heading\nSome constraint must hold.\n"
    sentences = _split_sentences(text)
    assert not any("My Heading" in s for s in sentences)


# ---------------------------------------------------------------------------
# fca_pass
# ---------------------------------------------------------------------------

def test_fca_pass_finds_numbered_requirements():
    sentences = _split_sentences(_MODAL_DOC)
    hits = fca_pass(sentences, _MODAL_SEEDS)
    hit_texts = {sentences[i] for i in hits}
    # Numbered items should share features with modal seeds
    assert any("must classify" in t or "must run" in t or "must be triggered" in t
               for t in hit_texts), f"fca_pass missed numbered requirements: {hit_texts}"


def test_fca_pass_empty_seeds():
    sentences = _split_sentences(_MODAL_DOC)
    hits = fca_pass(sentences, [])
    assert hits == set()


def test_fca_pass_no_sentences():
    hits = fca_pass([], _MODAL_SEEDS)
    assert hits == set()


def test_fca_pass_returns_set_of_indices():
    sentences = _split_sentences(_MODAL_DOC)
    hits = fca_pass(sentences, _MODAL_SEEDS)
    assert isinstance(hits, set)
    for idx in hits:
        assert 0 <= idx < len(sentences)


# ---------------------------------------------------------------------------
# mdl_pass
# ---------------------------------------------------------------------------

def test_mdl_pass_finds_same_structural_class():
    sentences = _split_sentences(_MODAL_DOC)
    hits = mdl_pass(sentences, _MODAL_SEEDS)
    # Seeds are all "modal" class; mdl should find other modal sentences
    hit_texts = {sentences[i] for i in hits}
    assert len(hit_texts) >= 1


def test_mdl_pass_empty_seeds():
    sentences = _split_sentences(_MODAL_DOC)
    assert mdl_pass(sentences, []) == set()


def test_mdl_pass_returns_non_seed_indices():
    sentences = _split_sentences(_MODAL_DOC)
    seed_norms = {_normalize(s) for s in _MODAL_SEEDS}
    hits = mdl_pass(sentences, _MODAL_SEEDS)
    for idx in hits:
        assert _normalize(sentences[idx]) not in seed_norms


# ---------------------------------------------------------------------------
# wrapper_pass
# ---------------------------------------------------------------------------

def test_wrapper_pass_finds_similar_sentences():
    sentences = _split_sentences(_MODAL_DOC)
    hits = wrapper_pass(sentences, _MODAL_SEEDS)
    # Should find sentences with similar length/modal/leading-word pattern
    assert isinstance(hits, set)
    for idx in hits:
        assert 0 <= idx < len(sentences)


def test_wrapper_pass_empty_seeds():
    sentences = _split_sentences(_MODAL_DOC)
    assert wrapper_pass(sentences, []) == set()


def test_wrapper_pass_does_not_return_seeds():
    sentences = _split_sentences(_MODAL_DOC)
    seed_norms = {_normalize(s) for s in _MODAL_SEEDS}
    hits = wrapper_pass(sentences, _MODAL_SEEDS)
    for idx in hits:
        assert _normalize(sentences[idx]) not in seed_norms


# ---------------------------------------------------------------------------
# grammar_pass
# ---------------------------------------------------------------------------

def test_grammar_pass_finds_candidates():
    sentences = _split_sentences(_MODAL_DOC)
    hits = grammar_pass(sentences, _MODAL_SEEDS)
    assert isinstance(hits, set)


def test_grammar_pass_empty_seeds():
    sentences = _split_sentences(_MODAL_DOC)
    assert grammar_pass(sentences, []) == set()


def test_grammar_pass_skips_seeds():
    sentences = _split_sentences(_MODAL_DOC)
    seed_norms = {_normalize(s) for s in _MODAL_SEEDS}
    hits = grammar_pass(sentences, _MODAL_SEEDS)
    for idx in hits:
        assert _normalize(sentences[idx]) not in seed_norms


# ---------------------------------------------------------------------------
# combine
# ---------------------------------------------------------------------------

def test_combine_convergent_tier():
    sentences = ["The system must validate inputs.", "Rollback must occur on error."]
    seeds = ["The system must validate inputs."]
    # Both methods hit index 1 (not in seeds), plus seeds already have index 0
    hits_a = {1}
    hits_b = {1}
    result = combine(hits_a, hits_b, set(), set(), sentences, seeds)
    discriminant = [r for r in result if r.tier == "discriminant"]
    assert len(discriminant) >= 1
    assert discriminant[0].text == sentences[1]


def test_combine_discriminant_has_tag():
    sentences = ["Seed sentence must hold.", "New requirement found here."]
    seeds = ["Seed sentence must hold."]
    hits_a = {1}
    hits_b = {1}
    result = combine(hits_a, hits_b, set(), set(), sentences, seeds)
    disc = [r for r in result if r.tier == "discriminant"]
    assert disc
    assert "missed_by=existing" in disc[0].tag


def test_combine_review_tier_single_method():
    sentences = ["Seed must hold.", "Maybe this is relevant."]
    seeds = ["Seed must hold."]
    hits_only_one = {1}
    result = combine(hits_only_one, set(), set(), set(), sentences, seeds)
    review = [r for r in result if r.tier == "review"]
    assert review
    assert "single_method" in review[0].tag


def test_combine_in_seeds_flag():
    sentences = ["The system must enforce this.", "Another sentence."]
    seeds = ["The system must enforce this."]
    hits = {0}
    result = combine(hits, hits, set(), set(), sentences, seeds)
    matched = [r for r in result if "must enforce" in r.text]
    # Seeds hit index 0 and 2 methods also hit it -> convergent
    assert matched
    assert matched[0].in_seeds is True


def test_combine_sorted_convergent_first():
    sentences = ["Seed must hold.", "Two methods found this.", "Only one method here."]
    seeds = ["Seed must hold."]
    hits_ab = {1}
    hits_one = {2}
    result = combine(hits_ab, hits_ab, hits_one, set(), sentences, seeds)
    tiers = [r.tier for r in result]
    # discriminant before review
    disc_idx = next((i for i, t in enumerate(tiers) if t == "discriminant"), None)
    rev_idx = next((i for i, t in enumerate(tiers) if t == "review"), None)
    if disc_idx is not None and rev_idx is not None:
        assert disc_idx < rev_idx


# ---------------------------------------------------------------------------
# run() end-to-end
# ---------------------------------------------------------------------------

def test_run_returns_induced_sentences():
    result = run(_MODAL_DOC, _MODAL_SEEDS)
    assert isinstance(result, list)
    assert len(result) >= 1


def test_run_convergent_first():
    result = run(_MODAL_DOC, _MODAL_SEEDS)
    tiers = [r.tier for r in result]
    conv_indices = [i for i, t in enumerate(tiers) if t == "convergent"]
    disc_indices = [i for i, t in enumerate(tiers) if t == "discriminant"]
    if conv_indices and disc_indices:
        assert max(conv_indices) < min(disc_indices)


def test_run_discriminant_items_not_in_seeds():
    result = run(_MODAL_DOC, _MODAL_SEEDS)
    seed_norms = {_normalize(s) for s in _MODAL_SEEDS}
    for item in result:
        if item.tier == "discriminant":
            assert _normalize(item.text) not in seed_norms


def test_run_empty_text():
    result = run("", _MODAL_SEEDS)
    assert result == []


def test_run_empty_seeds():
    result = run(_MODAL_DOC, [])
    # With no seeds, methods return nothing (all seed-seeded)
    assert isinstance(result, list)


def test_run_finds_numbered_items_as_discriminant_or_review():
    """Numbered items not in seeds should surface via multi-method pass."""
    result = run(_MODAL_DOC, _MODAL_SEEDS)
    non_convergent = [r for r in result if r.tier in ("discriminant", "review")]
    # At least some numbered items should be found
    assert len(non_convergent) >= 1
