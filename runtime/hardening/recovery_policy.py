"""
AVAListener — Recovery Policy (Phase 4.1)
==========================================
Defines the retry/backoff contract for subsystem recovery.
Never touches matcher scoring, phrase registry, or ASR decoding.
"""

from __future__ import annotations
import time


class RecoveryPolicy:
    """
    Exponential-backoff retry policy for a single subsystem.

    delay = min(backoff_initial_ms * (2 ** retries), backoff_max_ms)

    Parameters
    ----------
    max_retries : int
        After this many consecutive failures, the subsystem is escalated.
    backoff_initial_ms : float
        Starting delay for the first retry, in milliseconds.
    backoff_max_ms : float
        Hard ceiling on any single retry delay, in milliseconds.
    escalation_threshold : int
        Number of retries at max_backoff before escalation is signalled.
    """

    def __init__(
        self,
        max_retries: int = 5,
        backoff_initial_ms: float = 100.0,
        backoff_max_ms: float = 8000.0,
        escalation_threshold: int = 3,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_initial_ms = backoff_initial_ms
        self.backoff_max_ms = backoff_max_ms
        self.escalation_threshold = escalation_threshold

        self._retries: int = 0
        self._at_max_count: int = 0       # how many times we've hit the max delay
        self._last_failure_ts: float = 0.0
        self._total_failures: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_failure(self) -> None:
        """Record one failure. Call before next_backoff()."""
        self._retries += 1
        self._total_failures += 1
        self._last_failure_ts = time.monotonic()

    def next_backoff(self) -> float:
        """
        Return the delay (ms) to wait before the next recovery attempt.
        Tracks how many times we've reached the max ceiling.
        """
        delay = min(
            self.backoff_initial_ms * (2 ** (self._retries - 1)),
            self.backoff_max_ms,
        )
        if delay >= self.backoff_max_ms:
            self._at_max_count += 1
        return delay

    def should_escalate(self) -> bool:
        """True when we should give up on recovery and escalate."""
        if self._retries >= self.max_retries:
            return True
        if self._at_max_count >= self.escalation_threshold:
            return True
        return False

    def reset(self) -> None:
        """Call after a successful recovery to clear the failure counter."""
        self._retries = 0
        self._at_max_count = 0
        self._last_failure_ts = 0.0

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def retries(self) -> int:
        return self._retries

    @property
    def total_failures(self) -> int:
        return self._total_failures

    @property
    def seconds_since_last_failure(self) -> float:
        if self._last_failure_ts == 0.0:
            return float("inf")
        return time.monotonic() - self._last_failure_ts

    def __repr__(self) -> str:
        return (
            f"RecoveryPolicy(retries={self._retries}/{self.max_retries} "
            f"at_max={self._at_max_count}/{self.escalation_threshold} "
            f"total_failures={self._total_failures})"
        )
