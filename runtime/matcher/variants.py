"""
AVAListener — Wake Phrase Variants (Phase 0.5 refactor)
=========================================================
Single source of truth for the anchor variant set used by the anchor gate.

Phase 0.5 change: variants are now sourced from the PhraseRegistry, NOT from
config.settings.WAKEWORDS. The public API is identical to the Phase 0 version
so all callers (matcher.py, tests) require zero changes.

Public API (unchanged from Phase 0)
-------------------------------------
  get_variants()                  -> list[str]
      All unique anchor strings across every active phrase in the registry.

  get_canonical(variant: str)     -> str | None
      Map a variant back to its canonical phrase.
      Returns None if the variant is not registered.

  get_wakeword_for_phrase(phrase) -> dict | None
      Return a dict compatible with the old WAKEWORDS entry format.
      Bridges old test code that expects {"phrase": ..., "threshold": ..., "variants": [...]}

  rebuild_index()                 -> None
      Called by engine.load_profile() after registry is populated.
      Rebuilds the in-memory variant → canonical mapping from the registry.

Generic Engine Identity
-----------------------
  This module must NEVER contain assistant names, variant strings, or
  hardcoded threshold values. All data comes from the registry.
"""
from __future__ import annotations

import threading
from typing import Optional

from runtime.matcher.registry.phrase_registry import get_registry, PhraseConfig

# ---------------------------------------------------------------------------
# Index state — rebuilt on every profile load
# ---------------------------------------------------------------------------
# All three structures are rebuilt atomically under _index_lock when
# rebuild_index() is called. Reads happen under the same lock so the
# matcher always sees a consistent snapshot.

_index_lock: threading.RLock = threading.RLock()

_all_variants:     list[str]       = []   # deduplicated, lowercase anchor strings
_variant_to_canon: dict[str, str]  = {}   # variant string -> canonical phrase
_phrase_to_entry:  dict[str, dict] = {}   # canonical phrase -> entry-style dict


def _build_index_from_registry() -> tuple[list[str], dict[str, str], dict[str, dict]]:
    """
    Derive variant index structures from the current registry state.
    Equivalent to the Phase 0 _build_index() but reads from PhraseRegistry
    instead of config.settings.WAKEWORDS.
    """
    all_variants:     list[str]       = []
    variant_to_canon: dict[str, str]  = {}
    phrase_to_entry:  dict[str, dict] = {}

    seen: set[str] = set()
    registry = get_registry()

    for cfg in registry.get_all():   # all() so disabled phrases still register variants
        canonical = cfg.phrase        # already lowercased by PhraseConfig.from_dict()

        # Build a backward-compat entry dict (used by get_wakeword_for_phrase)
        phrase_to_entry[canonical] = {
            "phrase":     cfg.phrase,
            "threshold":  cfg.threshold,
            "variants":   list(cfg.variants),
            "phrase_id":  cfg.phrase_id,
            "cooldown_ms": cfg.cooldown_ms,
            "enabled":    cfg.enabled,
            "weight":     cfg.weight,
        }

        for v in cfg.variants:
            norm = v.strip().lower()
            if not norm:
                continue
            if norm not in seen:
                seen.add(norm)
                all_variants.append(norm)
            # Last writer wins for duplicate variants across phrases
            variant_to_canon[norm] = canonical

    return all_variants, variant_to_canon, phrase_to_entry


def rebuild_index() -> None:
    """
    Rebuild the in-memory variant index from the current registry state.
    Called by engine.load_profile() after populating the registry.
    Thread-safe: all readers block until rebuild is complete.
    """
    global _all_variants, _variant_to_canon, _phrase_to_entry
    new_variants, new_v2c, new_p2e = _build_index_from_registry()
    with _index_lock:
        _all_variants     = new_variants
        _variant_to_canon = new_v2c
        _phrase_to_entry  = new_p2e


# ---------------------------------------------------------------------------
# Public API (identical signatures to Phase 0)
# ---------------------------------------------------------------------------

def get_variants() -> list[str]:
    """
    Return the deduplicated, lowercased list of all anchor variants
    from the currently loaded profile.

    Returns an empty list if no profile has been loaded yet.
    """
    with _index_lock:
        return list(_all_variants)


def get_canonical(variant: str) -> Optional[str]:
    """
    Map a matched variant string back to its canonical phrase.

    Example (after loading a profile):
        get_canonical("my assist")       -> "my assistant"
        get_canonical("hey assist")      -> "hey assistant"
        get_canonical("unknown text")    -> None
    """
    with _index_lock:
        return _variant_to_canon.get(variant.strip().lower())


def get_wakeword_for_phrase(phrase: str) -> Optional[dict]:
    """
    Return an entry-style dict for a canonical phrase, or None if not found.

    Returned dict shape (backward-compatible with Phase 0 WAKEWORDS entries):
        {
            "phrase":      str,
            "threshold":   float,
            "variants":    list[str],
            "phrase_id":   str,
            "cooldown_ms": int,
            "enabled":     bool,
            "weight":      float,
        }
    """
    with _index_lock:
        return _phrase_to_entry.get(phrase.strip().lower())


def get_active_phrases() -> list[str]:
    """
    Return canonical phrase strings for all currently enabled phrases.
    Replaces the old WAKE_PHRASES derived constant.
    """
    return [cfg.phrase for cfg in get_registry().get_active()]