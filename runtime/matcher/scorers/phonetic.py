"""
AVAListener — Confidence Scorer
Lightweight Phase 1 scorer. Designed to be upgraded in Phase 2
with EMA trend tracking (confidence/smoothing.py) without API changes.
"""
from config.settings import CONFIDENCE_THRESHOLD


def compute_confidence(
    match_score: float,
    window_size: int,
    hit_count: int,
) -> float:
    """
    Compute final confidence value from available signals.

    Args:
        match_score:  0–1 from best_match() in matcher.py
        window_size:  total number of hypotheses in rolling window
        hit_count:    how many hypotheses in the window had match_score > 0.5

    The stability bonus rewards sustained matching across multiple ASR chunks,
    not just a single lucky partial.

    Phase 2 note: add EMA trend (smoothing.py) as a fourth signal here
    without changing the caller signature in engine.py.
    """
    # Repeat-rate: fraction of window entries that were positive hits.
    # Use effective_size >= 3 so small windows (early in an utterance) are not
    # penalized — 3 hits from 3 entries is as valid as 10 hits from 10.
    effective_size = max(window_size, 3)
    repeat_rate = (hit_count / effective_size)
    repeat_bonus = min(repeat_rate, 1.0) * 0.20  # up to +0.20

    # Raw score
    score = (match_score * 0.80) + repeat_bonus
    return min(score, 1.0)


def is_confident(score: float) -> bool:
    """True if score meets the configured trigger threshold."""
    return score >= CONFIDENCE_THRESHOLD
