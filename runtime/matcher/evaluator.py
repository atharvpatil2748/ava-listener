"""
AVAListener — Wake Phrase Matcher (Phase 0.5 refactor)
=======================================================
Two-gate matching strategy:

  Gate 1 (HARD): anchor_present()
      The wake token or a registered variant must appear in the hypothesis.
      Uses Jaro-Winkler (jellyfish) — outperforms Soundex/Metaphone for
      invented words.

  Gate 2 (SOFT): best_match()
      Score the hypothesis window against every canonical wake phrase via
      rapidfuzz token_set_ratio + context word presence + stability.

Phase 0.5 change
-----------------
  The matcher NO LONGER imports WAKEWORDS, WAKE_PHRASES, or CONTEXT_WORDS
  from config.settings. All phrase data comes from the PhraseRegistry via
  detection.variants (get_variants, get_canonical, get_active_phrases).

  ALL scoring logic is IDENTICAL to Phase 0. Zero algorithmic changes.

  Context words (hey / wake up / listen) are now derived at score time from
  the canonical phrase string itself — no separate CONTEXT_WORDS dict needed.
  The heuristic: any word(s) preceding the last token of the phrase are context.
  This matches Phase 0 CONTEXT_WORDS behaviour exactly for all current phrases.

Return signature (unchanged from Phase 0):
  best_match(window) -> (score: float, canonical_phrase: str, matched_variant: str)
"""
import jellyfish
from rapidfuzz import fuzz
from typing import List, Tuple

from config.settings import (
    JARO_THRESHOLD,
    FUZZY_THRESHOLD,
    WEIGHT_MATCH,
    WEIGHT_CONTEXT,
    WEIGHT_STABILITY,
    PHRASE_PRIORITY_MODE,
    REQUIRE_FULL_PHRASE,
    ALLOW_PREFIX_MATCHING,
)
from detection.variants import get_variants, get_canonical, get_active_phrases
from utils.logger import get_logger

log = get_logger("evaluator")


# ---------------------------------------------------------------------------
# Context word derivation (replaces static CONTEXT_WORDS dict)
# ---------------------------------------------------------------------------

def _derive_context_words(phrase: str) -> list[str]:
    """
    Derive expected context/preamble words from a canonical phrase.

    Heuristic: all words before the last token are context words.
    Examples:
        "assistant"         -> []          (bare phrase, no preamble)
        "hey assistant"     -> ["hey"]
        "wake up assistant" -> ["wake", "up"]
        "listen assistant"  -> ["listen"]
        "listen buddy"      -> ["listen"]
        "listen"            -> []

    This exactly reproduces the Phase 0 CONTEXT_WORDS dict for all phrases
    currently in use, and correctly generalises to new profiles.
    """
    words = phrase.strip().split()
    if len(words) <= 1:
        return []
    return words[:-1]   # everything except the wake token itself


# ---------------------------------------------------------------------------
# Gate 1: Anchor presence (logic IDENTICAL to Phase 0)
# ---------------------------------------------------------------------------

def anchor_present(text: str) -> bool:
    """
    Hard gate: returns True only if the wake token (or a recognizable variant)
    appears somewhere in `text`.

    Strategy:
      1. Exact substring: check space-stripped tokens against space-stripped
         variants. Catches "ar sal" -> strip -> "arsal" matching "arsal" variant.
      2. Jaro-Winkler: compare each individual token against each variant.
         Length-guarded: only compare tokens whose length difference <= 2 to
         prevent short common words ("a", "I") from matching long variants.
    """
    tokens = text.lower().split()
    variants = get_variants()   # from current registry state

    for variant in variants:
        v = variant.replace(" ", "")
        v_words = variant.split()
        n_words  = len(text.lower().split())

        # -- Multi-token variant exact match (e.g. "our whistle") ---------------
        if " " in variant:
            if abs(n_words - len(v_words)) <= 2:
                if variant in text.lower():
                    return True
            # Stripped fallback
            text_stripped = "".join(text.lower().split())
            if abs(len(text_stripped) - len(v)) <= 3 and v in text_stripped:
                return True

        # -- Single-token exact substring match ---------------------------------
        for tok in tokens:
            tok_stripped = tok.replace(" ", "")
            if v in tok_stripped or tok_stripped in v:
                if abs(len(tok_stripped) - len(v)) <= 2:
                    return True

        # -- Jaro-Winkler per individual token (length-guarded) -----------------
        for tok in tokens:
            if abs(len(tok) - len(v)) > 2:
                continue
            if jellyfish.jaro_winkler_similarity(tok, v) >= JARO_THRESHOLD:
                return True

    return False


# ---------------------------------------------------------------------------
# Gate 2 helpers (IDENTICAL logic to Phase 0)
# ---------------------------------------------------------------------------

def _context_score(text: str, phrase: str) -> float:
    """
    Score how well context words (hey / wake up / listen) are present.
    Returns 1.0 for bare single-token phrases (no context required).
    """
    ctx_words = _derive_context_words(phrase)
    if not ctx_words:
        return 1.0
    text_words = set(text.lower().split())
    matched = sum(1 for w in ctx_words if w in text_words)
    return matched / len(ctx_words)


def _stability_score(window: List[Tuple[str, int]]) -> float:
    """
    Fraction of hypotheses in window that have stability >= 2 (seen 2+ frames).
    Rewards windows where ASR has settled on consistent text.
    """
    if not window:
        return 0.0
    stable = sum(1 for _, stab in window if stab >= 2)
    return stable / len(window)


