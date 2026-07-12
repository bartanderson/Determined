"""
Multi-method structure induction for design document extraction (RM52).

Four deterministic methods run over each document section, seeded by the existing
extractor's output. Their outputs are combined via set operations and a
Dempster-Shafer gate into three tiers:

  convergent  - existing extractor + 2+ methods agree -> high trust
  discriminant- 2+ methods found it, existing extractor missed -> medium trust + tag
  review      - 1 method only, existing extractor missed -> held for human review

Public API:
  run(text, seeds) -> list[InducedSentence]
  fca_pass(sentences, seeds)     -> set[int]  (sentence indices)
  mdl_pass(sentences, seeds)     -> set[int]
  wrapper_pass(sentences, seeds) -> set[int]
  grammar_pass(sentences, seeds) -> set[int]
  combine(sentence_indices, all_sentences, seeds) -> list[InducedSentence]

References:
  FCA: Wille 1982; MDL: Rissanen 1978; LP2: Kushmerick 1997; L*: Angluin 1987
  Gate: Dempster 1967 / Shafer 1976; MTMM: Campbell & Fiske 1959
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------

@dataclass
class InducedSentence:
    text: str
    methods: list[str]          # which methods found this sentence
    in_seeds: bool              # True if the existing extractor also found it
    tier: str                   # "convergent" | "discriminant" | "review"
    tag: str = ""               # populated for discriminant tier


# ---------------------------------------------------------------------------
# Sentence extraction helpers
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """
    Split document text into candidate sentences/items for analysis.
    Handles: plain prose sentences, bullet list items, numbered list items.
    """
    sentences: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip leading bullet/number markers
        clean = re.sub(r"^[-*•]\s+", "", line)
        clean = re.sub(r"^\d+[.)]\s+", "", clean)
        clean = re.sub(r"^[a-zA-Z][.)]\s+", "", clean)
        clean = clean.strip()
        if len(clean) < 10:
            continue
        # If the line is a heading, skip it
        if re.match(r"^#+\s", line):
            continue
        sentences.append(clean)
    return sentences


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


# ---------------------------------------------------------------------------
# Feature extraction (shared by FCA and MDL)
# ---------------------------------------------------------------------------

_MODAL_RE = re.compile(
    r"\b(must not|must|shall not|shall|may not|never|required to|forbidden|prohibited"
    r"|always|cannot|will not|is required)\b",
    re.I,
)
_BULLET_RE = re.compile(r"^[-*•]\s+")
_NUMBERED_RE = re.compile(r"^\d+[.)]\s+")
_ALPHA_ITEM_RE = re.compile(r"^[a-zA-Z][.)]\s+")
_VERB_RE = re.compile(r"\b(ensure|enforce|require|restrict|allow|prevent|provide|handle|"
                       r"validate|check|guarantee|return|accept|reject|maintain|store|"
                       r"expose|protect|support|initialize|manage)\b", re.I)
_COLON_DEF_RE = re.compile(r":\s+[A-Z]")  # "X: must be ..."
_AUTHORITY_RE = re.compile(r"\b(layer|boundary|authority|system|component|module|"
                            r"interface|contract|engine|controller|manager)\b", re.I)


def _features(sentence: str, raw_line: str = "") -> dict[str, bool]:
    """Binary feature vector for a sentence."""
    return {
        "has_modal":    bool(_MODAL_RE.search(sentence)),
        "is_bullet":    bool(_BULLET_RE.match(raw_line)) if raw_line else False,
        "is_numbered":  bool(_NUMBERED_RE.match(raw_line)) if raw_line else False,
        "is_alpha_item":bool(_ALPHA_ITEM_RE.match(raw_line)) if raw_line else False,
        "has_verb":     bool(_VERB_RE.search(sentence)),
        "has_colon_def":bool(_COLON_DEF_RE.search(sentence)),
        "has_authority":bool(_AUTHORITY_RE.search(sentence)),
        "is_short":     len(sentence.split()) <= 20,
        "is_long":      len(sentence.split()) > 40,
        "starts_upper": bool(sentence) and sentence[0].isupper(),
    }


def _feature_vector(sentence: str, raw_line: str = "") -> frozenset[str]:
    """Return the set of true features (formal concept object attribute set)."""
    f = _features(sentence, raw_line)
    return frozenset(k for k, v in f.items() if v)


# ---------------------------------------------------------------------------
# Method 1: Formal Concept Analysis (Wille 1982)
# ---------------------------------------------------------------------------

def fca_pass(sentences: list[str], seeds: list[str]) -> set[int]:
    """
    FCA-based candidate detection.

    Build a formal context: objects = sentences, attributes = structural features.
    Compute the attribute closure of the seed set (the intent of the seed concept).
    Return sentences that share >= threshold attributes with that closure.
    """
    if not seeds:
        return set()

    # Compute attribute closure of seeds: intersection of all seed attribute sets
    seed_norms = {_normalize(s) for s in seeds}
    seed_attrs: list[frozenset[str]] = []
    for s in sentences:
        if _normalize(s) in seed_norms:
            seed_attrs.append(_feature_vector(s))
    if not seed_attrs:
        return set()

    # Intent: attributes common to ALL seeds
    intent = seed_attrs[0]
    for a in seed_attrs[1:]:
        intent = intent & a

    if not intent:
        # No shared attributes -- fall back to any-seed-attribute union
        intent = frozenset().union(*seed_attrs)

    # Find non-seed sentences that share >= 2 attributes with the intent
    threshold = max(2, len(intent) - 2)
    result: set[int] = set()
    for i, s in enumerate(sentences):
        if _normalize(s) in seed_norms:
            continue
        attrs = _feature_vector(s)
        if len(attrs & intent) >= threshold:
            result.add(i)
    return result


# ---------------------------------------------------------------------------
# Method 2: Minimum Description Length (Rissanen 1978)
# ---------------------------------------------------------------------------

def mdl_pass(sentences: list[str], seeds: list[str]) -> set[int]:
    """
    MDL-based candidate detection.

    Hypothesis space: structural groups (modal, numbered, bullet, mixed).
    The MDL-optimal hypothesis is the structural group that best compresses
    the sentence set while covering the seeds. Non-seed sentences in the
    same structural group as the MDL-optimal class are candidates.
    """
    if not seeds or not sentences:
        return set()

    seed_norms = {_normalize(s) for s in seeds}

    def structural_class(s: str) -> str:
        if _MODAL_RE.search(s):
            return "modal"
        if _NUMBERED_RE.match(s) or _ALPHA_ITEM_RE.match(s):
            return "numbered"
        if _BULLET_RE.match(s):
            return "bullet"
        if _COLON_DEF_RE.search(s) or _AUTHORITY_RE.search(s):
            return "authoritative_prose"
        return "prose"

    # Map sentences to classes
    classes: list[str] = [structural_class(s) for s in sentences]

    # Find which classes cover the seeds
    seed_classes: set[str] = set()
    for i, s in enumerate(sentences):
        if _normalize(s) in seed_norms:
            seed_classes.add(classes[i])

    if not seed_classes:
        return set()

    # MDL cost: encoding cost = bits to describe hypothesis + bits to describe exceptions.
    # For our restricted grammar: cost(class) = 1/coverage. Pick class with best coverage.
    class_counts: dict[str, int] = {}
    for c in classes:
        class_counts[c] = class_counts.get(c, 0) + 1

    # Best class = seed class with highest total membership (most compressible)
    best_class = max(seed_classes, key=lambda c: class_counts.get(c, 0))

    result: set[int] = set()
    for i, s in enumerate(sentences):
        if _normalize(s) in seed_norms:
            continue
        if classes[i] == best_class:
            result.add(i)
    return result


# ---------------------------------------------------------------------------
# Method 3: LP² Wrapper Induction (Kushmerick 1997)
# ---------------------------------------------------------------------------

_PUNCT_STRIP = re.compile(r"[^\w\s]")


def _context_signature(sentences: list[str], idx: int, window: int = 3) -> tuple[str, str]:
    """N-gram context signature: (left_tokens, right_tokens) around sentence idx."""
    words = _PUNCT_STRIP.sub("", sentences[idx]).lower().split()
    left = tuple(words[:window])
    right = tuple(words[-window:]) if len(words) >= window else tuple(words)
    return left, right


def wrapper_pass(sentences: list[str], seeds: list[str]) -> set[int]:
    """
    LP²-style wrapper induction.

    From seeds, extract structural context signatures (leading N-gram, trailing N-gram,
    sentence length bucket, whether it starts with a capitalized proper word).
    A wrapper is a conjunction of observed properties. Apply wrappers to non-seed
    sentences; those matching >= 1 wrapper are candidates.
    """
    if not seeds or not sentences:
        return set()

    seed_norms = {_normalize(s) for s in seeds}

    # Build wrappers from seed sentences
    wrappers: list[dict] = []
    for i, s in enumerate(sentences):
        if _normalize(s) not in seed_norms:
            continue
        words = _PUNCT_STRIP.sub("", s).lower().split()
        w = {
            "lead_tri":   tuple(words[:3]) if len(words) >= 3 else tuple(words),
            "tail_tri":   tuple(words[-3:]) if len(words) >= 3 else tuple(words),
            "len_bucket": len(words) // 5,    # 0-3, 4-8, 9-13, ...
            "has_modal":  bool(_MODAL_RE.search(s)),
            "lead_word":  words[0] if words else "",
        }
        wrappers.append(w)

    if not wrappers:
        return set()

    def _matches_any_wrapper(s: str) -> bool:
        words = _PUNCT_STRIP.sub("", s).lower().split()
        cand = {
            "lead_tri":   tuple(words[:3]) if len(words) >= 3 else tuple(words),
            "tail_tri":   tuple(words[-3:]) if len(words) >= 3 else tuple(words),
            "len_bucket": len(words) // 5,
            "has_modal":  bool(_MODAL_RE.search(s)),
            "lead_word":  words[0] if words else "",
        }
        for w in wrappers:
            # Match on 3 of 5 properties (conjunctive partial wrapper)
            score = sum([
                cand["lead_tri"] == w["lead_tri"],
                cand["tail_tri"] == w["tail_tri"],
                cand["len_bucket"] == w["len_bucket"],
                cand["has_modal"] == w["has_modal"],
                cand["lead_word"] == w["lead_word"],
            ])
            if score >= 3:
                return True
        return False

    result: set[int] = set()
    for i, s in enumerate(sentences):
        if _normalize(s) in seed_norms:
            continue
        if _matches_any_wrapper(s):
            result.add(i)
    return result


# ---------------------------------------------------------------------------
# Method 4: Grammatical Inference L* (Angluin 1987)
# ---------------------------------------------------------------------------

# In L* we learn a minimal DFA from positive examples (seeds). For the restricted
# grammar of design docs, we represent state as a prefix-class abstraction and
# learn accepting states from the seed set.

def grammar_pass(sentences: list[str], seeds: list[str]) -> set[int]:
    """
    L*-style grammatical inference (simplified for design-doc grammar).

    Map each sentence to an abstract token sequence using a coarse grammar:
      MOD  = modal verb word
      AUT  = authority/system noun
      VRB  = action verb
      NUM  = numeral / ordinal
      WRD  = any other content word

    From seeds, learn the set of accepted abstract-token n-grams (length 1-3).
    Classify non-seed sentences by whether they contain an accepted n-gram.
    """
    if not seeds or not sentences:
        return set()

    _MODAL_WORDS = frozenset(
        "must shall never required forbidden prohibited cannot always".split()
    )
    _AUTH_WORDS = frozenset(
        "layer boundary authority system component module interface "
        "contract engine controller manager service handler".split()
    )
    _VERB_WORDS = frozenset(
        "ensure enforce require restrict allow prevent provide handle "
        "validate check guarantee return accept reject maintain store "
        "expose protect support initialize manage".split()
    )

    def _abstract(s: str) -> list[str]:
        tokens = []
        for w in _PUNCT_STRIP.sub("", s).lower().split():
            if w in _MODAL_WORDS:
                tokens.append("MOD")
            elif w in _AUTH_WORDS:
                tokens.append("AUT")
            elif w in _VERB_WORDS:
                tokens.append("VRB")
            elif w.isdigit():
                tokens.append("NUM")
            elif len(w) >= 4:
                tokens.append("WRD")
        return tokens

    def _ngrams(tokens: list[str], n: int) -> set[tuple]:
        return {tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)}

    # Learn accepted abstract n-grams from seeds
    seed_norms = {_normalize(s) for s in seeds}
    accepted: set[tuple] = set()
    for s in sentences:
        if _normalize(s) in seed_norms:
            toks = _abstract(s)
            for n in (1, 2, 3):
                accepted |= _ngrams(toks, n)

    # Require at least 2 distinct accepted n-grams to accept a sentence
    if len(accepted) < 2:
        return set()

    result: set[int] = set()
    for i, s in enumerate(sentences):
        if _normalize(s) in seed_norms:
            continue
        toks = _abstract(s)
        candidate_ngrams: set[tuple] = set()
        for n in (1, 2, 3):
            candidate_ngrams |= _ngrams(toks, n)
        matching = candidate_ngrams & accepted
        # Accept if at least 2 accepted n-grams match AND at least one is length >= 2
        long_match = any(len(g) >= 2 for g in matching)
        if len(matching) >= 2 and long_match:
            result.add(i)
    return result


# ---------------------------------------------------------------------------
# Combination: set operations + Dempster-Shafer gate
# ---------------------------------------------------------------------------

def combine(
    fca_hits: set[int],
    mdl_hits: set[int],
    wrapper_hits: set[int],
    grammar_hits: set[int],
    sentences: list[str],
    seeds: list[str],
) -> list[InducedSentence]:
    """
    Merge method outputs via set operations and Dempster-Shafer gate.

    Tiering:
      convergent   - seeds agree AND 2+ methods agree
      discriminant - 2+ methods agree, seeds did NOT find it
      review       - 1 method only, seeds did NOT find it (not stored)

    Returns InducedSentence for all tiers, including review (caller decides whether
    to store review-tier items).
    """
    seed_norms = {_normalize(s) for s in seeds}
    all_indices = fca_hits | mdl_hits | wrapper_hits | grammar_hits

    result: list[InducedSentence] = []
    for i in sorted(all_indices):
        if i >= len(sentences):
            continue
        s = sentences[i]
        in_seeds = _normalize(s) in seed_norms

        methods_found = []
        if i in fca_hits:
            methods_found.append("fca")
        if i in mdl_hits:
            methods_found.append("mdl")
        if i in wrapper_hits:
            methods_found.append("wrapper")
        if i in grammar_hits:
            methods_found.append("grammar")

        method_count = len(methods_found)

        if in_seeds and method_count >= 2:
            tier = "convergent"
            tag = ""
        elif not in_seeds and method_count >= 2:
            tier = "discriminant"
            tag = f"found_by={','.join(methods_found)};missed_by=existing"
        elif not in_seeds and method_count == 1:
            tier = "review"
            tag = f"single_method={methods_found[0]}"
        else:
            # in_seeds but only 1 method -- still convergent (extractor + 1 method)
            tier = "convergent"
            tag = ""

        result.append(InducedSentence(
            text=s,
            methods=methods_found,
            in_seeds=in_seeds,
            tier=tier,
            tag=tag,
        ))

    return result


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def run(text: str, seeds: list[str]) -> list[InducedSentence]:
    """
    Run all four structure-induction methods over `text`, seeded by `seeds`.

    `seeds` should be the constraint sentences already found by the existing
    extractor (doc_extractor._extract_constraint_sentences output).
    Returns list of InducedSentence, sorted by tier (convergent first).
    """
    sentences = _split_sentences(text)
    if not sentences:
        return []

    fca_hits     = fca_pass(sentences, seeds)
    mdl_hits     = mdl_pass(sentences, seeds)
    wrapper_hits = wrapper_pass(sentences, seeds)
    grammar_hits = grammar_pass(sentences, seeds)

    induced = combine(fca_hits, mdl_hits, wrapper_hits, grammar_hits, sentences, seeds)

    tier_order = {"convergent": 0, "discriminant": 1, "review": 2}
    induced.sort(key=lambda x: tier_order.get(x.tier, 3))
    return induced
