"""
AVAListener — Phrase Registry (Phase 0.5)
==========================================
The single authoritative store of active wake phrases at runtime.

The engine has ZERO knowledge of assistant names, profile files, or specific
wake phrases. It only queries this registry. Profile loading (from JSON files)
is the ONLY path by which phrases enter the engine.

Design principles:
  - Registry is initialized EMPTY — no default phrases baked in.
  - Thread-safe: reads are the hot path; writes (load_profile) are rare.
  - PhraseConfig is a frozen dataclass — immutable after creation.
  - All mutation goes through registry methods, never by mutating PhraseConfig directly.

Public API:
  registry.add_phrase(phrase: PhraseConfig) -> None
  registry.remove_phrase(phrase_id: str)    -> None
  registry.enable_phrase(phrase_id: str)    -> None
  registry.disable_phrase(phrase_id: str)   -> None
  registry.update_phrase(phrase_id: str, updates: dict) -> None
  registry.get_active()                     -> list[PhraseConfig]
  registry.get_all()                        -> list[PhraseConfig]
  registry.get_by_id(phrase_id: str)        -> PhraseConfig | None
  registry.clear()                          -> None
  registry.is_empty()                       -> bool
  registry.count()                          -> int

Generic Engine Identity:
  This module must NEVER contain assistant names, variant strings, or
  hardcoded threshold values. Those live exclusively in profile JSON files.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace


# ---------------------------------------------------------------------------
# PhraseConfig — immutable phrase descriptor
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PhraseConfig:
    """
    Immutable descriptor for a single wake phrase.

    Fields
    ------
    phrase_id   : Unique identifier within the profile (e.g. "assistant_core").
                  Used for targeted enable/disable/update without touching others.
    phrase      : Canonical phrase string (e.g. "hey assistant").
                  This is what the engine logs and emits in wake events.
    variants    : Alternate ASR transcriptions (e.g. ["hey assistant", "hey assist"]).
                  Checked by the anchor gate before fuzzy scoring.
    threshold   : EMA-smoothed confidence required to fire (0.0 – 1.0).
    cooldown_ms : Minimum milliseconds between consecutive wakes for this phrase.
    enabled     : Whether the phrase participates in matching (soft toggle).
    weight      : Relative scoring weight (1.0 = normal; <1.0 = deprioritised).
    """
    phrase_id:   str
    phrase:      str
    variants:    tuple[str, ...]   # tuple for hashability / immutability
    threshold:   float
    cooldown_ms: int
    enabled:     bool  = True
    weight:      float = 1.0

    def __post_init__(self) -> None:
        if not self.phrase_id:
            raise ValueError("PhraseConfig.phrase_id must not be empty")
        if not self.phrase:
            raise ValueError("PhraseConfig.phrase must not be empty")
        if not (0.0 < self.threshold <= 1.0):
            raise ValueError(
                f"PhraseConfig.threshold must be in (0, 1]; got {self.threshold!r}"
            )
        if self.cooldown_ms < 0:
            raise ValueError(
                f"PhraseConfig.cooldown_ms must be >= 0; got {self.cooldown_ms!r}"
            )

    @classmethod
    def from_dict(cls, data: dict) -> "PhraseConfig":
        """
        Construct from a profile JSON phrase entry dict.

        Expected keys (from profiles/*.json wakePhrases entries):
            phraseId, phrase, variants, threshold, cooldownMs, enabled, weight
        """
        raw_variants = data.get("variants", [])
        # Normalise: deduplicate, lowercase, strip whitespace
        seen: set[str] = set()
        clean_variants: list[str] = []
        for v in raw_variants:
            norm = v.strip().lower()
            if norm and norm not in seen:
                seen.add(norm)
                clean_variants.append(norm)

        return cls(
            phrase_id=data["phraseId"],
            phrase=data["phrase"].strip().lower(),
            variants=tuple(clean_variants),
            threshold=float(data["threshold"]),
            cooldown_ms=int(data.get("cooldownMs", 2000)),
            enabled=bool(data.get("enabled", True)),
            weight=float(data.get("weight", 1.0)),
        )

    def with_updates(self, updates: dict) -> "PhraseConfig":
        """
        Return a new PhraseConfig with the given fields overridden.
        Only hot-reloadable fields are accepted here; immutable fields
        raise ValueError when the runtime is active (enforced by mutability.py
        in Phase 5.5; at Phase 0.5 we accept all updates for flexibility).
        """
        mapped = {}
        field_map = {
            "threshold":   "threshold",
            "cooldown_ms": "cooldown_ms",
            "cooldownMs":  "cooldown_ms",
            "enabled":     "enabled",
            "weight":      "weight",
            "variants":    "variants",
        }
        for k, v in updates.items():
            if k in field_map:
                dest = field_map[k]
                if dest == "variants":
                    seen: set[str] = set()
                    clean: list[str] = []
                    for item in v:
                        n = item.strip().lower()
                        if n and n not in seen:
                            seen.add(n)
                            clean.append(n)
                    mapped[dest] = tuple(clean)
                else:
                    mapped[dest] = v
        return replace(self, **mapped)


# ---------------------------------------------------------------------------
# PhraseRegistry — thread-safe, mutable store of PhraseConfig instances
# ---------------------------------------------------------------------------

class PhraseRegistry:
    """
    Thread-safe runtime registry of active wake phrases.

    The registry is:
      - Initialized EMPTY (no default phrases).
      - Populated exclusively via load_profile() → add_phrase() calls.
      - Queried by the matcher on every ASR hypothesis (get_active() hot path).
      - Mutated rarely (load_profile, enable/disable, update).

    Locking strategy:
      - RLock (re-entrant) because some public methods call other public methods.
      - Writes acquire the lock; reads acquire the lock for a snapshot copy.
      - get_active() returns a list copy so callers hold no reference to internals.
    """

    def __init__(self) -> None:
        self._lock: threading.RLock = threading.RLock()
        # Ordered dict preserves insertion order (profile load order)
        self._phrases: dict[str, PhraseConfig] = {}

    # ------------------------------------------------------------------
    # Mutating operations (acquire write lock)
    # ------------------------------------------------------------------

    def add_phrase(self, phrase: PhraseConfig) -> None:
        """
        Add or replace a phrase in the registry.
        If a phrase with the same phrase_id already exists, it is replaced.
        """
        if not isinstance(phrase, PhraseConfig):
            raise TypeError(f"Expected PhraseConfig, got {type(phrase).__name__}")
        with self._lock:
            self._phrases[phrase.phrase_id] = phrase

    def remove_phrase(self, phrase_id: str) -> None:
        """
        Remove a phrase by its phrase_id. No-op if not present.
        """
        with self._lock:
            self._phrases.pop(phrase_id, None)

    def enable_phrase(self, phrase_id: str) -> None:
        """
        Enable a phrase (sets enabled=True). No-op if phrase_id not found.
        """
        with self._lock:
            if phrase_id in self._phrases:
                self._phrases[phrase_id] = replace(
                    self._phrases[phrase_id], enabled=True
                )

    def disable_phrase(self, phrase_id: str) -> None:
        """
        Disable a phrase (sets enabled=False). No-op if phrase_id not found.
        The phrase stays registered but is excluded from get_active().
        """
        with self._lock:
            if phrase_id in self._phrases:
                self._phrases[phrase_id] = replace(
                    self._phrases[phrase_id], enabled=False
                )

    def update_phrase(self, phrase_id: str, updates: dict) -> None:
        """
        Apply field updates to an existing phrase.
        Uses PhraseConfig.with_updates() so validation is preserved.
        No-op if phrase_id not found.

        Accepted keys: threshold, cooldown_ms, cooldownMs, enabled, weight, variants
        """
        with self._lock:
            if phrase_id in self._phrases:
                self._phrases[phrase_id] = self._phrases[phrase_id].with_updates(updates)

    def clear(self) -> None:
        """
        Remove all phrases from the registry.
        The runtime can continue operating with an empty registry — it simply
        produces no wake events until new phrases are loaded.
        """
        with self._lock:
            self._phrases.clear()

    # ------------------------------------------------------------------
    # Read operations (return snapshots — no lingering lock held)
    # ------------------------------------------------------------------

    def get_active(self) -> list[PhraseConfig]:
        """
        Return a snapshot list of all enabled phrases.
        Hot path: called on every ASR hypothesis. Returns a list copy so the
        caller holds no reference to internal state.
        """
        with self._lock:
            return [p for p in self._phrases.values() if p.enabled]

    def get_all(self) -> list[PhraseConfig]:
        """
        Return a snapshot list of all phrases (enabled AND disabled).
        """
        with self._lock:
            return list(self._phrases.values())

    def get_by_id(self, phrase_id: str) -> PhraseConfig | None:
        """
        Return a specific phrase by id, or None if not found.
        """
        with self._lock:
            return self._phrases.get(phrase_id)

    def is_empty(self) -> bool:
        """True if no phrases are registered (enabled or disabled)."""
        with self._lock:
            return len(self._phrases) == 0

    def count(self) -> int:
        """Total number of registered phrases (enabled + disabled)."""
        with self._lock:
            return len(self._phrases)

    def active_count(self) -> int:
        """Number of currently enabled phrases."""
        with self._lock:
            return sum(1 for p in self._phrases.values() if p.enabled)

    def __repr__(self) -> str:
        with self._lock:
            ids = list(self._phrases.keys())
        return f"PhraseRegistry(phrases={ids!r})"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
# The engine and matcher both reference this singleton.
# Profile loading calls registry.clear() then registry.add_phrase() for each
# phrase in the profile. The matcher calls registry.get_active() on each hypothesis.

_registry: PhraseRegistry = PhraseRegistry()


def get_registry() -> PhraseRegistry:
    """Return the module-level singleton PhraseRegistry."""
    return _registry