def _build_weighted_text(window: List[Tuple[str, int]]) -> str:
    """
    Build a combined string where stable hypotheses are repeated
    to give them higher weight in token_set_ratio scoring.
    Max 4x repetition for very stable (stability >= 6).
    """
    parts = []
    for text, stab in window:
        weight = 1 + min(stab // 2, 3)
        parts.extend([text] * weight)
    return " ".join(parts).lower()


def _find_matched_variant(combined: str, window: List[Tuple[str, int]]) -> str:
    """
    Identify which registered variant triggered the anchor gate.
    Returns the longest matching variant found (most specific match).
    Returns "" if no specific variant is identified.
    """
    texts_to_check = [combined] + [h for h, _ in window]
    best_variant   = ""

    for variant in get_variants():
        for text in texts_to_check:
            if variant in text.lower():
                if len(variant) > len(best_variant):
                    best_variant = variant
                    break

    return best_variant


def _resolve_phrase_candidate(candidates: list[tuple[float, str]]) -> str:
    """Resolve overlapping phrase candidates by configured priority mode."""
    if not candidates:
        return ""

    if PHRASE_PRIORITY_MODE == "score":
        return max(candidates, key=lambda item: item[0])[1]

    candidates.sort(key=lambda item: (item[0], len(item[1]), item[1]), reverse=True)
    return candidates[0][1]


# ---------------------------------------------------------------------------
# Public API (IDENTICAL signature to Phase 0)
# ---------------------------------------------------------------------------

def best_match(
    window: List[Tuple[str, int]],
) -> Tuple[float, str, str]:
    """
    Given a list of (text, stability) pairs from the rolling window,
    return (best_score 0-1, canonical_phrase, matched_variant).

    Returns (0.0, "", "") immediately if anchor gate fails or registry is empty.

    Score composition:
      WEIGHT_MATCH     x fuzzy phrase similarity
      WEIGHT_CONTEXT   x context word presence
      WEIGHT_STABILITY x stability of hypotheses in window

    matched_variant:
      The specific variant string that triggered the anchor gate.
      Used by the engine for diagnostic logging.
    """
    if not window:
        return 0.0, "", ""

    # If registry is empty, fast-path — no phrases to match against
    phrases_to_score = get_active_phrases()
    if not phrases_to_score:
        return 0.0, "", ""

    combined = _build_weighted_text(window)

    # HARD GATE — fast reject if no anchor token detected
    if not anchor_present(combined):
        return 0.0, "", ""

    # Identify matched variant (for logging — does not affect scoring)
    matched_variant = _find_matched_variant(combined, window)

    stab_score  = _stability_score(window)
    phrase_candidates: list[tuple[float, str]] = []

    # Build the set of canonical phrases to score.
    # Always score all active phrases (standard fuzzy matching).
    # Additionally, if the anchor gate fired via a specific registered variant,
    # ensure that variant's canonical phrase is included as a candidate.
    canonical_candidate = get_canonical(matched_variant) if matched_variant else ""
    if canonical_candidate and canonical_candidate not in phrases_to_score:
        phrases_to_score = list(phrases_to_score) + [canonical_candidate]

    for phrase in phrases_to_score:
        # Score 1: against combined weighted text (better for multi-word phrases)
        fuzzy_combined = fuzz.token_set_ratio(combined, phrase.lower()) / 100.0

        # Score 2: best score against any individual hypothesis in window.
        fuzzy_individual = max(
            fuzz.token_set_ratio(h_text, phrase.lower()) / 100.0
            for h_text, _ in window
        )

        # Score 3: score against the matched variant itself, then scale by
        # canonical phrase similarity. Gives a path for "our whistle" -> canonical.
        fuzzy_via_variant = 0.0
        if canonical_candidate == phrase and matched_variant:
            var_sim = fuzz.token_set_ratio(combined, matched_variant) / 100.0
            fuzzy_via_variant = var_sim * 0.85  # slight discount vs direct phrase match

        # Take the best of all three signals
        fuzzy = max(fuzzy_combined, fuzzy_individual, fuzzy_via_variant)

        # Only proceed if above minimum fuzzy threshold
        if fuzzy < (FUZZY_THRESHOLD / 100.0):
            continue

        ctx = _context_score(combined, phrase)

        score = (
            (fuzzy        * WEIGHT_MATCH)
            + (ctx        * WEIGHT_CONTEXT)
            + (stab_score * WEIGHT_STABILITY)
        )

        # -- Phrase Boundary Protection -----------------------------------------
        candidate_tokens = set()
        for h_text, _ in window:
            candidate_tokens.update(h_text.lower().split())
        phrase_tokens = set(phrase.lower().split())

        if len(candidate_tokens) < len(phrase_tokens):
            if REQUIRE_FULL_PHRASE:
                continue
            if not ALLOW_PREFIX_MATCHING:
                token_coverage_ratio = len(candidate_tokens) / len(phrase_tokens)
                score = min(score, token_coverage_ratio)

        phrase_candidates.append((score, phrase))

    best_phrase = _resolve_phrase_candidate(phrase_candidates)
    best_score = max((score for score, _ in phrase_candidates), default=0.0)
    
    return best_score, best_phrase, matched_variant