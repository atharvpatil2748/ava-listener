"""
AVAListener — Cooldown Gate
Hard temporal gate. Prevents any trigger within COOLDOWN_SECONDS of the last.
This is mandatory — confidence alone cannot prevent double-triggers.
"""
import time
from config.settings import COOLDOWN_SECONDS


class CooldownGate:
    """
    Simple monotonic-clock-based cooldown.

    Phase 2 note: extend with per-phrase cooldown tracking if needed.
    The current global cooldown is sufficient for Phase 1.
    """

    def __init__(self):
        self._last_trigger: float = 0.0

    def can_trigger(self) -> bool:
        """True if enough time has passed since last trigger."""
        return (time.monotonic() - self._last_trigger) >= COOLDOWN_SECONDS

    def mark_triggered(self) -> None:
        """Call immediately after a wake event is emitted."""
        self._last_trigger = time.monotonic()

    def time_remaining(self) -> float:
        """Seconds remaining in cooldown. 0.0 if cooldown has expired."""
        remaining = COOLDOWN_SECONDS - (time.monotonic() - self._last_trigger)
        return max(0.0, remaining)

    def reset(self) -> None:
        """Force-clear cooldown (for testing)."""
        self._last_trigger = 0.0
