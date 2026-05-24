"""
AVAListener — Runtime Clock (Phase 5.2)
=======================================
Authoritative time source for the runtime.
All runtime code MUST use RuntimeClock instead of time.time() directly.
This ensures time can be mocked in tests and is consistent across subsystems.
"""
from __future__ import annotations
import time


class RuntimeClock:
    """
    Singleton-style clock wrapper.
    All runtime subsystems call RuntimeClock.now_ns() / now_s() / monotonic().
    """
    _instance: "RuntimeClock | None" = None

    def __init__(self) -> None:
        self._start_monotonic = time.monotonic()
        self._start_time_ns = time.time_ns()

    @classmethod
    def instance(cls) -> "RuntimeClock":
        if cls._instance is None:
            cls._instance = RuntimeClock()
        return cls._instance

    def now_ns(self) -> int:
        """Current wall-clock time in nanoseconds."""
        return time.time_ns()

    def now_s(self) -> float:
        """Current wall-clock time in seconds (float)."""
        return time.time()

    def monotonic(self) -> float:
        """Monotonic time in seconds — use for duration measurement."""
        return time.monotonic()

    def uptime_s(self) -> float:
        """Seconds since RuntimeClock was first instantiated."""
        return time.monotonic() - self._start_monotonic


# Module-level singleton accessor
_clock = RuntimeClock()

def now_ns() -> int:
    return _clock.now_ns()

def now_s() -> float:
    return _clock.now_s()

def monotonic() -> float:
    return _clock.monotonic()

def uptime_s() -> float:
    return _clock.uptime_s()
